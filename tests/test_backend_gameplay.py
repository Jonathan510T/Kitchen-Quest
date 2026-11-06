"""Unit and integration tests for backend gameplay, challenges, attempts, and progress."""

import unittest
import uuid

try:
    from backend.app.database import SessionLocal, Base, engine
    from backend.app import main, models, schemas
except ImportError:
    SessionLocal = None


@unittest.skipIf(SessionLocal is None, "Install sqlalchemy and pydantic to run backend tests")
class BackendGameplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        self.username = f"chef_{uuid.uuid4().hex[:8]}"
        self.user = models.User(
            username=self.username,
            password_hash="test_hash_value",
            role=models.Role.user,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()

    def test_list_and_get_challenges(self):
        challenges = main.list_challenges(db=self.db, current_user=self.user)
        self.assertGreaterEqual(len(challenges), 4)

        first = challenges[0]
        c = main.get_challenge(challenge_id=first.id, db=self.db, current_user=self.user)
        self.assertEqual(c.id, first.id)
        self.assertEqual(c.title, first.title)
        self.assertTrue(len(c.ingredients) > 0)
        self.assertTrue(len(c.steps) > 0)
        self.assertEqual(c.best_stars, 0)

    def test_submit_attempt_and_update_progress(self):
        # Initial progress
        prog = main.get_progress(db=self.db, current_user=self.user)
        self.assertEqual(prog.total_xp, 0)
        self.assertEqual(prog.current_level, 1)
        self.assertEqual(prog.total_stars, 0)

        # Submit attempt
        payload = schemas.AttemptSubmitIn(
            actions=[
                schemas.PlayerActionIn(
                    timestamp=1.0,
                    station="prep",
                    action_type="chop",
                    ingredient_names=["Tomato"],
                    parameters={},
                ),
                schemas.PlayerActionIn(
                    timestamp=3.0,
                    station="prep",
                    action_type="mince",
                    ingredient_names=["Garlic"],
                    parameters={},
                ),
                schemas.PlayerActionIn(
                    timestamp=7.0,
                    station="stove",
                    action_type="saute",
                    ingredient_names=["Olive Oil", "Garlic"],
                    parameters={"heat": "medium", "duration": 4.0},
                ),
                schemas.PlayerActionIn(
                    timestamp=14.0,
                    station="stove",
                    action_type="simmer",
                    ingredient_names=["Tomato"],
                    parameters={"heat": "medium", "duration": 6.0},
                ),
                schemas.PlayerActionIn(
                    timestamp=20.0,
                    station="plating",
                    action_type="serve",
                    ingredient_names=["Salt", "Fresh Basil"],
                    parameters={},
                ),
            ],
            time_taken_seconds=22.0,
        )

        result = main.submit_challenge_attempt(
            challenge_id=1, payload=payload, db=self.db, current_user=self.user
        )
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.accuracy_score, 80.0)
        self.assertIn(result.stars, [2, 3])
        self.assertGreater(result.xp_earned, 70)
        self.assertGreater(result.new_total_xp, 0)
        self.assertTrue(len(result.feedback) > 0)

        # Check updated progress
        updated_prog = main.get_progress(db=self.db, current_user=self.user)
        self.assertEqual(updated_prog.total_xp, result.new_total_xp)
        self.assertEqual(updated_prog.total_stars, result.stars)
        self.assertEqual(updated_prog.completed_challenges_count, 1)


if __name__ == "__main__":
    unittest.main()

