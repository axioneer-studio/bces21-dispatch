from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "BCES Dispatch API"
    app_version: str = "0.1.0"
    debug: bool = False

    app_timezone: str = "Europe/Paris"

    database_url: str = Field(
        default="sqlite+aiosqlite:///./BCES.db",
        description="SQLAlchemy async URL",
    )

    frontend_base_url: str = "http://localhost:3000"

    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = "http://localhost:8000/api/auth/discord/callback"
    discord_scopes: str = "identify"

    session_secret: str = "change-me-in-production"
    session_cookie_name: str = "bces_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 14
    session_cookie_domain: str | None = None
    session_cookie_secure: bool = False

    profile_deadline_seconds: int = 60 * 60 * 24

    cleanup_interval_seconds: int = 60 * 30

    # --- Stockage S3 (compatible) pour les credentials Google Service Account ---
    s3_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # --- Chiffrement des credentials Google Service Account ---
    google_sa_encryption_key: str = ""

    cors_allow_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def discord_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.discord_scopes.split(",") if scope.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()