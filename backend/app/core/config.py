from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://ticketing:ticketing@postgres:5432/ticketing"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8  # 8 hours
    refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"

    # Bootstrap super admin (created on first startup if no users exist)
    first_super_admin_email: str = "admin@company.com"
    first_super_admin_password: str = "ChangeMe123!"

    # CORS
    cors_origins: list[str] = ["http://localhost", "http://localhost:5173", "http://localhost:8080"]

    # File attachments — path on disk (shared reports_data-style volume)
    upload_root: str = "/app/uploads"
    max_attachment_size_bytes: int = 15 * 1024 * 1024  # 15 MB per file

    class Config:
        env_file = ".env"


settings = Settings()
