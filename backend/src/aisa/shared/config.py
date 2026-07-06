from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration. 12-factor: everything from AISA_* env vars."""

    model_config = SettingsConfigDict(env_prefix="AISA_", env_file=".env", extra="ignore")

    env: str = "dev"
    # Runtime role: aisa_app has no BYPASSRLS, so row-level security applies.
    database_url: str = "postgresql+asyncpg://aisa_app:aisa_app@localhost:5432/aisa"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

    # Auth. The default secret is for local dev only; deployed envs must set it.
    secret_key: str = "dev-secret-do-not-use-in-production"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 30
    verification_token_ttl_hours: int = 48

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    def model_post_init(self, __context: object) -> None:
        if not self.is_dev and self.secret_key == "dev-secret-do-not-use-in-production":
            raise ValueError("AISA_SECRET_KEY must be set outside dev")
