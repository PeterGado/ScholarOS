from functools import lru_cache

from pydantic import model_validator
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
    # Global request body-size ceiling (2026-10-10, production-readiness pass): applied to
    # every request by MaxBodySizeMiddleware (app.core.middleware), before CORS/rate
    # limiting/routes run. 25MB is deliberately just above max_upload_size_bytes plus
    # multipart overhead, so the one real route that needs up to 20MB still passes through
    # untouched while a pathologically large body to any other route (which should never see
    # more than a few KB) is rejected before it reaches anything else.
    max_request_body_bytes: int = 25 * 1024 * 1024
    # Data retention (2026-10-10, production-readiness pass): how long purely operational
    # bookkeeping rows survive before DataRetentionJob (app.workers.retention) deletes them.
    # Scoped deliberately narrow - ai_usage_records and rate_limit_counters are billing/abuse
    # ledgers, not content; work_items is transient queue bookkeeping, not an audit trail.
    # Never applies to KnowledgeChunk, MemoryRecord, Message, or any other content table - the
    # AI's actual knowledge and conversation history stay permanent and unbounded.
    data_retention_usage_days: int = 90
    data_retention_work_item_days: int = 30
    data_retention_check_interval_seconds: float = 86400.0
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
    # Gemini model selection (2026-10-06, bumped from "gemini-3.6-flash"): the project owner
    # asked for the strongest available tier for quality, but a real live call against the
    # actual deployed API key confirmed the free tier has ZERO quota for any Pro-tier model
    # ("limit: 0" on a live 429) and gemini-2.5-pro is outright deprecated for new users - Pro
    # access requires billing enabled on a Google Cloud project, which this app's multi-key
    # failover pool (all free-tier accounts) deliberately doesn't have. gemini-3.7-flash is the
    # newest Flash-tier model confirmed to actually work on this key with a real live call
    # (gemini-3.8-flash, the newest release, returned a real 503 "high demand" twice in a row a
    # few minutes apart on this same key - not reliable enough to default to yet; revisit once
    # that settles). If billing is ever enabled on a key in the pool, a Pro-tier model becomes
    # worth retrying for a further quality jump.
    ai_model: str = "gemini-3.7-flash"
    # Generation temperature (2026-10-06): no deliberate value was ever set before this - every
    # call ran at whichever default the provider SDK happens to apply when the field is left
    # unset. 0.4 is deliberately below a typical 1.0 default, chosen to reduce rambling and
    # factual drift on grounded academic writing without going fully deterministic (0.0 reads
    # flat and repetitive across replies in the same conversation). None preserves the old
    # "whatever the provider defaults to" behavior - both GoogleGenAIProvider.generate and
    # OpenAICompatibleProvider.generate already treat max_output_tokens=None as "don't force a
    # value" the same way; temperature follows that same precedent.
    ai_temperature: float | None = 0.4
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
    # Multi-pass reply generation (2026-10-06, draft -> critique -> revise): a chat reply used
    # to be exactly one generate() call; this makes GenerateConversationReplyUseCase run a
    # second model-driven self-critique pass and a third revision pass before anything reaches
    # the user. Defaults to True (an explicit, user-approved trade-off, not a conservative
    # default like registration_invite_code/google_oauth_client_id above) - the project owner
    # has already weighed the ~3x AI-call cost and latency per reply against the quality gain
    # and accepted it at this project's current scale (free-tier keys, no real-time latency
    # SLA). GenerateConversationReplyUseCase's own `enable_multi_pass` constructor parameter is
    # what this actually drives, threaded down through WorkItemExecutorLoop and
    # process_one_work_item (app.workers.executor) - see those for the wiring. Set to False here
    # as a zero-code-change escape hatch if the cost/latency ever becomes a real problem.
    ai_enable_multi_pass_generation: bool = True
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
    # Test-infrastructure-only escape hatch (2026-10-09): lets a specific test process opt out
    # of starting the real executor entirely, for a spec that genuinely doesn't need background
    # processing at all (see e.g. frontend/e2e/upload-limits.spec.ts's own header: "No AI
    # provider call needed - the limit is checked before a document is ever enqueued for
    # processing"). Running the real executor against the throwaway SQLite database such a spec
    # uses races its own foreground requests for SQLite's single writer lock - a known, already
    # -documented failure mode (see app.main's lifespan function, the comment on its
    # get_content_store call, for a related prior incident) - not something a busier Postgres
    # production database ever hits, since Postgres has no such single-writer limitation.
    # Defaults False: production and every other test always start the real executor, unchanged.
    disable_work_item_executor: bool = False
    # Test-infrastructure-only fake AI provider (2026-10-09): selected via ai_provider="fake",
    # same configuration-only selection as every other provider (ADR-002). Lets CI run e2e specs
    # that need *a* provider response (chat replies, document knowledge extraction, style
    # extraction) without a real API key or a live billable call - see app.ai.providers.fake.
    # ai_fake_provider_fail flips it to always raise instead of succeeding, for the one spec
    # that specifically tests the failure/retry path (chat-reply-failure.spec.ts). Never set in
    # production; mirrors disable_work_item_executor's own "test-only, defaults off" pattern.
    ai_fake_provider_fail: bool = False
    # Connection pool sizing (2026-09-30, concurrent-load planning; retightened 2026-10-11 against
    # a real confirmed ceiling). The original 2026-09-30 values (web 10+15, worker 10+10) were
    # picked as "comfortably conservative" against an unknown ceiling - checking Neon's dashboard
    # at the time didn't surface a hard connection-count figure. The project owner has since
    # confirmed the real number directly from Neon: this project's direct/backend connection
    # ceiling is 104 total, 7 reserved for the Neon superuser, 97 usable. At the old settings,
    # worst-case simultaneous overflow across this app's 2 Fly machines was up to 90 connections
    # (45/machine: web 10+15=25, worker 10+10=20) - only ~7 of headroom against 97, before
    # counting the release_command migration connection, any direct psql/dashboard session, or
    # headroom for a future third machine. Retightened to a worst-case ceiling of 60 across 2
    # machines (30/machine: web 10+10=20, worker 5+5=10), leaving ~37 of real headroom. The app
    # connects through Neon's pooled (PgBouncer transaction-mode) endpoint, but the pooler's own
    # backend connections to Postgres are themselves bounded by this same project-wide ceiling -
    # it is not a separate, larger number. Revisit if the pool is ever genuinely observed to be a
    # bottleneck (connections timing out waiting for the pool, not a symptom this app has seen).
    web_engine_pool_size: int = 10
    web_engine_max_overflow: int = 10
    worker_engine_pool_size: int = 5
    worker_engine_max_overflow: int = 5
    # Password reset (2026-10-06): unset means the feature fails closed with EmailSendError
    # rather than silently pretending to send (app.email.resend.send_email's own docstring) -
    # same "missing config fails the same way a bad call would" precedent as ai_api_key/
    # google_oauth_client_id above, not a new pattern.
    resend_api_key: str | None = None
    # Resend's own shared sender address, usable with zero domain setup - switch this to a
    # verified address on your own domain once one exists (see docs/Social_Media_Post's
    # eventual custom-domain work); nothing else about the integration needs to change.
    password_reset_from_address: str = "ScholarOS <onboarding@resend.dev>"
    # How long a reset link stays usable before ConfirmPasswordResetUseCase rejects it as
    # expired (InvalidResetTokenError) - an hour is generous for someone to receive and click
    # an email, short enough that a stale, unused link in an old inbox isn't a standing risk
    # forever.
    password_reset_token_ttl_minutes: int = 60
    # Email verification (2026-10-06, external security review) - longer than the password
    # reset TTL above: an unverified account can still log in and browse, it just can't upload
    # documents or use AI yet, so there's no urgency pressure that calls for a short window the
    # way "someone is mid-account-recovery right now" does for password reset.
    email_verification_token_ttl_minutes: int = 1440
    # The reset link emailed to a user points at the frontend's own confirm-reset page (which
    # then calls this API with the token from the URL), not at this API directly - the backend
    # has no reason to otherwise know where its frontend is deployed, so this must be set
    # explicitly per environment rather than guessed from a request header.
    frontend_base_url: str = "http://localhost:5173"
    # Email-squatting fix (2026-10-10): how long an unverified email claim (password
    # registration or - rare, since Google's own claim is normally authoritative immediately -
    # a Google account somehow left unverified) is held exclusively before
    # app.auth.abandoned_account.reclaim_if_abandoned treats it as abandoned and frees the
    # email for the real owner to register or sign in with. Long enough that a real user who
    # just hasn't checked their inbox yet is never bumped (email_verification_token_ttl_minutes
    # above is only 24h itself, so this is double that), short enough that an attacker's
    # squatted claim is not a practically-permanent block.
    unverified_email_reap_after_hours: int = 48

    @model_validator(mode="after")
    def _forbid_fake_ai_provider_in_production(self) -> "Settings":
        """Production-readiness guard (2026-10-10): nothing previously stopped
        `AI_PROVIDER=fake` (app.ai.providers.fake, test-infrastructure-only - see its own
        docstring) from being accidentally set on a real `ENVIRONMENT=production` deploy,
        which would silently serve every user a canned response instead of a real AI reply.
        Fails fast at settings construction (process startup) rather than letting it run
        and only be noticed from user reports - the same fail-closed instinct as every other
        test-only escape hatch in this file (ai_fake_provider_fail, disable_work_item_executor)
        being scoped tightly, just enforced instead of merely documented.
        """
        if self.environment == "production" and self.ai_provider == "fake":
            raise ValueError(
                "AI_PROVIDER=fake is test-infrastructure-only and must never be set when "
                "ENVIRONMENT=production - it would silently serve canned responses to real users."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
