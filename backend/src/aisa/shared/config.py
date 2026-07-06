from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration. 12-factor: everything from AISA_* env vars."""

    model_config = SettingsConfigDict(env_prefix="AISA_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://aisa:aisa@localhost:5432/aisa"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"
