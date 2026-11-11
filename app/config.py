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

    # HTTP policy
    request_timeout_seconds: float = 20.0
    min_request_interval_seconds: float = 1.0
    max_detail_concurrency: int = 2
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    user_agent: str = "JDashboard/0.1 (personal job dashboard; +http://127.0.0.1:8000)"

    # Per-source switches
    enable_michael_page: bool = True
    enable_japan_dev: bool = True
    enable_tokyo_dev: bool = True
    enable_daijob: bool = True
    enable_robert_half: bool = True


settings = Settings()
