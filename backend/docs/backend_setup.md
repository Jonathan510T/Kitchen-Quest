# Kitchen Quest

Desktop app (PySide6/Qt) with a FastAPI + PostgreSQL backend.

## Backend setup (macOS)

1. Install Postgres 16:
```bash
   brew install postgresql@16
   brew services start postgresql@16
   echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
   source ~/.zshrc
```
2. Create the database user and database:
```bash
   psql postgres
```
```sql
   CREATE USER kq WITH PASSWORD 'devpass';
   CREATE DATABASE kitchenquest OWNER kq;
   \q
```
3. From the repo root, create the venv and install dependencies (Python 3.13):
```bash
   python3.13 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
```
4. Create your env file:
```bash
   cd backend
   cp .env.example .env
   python -c "import secrets; print(secrets.token_hex(32))"
```
   Paste the printed value after `SECRET_KEY=` in `backend/.env`.
5. Create the tables and an admin account (from `backend/`):
```bash
   alembic upgrade head
   python -m app.create_admin
```
6. Run the server (from `backend/`):
```bash
   uvicorn app.main:app --reload --port 8000
```
   API docs: http://localhost:8000/docs

## Roles

- Anyone can register through `POST /api/auth/register` and becomes a normal user (read-only).
- Only admins can create or delete recipes. Admins are created with `python -m app.create_admin`.