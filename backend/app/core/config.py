from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./scholaros.db"
    storage_root: str = "./data/documents"
    # Authentication Boundary (ADR-010): the one pre-provisioned account, seeded from
    # configuration, never hard-coded. auth_password_hash is a bcrypt hash, never plaintext -
    # see backend/README.md "Authentication Setup" for how to generate one.
    auth_username: str | None = None
    auth_password_hash: str | None = None
    # AI Provider Abstraction (ADR-002; Backend_Slice2_Implementation_Plan.md §4, corrected
    # Stage 9): the first concrete provider is Google's Gemini via the native `google-genai`
    # SDK ("google_genai"), selected by configuration - never by business logic. The original
    # OpenAI-compatible HTTP shim ("openai_compatible") remains available as an alternative,
    # selectable the same way. ai_api_key is a secret, never logged or returned in any API
    # response. ai_base_url is only read by the "openai_compatible" provider.
    ai_provider: str = "google_genai"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str | None = None
    ai_model: str = "gemini-3.6-flash"
    ai_embedding_model: str = "gemini-embedding-001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
