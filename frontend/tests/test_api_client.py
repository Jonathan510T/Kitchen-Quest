"""Exercise the HTTP contract against a local fake server; no database needed."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

from frontend.api_client import ApiClient, ApiError


@contextmanager
def backend(responses):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            requests.append((self.command, self.path, self.headers, body))
            status, payload = responses[len(requests) - 1]
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        do_POST = do_GET = handle_request

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield ApiClient(f"http://127.0.0.1:{server.server_port}"), requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


TOKEN = {"access_token": "test-token", "token_type": "bearer"}
USER = {"id": 7, "username": "qa_user", "role": "user"}


class ApiClientTests(unittest.TestCase):
    def test_login_uses_form_then_bearer_and_returns_server_identity(self):
        with backend([(200, TOKEN), (200, USER)]) as (client, requests):
            session = client.login(" QA_USER ", "a&b+= secret", "user")
        self.assertEqual(session.profile.username, "qa_user")
        self.assertEqual(session.profile.id, 7)
        self.assertEqual(session.access_token, "test-token")
        self.assertNotIn("test-token", repr(session))
        method, path, headers, body = requests[0]
        self.assertEqual((method, path), ("POST", "/api/auth/login"))
        self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")
        self.assertEqual(parse_qs(body.decode()), {"username": [" QA_USER "], "password": ["a&b+= secret"]})
        self.assertEqual(requests[1][:2], ("GET", "/api/auth/me"))
        self.assertEqual(requests[1][2]["Authorization"], "Bearer test-token")

    def test_admin_login_checks_backend_role(self):
        profile = dict(USER, role="admin")
        with backend([(200, TOKEN), (200, profile)]) as (client, _):
            self.assertEqual(client.login("qa_user", "password", "admin").profile.role, "admin")

    def test_wrong_role_cannot_open_either_tab(self):
        for actual, selected, message in [("user", "admin", "does not have admin"), ("admin", "user", "Admin tab")]:
            with self.subTest(actual=actual), backend([(200, TOKEN), (200, dict(USER, role=actual))]) as (client, _):
                with self.assertRaisesRegex(ApiError, message):
                    client.login("qa_user", "password", selected)

    def test_registration_sends_json_without_role_or_login_request(self):
        with backend([(201, USER)]) as (client, requests):
            self.assertEqual(client.register("qa_user", "QApass123!").id, 7)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][:2], ("POST", "/api/auth/register"))
        self.assertEqual(requests[0][2]["Content-Type"], "application/json")
        self.assertEqual(json.loads(requests[0][3]), {"username": "qa_user", "password": "QApass123!"})

    def test_http_errors_are_readable_without_echoing_server_secrets(self):
        for status, message in [(401, "Incorrect username or password"), (403, "permission"), (409, "already taken"), (422, "3-50"), (500, "HTTP 500")]:
            with self.subTest(status=status), backend([(status, {"detail": "sensitive backend text"})]) as (client, requests):
                with self.assertRaisesRegex(ApiError, message) as error:
                    client.login("qa_user", "password", "user")
                self.assertNotIn("sensitive", str(error.exception))
                self.assertEqual(len(requests), 1)

    def test_profile_request_failure_does_not_return_a_session(self):
        with backend([(200, TOKEN), (401, {})]) as (client, _):
            with self.assertRaisesRegex(ApiError, "session has expired"):
                client.login("qa_user", "password", "user")

    def test_malformed_success_payloads_are_rejected(self):
        for payload in [{}, {"access_token": 123}, [], {"access_token": "x", "token_type": "other"}]:
            with self.subTest(payload=payload), backend([(200, payload)]) as (client, _):
                with self.assertRaises(ApiError):
                    client.login("qa_user", "password", "user")
        for profile in [{}, dict(USER, role="owner"), dict(USER, id="7")]:
            with self.subTest(profile=profile), backend([(200, TOKEN), (200, profile)]) as (client, _):
                with self.assertRaisesRegex(ApiError, "invalid account profile"):
                    client.login("qa_user", "password", "user")

    def test_connection_and_timeout_failures(self):
        from urllib.error import URLError
        for error, message in [(URLError("connection refused"), "Cannot reach"), (socket.timeout(), "too long")]:
            with self.subTest(error=error), patch("frontend.api_client.urlopen", side_effect=error):
                with self.assertRaisesRegex(ApiError, message):
                    ApiClient().login("qa_user", "password", "user")

    def test_url_configuration(self):
        with patch.dict("os.environ", {"KITCHEN_QUEST_API_URL": "http://127.0.0.1:8123/"}):
            self.assertEqual(ApiClient().base_url, "http://127.0.0.1:8123")
        for url in ["file:///tmp/backend", "backend", "http://example.test?token=x", "http://user:password@example.test"]:
            with self.subTest(url=url), self.assertRaises(ApiError):
                ApiClient(url)


if __name__ == "__main__":
    unittest.main()
