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

class LoginWindow(QWidget):
    login_succeeded = Signal(str, str)  # username, role

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Sign in")
        self.setMinimumSize(480, 740)
        self._settings = QSettings("KitchenQuest", "KitchenLogin")

        self._build_ui()

# UI construction
    def _build_ui(self):
        outer = QVBoxLayout(self)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    login = LoginWindow()

    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()