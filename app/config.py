from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://eve:eve@localhost:5432/eve"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    webhook_secret: str = "dev-webhook-secret-change-me"

    retry_loop_enabled: bool = True
    retry_interval_seconds: float = 5.0
    retry_max_attempts: int = 5
    retry_base_backoff_seconds: float = 2.0

    simulated_provider_delay_seconds: float = 1.5

    rate_limit_auth: int = 10
    rate_limit_payments: int = 30
    rate_limit_window_seconds: int = 60

    seed_admin_email: str = "admin@eve.local"
    seed_admin_password: str = "admin12345"


settings = Settings()
