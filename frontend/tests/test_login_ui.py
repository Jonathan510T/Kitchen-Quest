"""Offscreen UI checks with a fake API client; no account or database writes."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
import unittest
from unittest.mock import Mock, patch

try:
    import PySide6
except ModuleNotFoundError:
    QApplication = None
else:
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from frontend.login_ui import LoginWindow, UserWindow

from frontend.api_client import ApiError, Profile, Session


@unittest.skipIf(QApplication is None, "Install PySide6 to run UI checks")
class LoginUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / "test.ini"), QSettings.Format.IniFormat)
        self.settings_patch = patch("frontend.login_ui.QSettings", return_value=self.settings)
        self.settings_patch.start()
        self.client = Mock()
        self.session = Session(Profile(7, "qa_user", "user"), "test-token")
        self.client.login.return_value = self.session
        self.client.register.return_value = self.session.profile
        self.window = LoginWindow(self.client)

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.settings_patch.stop()
        self.settings.clear()
        self.settings.sync()
        self.temp.cleanup()

    def finish_request(self):
        deadline = time.monotonic() + 5
        while self.window._worker is not None and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertIsNone(self.window._worker, "Authentication worker did not finish")

    def enter_credentials(self):
        self.window.username.setText("qa_user")
        self.window.password.setText("QApass123!")

    def test_empty_fields_do_not_call_backend(self):
        self.window.username.clear()
        self.window._on_login()
        self.client.login.assert_not_called()
        self.assertIn("both username and password", self.window.error_label.text())

    def test_success_emits_verified_session_and_remembers_only_username(self):
        results = []
        self.window.login_succeeded.connect(results.append)
        self.enter_credentials()
        self.window.remember.setChecked(True)
        self.window._on_login()
        self.assertFalse(self.window.login_btn.isEnabled())
        self.finish_request()
        self.assertEqual(results, [self.session])
        self.assertEqual(self.window.password.text(), "")
        self.assertEqual(self.settings.allKeys(), ["user/username"])
        self.assertEqual(self.settings.value("user/username"), "qa_user")

    def test_failure_restores_form_and_does_not_open_main(self):
        results = []
        self.window.login_succeeded.connect(results.append)
        self.client.login.side_effect = ApiError("Incorrect username or password.")
        self.enter_credentials()
        self.window._on_login()
        self.finish_request()
        self.assertEqual(results, [])
        self.assertIn("Incorrect", self.window.error_label.text())
        self.assertTrue(self.window.login_btn.isEnabled())

    def test_login_screen_connects_through_http_client(self):
        from frontend.tests.test_api_client import backend, TOKEN, USER
        with backend([(200, TOKEN), (200, USER)]) as (client, requests):
            self.window.client = client
            results = []
            self.window.login_succeeded.connect(results.append)
            self.enter_credentials()
            self.window._on_login()
            self.finish_request()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].profile.username, "qa_user")
            self.assertEqual([r[1] for r in requests], ["/api/auth/login", "/api/auth/me"])

    def test_registration_returns_to_login_without_creating_a_session(self):
        results = []
        self.window.login_succeeded.connect(results.append)
        self.window._on_signup()
        self.enter_credentials()
        self.window._on_login()
        self.finish_request()
        self.client.register.assert_called_once_with("qa_user", "QApass123!")
        self.client.login.assert_not_called()
        self.assertEqual(results, [])
        self.assertFalse(self.window._registering)
        self.assertEqual(self.window.password.text(), "")
        self.assertIn("Account created", self.window.error_label.text())

    def test_registration_limits_and_return_to_sign_in(self):
        self.window._on_signup()
        self.window.username.setText("ab")
        self.window.password.setText("short")
        self.window._on_login()
        self.client.register.assert_not_called()
        self.assertIn("3-50", self.window.error_label.text())
        self.window._on_signup()
        self.assertFalse(self.window._registering)
        self.assertEqual(self.window.login_btn.text(), "Sign in")

    def test_close_during_request_waits_safely_and_suppresses_login(self):
        release = Event()
        self.client.login.side_effect = lambda *_: (release.wait(3), self.session)[1]
        results = []
        self.window.login_succeeded.connect(results.append)
        self.enter_credentials()
        self.window.show()
        self.window._on_login()
        try:
            self.window.close()
            self.assertTrue(self.window._closing)
            self.assertIsNotNone(self.window._worker)
        finally:
            release.set()
            self.finish_request()
        self.assertEqual(results, [])
        self.assertFalse(self.window.isVisible())

    def test_sign_out_drops_session_and_emits_signal(self):
        page = UserWindow(self.session)
        events = []
        page.signed_out.connect(lambda: events.append(True))
        page._sign_out()
        self.assertIsNone(page.session)
        self.assertEqual(events, [True])


if __name__ == "__main__":
    unittest.main()
