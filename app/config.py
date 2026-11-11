from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables / `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Japan Cybersecurity Jobs"
    database_url: str = "sqlite:///./data/jobs.db"
    host: str = "127.0.0.1"
    port: int = 8000
    default_window_days: int = 3
    log_level: str = "INFO"


settings = Settings()
