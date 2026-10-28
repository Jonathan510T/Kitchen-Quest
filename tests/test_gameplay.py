"""Unit tests for the core gameplay engine, scoring rules, and progression."""

import unittest
from gameplay.models import (
    ActionType,
    HeatLevel,
    IngredientState,
    Station,
)
from gameplay.recipes import get_challenge_by_id, get_default_challenges
from gameplay.engine import KitchenSimulator, CookingEvaluator, ProgressionManager


class GameplayEngineTests(unittest.TestCase):
    def setUp(self):
        self.challenges = get_default_challenges()
        self.assertGreater(len(self.challenges), 0)
        self.soup_challenge = get_challenge_by_id(1)
        self.assertIsNotNone(self.soup_challenge)

    def test_default_challenges_structure(self):
        for c in self.challenges:
            self.assertTrue(c.id > 0)
            self.assertTrue(len(c.title) > 0)
            self.assertTrue(len(c.ingredients) > 0)
            self.assertTrue(len(c.steps) > 0)
            self.assertTrue(c.time_limit_seconds > 0)
            self.assertTrue(c.base_xp > 0)

    def test_progression_thresholds(self):
        lvl, title, base, nxt = ProgressionManager.get_level_info(0)
        self.assertEqual(lvl, 1)
        self.assertEqual(title, "Prep Cook")
        self.assertEqual(nxt, 100)

        lvl, title, base, nxt = ProgressionManager.get_level_info(150)
        self.assertEqual(lvl, 2)
        self.assertEqual(title, "Commis Chef")

        lvl, title, base, nxt = ProgressionManager.get_level_info(520)
        self.assertEqual(lvl, 4)
        self.assertEqual(title, "Sous Chef")

        new_xp, new_lvl, new_title, leveled = ProgressionManager.award_xp(90, 25)
        self.assertEqual(new_xp, 115)
        self.assertEqual(new_lvl, 2)
        self.assertTrue(leveled)

    def test_simulator_ingredient_movement(self):
        sim = KitchenSimulator(self.soup_challenge)
        self.assertEqual(len(sim.pantry_items), len(self.soup_challenge.ingredients))
        self.assertEqual(len(sim.prep_board), 0)

        # Move tomato to prep board
        tomato = [i for i in sim.pantry_items if i.name == "Tomato"][0]
        moved = sim.move_ingredient(tomato.id, Station.PREP)
        self.assertTrue(moved)
        self.assertEqual(len(sim.prep_board), 1)
        self.assertEqual(sim.prep_board[0].name, "Tomato")
        self.assertEqual(sim.prep_board[0].current_station, Station.PREP)

    def test_prep_cutting_actions(self):
        sim = KitchenSimulator(self.soup_challenge)
        tomato = [i for i in sim.pantry_items if i.name == "Tomato"][0]
        sim.move_ingredient(tomato.id, Station.PREP)

        self.assertEqual(sim.prep_board[0].state, IngredientState.RAW)
        sim.perform_prep(ActionType.CHOP)
        self.assertEqual(sim.prep_board[0].state, IngredientState.CHOPPED)

        sim.perform_prep(ActionType.DICE)
        self.assertEqual(sim.prep_board[0].state, IngredientState.DICED)

    def test_mixing_bowl_actions(self):
        salad_challenge = get_challenge_by_id(2)
        sim = KitchenSimulator(salad_challenge)

        oil = [i for i in sim.pantry_items if i.name == "Olive Oil"][0]
        lemon = [i for i in sim.pantry_items if i.name == "Lemon"][0]
        sim.move_ingredient(oil.id, Station.MIXING)
        sim.move_ingredient(lemon.id, Station.MIXING)

        self.assertEqual(len(sim.mixing_bowl), 2)
        mixed = sim.perform_mix(ActionType.WHISK)
        self.assertTrue(mixed)
        self.assertEqual(sim.mixing_bowl[0].state, IngredientState.MIXED)
        self.assertEqual(sim.mixing_bowl[1].state, IngredientState.MIXED)

    def test_stove_cooking_and_heat(self):
        sim = KitchenSimulator(self.soup_challenge)
        garlic = [i for i in sim.pantry_items if i.name == "Garlic"][0]
        sim.move_ingredient(garlic.id, Station.STOVE)

        # Off heat does not cook
        sim.cook_tick(5.0)
        self.assertEqual(sim.stove_pan[0].state, IngredientState.RAW)

        # Set medium heat and cook
        sim.set_stove_heat(HeatLevel.MEDIUM)
        sim.cook_tick(4.0)
        self.assertIn(sim.stove_pan[0].state, (IngredientState.COOKING, IngredientState.PERFECT))

        # Overcook / burn with excessive time on high heat
        sim.set_stove_heat(HeatLevel.HIGH)
        sim.cook_tick(15.0)
        self.assertEqual(sim.stove_pan[0].state, IngredientState.BURNT)

    def test_perfect_cooking_attempt_scoring(self):
        sim = KitchenSimulator(self.soup_challenge)
        # Execute steps according to recipe
        # Step 1: Prep tomato
        tomato = [i for i in sim.pantry_items if i.name == "Tomato"][0]
        sim.move_ingredient(tomato.id, Station.PREP)
        sim.perform_prep(ActionType.CHOP)

        # Step 2: Prep garlic
        garlic = [i for i in sim.pantry_items if i.name == "Garlic"][0]
        sim.move_ingredient(garlic.id, Station.PREP)
        sim.perform_prep(ActionType.MINCE)

        # Step 3: Sauté garlic on stove
        oil = [i for i in sim.pantry_items if i.name == "Olive Oil"][0]
        sim.move_ingredient(oil.id, Station.STOVE)
        sim.move_ingredient(garlic.id, Station.STOVE)
        sim.set_stove_heat(HeatLevel.MEDIUM)
        sim.perform_stove_action(ActionType.SAUTE, duration_seconds=3.5)

        # Step 4: Simmer tomatoes on stove
        sim.move_ingredient(tomato.id, Station.STOVE)
        sim.perform_stove_action(ActionType.SIMMER, duration_seconds=3.0)

        # Step 5: Transfer to plate and season
        sim.move_ingredient(tomato.id, Station.PLATING)
        sim.move_ingredient(garlic.id, Station.PLATING)
        sim.add_seasoning("salt")
        sim.add_seasoning("fresh basil")

        # Finish
        result = sim.finish_and_serve()
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.accuracy_score, 85.0)
        self.assertIn(result.stars, (2, 3))
        self.assertGreater(result.xp_earned, 80)
        self.assertTrue(len(result.feedback) > 0)


if __name__ == "__main__":
    unittest.main()

