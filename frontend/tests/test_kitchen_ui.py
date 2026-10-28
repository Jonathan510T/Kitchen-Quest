"""Unit tests for Kitchen Quest PySide6 gameplay widgets."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

try:
    import PySide6
    from PySide6.QtWidgets import QApplication
    from frontend.kitchen_ui import (
        CookingStationWidget,
        KitchenHubWidget,
        ResultsDialog,
    )
except ImportError:
    QApplication = None

from gameplay.engine import KitchenSimulator
from gameplay.models import ActionType, AttemptResult, HeatLevel, Station
from gameplay.recipes import get_challenge_by_id


@unittest.skipIf(QApplication is None, "Install PySide6 to run UI checks")
class KitchenUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.challenge = get_challenge_by_id(1)
        self.assertIsNotNone(self.challenge)

    def test_hub_widget_initialization(self):
        hub = KitchenHubWidget(username="test_chef", user_id=1)
        self.assertEqual(hub.name_lbl.text(), "Chef <b>test_chef</b>")
        self.assertGreaterEqual(hub.cards_layout.count(), 4)

    def test_cooking_station_widget_actions(self):
        widget = CookingStationWidget(self.challenge)
        self.assertEqual(widget.sim.current_station, Station.PANTRY)

        # Tab switch to prep
        widget.tabs.setCurrentIndex(0)
        self.assertEqual(widget.sim.current_station, Station.PREP)

        # Move tomato
        tomato = [i for i in widget.sim.pantry_items if i.name == "Tomato"][0]
        moved = widget.sim.move_ingredient(tomato.id, Station.PREP)
        self.assertTrue(moved)
        widget._refresh_all_views()
        self.assertIn("Tomato", widget.prep_items_lbl.text())

        # Test heat controls
        widget.tabs.setCurrentIndex(2)  # Stove
        widget._set_stove_heat(HeatLevel.MEDIUM)
        self.assertEqual(widget.sim.stove_heat, HeatLevel.MEDIUM)
        self.assertIn("MEDIUM", widget.heat_indicator_lbl.text())

        widget.timer.stop()

    def test_results_dialog(self):
        res = AttemptResult(
            challenge_id=1,
            accuracy_score=94.5,
            stars=3,
            xp_earned=125,
            time_taken_seconds=32.0,
            passed=True,
            feedback=["Outstanding execution!"],
            category_scores={"Technique": 95.0, "Cooking": 92.0},
            new_total_xp=125,
            new_level=2,
            rank_title="Commis Chef",
            leveled_up=True,
        )
        dialog = ResultsDialog(res)
        self.assertEqual(dialog.windowTitle(), "Dish Evaluation")


if __name__ == "__main__":
    unittest.main()

