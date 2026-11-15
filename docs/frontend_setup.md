# Frontend setup and Sprint 1 demo

The `login-ui` branch contains the PySide6 frontend. It now uses the existing
authentication endpoints from `backend-setup`; demo passwords are no longer
accepted locally. The backend must be running separately with its existing
configuration and accounts. This frontend change does not add database tables,
migrations, seed accounts, or backend code.

## Install and run (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:KITCHEN_QUEST_API_URL = "http://localhost:8000"
python frontend/login_ui.py
```

The address defaults to `http://localhost:8000`, so the environment variable is
optional for local development. Set it before launching if the backend runs on
another address. `python -m frontend.login_ui` also works from the repository root.

## What to demonstrate

1. Start the existing backend separately. Its Swagger documentation should be
   available at `http://localhost:8000/docs`. Have an existing normal account and,
   for the Admin tab, an existing admin account ready.
2. Select **User** and sign in with the normal account. The frontend sends
   form-urlencoded credentials to `POST /api/auth/login`, then calls
   `GET /api/auth/me` with the returned bearer token. The welcome window shows
   the username, account ID, and role returned by the backend.
3. Sign out and try an incorrect password. The login page should show an error
   and remain open. Repeat on the Admin tab with the normal account: the frontend
   should require the User tab. An admin account must use the Admin tab.
4. To demonstrate a database update **when database work is authorized and the
   existing backend is ready**, choose **Create an account** on the User tab.
   Enter an unused username (3-50 characters) and password (8-128 characters).
   Registration calls the existing `POST /api/auth/register` endpoint; the
   backend owns persistence. After the confirmation, sign in with that account.
   Have the database owner refresh their existing users-table view to show the
   new ID, normalized username, and `user` role. No database browser or direct
   database access is added to the frontend. Creating an account performs a real
   write; normal login only reads account data and issues a token.
5. Stop the backend and attempt a login. A connection error should appear without
   freezing the page. Network calls time out after 10 seconds per request.

**Remember username** stores only the username for each tab in local Qt settings.
Passwords are cleared after success; tokens remain in memory and are dropped on
sign-out or window close. Sign-out ends the local session; the current backend
does not provide a token-revocation endpoint. Password reset is not implemented
by the backend; its link explains that it is unavailable.

## Checks without a database

```powershell
python -m unittest discover -s frontend/tests -v
```

HTTP tests use a local fake server and check request encoding, bearer tokens,
backend roles, registration, malformed responses, and connection failures.
UI checks use Qt's offscreen mode and a fake client, covering login, registration,
remembered usernames, safe shutdown during a request, and sign-out. UI checks are
skipped if PySide6 is not installed. No tests connect to PostgreSQL or create real
accounts. Real backend/database acceptance testing remains a separate step.
