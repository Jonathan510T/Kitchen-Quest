"""Local in-memory game service providing full gameplay and progression when offline."""

from typing import Any

from gameplay.engine import CookingEvaluator, ProgressionManager
from gameplay.models import (
    ActionType,
    CookingStep,
    IngredientItem,
    PlayerActionRecord,
    RecipeChallenge,
    Station,
)
from gameplay.recipes import get_challenge_by_id, get_default_challenges


class LocalGameService:
    def __init__(self, user_id: int = 1):
        self.user_id = user_id
        self.total_xp: int = 0
        self.current_level: int = 1
        self.rank_title: str = "Prep Cook"
        self.completed_attempts: list[dict[str, Any]] = []

    def get_challenges(self) -> list[dict[str, Any]]:
        results = []
        for c in get_default_challenges():
            d = c.to_dict()
            # Find best stars from local attempts
            attempts = [a for a in self.completed_attempts if a["challenge_id"] == c.id]
            best_stars = max((a["stars"] for a in attempts), default=0)
            best_score = max((a["accuracy_score"] for a in attempts), default=0.0)
            d["best_stars"] = best_stars
            d["best_score"] = best_score
            results.append(d)
        return results

    def get_challenge(self, challenge_id: int) -> dict[str, Any] | None:
        c = get_challenge_by_id(challenge_id)
        if not c:
            return None
        d = c.to_dict()
        attempts = [a for a in self.completed_attempts if a["challenge_id"] == c.id]
        d["best_stars"] = max((a["stars"] for a in attempts), default=0)
        d["best_score"] = max((a["accuracy_score"] for a in attempts), default=0.0)
        return d

    def submit_attempt(
        self,
        challenge_id: int,
        actions_data: list[dict[str, Any]],
        time_taken_seconds: float,
    ) -> dict[str, Any]:
        challenge = get_challenge_by_id(challenge_id)
        if not challenge:
            raise ValueError("Challenge not found")

        domain_actions: list[PlayerActionRecord] = []
        for a in actions_data:
            try:
                domain_actions.append(
                    PlayerActionRecord(
                        timestamp=float(a.get("timestamp", 0.0)),
                        station=Station(a["station"].lower()),
                        action_type=ActionType(a["action_type"].lower()),
                        ingredient_names=a.get("ingredient_names", []),
                        parameters=a.get("parameters", {}),
                    )
                )
            except Exception:
                continue

        evaluator = CookingEvaluator()
        result = evaluator.evaluate(
            challenge,
            domain_actions,
            time_taken_seconds,
            existing_total_xp=self.total_xp,
        )

        self.total_xp = result.new_total_xp
        self.current_level = result.new_level
        self.rank_title = result.rank_title

        attempt_dict = result.to_dict()
        self.completed_attempts.append(attempt_dict)
        return attempt_dict

    def get_progress(self) -> dict[str, Any]:
        lvl, title, base_xp, next_xp = ProgressionManager.get_level_info(self.total_xp)
        passed = [a for a in self.completed_attempts if a["passed"]]
        unique_challenges = len(set(a["challenge_id"] for a in passed))
        total_stars = sum(a["stars"] for a in passed)

        return {
            "user_id": self.user_id,
            "total_xp": self.total_xp,
            "current_level": lvl,
            "rank_title": title,
            "current_level_base_xp": base_xp,
            "next_level_xp": next_xp,
            "completed_challenges_count": unique_challenges,
            "total_stars": total_stars,
        }

