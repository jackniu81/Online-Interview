"""Application settings loaded from environment variables / repo-root .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = admin/app/config.py -> parents[2]
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://interview:interview@localhost:5433/interview"
    admin_password: str = "change-me"
    jwt_secret: str = "change-me-jwt-secret"
    link_encryption_key: str = ""

    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"

    frontend_url: str = "http://localhost:5173"

    # local storage for screen recordings (relative to admin/ dir)
    recordings_dir: str = "data/recordings"


@lru_cache
def get_settings() -> Settings:
    return Settings()
