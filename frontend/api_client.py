"""HTTP client for Kitchen Quest backend with automatic offline fallback."""

from dataclasses import dataclass, field
import json
import os
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

try:
    from .local_service import LocalGameService
except ImportError:
    from local_service import LocalGameService


class ApiError(Exception):
    """A user-facing authentication or connection error."""


@dataclass(frozen=True)
class Profile:
    id: int
    username: str
    role: str


@dataclass(frozen=True)
class Session:
    profile: Profile
    access_token: str = field(repr=False)


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10):
        self.base_url = (
            base_url or os.environ.get("KITCHEN_QUEST_API_URL", "http://localhost:8000")
        ).strip().rstrip("/")
        parts = urlsplit(self.base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment or parts.username or parts.password:
            raise ApiError("Set KITCHEN_QUEST_API_URL to a valid HTTP or HTTPS server URL.")
        self.timeout = timeout
        self.local_service = LocalGameService()

    def _request(self, method, path, *, body=None, content_type=None, token=None, allow_empty=False) -> Any:
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
            if allow_empty and not raw:
                return {}
            result = json.loads(raw)
        except HTTPError as exc:
            messages = {
                401: "Incorrect username or password." if path.endswith("/login") else "Your session has expired. Please sign in again.",
                403: "This account does not have permission for this action.",
                409: "That username is already taken. Choose another username.",
                422: "Check your entries. Usernames must be 3-50 characters and passwords 8-128 characters.",
            }
            if path.startswith("/api/challenges"):
                messages.update({
                    404: "That challenge was not found.",
                    409: "A challenge with this title already exists.",
                    422: "The server rejected the challenge data. Check the fields and try again.",
                })
            with exc:
                message = messages.get(exc.code, f"The server could not complete the request (HTTP {exc.code}). Please try again.")
            raise ApiError(message) from None
        except (TimeoutError, socket.timeout):
            raise ApiError("The server took too long to respond. Please try again.") from None
        except (URLError, OSError):
            raise ApiError("Cannot reach the Kitchen Quest server. Check that the backend is running and the server address is correct.") from None
        except (ValueError, UnicodeError):
            raise ApiError("The server returned an unexpected response. Please try again.") from None
        if not isinstance(result, (dict, list)):
            raise ApiError("The server returned an unexpected response. Please try again.")
        return result

    @staticmethod
    def _profile(data):
        if (
            type(data.get("id")) is not int
            or not isinstance(data.get("username"), str)
            or not data["username"]
            or data.get("role") not in ("user", "admin")
        ):
            raise ApiError("The server returned an invalid account profile.")
        return Profile(data["id"], data["username"], data["role"])

    def login(self, username: str, password: str, role: str) -> Session:
        data = self._request(
            "POST", "/api/auth/login",
            body=urlencode({"username": username, "password": password}).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
        )
        token = data.get("access_token")
        if not isinstance(token, str) or not token or data.get("token_type", "").lower() != "bearer":
            raise ApiError("The server returned an invalid sign-in response.")
        profile = self._profile(self._request("GET", "/api/auth/me", token=token))
        if profile.role != role:
            if role == "admin":
                raise ApiError("This account does not have admin access. Use the User tab.")
            raise ApiError("Administrators must sign in from the Admin tab.")
        self.local_service.user_id = profile.id
        return Session(profile, token)

    def register(self, username: str, password: str) -> Profile:
        return self._profile(self._request(
            "POST", "/api/auth/register",
            body=json.dumps({"username": username, "password": password}).encode("utf-8"),
            content_type="application/json",
        ))

    # Signed-in requests (a token is passed) always go to the server and raise ApiError
    # on failure. They never fall back to the in-memory LocalGameService, because that
    # would hide a failed save and show progress that is lost on the next sign-in.
    # Only calls made without a token (offline/guest play) use the local service.

    def get_challenges(self, token: str | None = None) -> list[dict[str, Any]]:
        """Fetch cooking challenges (with this user's best stars) from the backend."""
        if token:
            res = self._request("GET", "/api/challenges", token=token)
            if not isinstance(res, list):
                raise ApiError("The server returned an unexpected response. Please try again.")
            return res
        return self.local_service.get_challenges()

    def get_challenge(self, challenge_id: int, token: str | None = None) -> dict[str, Any] | None:
        """Fetch challenge details."""
        if token:
            res = self._request("GET", f"/api/challenges/{challenge_id}", token=token)
            if not isinstance(res, dict):
                raise ApiError("The server returned an unexpected response. Please try again.")
            return res
        return self.local_service.get_challenge(challenge_id)

    def create_challenge(self, data: dict[str, Any], token: str) -> dict[str, Any]:
        """Admin only: create a challenge."""
        return self._request(
            "POST", "/api/challenges",
            body=json.dumps(data).encode("utf-8"),
            content_type="application/json",
            token=token,
        )

    def update_challenge(self, challenge_id: int, data: dict[str, Any], token: str) -> dict[str, Any]:
        """Admin only: update the given fields of a challenge."""
        return self._request(
            "PUT", f"/api/challenges/{challenge_id}",
            body=json.dumps(data).encode("utf-8"),
            content_type="application/json",
            token=token,
        )

    def delete_challenge(self, challenge_id: int, token: str) -> None:
        """Admin only: delete a challenge and all attempts recorded for it."""
        self._request("DELETE", f"/api/challenges/{challenge_id}", token=token, allow_empty=True)

    def submit_attempt(
        self,
        challenge_id: int,
        actions_data: list[dict[str, Any]],
        time_taken_seconds: float,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Submit a completed attempt. The server scores it and saves XP, level and best stars."""
        if token:
            payload = {
                "actions": actions_data,
                "time_taken_seconds": round(time_taken_seconds, 2),
            }
            res = self._request(
                "POST",
                f"/api/challenges/{challenge_id}/attempts",
                body=json.dumps(payload).encode("utf-8"),
                content_type="application/json",
                token=token,
            )
            if not isinstance(res, dict):
                raise ApiError("The server returned an unexpected response. Please try again.")
            return res
        return self.local_service.submit_attempt(challenge_id, actions_data, time_taken_seconds)

    def get_progress(self, token: str | None = None) -> dict[str, Any]:
        """Fetch the user's saved level, XP and completed challenges."""
        if token:
            res = self._request("GET", "/api/progress", token=token)
            if not isinstance(res, dict):
                raise ApiError("The server returned an unexpected response. Please try again.")
            return res
        return self.local_service.get_progress()