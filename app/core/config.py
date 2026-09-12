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

    memory_cleanup_enabled: bool = True
    memory_cleanup_interval_seconds: int = 3600
    max_photo_dimension: int = 4096
    max_photo_size_mb: int = 15
    max_photos_per_event: int = 500
    uploads_enabled: bool = True
    uploads_per_minute: int = 10
    logins_per_minute: int = 10
    messages_per_minute: int = 20
    rsvps_per_minute: int = 20
    signed_url_expiry_seconds: int = 300

    frontend_origins: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000"

    admin_email: str = "admin@example.com"
    admin_password: str = "change-me-admin"

    seed_event_name: str = "Örnek Etkinlik"
    seed_event_token: str | None = None

    public_base_url: str | None = None
    email_backend: str = "console"
    email_from: str = "Luma <noreply@localhost>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    environment: str = "development"
    sentry_dsn: str | None = None
    rate_limit_backend: str = "memory"

    def validate_production(self) -> None:
        if self.environment != "production": return
        errors=[]
        if self.secret_key in {"change-me-in-production", "change-me-use-openssl-rand-hex-32"} or len(self.secret_key)<32: errors.append("SECRET_KEY en az 32 karakter olmalı")
        if not self.database_url.startswith("postgresql"): errors.append("DATABASE_URL PostgreSQL olmalı")
        if self.storage_backend != "s3" or not all((self.storage_endpoint,self.storage_bucket,self.storage_access_key_id,self.storage_secret_access_key)): errors.append("özel S3/R2 ayarları eksik")
        if not self.public_base_url or not self.public_base_url.startswith("https://"): errors.append("PUBLIC_BASE_URL HTTPS olmalı")
        if any(not origin.startswith("https://") for origin in self.cors_origins): errors.append("FRONTEND_ORIGINS yalnızca HTTPS olmalı")
        if self.rate_limit_backend != "database": errors.append("RATE_LIMIT_BACKEND=database olmalı")
        if self.email_backend == "smtp" and not self.smtp_host: errors.append("SMTP_HOST eksik")
        if errors: raise RuntimeError("Üretim yapılandırması geçersiz: " + "; ".join(errors))

    serve_frontend: bool = True
    frontend_path: Path = ROOT.parent / "luma-frontend"

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
