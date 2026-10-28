"""Unit tests for ApiClient gameplay methods and LocalGameService offline fallback."""

import unittest
from frontend.api_client import ApiClient, Profile, Session
from frontend.local_service import LocalGameService
from gameplay.models import ActionType, HeatLevel, Station
from gameplay.recipes import get_challenge_by_id


class GameplayClientTests(unittest.TestCase):
    def setUp(self):
        self.local_service = LocalGameService(user_id=10)
        self.api_client = ApiClient()
        self.session = Session(Profile(10, "chef_test", "user"), "token123")

    def test_local_service_challenges_and_details(self):
        challenges = self.local_service.get_challenges()
        self.assertGreaterEqual(len(challenges), 4)

        first = challenges[0]
        self.assertIn("title", first)
        self.assertIn("steps", first)
        self.assertIn("ingredients", first)

        detail = self.local_service.get_challenge(first["id"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["id"], first["id"])

    def test_local_service_attempt_submission_and_progress(self):
        init_prog = self.local_service.get_progress()
        self.assertEqual(init_prog["total_xp"], 0)
        self.assertEqual(init_prog["current_level"], 1)

        actions = [
            {"timestamp": 1.0, "station": "prep", "action_type": "chop", "ingredient_names": ["Tomato"]},
            {"timestamp": 3.0, "station": "prep", "action_type": "mince", "ingredient_names": ["Garlic"]},
            {"timestamp": 7.0, "station": "stove", "action_type": "saute", "ingredient_names": ["Olive Oil", "Garlic"], "parameters": {"heat": "medium", "duration": 4.0}},
            {"timestamp": 12.0, "station": "stove", "action_type": "simmer", "ingredient_names": ["Tomato"], "parameters": {"heat": "medium", "duration": 6.0}},
            {"timestamp": 18.0, "station": "plating", "action_type": "serve", "ingredient_names": ["Salt", "Fresh Basil"]},
        ]

        result = self.local_service.submit_attempt(1, actions, time_taken_seconds=20.0)
        self.assertTrue(result["passed"])
        self.assertGreaterEqual(result["accuracy_score"], 80.0)
        self.assertIn(result["stars"], [2, 3])
        self.assertGreater(result["xp_earned"], 70)

        updated_prog = self.local_service.get_progress()
        self.assertEqual(updated_prog["total_xp"], result["new_total_xp"])
        self.assertEqual(updated_prog["completed_challenges_count"], 1)
        self.assertGreaterEqual(updated_prog["total_stars"], result["stars"])

    def test_api_client_offline_fallback(self):
        # Without running backend server, ApiClient should automatically fallback to local service
        challenges = self.api_client.get_challenges(token="test_offline_token")
        self.assertGreaterEqual(len(challenges), 4)

        c = self.api_client.get_challenge(1, token="test_offline_token")
        self.assertIsNotNone(c)
        self.assertEqual(c["id"], 1)

        prog = self.api_client.get_progress(token="test_offline_token")
        self.assertIn("total_xp", prog)
        self.assertIn("current_level", prog)


if __name__ == "__main__":
    unittest.main()

