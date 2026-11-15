from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent  # the backend folder


def _read_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip().lower()] = v.strip().strip("'\"")
    except Exception:
        pass
    return values


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./kitchen_quest.db")
        secret_key: str = os.environ.get("SECRET_KEY", "kitchen-quest-secret-key-development")
        algorithm: str = "HS256"
        access_token_expire_minutes: int = 60

        model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    settings = Settings()
except ImportError:
    from pydantic import BaseModel

    env_vals = _read_env_file(BASE_DIR / ".env")

    class Settings(BaseModel):
        database_url: str = os.environ.get(
            "DATABASE_URL",
            env_vals.get("database_url", "sqlite:///./kitchen_quest.db"),
        )
        secret_key: str = os.environ.get(
            "SECRET_KEY",
            env_vals.get("secret_key", "kitchen-quest-secret-key-development"),
        )
        algorithm: str = os.environ.get(
            "ALGORITHM", env_vals.get("algorithm", "HS256")
        )
        access_token_expire_minutes: int = int(
            os.environ.get(
                "ACCESS_TOKEN_EXPIRE_MINUTES",
                env_vals.get("access_token_expire_minutes", 60),
            )
        )

    settings = Settings()
