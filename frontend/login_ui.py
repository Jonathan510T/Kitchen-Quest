"""
Kitchen-themed PySide6 login with separate User and Admin sign-in.
Demo credentials:
    User  tab:  user  / user123
    Admin tab:  admin / admin123
"""

import sys
import time

from PySide6.QtCore import Qt, QSettings, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# PALETTE
BEIGE = "#f6ecd6"        # tablecloth / page background

def make_tablecloth_tile() -> QPixmap:
    # Red and beige gingham tablecloth tile.
    size, half = 48, 24
    tile = QPixmap(size, size)
    tile.fill(QColor(BEIGE))
    p = QPainter(tile)
    stripe = QColor(200, 54, 43, 48)
    p.fillRect(0, 0, half, size, stripe)   
    p.fillRect(0, 0, size, half, stripe)   
    p.end()
    return tile

class LoginWindow(QWidget):
    login_succeeded = Signal(str, str)  # username, role

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Sign in")
        self._tile = make_tablecloth_tile()
        self.setMinimumSize(480, 740)
        self._settings = QSettings("KitchenQuest", "KitchenLogin")

        self._build_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawTiledPixmap(self.rect(), self._tile)

    # UI construction
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 30, 30, 30)
        outer.addStretch()

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(400)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 26)
        layout.setSpacing(6)

        # Username
        layout.addWidget(self._field_label("Username"))
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter your username")
        layout.addWidget(self.username)
        layout.addSpacing(8)

        # Password
        layout.addWidget(self._field_label("Password"))
        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter your password")
        self.password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password)

        # Login button
        self.login_btn = QPushButton("Sign in")
        self.login_btn.setObjectName("primary")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        layout.addSpacing(8)
        layout.addWidget(self.login_btn)

        outer.addWidget(card, alignment=Qt.AlignCenter)
        outer.addStretch()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    login = LoginWindow()

    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()