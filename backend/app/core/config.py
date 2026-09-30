from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./scholaros.db"
    # Row-Level Security (2026-09-21): Postgres-only, unused until the app is actually cut over
    # to a restricted, non-owner DB role (see the RLS rollout plan) - falls back to
    # `database_url` when unset, so SQLite dev/test and the pre-cutover deploy steps are
    # completely unaffected. `database_url` itself keeps being used for Alembic migrations
    # (alembic/env.py reads it directly, unchanged) - the owner role always runs DDL, the app
    # role never gets DDL rights even if misconfigured.
    app_database_url: str | None = None
    storage_root: str = "./data/documents"
    # 2026-09-19 production security pass: no upload size limit existed anywhere before this -
    # every upload route read an entire file into memory unconditionally regardless of size.
    # 20MB comfortably covers real research documents/PDFs/docx writing samples at this
    # project's scale without inviting a trivial memory/storage-cost abuse vector.
    max_upload_size_bytes: int = 20 * 1024 * 1024
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
    # Google Sign-In (2026-09-20): the OAuth Client ID from Google Cloud Console, used to verify
    # the `aud` claim of every ID token. Not a secret (it's also embedded in the frontend
    # bundle as VITE_GOOGLE_CLIENT_ID) - unset means the feature is off (GoogleSignInNotConfiguredError).
    google_oauth_client_id: str | None = None
    # AI Provider Abstraction (ADR-002; Backend_Slice2_Implementation_Plan.md §4, corrected
    # Stage 9): the first concrete provider is Google's Gemini via the native `google-genai`
    # SDK ("google_genai"), selected by configuration - never by business logic. The original
    # OpenAI-compatible HTTP shim ("openai_compatible") remains available as an alternative,
    # selectable the same way. ai_api_key is a secret, never logged or returned in any API
    # response. ai_base_url is only read by the "openai_compatible" provider.
    ai_provider: str = "google_genai"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str | None = None
    # Multi-key failover (2026-09-30, for personal use across multiple free-tier accounts,
    # each with its own separate daily quota): when set (a JSON array in the env var, same
    # parsing as cors_allowed_origins), the provider factory wraps one provider instance per
    # key in FailoverProvider instead of constructing a single provider from ai_api_key -
    # ai_api_key is simply unused when this is set. Left empty by default so every existing
    # single-key deployment is completely unaffected.
    ai_api_keys: list[str] = []
    # Per-key request pacing (2026-09-30, added alongside multi-key failover): each key in
    # ai_api_keys gets its own RateLimitedProvider capping it to this many calls per rolling
    # 60s window, proactively sleeping instead of relying on a real 429 + FailoverProvider's
    # retry-next-key to absorb bursts - cheaper (no wasted round trip) and keeps latency lower
    # under the burst pattern that caused the original rate-limit incident (several provider
    # calls fired in quick succession while processing a document). 10/min is a conservative
    # placeholder below Gemini free tier's documented per-minute caps, not tuned against a
    # confirmed number for the specific model configured below - adjust if it proves too tight
    # or still too loose. Only applied to the multi-key path; the single-key path is unchanged.
    ai_max_calls_per_minute_per_key: int = 10
    ai_model: str = "gemini-3.6-flash"
    ai_embedding_model: str = "gemini-embedding-001"
    # 2026-09-21: no per-call output bound existed anywhere - a single generate() call could run
    # to whatever the provider's own model default allows, uncapped by ScholarOS. Bounds runaway
    # generation cost per call, complementing the AI usage cap above (which bounds cumulative
    # cost, not any one call). 4096 tokens comfortably covers a full thesis-chapter-section reply
    # (the longest realistic single output this app produces) without being open-ended.
    ai_max_output_tokens: int | None = 4096
    # AI usage cap (2026-09-21 security pass, ADR-011's deferred per-user quota item): rate
    # limiting bounds the *rate* of AI-triggering requests, not the *total* - a sustained user
    # within the rate limit could still drive unlimited real Gemini cost. Defaults ON (unlike
    # registration_invite_code/google_oauth_client_id, which default off because they need
    # external setup first) - this needs none, so it closes the gap the moment this deploys.
    # Raised from the original 500,000 to 2,000,000 (2026-09-30) once multi-key failover made
    # the original "bound real Gemini billing cost" reasoning mostly moot (free-tier keys, no
    # billing enabled) - kept as a generous but finite safety net against a bug/runaway loop
    # rather than disabled outright, since self-service registration (registration_invite_code)
    # is already live even though only the project owner is using it today. Revisit downward -
    # back toward a real per-user fair-share limit across the 9-key pool, not a pure safety net -
    # once friends actually start registering and using it concurrently. Set to null to disable
    # entirely.
    ai_daily_token_cap_per_user: int | None = 2_000_000
    # Frontend milestone (2026-09-16): a browser-based frontend on its own origin (the Vite
    # dev server) cannot reach this API at all without CORS headers - not a design choice,
    # every cross-origin browser request is blocked by default. Defaults cover the Vite dev
    # server's default port on both loopback forms; override via the CORS_ALLOWED_ORIGINS env
    # var (a JSON array of origins, e.g. ["http://localhost:5173"] - pydantic-settings' own
    # default parsing for a list field) for any other deployment origin.
    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Sentry (2026-09-21): unset means the feature is off (sentry_sdk.init is never called, and
    # sentry_sdk.capture_exception is always a safe no-op before init - see app.main and
    # app.api.exception_handlers). Not a secret in the usual sense (a DSN is write-only, it
    # can't be used to read data out of Sentry), but treated like other config here regardless.
    sentry_dsn: str | None = None
    # Work Item queue health check (2026-09-30, added after a production outage where the
    # executor silently stopped making progress for hours with no signal anywhere - Fly's own
    # `/health` check kept passing the whole time, since the web server itself was never the
    # problem). 600s (10 min) is well past the slowest legitimate single item (an AI generation
    # call, seconds; document processing, at most low tens of seconds) - a real item should
    # never sit unresolved this long in normal operation.
    queue_stale_threshold_seconds: int = 600
    # Work Item executor concurrency (2026-09-30, concurrent-load planning): the executor now
    # runs this many OS threads concurrently claiming/processing Work Items, instead of exactly
    # one (see WorkItemExecutorLoop's own docstring for why threads, not asyncio tasks). Raised
    # from 1 to 3 only after claim_next_queued became concurrency-safe (Postgres SKIP LOCKED),
    # a real Postgres test proved concurrent claiming never double-processes an item and that
    # more workers measurably drain the queue faster, and the connection pool below was sized
    # to cover it. 3 is a deliberately conservative starting point, not a measured ceiling - the
    # existing /health/queue check and Sentry are what this deploy is watched against before
    # ever raising it further.
    work_item_worker_count: int = 3
    # Connection pool sizing (2026-09-30, concurrent-load planning): both engines previously
    # relied on SQLAlchemy's own defaults (pool_size=5, max_overflow=10 - up to 15 connections
    # each, ~30 total from one process) - never deliberately chosen. The app connects through
    # Neon's pooled (PgBouncer transaction-mode) endpoint, whose own client-connection ceiling is
    # documented as being far above what this app needs at its target scale (~100-300 concurrent
    # users, a handful of worker threads) regardless of compute size - these values are picked to
    # be comfortably conservative for that scale, not measured against an exact confirmed number
    # (checking the dashboard for compute size alone didn't surface a hard connection-count
    # figure, and hunting further wasn't worth it at this scale - see the RLS incident memory/
    # this session's own discussion for that judgment call). Revisit if the pool is ever
    # genuinely observed to be a bottleneck (connections timing out waiting for the pool, not a
    # symptom this app has seen).
    web_engine_pool_size: int = 10
    web_engine_max_overflow: int = 15
    worker_engine_pool_size: int = 10
    worker_engine_max_overflow: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
