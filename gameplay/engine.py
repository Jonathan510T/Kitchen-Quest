"""Gameplay simulation engine, action evaluator, and progression logic for Kitchen Quest."""

import copy
import math
import time
from typing import Any

from .models import (
    ActionType,
    AttemptResult,
    CookingStep,
    HeatLevel,
    IngredientItem,
    IngredientState,
    PlayerActionRecord,
    RecipeChallenge,
    Station,
    UserProgressData,
)

LEVEL_THRESHOLDS = [
    (1, 0, "Prep Cook"),
    (2, 100, "Commis Chef"),
    (3, 250, "Chef de Partie"),
    (4, 500, "Sous Chef"),
    (5, 850, "Executive Chef"),
    (6, 1300, "Master Chef"),
]


class ProgressionManager:
    @staticmethod
    def get_level_info(total_xp: int) -> tuple[int, str, int, int]:
        """Returns (current_level, rank_title, xp_for_current_level, xp_for_next_level)."""
        current_lvl = 1
        current_title = "Prep Cook"
        current_base = 0
        next_threshold = 100

        for idx, (lvl, xp_thresh, title) in enumerate(LEVEL_THRESHOLDS):
            if total_xp >= xp_thresh:
                current_lvl = lvl
                current_title = title
                current_base = xp_thresh
                if idx + 1 < len(LEVEL_THRESHOLDS):
                    next_threshold = LEVEL_THRESHOLDS[idx + 1][1]
                else:
                    next_threshold = current_base + 1000  # Cap progression extension
            else:
                break

        return current_lvl, current_title, current_base, next_threshold

    @staticmethod
    def award_xp(current_total_xp: int, xp_to_add: int) -> tuple[int, int, str, bool]:
        """Returns (new_total_xp, new_level, new_title, did_level_up)."""
        old_lvl, _, _, _ = ProgressionManager.get_level_info(current_total_xp)
        new_total_xp = current_total_xp + max(0, xp_to_add)
        new_lvl, new_title, _, _ = ProgressionManager.get_level_info(new_total_xp)
        return new_total_xp, new_lvl, new_title, (new_lvl > old_lvl)


class KitchenSimulator:
    """Simulates an active cooking challenge session."""

    def __init__(self, challenge: RecipeChallenge):
        self.challenge = copy.deepcopy(challenge)
        self.current_station: Station = Station.PANTRY
        self.pantry_items: list[IngredientItem] = copy.deepcopy(challenge.ingredients)
        self.prep_board: list[IngredientItem] = []
        self.mixing_bowl: list[IngredientItem] = []
        self.stove_pan: list[IngredientItem] = []
        self.plate: list[IngredientItem] = []

        self.stove_heat: HeatLevel = HeatLevel.OFF
        self.stove_cook_seconds: float = 0.0
        self.start_time: float = time.time()
        self.action_history: list[PlayerActionRecord] = []
        self.current_step_index: int = 0
        self.is_finished: bool = False
        self.seasonings_added: set[str] = set()

    def get_items_at_station(self, station: Station) -> list[IngredientItem]:
        if station == Station.PANTRY:
            return self.pantry_items
        elif station == Station.PREP:
            return self.prep_board
        elif station == Station.MIXING:
            return self.mixing_bowl
        elif station == Station.STOVE:
            return self.stove_pan
        elif station == Station.PLATING:
            return self.plate
        return []

    def move_ingredient(self, item_id: str, target_station: Station) -> bool:
        """Move an ingredient from its current station to target station."""
        for station_list in (self.pantry_items, self.prep_board, self.mixing_bowl, self.stove_pan, self.plate):
            for i, item in enumerate(station_list):
                if item.id == item_id:
                    station_list.pop(i)
                    item.current_station = target_station
                    self.get_items_at_station(target_station).append(item)
                    self._record_action(
                        target_station,
                        ActionType.COMBINE if target_station in (Station.MIXING, Station.STOVE) else ActionType.ADD_TO_PLATE,
                        [item.name],
                        {"target_station": target_station.value},
                    )
                    return True
        return False

    def perform_prep(self, action: ActionType, item_id: str | None = None) -> bool:
        """Perform chopping/slicing/dicing on prep cutting board."""
        target_items = [i for i in self.prep_board if item_id is None or i.id == item_id]
        if not target_items:
            return False

        transformed_names = []
        for item in target_items:
            if action == ActionType.SLICE:
                item.state = IngredientState.SLICED
            elif action == ActionType.CHOP:
                item.state = IngredientState.CHOPPED
            elif action == ActionType.DICE:
                item.state = IngredientState.DICED
            elif action == ActionType.MINCE:
                item.state = IngredientState.MINCED
            transformed_names.append(item.name)

        self._record_action(Station.PREP, action, transformed_names)
        self._check_step_advancement()
        return True

    def perform_mix(self, action: ActionType) -> bool:
        """Mix/whisk ingredients in the mixing bowl."""
        if not self.mixing_bowl:
            return False

        names = [i.name for i in self.mixing_bowl]
        for item in self.mixing_bowl:
            item.state = IngredientState.MIXED

        self._record_action(Station.MIXING, action, names)
        self._check_step_advancement()
        return True

    def set_stove_heat(self, heat: HeatLevel) -> None:
        """Set heat level of the active burner."""
        self.stove_heat = heat
        self._record_action(Station.STOVE, ActionType.HEAT_SET, [], {"heat": heat.value})

    def cook_tick(self, delta_seconds: float) -> None:
        """Advance time for ingredients in the stove pan."""
        if self.stove_heat == HeatLevel.OFF or not self.stove_pan:
            return

        heat_factor = {
            HeatLevel.LOW: 0.8,
            HeatLevel.MEDIUM: 1.0,
            HeatLevel.HIGH: 1.6,
        }.get(self.stove_heat, 1.0)

        effective_cook_time = delta_seconds * heat_factor
        self.stove_cook_seconds += effective_cook_time

        # Update ingredient state based on effective cook duration
        for item in self.stove_pan:
            if self.stove_cook_seconds < 2.0:
                item.state = IngredientState.COOKING
            elif self.stove_cook_seconds <= 8.5:
                item.state = IngredientState.PERFECT
            elif self.stove_cook_seconds <= 12.0:
                item.state = IngredientState.OVERCOOKED
            else:
                item.state = IngredientState.BURNT

    def perform_stove_action(self, action: ActionType, duration_seconds: float = 4.0) -> bool:
        """Execute a cooking action on the stove for a specified duration."""
        if not self.stove_pan or self.stove_heat == HeatLevel.OFF:
            return False

        self.cook_tick(duration_seconds)
        names = [i.name for i in self.stove_pan]
        self._record_action(
            Station.STOVE,
            action,
            names,
            {"duration": duration_seconds, "heat": self.stove_heat.value},
        )
        self._check_step_advancement()
        return True

    def add_seasoning(self, seasoning_name: str) -> None:
        """Add seasoning (salt, pepper, herbs) to active station or plate."""
        self.seasonings_added.add(seasoning_name.lower())
        action_map = {
            "salt": ActionType.SEASON_SALT,
            "pepper": ActionType.SEASON_PEPPER,
            "herbs": ActionType.SEASON_HERBS,
            "fresh basil": ActionType.SEASON_HERBS,
        }
        action = action_map.get(seasoning_name.lower(), ActionType.GARNISH)
        self._record_action(self.current_station, action, [seasoning_name])
        self._check_step_advancement()

    def finish_and_serve(self) -> AttemptResult:
        """Finish cooking session and evaluate."""
        self.is_finished = True
        elapsed = time.time() - self.start_time
        self._record_action(Station.PLATING, ActionType.SERVE, ["Dish"], {"time_taken": elapsed})

        evaluator = CookingEvaluator()
        result = evaluator.evaluate(self.challenge, self.action_history, elapsed, self)
        return result

    def _record_action(
        self,
        station: Station,
        action: ActionType,
        ingredients: list[str],
        params: dict[str, Any] | None = None,
    ) -> None:
        rec = PlayerActionRecord(
            timestamp=time.time() - self.start_time,
            station=station,
            action_type=action,
            ingredient_names=ingredients,
            parameters=params or {},
        )
        self.action_history.append(rec)

    def _check_step_advancement(self) -> None:
        if self.current_step_index >= len(self.challenge.steps):
            return
        step = self.challenge.steps[self.current_step_index]
        # Check if the recent actions satisfied this step
        if not self.action_history:
            return
        last = self.action_history[-1]
        if last.action_type == step.required_action and last.station == step.station:
            # Check ingredients
            if not step.target_ingredients or any(
                req.lower() in [i.lower() for i in last.ingredient_names]
                for req in step.target_ingredients
            ):
                self.current_step_index += 1


class CookingEvaluator:
    """Scores a cooking attempt against the challenge requirements."""

    def evaluate(
        self,
        challenge: RecipeChallenge,
        actions: list[PlayerActionRecord],
        elapsed_time: float,
        sim: KitchenSimulator | None = None,
        existing_total_xp: int = 0,
    ) -> AttemptResult:
        feedback: list[str] = []
        prep_score = 100.0
        cook_score = 100.0
        season_score = 100.0
        sequence_score = 100.0

        # 1. Analyze Actions for Step Completion & Sequence
        steps = challenge.steps
        matched_steps = 0

        action_idx = 0
        for step in steps:
            found = False
            while action_idx < len(actions):
                act = actions[action_idx]
                action_idx += 1
                if act.action_type == step.required_action:
                    # Check station match
                    if act.station != step.station:
                        sequence_score -= 10.0
                    # Check heat setting if applicable
                    if step.target_heat and act.parameters.get("heat") != step.target_heat.value:
                        cook_score -= 15.0
                        feedback.append(
                            f"Step '{step.title}': Expected heat {step.target_heat.value}, but used {act.parameters.get('heat')}."
                        )
                    found = True
                    matched_steps += 1
                    break
            if not found:
                sequence_score -= (100.0 / max(1, len(steps)))
                feedback.append(f"Missed step: {step.title} ({step.instruction})")

        # 2. Check Ingredient & Prep Quality
        if sim is not None:
            # Check if any food burned on stove
            burnt_items = [i.name for i in sim.stove_pan + sim.plate if i.state == IngredientState.BURNT]
            overcooked_items = [i.name for i in sim.stove_pan + sim.plate if i.state == IngredientState.OVERCOOKED]
            if burnt_items:
                cook_score -= 40.0
                feedback.append(f"Caution: Burned {', '.join(burnt_items)} on the stove! Watch your heat and cooking time.")
            elif overcooked_items:
                cook_score -= 15.0
                feedback.append(f"Slightly overcooked {', '.join(overcooked_items)}.")
            else:
                cook_score = min(100.0, cook_score + 5.0)

            # Check seasoning
            recipe_seasonings = [
                i.name.lower()
                for i in challenge.ingredients
                if i.name.lower() in ("salt", "pepper", "fresh basil", "chives", "herbs")
            ]
            for s in recipe_seasonings:
                if s not in sim.seasonings_added:
                    season_score -= 20.0
                    feedback.append(f"Missing seasoning: Remember to add {s.title()} before serving.")
                else:
                    feedback.append(f"Great seasoning: {s.title()} added nicely.")

        # 3. Time Evaluation
        time_bonus = 0.0
        if elapsed_time <= challenge.time_limit_seconds:
            time_bonus = 5.0
            feedback.append(f"Speed bonus! Completed within {round(elapsed_time, 1)}s (limit {challenge.time_limit_seconds}s).")
        else:
            time_penalty = min(20.0, (elapsed_time - challenge.time_limit_seconds) * 0.5)
            sequence_score -= time_penalty
            feedback.append(f"Took {round(elapsed_time, 1)}s. Try to move faster next time (time limit: {challenge.time_limit_seconds}s).")

        # Clamp category scores
        prep_score = max(0.0, min(100.0, prep_score))
        cook_score = max(0.0, min(100.0, cook_score))
        season_score = max(0.0, min(100.0, season_score))
        sequence_score = max(0.0, min(100.0, sequence_score))

        # Overall weighted accuracy
        final_accuracy = (
            sequence_score * 0.35 +
            cook_score * 0.35 +
            prep_score * 0.15 +
            season_score * 0.15 +
            time_bonus
        )
        final_accuracy = max(0.0, min(100.0, final_accuracy))

        # Star Rating
        if final_accuracy >= 90.0:
            stars = 3
        elif final_accuracy >= 75.0:
            stars = 2
        elif final_accuracy >= 50.0:
            stars = 1
        else:
            stars = 0

        passed = stars >= 1

        # Calculate XP
        base = challenge.base_xp
        multiplier = final_accuracy / 100.0
        star_bonus = 30 if stars == 3 else (15 if stars == 2 else 0)
        xp_earned = int(base * multiplier + star_bonus) if passed else 10

        # Progression
        new_xp, new_lvl, new_title, leveled_up = ProgressionManager.award_xp(
            existing_total_xp, xp_earned
        )

        if stars == 3:
            feedback.insert(0, "🌟 Outstanding Culinary Execution! 3 Stars achieved!")
        elif stars == 2:
            feedback.insert(0, "⭐ Great Job! Delicious dish with minor room for improvement.")
        elif stars == 1:
            feedback.insert(0, "Solid attempt! Follow the step guidelines closely to improve your score.")
        else:
            feedback.insert(0, "Dish needs improvement. Review the recipe steps and try again!")

        category_scores = {
            "Technique & Prep": prep_score,
            "Heat & Cooking": cook_score,
            "Seasoning": season_score,
            "Sequence & Time": sequence_score,
        }

        return AttemptResult(
            challenge_id=challenge.id,
            accuracy_score=final_accuracy,
            stars=stars,
            xp_earned=xp_earned,
            time_taken_seconds=elapsed_time,
            passed=passed,
            feedback=feedback,
            category_scores=category_scores,
            new_total_xp=new_xp,
            new_level=new_lvl,
            rank_title=new_title,
            leveled_up=leveled_up,
        )

