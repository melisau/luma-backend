from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Luma Planner API"
    secret_key: str = "change-me-in-production"
    database_url: str = f"sqlite:///{ROOT / 'planner.db'}"

    storage_backend: str = "local"
    local_storage_path: Path = ROOT / "private_uploads"

    storage_endpoint: str | None = None
    storage_bucket: str | None = None
    storage_access_key_id: str | None = None
    storage_secret_access_key: str | None = None
    storage_region: str = "auto"

    max_photo_size_mb: int = 15
    max_photos_per_event: int = 500
    uploads_enabled: bool = True
    uploads_per_minute: int = 10
    logins_per_minute: int = 10
    messages_per_minute: int = 20
    signed_url_expiry_seconds: int = 300

    frontend_origins: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000"

    admin_email: str = "admin@example.com"
    admin_password: str = "change-me-admin"

    seed_event_name: str = "Melisa & Berk"
    seed_event_token: str | None = None

    public_base_url: str | None = None

    serve_frontend: bool = True
    frontend_path: Path = ROOT.parent / "frontend"

    @property
    def resolved_frontend_path(self) -> Path | None:
        if not self.serve_frontend:
            return None
        path = self.frontend_path.expanduser()
        if path.is_dir() and (path / "index.html").is_file():
            return path.resolve()
        return None

    @property
    def max_photo_size_bytes(self) -> int:
        return self.max_photo_size_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
