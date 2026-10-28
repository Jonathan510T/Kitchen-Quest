"""Interactive 2D virtual kitchen with multi-station cooking and challenge hub."""

import sys
import time
from typing import Any

try:
    from PySide6.QtCore import QTimer, Qt, Signal
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    from PySide6.QtWidgets import (
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QStackedWidget,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    # PySide6 not installed in current environment; stub for headless execution
    Qt = None
    Signal = lambda *args, **kwargs: None
    QWidget = object
    QDialog = object
    QFrame = object

from gameplay.engine import KitchenSimulator, ProgressionManager
from gameplay.models import (
    ActionType,
    AttemptResult,
    HeatLevel,
    IngredientItem,
    IngredientState,
    RecipeChallenge,
    Station,
)
from gameplay.recipes import get_challenge_by_id, get_default_challenges

# Kitchen theme palette
BEIGE = "#f6ecd6"
BEIGE_DARK = "#ead9b8"
CREAM = "#fffaf0"
WOOD_BOARD = "#d7b48c"
WOOD_DARK = "#8b5a2b"
PAN_COLOR = "#2b2b2b"
INPUT_BG = "#fbf3e1"
BROWN = "#3e2a1e"
BROWN_SOFT = "#7a6352"
RED = "#c8362b"
GREEN = "#2e7d32"
GOLD = "#d48806"
BLUE = "#1976d2"


class ResultsDialog(QDialog):
    """Displays challenge results, star ratings, accuracy score, and XP rewards."""

    def __init__(self, result: AttemptResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dish Evaluation")
        self.resize(520, 560)
        self.setStyleSheet(f"""
            QDialog {{ background: {BEIGE}; }}
            QLabel {{ color: {BROWN}; }}
            QFrame#card {{ background: {CREAM}; border: 2px solid {BEIGE_DARK}; border-radius: 12px; }}
            QPushButton#primary {{
                background: {RED}; color: white; font-weight: bold; border-radius: 8px; padding: 10px 20px; font-size: 14px;
            }}
            QPushButton#primary:hover {{ background: #b02d23; }}
        """)

        layout = QVBoxLayout(self)
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        # Star Rating Header
        stars_str = "⭐" * result.stars + "☆" * (3 - result.stars)
        stars_lbl = QLabel(stars_str)
        stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stars_lbl.setStyleSheet("font-size: 40px; margin-top: 10px;")
        card_layout.addWidget(stars_lbl)

        # Title
        title_text = "Culinary Triumph!" if result.passed else "Needs More Practice"
        title_lbl = QLabel(title_text)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {RED if not result.passed else GREEN};")
        card_layout.addWidget(title_lbl)

        # Score & XP
        score_box = QHBoxLayout()
        acc_lbl = QLabel(f"Accuracy: <b>{result.accuracy_score}%</b>")
        acc_lbl.setStyleSheet("font-size: 16px;")
        xp_lbl = QLabel(f"XP Earned: <b>+{result.xp_earned} XP</b>")
        xp_lbl.setStyleSheet(f"font-size: 16px; color: {GOLD}; font-weight: bold;")
        score_box.addWidget(acc_lbl)
        score_box.addWidget(xp_lbl)
        card_layout.addLayout(score_box)

        # Leveled up banner
        if result.leveled_up:
            lvl_banner = QLabel(f"🎉 LEVEL UP! You are now a <b>{result.rank_title}</b> (Level {result.new_level})!")
            lvl_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lvl_banner.setStyleSheet(f"background: #fff8e1; border: 1px solid {GOLD}; border-radius: 6px; padding: 8px; font-size: 14px;")
            card_layout.addWidget(lvl_banner)

        # Category Scores
        cat_group = QGroupBox("Performance Breakdown")
        cat_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {BROWN}; margin-top: 10px; }}")
        cat_layout = QVBoxLayout(cat_group)
        for cat, score in result.category_scores.items():
            row = QHBoxLayout()
            row.addWidget(QLabel(cat))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(score))
            bar.setFixedHeight(14)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{ background: {BEIGE_DARK}; border-radius: 4px; }}
                QProgressBar::chunk {{ background: {GREEN if score >= 80 else (GOLD if score >= 60 else RED)}; border-radius: 4px; }}
            """)
            row.addWidget(bar)
            val_lbl = QLabel(f"{int(score)}%")
            val_lbl.setFixedWidth(40)
            row.addWidget(val_lbl)
            cat_layout.addLayout(row)
        card_layout.addWidget(cat_group)

        # Chef Feedback
        fb_group = QGroupBox("Head Chef's Notes")
        fb_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {BROWN}; margin-top: 10px; }}")
        fb_layout = QVBoxLayout(fb_group)
        for note in result.feedback[:4]:
            n_lbl = QLabel(f"• {note}")
            n_lbl.setWordWrap(True)
            n_lbl.setStyleSheet(f"color: {BROWN_SOFT}; font-size: 13px;")
            fb_layout.addWidget(n_lbl)
        card_layout.addWidget(fb_group)

        layout.addWidget(card)

        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Continue", self)
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self.accept)
        btn_box.addStretch()
        btn_box.addWidget(ok_btn)
        btn_box.addStretch()
        layout.addLayout(btn_box)


class CookingStationWidget(QWidget):
    """The interactive 2D cooking station simulating prep, mix, stove, and plating."""

    cooking_finished = Signal(object)  # Emits AttemptResult
    back_to_hub_requested = Signal()

    def __init__(self, challenge: RecipeChallenge, parent=None):
        super().__init__(parent)
        self.challenge = challenge
        self.sim = KitchenSimulator(challenge)
        self.prep_clicks: int = 0
        self.mix_clicks: int = 0

        self._setup_ui()

        # Timer for active stove simulation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(500)  # Tick every 0.5 seconds

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # TOP BAR
        top_bar = QHBoxLayout()
        back_btn = QPushButton("← Return to Hub")
        back_btn.setStyleSheet(f"background: {BEIGE_DARK}; color: {BROWN}; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        back_btn.clicked.connect(self._on_back)
        top_bar.addWidget(back_btn)

        self.title_lbl = QLabel(f"Cooking: <b>{self.challenge.title}</b>")
        self.title_lbl.setStyleSheet(f"font-size: 18px; color: {BROWN};")
        top_bar.addWidget(self.title_lbl)

        top_bar.addStretch()

        self.time_lbl = QLabel("Time: 0.0s")
        self.time_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {RED};")
        top_bar.addWidget(self.time_lbl)

        main_layout.addLayout(top_bar)

        # STEP INSTRUCTION BANNER
        self.instruction_banner = QLabel()
        self.instruction_banner.setWordWrap(True)
        self.instruction_banner.setStyleSheet(f"""
            background: #fff8e1; border: 2px solid {GOLD}; border-radius: 8px;
            padding: 10px; font-size: 14px; color: {BROWN};
        """)
        main_layout.addWidget(self.instruction_banner)

        # STATIONS TABS
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 2px solid {BEIGE_DARK}; background: {CREAM}; border-radius: 8px; }}
            QTabBar::tab {{
                background: {BEIGE_DARK}; color: {BROWN}; padding: 10px 18px; font-weight: bold; font-size: 14px;
                border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px;
            }}
            QTabBar::tab:selected {{ background: {CREAM}; color: {RED}; border-bottom: 2px solid {CREAM}; }}
        """)

        self.prep_tab = self._create_prep_tab()
        self.mixing_tab = self._create_mixing_tab()
        self.stove_tab = self._create_stove_tab()
        self.plating_tab = self._create_plating_tab()

        self.tabs.addTab(self.prep_tab, "🔪 Prep Station")
        self.tabs.addTab(self.mixing_tab, "🥣 Mixing Station")
        self.tabs.addTab(self.stove_tab, "🍳 Stove Station")
        self.tabs.addTab(self.plating_tab, "🍽️ Plating Station")
        self.tabs.currentChanged.connect(self._on_station_tab_changed)

        main_layout.addWidget(self.tabs, stretch=2)

        # BOTTOM WORK AREA: PANTRY & ACTION LOG
        bottom_box = QHBoxLayout()

        # Pantry Group
        pantry_group = QGroupBox("🧺 Pantry & Ingredients Counter")
        pantry_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {BROWN}; }}")
        pantry_layout = QVBoxLayout(pantry_group)
        self.pantry_list = QListWidget()
        self.pantry_list.setStyleSheet(f"background: {INPUT_BG}; border: 1px solid {BEIGE_DARK}; border-radius: 6px;")
        pantry_layout.addWidget(self.pantry_list)

        move_btn_row = QHBoxLayout()
        to_prep_btn = QPushButton("Move to Prep")
        to_prep_btn.clicked.connect(lambda: self._move_selected_ingredient(Station.PREP))
        to_mix_btn = QPushButton("Move to Bowl")
        to_mix_btn.clicked.connect(lambda: self._move_selected_ingredient(Station.MIXING))
        to_stove_btn = QPushButton("Add to Pan")
        to_stove_btn.clicked.connect(lambda: self._move_selected_ingredient(Station.STOVE))
        to_plate_btn = QPushButton("Transfer to Plate")
        to_plate_btn.clicked.connect(lambda: self._move_selected_ingredient(Station.PLATING))

        for b in (to_prep_btn, to_mix_btn, to_stove_btn, to_plate_btn):
            b.setStyleSheet(f"background: {BEIGE_DARK}; color: {BROWN}; font-size: 12px; padding: 4px; border-radius: 4px;")
            move_btn_row.addWidget(b)
        pantry_layout.addLayout(move_btn_row)
        bottom_box.addWidget(pantry_group, stretch=1)

        # Live Kitchen Feed
        feed_group = QGroupBox("📜 Live Kitchen Action Log")
        feed_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {BROWN}; }}")
        feed_layout = QVBoxLayout(feed_group)
        self.feed_list = QListWidget()
        self.feed_list.setStyleSheet(f"background: {INPUT_BG}; border: 1px solid {BEIGE_DARK}; border-radius: 6px;")
        feed_layout.addWidget(self.feed_list)
        bottom_box.addWidget(feed_group, stretch=1)

        main_layout.addLayout(bottom_box, stretch=1)

        self._refresh_all_views()

    def _create_prep_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("🔪 Wooden Cutting Board")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {WOOD_DARK};")
        layout.addWidget(header)

        board_frame = QFrame()
        board_frame.setStyleSheet(f"""
            background: {WOOD_BOARD}; border: 3px solid {WOOD_DARK}; border-radius: 12px; min-height: 120px;
        """)
        bf_layout = QVBoxLayout(board_frame)
        self.prep_items_lbl = QLabel("Cutting Board is empty. Select an ingredient from Pantry and click 'Move to Prep'.")
        self.prep_items_lbl.setWordWrap(True)
        self.prep_items_lbl.setStyleSheet(f"color: {BROWN}; font-size: 14px; font-weight: bold;")
        bf_layout.addWidget(self.prep_items_lbl)
        layout.addWidget(board_frame)

        # Action Buttons
        btn_box = QHBoxLayout()
        chop_btn = QPushButton("Chop 🔪")
        chop_btn.setStyleSheet(f"background: {WOOD_DARK}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        chop_btn.clicked.connect(lambda: self._on_prep_action(ActionType.CHOP))

        slice_btn = QPushButton("Slice 🗡️")
        slice_btn.setStyleSheet(f"background: {WOOD_DARK}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        slice_btn.clicked.connect(lambda: self._on_prep_action(ActionType.SLICE))

        dice_btn = QPushButton("Dice 🎲")
        dice_btn.setStyleSheet(f"background: {WOOD_DARK}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        dice_btn.clicked.connect(lambda: self._on_prep_action(ActionType.DICE))

        mince_btn = QPushButton("Mince 🌿")
        mince_btn.setStyleSheet(f"background: {WOOD_DARK}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        mince_btn.clicked.connect(lambda: self._on_prep_action(ActionType.MINCE))

        btn_box.addWidget(chop_btn)
        btn_box.addWidget(slice_btn)
        btn_box.addWidget(dice_btn)
        btn_box.addWidget(mince_btn)
        layout.addLayout(btn_box)

        self.prep_progress = QProgressBar()
        self.prep_progress.setRange(0, 3)
        self.prep_progress.setValue(0)
        self.prep_progress.setStyleSheet(f"""
            QProgressBar {{ background: {BEIGE_DARK}; border-radius: 4px; height: 16px; text-align: center; }}
            QProgressBar::chunk {{ background: {GREEN}; border-radius: 4px; }}
        """)
        layout.addWidget(self.prep_progress)

        return tab

    def _create_mixing_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("🥣 Stainless Steel Mixing Bowl")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {BLUE};")
        layout.addWidget(header)

        bowl_frame = QFrame()
        bowl_frame.setStyleSheet(f"""
            background: #e0e0e0; border: 3px solid #9e9e9e; border-radius: 12px; min-height: 120px;
        """)
        bf_layout = QVBoxLayout(bowl_frame)
        self.mix_items_lbl = QLabel("Mixing Bowl is empty. Move ingredients here to combine.")
        self.mix_items_lbl.setWordWrap(True)
        self.mix_items_lbl.setStyleSheet(f"color: {BROWN}; font-size: 14px; font-weight: bold;")
        bf_layout.addWidget(self.mix_items_lbl)
        layout.addWidget(bowl_frame)

        btn_box = QHBoxLayout()
        whisk_btn = QPushButton("Whisk Briskly 🌀")
        whisk_btn.setStyleSheet(f"background: {BLUE}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        whisk_btn.clicked.connect(lambda: self._on_mix_action(ActionType.WHISK))

        stir_btn = QPushButton("Stir Gently 🥄")
        stir_btn.setStyleSheet(f"background: {BLUE}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        stir_btn.clicked.connect(lambda: self._on_mix_action(ActionType.STIR))

        btn_box.addWidget(whisk_btn)
        btn_box.addWidget(stir_btn)
        layout.addLayout(btn_box)

        self.mix_progress = QProgressBar()
        self.mix_progress.setRange(0, 4)
        self.mix_progress.setValue(0)
        self.mix_progress.setStyleSheet(f"""
            QProgressBar {{ background: {BEIGE_DARK}; border-radius: 4px; height: 16px; text-align: center; }}
            QProgressBar::chunk {{ background: {BLUE}; border-radius: 4px; }}
        """)
        layout.addWidget(self.mix_progress)

        return tab

    def _create_stove_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        top_ctrl = QHBoxLayout()
        header = QLabel("🍳 Kitchen Stovetop & Pan")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {PAN_COLOR};")
        top_ctrl.addWidget(header)
        top_ctrl.addStretch()

        heat_lbl = QLabel("Heat Setting:")
        heat_lbl.setStyleSheet("font-weight: bold;")
        top_ctrl.addWidget(heat_lbl)

        self.heat_off_btn = QPushButton("OFF")
        self.heat_low_btn = QPushButton("LOW")
        self.heat_med_btn = QPushButton("MED")
        self.heat_high_btn = QPushButton("HIGH")

        for b, h in (
            (self.heat_off_btn, HeatLevel.OFF),
            (self.heat_low_btn, HeatLevel.LOW),
            (self.heat_med_btn, HeatLevel.MEDIUM),
            (self.heat_high_btn, HeatLevel.HIGH),
        ):
            b.setFixedWidth(50)
            b.clicked.connect(lambda _, lvl=h: self._set_stove_heat(lvl))
            top_ctrl.addWidget(b)
        layout.addLayout(top_ctrl)

        pan_frame = QFrame()
        pan_frame.setStyleSheet(f"""
            background: {PAN_COLOR}; border: 3px solid #111; border-radius: 12px; min-height: 120px;
        """)
        pf_layout = QVBoxLayout(pan_frame)
        self.stove_items_lbl = QLabel("Pan is empty. Add ingredients to cook on the burner.")
        self.stove_items_lbl.setWordWrap(True)
        self.stove_items_lbl.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        pf_layout.addWidget(self.stove_items_lbl)

        self.heat_indicator_lbl = QLabel("Burner is OFF")
        self.heat_indicator_lbl.setStyleSheet("color: #aaa; font-size: 13px;")
        pf_layout.addWidget(self.heat_indicator_lbl)
        layout.addWidget(pan_frame)

        # Cooking state meter
        meter_box = QHBoxLayout()
        meter_box.addWidget(QLabel("Cooking Progress:"))
        self.cook_progress = QProgressBar()
        self.cook_progress.setRange(0, 100)
        self.cook_progress.setValue(0)
        self.cook_progress.setStyleSheet(f"""
            QProgressBar {{ background: {BEIGE_DARK}; border-radius: 4px; height: 18px; text-align: center; }}
            QProgressBar::chunk {{ background: {GOLD}; border-radius: 4px; }}
        """)
        meter_box.addWidget(self.cook_progress)
        layout.addLayout(meter_box)

        # Action Buttons
        btn_box = QHBoxLayout()
        saute_btn = QPushButton("Sauté (4s) 🥘")
        saute_btn.setStyleSheet(f"background: {GOLD}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        saute_btn.clicked.connect(lambda: self._on_stove_action(ActionType.SAUTE, 4.0))

        simmer_btn = QPushButton("Simmer (6s) 🍲")
        simmer_btn.setStyleSheet(f"background: {GOLD}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        simmer_btn.clicked.connect(lambda: self._on_stove_action(ActionType.SIMMER, 6.0))

        boil_btn = QPushButton("Boil (7s) ♨️")
        boil_btn.setStyleSheet(f"background: {BLUE}; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        boil_btn.clicked.connect(lambda: self._on_stove_action(ActionType.BOIL, 7.0))

        btn_box.addWidget(saute_btn)
        btn_box.addWidget(simmer_btn)
        btn_box.addWidget(boil_btn)
        layout.addLayout(btn_box)

        return tab

    def _create_plating_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("🍽️ Plating & Serving Counter")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {RED};")
        layout.addWidget(header)

        plate_frame = QFrame()
        plate_frame.setStyleSheet(f"""
            background: white; border: 3px solid {BEIGE_DARK}; border-radius: 12px; min-height: 120px;
        """)
        pl_layout = QVBoxLayout(plate_frame)
        self.plate_items_lbl = QLabel("Plate is empty. Transfer finished ingredients here to assemble your dish.")
        self.plate_items_lbl.setWordWrap(True)
        self.plate_items_lbl.setStyleSheet(f"color: {BROWN}; font-size: 14px; font-weight: bold;")
        pl_layout.addWidget(self.plate_items_lbl)
        layout.addWidget(plate_frame)

        # Seasoning Shakers
        season_box = QHBoxLayout()
        season_lbl = QLabel("Seasoning & Herbs:")
        season_lbl.setStyleSheet("font-weight: bold;")
        season_box.addWidget(season_lbl)

        salt_btn = QPushButton("🧂 Salt")
        salt_btn.clicked.connect(lambda: self._add_seasoning("Salt"))
        pepper_btn = QPushButton("🌶️ Pepper")
        pepper_btn.clicked.connect(lambda: self._add_seasoning("Pepper"))
        basil_btn = QPushButton("🌿 Basil")
        basil_btn.clicked.connect(lambda: self._add_seasoning("Fresh Basil"))
        chives_btn = QPushButton("🌱 Chives")
        chives_btn.clicked.connect(lambda: self._add_seasoning("Chives"))

        for b in (salt_btn, pepper_btn, basil_btn, chives_btn):
            b.setStyleSheet(f"background: {BEIGE_DARK}; color: {BROWN}; padding: 6px 12px; border-radius: 6px;")
            season_box.addWidget(b)
        layout.addLayout(season_box)

        # Big Finish Button
        layout.addSpacing(10)
        self.serve_btn = QPushButton("🌟 Finish & Serve Dish 🌟")
        self.serve_btn.setStyleSheet(f"""
            background: {RED}; color: white; font-size: 18px; font-weight: bold;
            padding: 14px; border-radius: 8px;
        """)
        self.serve_btn.clicked.connect(self._on_serve_dish)
        layout.addWidget(self.serve_btn)

        return tab

    def _on_station_tab_changed(self, index: int):
        station_map = [Station.PREP, Station.MIXING, Station.STOVE, Station.PLATING]
        if 0 <= index < len(station_map):
            self.sim.current_station = station_map[index]

    def _on_tick(self):
        """Timer tick every 0.5s."""
        if self.sim.is_finished:
            return

        elapsed = time.time() - self.sim.start_time
        self.time_lbl.setText(f"Time: {elapsed:.1f}s / {self.challenge.time_limit_seconds}s")
        if elapsed > self.challenge.time_limit_seconds:
            self.time_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {RED};")

        # Cook tick on stove
        self.sim.cook_tick(0.5)
        cook_pct = min(100, int((self.sim.stove_cook_seconds / 10.0) * 100))
        self.cook_progress.setValue(cook_pct)

        # Update stove progress color
        if self.sim.stove_cook_seconds > 12.0:
            self.cook_progress.setStyleSheet(f"""
                QProgressBar {{ background: {BEIGE_DARK}; border-radius: 4px; height: 18px; }}
                QProgressBar::chunk {{ background: black; }}
            """)
        elif self.sim.stove_cook_seconds >= 3.0:
            self.cook_progress.setStyleSheet(f"""
                QProgressBar {{ background: {BEIGE_DARK}; border-radius: 4px; height: 18px; }}
                QProgressBar::chunk {{ background: {GREEN}; }}
            """)

        self._refresh_all_views()

    def _move_selected_ingredient(self, target_station: Station):
        sel = self.pantry_list.currentItem()
        if not sel:
            return
        item_id = sel.data(Qt.ItemDataRole.UserRole)
        if item_id:
            moved = self.sim.move_ingredient(item_id, target_station)
            if moved:
                self._log_action(f"Moved {sel.text()} to {target_station.value.title()} Station.")
                self._refresh_all_views()

    def _on_prep_action(self, action: ActionType):
        if not self.sim.prep_board:
            self._log_action("Cutting board is empty! Move an ingredient from the Pantry first.")
            return

        self.prep_clicks += 1
        self.prep_progress.setValue(min(3, self.prep_clicks))

        if self.prep_clicks >= 3:
            self.sim.perform_prep(action)
            names = ", ".join(i.name for i in self.sim.prep_board)
            self._log_action(f"{action.value.title()}ed {names} on the cutting board!")
            self.prep_clicks = 0
            self.prep_progress.setValue(0)
            self._refresh_all_views()
        else:
            self._log_action(f"{action.value.title()} progress: {self.prep_clicks}/3 clicks.")

    def _on_mix_action(self, action: ActionType):
        if not self.sim.mixing_bowl:
            self._log_action("Mixing bowl is empty! Add ingredients first.")
            return

        self.mix_clicks += 1
        self.mix_progress.setValue(min(4, self.mix_clicks))

        if self.mix_clicks >= 4:
            self.sim.perform_mix(action)
            self._log_action(f"Thoroughly {action.value.title()}ed mixture in the bowl.")
            self.mix_clicks = 0
            self.mix_progress.setValue(0)
            self._refresh_all_views()
        else:
            self._log_action(f"{action.value.title()}ing... ({self.mix_clicks}/4)")

    def _set_stove_heat(self, heat: HeatLevel):
        self.sim.set_stove_heat(heat)
        heat_colors = {
            HeatLevel.OFF: "#aaa",
            HeatLevel.LOW: BLUE,
            HeatLevel.MEDIUM: GOLD,
            HeatLevel.HIGH: RED,
        }
        self.heat_indicator_lbl.setText(f"Burner is set to {heat.value.upper()} 🔥" if heat != HeatLevel.OFF else "Burner is OFF")
        self.heat_indicator_lbl.setStyleSheet(f"color: {heat_colors.get(heat, '#aaa')}; font-size: 14px; font-weight: bold;")
        self._log_action(f"Stove burner adjusted to {heat.value.upper()}.")

    def _on_stove_action(self, action: ActionType, duration: float):
        if not self.sim.stove_pan:
            self._log_action("Pan is empty! Add ingredients to pan first.")
            return
        if self.sim.stove_heat == HeatLevel.OFF:
            self._log_action("Turn on the burner before cooking!")
            return

        success = self.sim.perform_stove_action(action, duration)
        if success:
            names = ", ".join(i.name for i in self.sim.stove_pan)
            self._log_action(f"{action.value.title()}ed {names} for {duration:.1f}s at {self.sim.stove_heat.value.title()} heat.")
            self._refresh_all_views()

    def _add_seasoning(self, name: str):
        self.sim.add_seasoning(name)
        self._log_action(f"Added a pinch of {name}.")
        self._refresh_all_views()

    def _on_serve_dish(self):
        self.timer.stop()
        result = self.sim.finish_and_serve()
        dialog = ResultsDialog(result, self)
        dialog.exec()
        self.cooking_finished.emit(result)

    def _on_back(self):
        self.timer.stop()
        self.back_to_hub_requested.emit()

    def _log_action(self, text: str):
        t = time.strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{t}] {text}")
        self.feed_list.insertItem(0, item)

    def _refresh_all_views(self):
        # Step instruction
        step_idx = self.sim.current_step_index
        if step_idx < len(self.challenge.steps):
            step = self.challenge.steps[step_idx]
            self.instruction_banner.setText(
                f"<b>Step {step.step_number}: {step.title}</b> — {step.instruction}\n"
                f"<span style='color: {BROWN_SOFT}; font-size: 12px;'>Hint: {step.hint}</span>"
            )
        else:
            self.instruction_banner.setText("<b>All steps ready!</b> Season your dish and click 'Finish & Serve Dish' on the Plating Station.")

        # Pantry
        self.pantry_list.clear()
        for i in self.sim.pantry_items:
            item = QListWidgetItem(f"{i.icon} {i.name} ({i.quantity} {i.unit}) — [{i.state.value}]")
            item.setData(Qt.ItemDataRole.UserRole, i.id)
            self.pantry_list.addItem(item)

        # Prep board
        if self.sim.prep_board:
            self.prep_items_lbl.setText("\n".join(f"{i.icon} {i.name} — [{i.state.value.upper()}]" for i in self.sim.prep_board))
        else:
            self.prep_items_lbl.setText("Cutting Board is empty. Select an ingredient from Pantry and click 'Move to Prep'.")

        # Mixing bowl
        if self.sim.mixing_bowl:
            self.mix_items_lbl.setText("\n".join(f"{i.icon} {i.name} — [{i.state.value.upper()}]" for i in self.sim.mixing_bowl))
        else:
            self.mix_items_lbl.setText("Mixing Bowl is empty. Move ingredients here to combine.")

        # Stove pan
        if self.sim.stove_pan:
            status_lines = []
            for i in self.sim.stove_pan:
                color = RED if i.state == IngredientState.BURNT else (GREEN if i.state == IngredientState.PERFECT else GOLD)
                status_lines.append(f"{i.icon} {i.name} — <span style='color:{color}; font-weight:bold;'>{i.state.value.upper()}</span>")
            self.stove_items_lbl.setText("<br>".join(status_lines))
        else:
            self.stove_items_lbl.setText("Pan is empty. Add ingredients to cook on the burner.")

        # Plate
        if self.sim.plate:
            items_str = "<br>".join(f"{i.icon} {i.name} ({i.state.value})" for i in self.sim.plate)
            season_str = f"<br>Seasonings added: {', '.join(s.title() for s in self.sim.seasonings_added)}" if self.sim.seasonings_added else ""
            self.plate_items_lbl.setText(items_str + season_str)
        else:
            self.plate_items_lbl.setText("Plate is empty. Transfer finished components here to assemble your dish.")


class KitchenHubWidget(QWidget):
    """The game hub displaying user level, XP progress, and available cooking challenges."""

    challenge_selected = Signal(object)  # Emits RecipeChallenge
    signout_requested = Signal()

    def __init__(self, username: str, user_id: int, api_client=None, token: str | None = None, parent=None):
        super().__init__(parent)
        self.username = username
        self.user_id = user_id
        self.api_client = api_client
        self.token = token
        self._setup_ui()
        self.refresh_progress()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # PROFILE / XP HEADER
        header_card = QFrame()
        header_card.setObjectName("card")
        header_card.setStyleSheet(f"""
            QFrame#card {{ background: {CREAM}; border: 2px solid {BEIGE_DARK}; border-radius: 12px; padding: 12px; }}
        """)
        h_layout = QHBoxLayout(header_card)

        avatar_lbl = QLabel("👨‍🍳")
        avatar_lbl.setStyleSheet("font-size: 44px;")
        h_layout.addWidget(avatar_lbl)

        info_box = QVBoxLayout()
        self.name_lbl = QLabel(f"Chef <b>{self.username}</b>")
        self.name_lbl.setStyleSheet(f"font-size: 20px; color: {BROWN};")
        info_box.addWidget(self.name_lbl)

        self.rank_lbl = QLabel("Level 1: Prep Cook")
        self.rank_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {RED};")
        info_box.addWidget(self.rank_lbl)

        # XP Bar
        self.xp_bar = QProgressBar()
        self.xp_bar.setRange(0, 100)
        self.xp_bar.setValue(0)
        self.xp_bar.setStyleSheet(f"""
            QProgressBar {{ background: {BEIGE_DARK}; border-radius: 6px; height: 14px; text-align: center; }}
            QProgressBar::chunk {{ background: {GOLD}; border-radius: 6px; }}
        """)
        info_box.addWidget(self.xp_bar)
        self.xp_text_lbl = QLabel("0 / 100 XP")
        self.xp_text_lbl.setStyleSheet(f"font-size: 11px; color: {BROWN_SOFT};")
        info_box.addWidget(self.xp_text_lbl)
        h_layout.addLayout(info_box)

        h_layout.addStretch()

        self.stars_count_lbl = QLabel("⭐ Total Stars: 0")
        self.stars_count_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {GOLD};")
        h_layout.addWidget(self.stars_count_lbl)

        signout_btn = QPushButton("Sign out")
        signout_btn.setStyleSheet(f"background: {BEIGE_DARK}; color: {BROWN}; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
        signout_btn.clicked.connect(self.signout_requested.emit)
        h_layout.addWidget(signout_btn)

        main_layout.addWidget(header_card)

        # RECIPES / CHALLENGES TITLE
        ch_title = QLabel("🍳 Cooking Challenges & Lessons")
        ch_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {BROWN};")
        main_layout.addWidget(ch_title)

        # SCROLLABLE CHALLENGE CARDS
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }}")
        cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(cards_widget)
        self.cards_layout.setSpacing(12)
        scroll.setWidget(cards_widget)

        main_layout.addWidget(scroll, stretch=1)

    def refresh_progress(self):
        """Fetch updated progress and challenges from API client or local service."""
        if self.api_client:
            progress = self.api_client.get_progress(self.token)
            challenges = self.api_client.get_challenges(self.token)
        else:
            challenges = [c.to_dict() for c in get_default_challenges()]
            progress = {"current_level": 1, "rank_title": "Prep Cook", "total_xp": 0, "current_level_base_xp": 0, "next_level_xp": 100, "total_stars": 0}

        # Update header
        lvl = progress.get("current_level", 1)
        title = progress.get("rank_title", "Prep Cook")
        total_xp = progress.get("total_xp", 0)
        base_xp = progress.get("current_level_base_xp", 0)
        next_xp = progress.get("next_level_xp", 100)
        stars = progress.get("total_stars", 0)

        self.rank_lbl.setText(f"Level {lvl}: <b>{title}</b>")
        self.stars_count_lbl.setText(f"⭐ Total Stars: {stars}")

        range_xp = max(1, next_xp - base_xp)
        cur_xp_in_lvl = max(0, total_xp - base_xp)
        pct = min(100, int((cur_xp_in_lvl / range_xp) * 100))
        self.xp_bar.setValue(pct)
        self.xp_text_lbl.setText(f"{total_xp} / {next_xp} XP to next level")

        # Rebuild challenge cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for c_dict in challenges:
            card = self._create_challenge_card(c_dict)
            self.cards_layout.addWidget(card)

    def _create_challenge_card(self, c_dict: dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{ background: {CREAM}; border: 2px solid {BEIGE_DARK}; border-radius: 10px; padding: 14px; }}
            QFrame:hover {{ border: 2px solid {GOLD}; }}
        """)
        layout = QHBoxLayout(card)

        info = QVBoxLayout()
        title_row = QHBoxLayout()
        t_lbl = QLabel(c_dict.get("title", ""))
        t_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {BROWN};")
        title_row.addWidget(t_lbl)

        diff = c_dict.get("difficulty", "Beginner")
        diff_colors = {"Beginner": GREEN, "Intermediate": GOLD, "Advanced": RED}
        diff_lbl = QLabel(diff)
        diff_lbl.setStyleSheet(f"""
            background: {diff_colors.get(diff, GREEN)}; color: white; border-radius: 4px;
            padding: 2px 8px; font-size: 11px; font-weight: bold;
        """)
        title_row.addWidget(diff_lbl)
        title_row.addStretch()
        info.addLayout(title_row)

        desc_lbl = QLabel(c_dict.get("description", ""))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {BROWN_SOFT}; font-size: 13px;")
        info.addWidget(desc_lbl)

        meta_lbl = QLabel(f"⏱️ Limit: {c_dict.get('time_limit_seconds', 90)}s | 🏆 Base XP: {c_dict.get('base_xp', 100)} XP")
        meta_lbl.setStyleSheet(f"color: {BROWN_SOFT}; font-size: 12px; margin-top: 4px;")
        info.addWidget(meta_lbl)

        layout.addLayout(info, stretch=3)

        # Stars & Cook button
        right_box = QVBoxLayout()
        stars = c_dict.get("best_stars", 0)
        stars_lbl = QLabel("⭐" * stars + "☆" * (3 - stars) if stars > 0 else "Unplayed")
        stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stars_lbl.setStyleSheet(f"font-size: 18px; color: {GOLD}; font-weight: bold;")
        right_box.addWidget(stars_lbl)

        cook_btn = QPushButton("Cook Recipe 🍳")
        cook_btn.setStyleSheet(f"""
            background: {RED}; color: white; font-weight: bold; padding: 10px 18px;
            border-radius: 6px; font-size: 14px;
        """)
        ch_id = c_dict.get("id")
        cook_btn.clicked.connect(lambda _, cid=ch_id: self._start_challenge(cid))
        right_box.addWidget(cook_btn)

        layout.addLayout(right_box, stretch=1)
        return card

    def _start_challenge(self, challenge_id: int):
        c = get_challenge_by_id(challenge_id)
        if c:
            self.challenge_selected.emit(c)

