from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./scholaros.db"
    storage_root: str = "./data/documents"
    # Object storage backend (ADR-004 §5's content-addressed store, now provider-agnostic):
    # "filesystem" (default, unchanged) or "s3" - any S3-compatible endpoint (MinIO, Cloudflare
    # R2, AWS S3 itself), selected by configuration exactly like the AI provider gateway
    # (ADR-002's own pattern), never by business logic. The s3_* fields are only read when
    # storage_backend is "s3"; storage_root remains what "filesystem" uses.
    storage_backend: str = "filesystem"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    # Authentication Boundary (ADR-010): the one pre-provisioned account, seeded from
    # configuration, never hard-coded. auth_password_hash is a bcrypt hash, never plaintext -
    # see backend/README.md "Authentication Setup" for how to generate one.
    auth_username: str | None = None
    auth_password_hash: str | None = None
    # Self-service registration (ADR-011): additive alongside the one pre-provisioned account
    # above. When set, POST /auth/register requires a matching invite_code - a temporary,
    # config-only gate for a friends-testing phase, removable later (clear this var) without a
    # code change when the project owner is ready for fully public registration.
    registration_invite_code: str | None = None
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
    # Frontend milestone (2026-09-16): a browser-based frontend on its own origin (the Vite
    # dev server) cannot reach this API at all without CORS headers - not a design choice,
    # every cross-origin browser request is blocked by default. Defaults cover the Vite dev
    # server's default port on both loopback forms; override via the CORS_ALLOWED_ORIGINS env
    # var (a JSON array of origins, e.g. ["http://localhost:5173"] - pydantic-settings' own
    # default parsing for a list field) for any other deployment origin.
    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
