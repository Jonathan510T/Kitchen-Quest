"""HTTP authentication client for the existing FastAPI backend."""

from dataclasses import dataclass, field
import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


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

    def _request(self, method, path, *, body=None, content_type=None, token=None):
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            messages = {
                401: "Incorrect username or password." if path.endswith("/login") else "Your session has expired. Please sign in again.",
                403: "This account does not have permission for this action.",
                409: "That username is already taken. Choose another username.",
                422: "Check your entries. Usernames must be 3-50 characters and passwords 8-128 characters.",
            }
            with exc:
                message = messages.get(exc.code, f"The server could not complete the request (HTTP {exc.code}). Please try again.")
            raise ApiError(message) from None
        except (TimeoutError, socket.timeout):
            raise ApiError("The server took too long to respond. Please try again.") from None
        except (URLError, OSError):
            raise ApiError("Cannot reach the Kitchen Quest server. Check that the backend is running and the server address is correct.") from None
        except (ValueError, UnicodeError):
            raise ApiError("The server returned an unexpected response. Please try again.") from None
        if not isinstance(result, dict):
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
        return Session(profile, token)

    def register(self, username: str, password: str) -> Profile:
        return self._profile(self._request(
            "POST", "/api/auth/register",
            body=json.dumps({"username": username, "password": password}).encode("utf-8"),
            content_type="application/json",
        ))
