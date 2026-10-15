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
BEIGE = "#f6ecd6"  # tablecloth / page background
BEIGE_DARK = "#ead9b8"  # borders, segmented control
CREAM = "#fffaf0"  # card surface
INPUT_BG = "#fbf3e1"  # text field fill
BROWN = "#3e2a1e"  # headings
BROWN_SOFT = "#7a6352"  # secondary text
RED = "#c8362b"  # brand red
SERIF = '"Georgia", "Palatino Linotype", "Times New Roman", serif'

USER = "user"

ROLE_CONFIG = {
    USER: {
        "emoji": "🍳",
        "accent": RED,
        "accent_hover": "#b02d23",
        "accent_pressed": "#96251c",
        "accent_disabled": "#e0948d",
        "badge_bg": "#fbe0dc",
        "title": "Welcome to the kitchen!",
        "subtitle": "Sign in to start cooking",
        "button": "Sign in",
    },
}

# fake authentication for testing purposes
FAKE_DB = {
    "user": {"password": "user123"},
    "admin": {"password": "admin123"},
}

def authenticate(username: str, password: str) -> tuple[bool, str]:
    """Return (success, message)."""
    time.sleep(1.0)  # simulate network latency
    record = FAKE_DB.get(username)
    if record is None or record["password"] != password:
        return False, "Invalid username or password."
    return True, "OK"

class AuthWorker(QThread):
    """Runs authentication off the UI thread so the window never freezes."""

    finished_auth = Signal(bool, str)

    def __init__(self, username: str, password: str):
        super().__init__()
        self._args = (username, password)

    def run(self):
        try:
            ok, msg = authenticate(*self._args)
        except Exception as exc:  # network errors etc.
            ok, msg = False, f"Could not sign in: {exc}"
        self.finished_auth.emit(ok, msg)

def build_style(role: str) -> str:
    c = ROLE_CONFIG[role]
    return f"""
QFrame#card {{
    background: {CREAM};
    border: 2px solid {BEIGE_DARK};
    border-radius: 20px;
}}

QLabel#badge {{
    background: {c['badge_bg']};
    border: 2px solid {BEIGE_DARK};
    border-radius: 36px;
    font-size: 34px;
}}
QLabel#title {{
    font-family: {SERIF};
    font-size: 26px;
    font-weight: 700;
    color: {BROWN};
}}
QLabel#subtitle {{ font-size: 13px; font-style: italic; color: {BROWN_SOFT}; }}
QLabel#fieldLabel {{ font-size: 12px; font-weight: 700; color: {BROWN}; }}
QLabel#muted {{ font-size: 12px; color: {BROWN_SOFT}; }}
QLabel#error {{ color: #b3261e; font-size: 12px; font-weight: 600; }}

/* Segmented User / Admin switch */
QFrame#segment {{ background: {BEIGE_DARK}; border-radius: 12px; }}
QPushButton#segBtn {{
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 9px 0;
    font-size: 13px;
    font-weight: 700;
    color: {BROWN_SOFT};
}}
QPushButton#segBtn:checked {{ background: {CREAM}; color: {c['accent']}; }}

QLineEdit {{
    border: 1.5px solid {BEIGE_DARK};
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 14px;
    background: {INPUT_BG};
    color: {BROWN};
    selection-background-color: {c['accent']};
    selection-color: white;
}}
QLineEdit:focus {{ border-color: {c['accent']}; background: #ffffff; }}
QLineEdit[invalid="true"] {{ border-color: #b3261e; }}

QCheckBox {{ font-size: 12px; color: {BROWN_SOFT}; spacing: 6px; }}

QPushButton#primary {{
    background: {c['accent']};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#primary:hover    {{ background: {c['accent_hover']}; }}
QPushButton#primary:pressed  {{ background: {c['accent_pressed']}; }}
QPushButton#primary:disabled {{ background: {c['accent_disabled']}; }}

QPushButton#link {{
    background: transparent;
    border: none;
    color: {c['accent']};
    font-size: 12px;
    font-weight: 600;
    padding: 0;
}}
QPushButton#link:hover {{ text-decoration: underline; }}
"""

PAGE_STYLE = f"""
QMainWindow, QWidget#page {{ background: {BEIGE}; }}
QLabel#welcome {{
    font-family: {SERIF};
    font-size: 26px;
    font-weight: 700;
    color: {RED};
}}
QListWidget {{
    background: {CREAM};
    border: 2px solid {BEIGE_DARK};
    border-radius: 12px;
    padding: 6px;
    font-size: 14px;
    color: {BROWN};
}}
QListWidget::item {{ padding: 10px; border-radius: 8px; }}
QListWidget::item:selected {{ background: {RED}; color: white; }}
"""

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
    login_succeeded = Signal(str)  # username

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Sign in")
        self._tile = make_tablecloth_tile()
        self.setMinimumSize(480, 740)
        self._settings = QSettings("KitchenQuest", "KitchenLogin")
        self._worker: AuthWorker | None = None
        self.role = USER

        self._build_ui()
        self._apply_role(USER)

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
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(62, 42, 30, 70))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 26)
        layout.setSpacing(6)

        # Badge + heading
        self.badge = QLabel()
        self.badge.setObjectName("badge")
        self.badge.setFixedSize(72, 72)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)

        self.title = QLabel()
        self.title.setObjectName("title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle = QLabel()
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(16)

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
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)

        # Show password + forgot
        options = QHBoxLayout()
        self.show_pw = QCheckBox("Show password")
        self.show_pw.toggled.connect(self._toggle_password)
        forgot = QPushButton("Forgot password?")
        forgot.setObjectName("link")
        forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot.clicked.connect(self._on_forgot)
        options.addWidget(self.show_pw)
        options.addStretch()
        options.addWidget(forgot)
        layout.addSpacing(4)
        layout.addLayout(options)

        self.remember = QCheckBox("Remember me")
        layout.addWidget(self.remember)

        # Error message
        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setMinimumHeight(20)
        layout.addSpacing(4)
        layout.addWidget(self.error_label)

        # Login button
        self.login_btn = QPushButton()
        self.login_btn.setObjectName("primary")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._on_login)
        layout.addSpacing(8)
        layout.addWidget(self.login_btn)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

        # Keyboard + validation behaviour
        self.username.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self._on_login)
        self.username.textChanged.connect(self._clear_error)
        self.password.textChanged.connect(self._clear_error)  

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    # apply the role-specific configuration to the UI
    def _apply_role(self, role: str):
        cfg = ROLE_CONFIG[role]
        self.setStyleSheet(build_style(role))
        self.badge.setText(cfg["emoji"])
        self.title.setText(cfg["title"])
        self.subtitle.setText(cfg["subtitle"])
        self.login_btn.setText(cfg["button"])

    def _toggle_password(self, checked: bool):
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _set_invalid(self, widget: QLineEdit, invalid: bool):
        widget.setProperty("invalid", invalid)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _clear_error(self):
        self.error_label.setText("")
        self._set_invalid(self.username, False)
        self._set_invalid(self.password, False)

    def _set_busy(self, busy: bool):
        self.login_btn.setEnabled(not busy)
        cfg = ROLE_CONFIG[self.role]
        self.login_btn.setText("Warming up the stove..." if busy else cfg["button"])
        for w in (
            self.username,
            self.password,
            self.show_pw,
        ):
            w.setEnabled(not busy)

    def _on_login(self):
        if self._worker is not None:
            return

        user = self.username.text().strip()
        pw = self.password.text()

        missing = False
        if not user:
            self._set_invalid(self.username, True)
            missing = True
        if not pw:
            self._set_invalid(self.password, True)
            missing = True
        if missing:
            self.error_label.setText("Please enter both username and password.")
            return

        self._set_busy(True)
        self._worker = AuthWorker(user, pw)
        self._worker.finished_auth.connect(self._on_auth_done)
        self._worker.start()
        
    def _on_auth_done(self, ok: bool, message: str):
        self._worker = None
        self._set_busy(False)

        if ok:
            self.login_succeeded.emit(self.username.text().strip())
        else:
            self.error_label.setText(message)
            self._set_invalid(self.password, True)
            self.password.selectAll()
            self.password.setFocus()

    def _on_forgot(self):
        self.error_label.setText("Password reset not set up yet (?)")

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.wait(2000)
        super().closeEvent(event)

# temporary user window to show login success
class UserWindow(QMainWindow):
    def __init__(self, username: str):
        super().__init__()
        self.setWindowTitle("Kitchen")
        self.resize(700, 450)
        self.setStyleSheet(PAGE_STYLE)
        label = QLabel(f"Hello, {username}!")
        label.setObjectName("welcome")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    login = LoginWindow()
    windows = {}

    def open_main(username: str):
        windows["main"] = UserWindow(username)
        windows["main"].show()
        login.close()

    login.login_succeeded.connect(open_main)
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()