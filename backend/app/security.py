import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Graceful password hashing fallback
try:
    from pwdlib import PasswordHash
    _pwd_hash = PasswordHash.recommended()

    def hash_password(password: str) -> str:
        return _pwd_hash.hash(password)

    def verify_password(password: str, hashed: str) -> bool:
        if hashed.startswith("pbkdf2$"):
            parts = hashed.split("$")
            if len(parts) == 4:
                _, iterations, salt_b64, hash_b64 = parts
                test_hash = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    base64.b64decode(salt_b64),
                    int(iterations),
                )
                return hmac.compare_digest(base64.b64decode(hash_b64), test_hash)
        try:
            return _pwd_hash.verify(password, hashed)
        except Exception:
            return False

except ImportError:
    def hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        iterations = 100000
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"pbkdf2${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(key).decode()}"

    def verify_password(password: str, hashed: str) -> bool:
        if hashed.startswith("pbkdf2$"):
            parts = hashed.split("$")
            if len(parts) == 4:
                _, iterations, salt_b64, hash_b64 = parts
                test_hash = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    base64.b64decode(salt_b64),
                    int(iterations),
                )
                return hmac.compare_digest(base64.b64decode(hash_b64), test_hash)
        return False


# Graceful JWT fallback
try:
    import jwt

    def _jwt_encode(payload: dict[str, Any], key: str, algorithm: str) -> str:
        return jwt.encode(payload, key, algorithm=algorithm)

    def _jwt_decode(token: str, key: str, algorithms: list[str]) -> dict[str, Any]:
        return jwt.decode(token, key, algorithms=algorithms)

    JWTError = jwt.InvalidTokenError

except ImportError:
    class JWTError(Exception):
        pass

    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    def _b64url_decode(data_str: str) -> bytes:
        pad = len(data_str) % 4
        if pad:
            data_str += "=" * (4 - pad)
        return base64.urlsafe_b64decode(data_str.encode("ascii"))

    def _jwt_encode(payload: dict[str, Any], key: str, algorithm: str) -> str:
        header = {"typ": "JWT", "alg": algorithm}
        h_str = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p_str = _b64url_encode(json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"))
        signing_input = f"{h_str}.{p_str}".encode("ascii")
        sig = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        s_str = _b64url_encode(sig)
        return f"{h_str}.{p_str}.{s_str}"

    def _jwt_decode(token: str, key: str, algorithms: list[str]) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise JWTError("Invalid token format")
        h_str, p_str, s_str = parts
        try:
            sig = _b64url_decode(s_str)
            signing_input = f"{h_str}.{p_str}".encode("ascii")
            expected_sig = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
            if not hmac.compare_digest(sig, expected_sig):
                raise JWTError("Signature verification failed")
            payload = json.loads(_b64url_decode(p_str).decode("utf-8"))
            exp = payload.get("exp")
            if exp is not None and time.time() > float(exp):
                raise JWTError("Token expired")
            return payload
        except Exception as e:
            raise JWTError(str(e)) from e

import time


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": int(expire.timestamp())}
    return _jwt_encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = _jwt_decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_error
    user = db.get(models.User, user_id)
    if user is None:
        raise credentials_error
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.Role.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
