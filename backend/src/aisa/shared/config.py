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

    # LLM. provider "gemini" needs a key; "fake" is a deterministic stub for
    # local dev/tests without network or credentials.
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    llm_model_quality: str = "gemini-3.1-flash-lite"
    llm_model_fast: str = "gemini-3.1-flash-lite"
    llm_max_output_tokens: int = 8192
    intake_max_rounds: int = 3

    # Plan limits + cost estimation for metering (doc 03 NFR-4).
    free_monthly_run_quota: int = 50
    pro_monthly_run_quota: int = 1000
    free_run_token_budget: int = 500_000
    pro_run_token_budget: int = 2_000_000
    llm_price_per_1m_tokens: float = 0.30

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    def model_post_init(self, __context: object) -> None:
        if not self.is_dev and self.secret_key == "dev-secret-do-not-use-in-production":
            raise ValueError("AISA_SECRET_KEY must be set outside dev")
