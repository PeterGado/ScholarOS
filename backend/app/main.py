from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from slowapi.middleware import SlowAPIMiddleware

from app.ai.providers.factory import create_provider
from app.api.exception_handlers import register_exception_handlers
from app.api.router import api_router
from app.auth.provisioning import sync_configured_user
from app.core.config import get_settings
from app.core.dependencies import get_content_store
from app.core.rate_limit import limiter
from app.database import session as db_session_module
from app.database.session import init_db
from app.workers.executor import WorkItemExecutorLoop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Schema bootstrap for the current SQLite/dev-test scope (ADR-004); create_all is
    # idempotent, so this is safe on every startup. Superseded by real migrations (Alembic)
    # before any PostgreSQL cutover - not needed for this stage (Stage 3's open item).
    init_db()

    # Single-user credential provisioning (ADR-010 Decision item 1; Stage 4). A no-op if
    # AUTH_USERNAME/AUTH_PASSWORD_HASH aren't configured yet - acceptable before Stage 6 makes
    # authentication mandatory. Uses its own session, not a request-scoped one. Looked up via
    # the module (not `from ... import SessionLocal`) so tests that monkeypatch
    # app.database.session.SessionLocal are honored here too - the same reason init_db()
    # resolves its default engine at call time rather than via a stale bound default.
    settings = get_settings()
    db = db_session_module.SessionLocal()
    try:
        sync_configured_user(db, username=settings.auth_username, password_hash=settings.auth_password_hash)
    finally:
        db.close()

    # Work Item executor (ADR-006; Stage 6). A no-op if AI_API_KEY isn't configured yet -
    # mirrors sync_configured_user's own "optional, no-op until configured" pattern, so every
    # test and deployment that doesn't need the Knowledge Processing Pipeline is unaffected.
    # session_factory is a closure over the module, not a bound SessionLocal reference, for
    # the same stale-binding reason init_db()/sync_configured_user's db access already avoid it.
    executor_loop: WorkItemExecutorLoop | None = None
    if settings.ai_api_key:
        text_provider = create_provider(settings)
        # get_content_store() (not a hardcoded FilesystemStorage) - a real bug found live
        # during the S3-compatible storage rollout (2026-09-18): the executor previously always
        # wrote/read against local disk regardless of STORAGE_BACKEND, while the upload route
        # (already wired through this same factory) correctly used S3 - a document uploaded
        # under STORAGE_BACKEND=s3 would upload fine, then fail processing with "stored content
        # not found" the moment the executor tried to read it back from the wrong backend.
        storage = get_content_store()
        executor_loop = WorkItemExecutorLoop(
            lambda: db_session_module.SessionLocal(),
            text_provider,
            text_provider,  # every concrete provider satisfies both provider Protocols
            settings.ai_embedding_model,
            storage,
        )
        executor_loop.start()

    yield

    if executor_loop is not None:
        await executor_loop.stop()


# Sentry (2026-09-21): a no-op if SENTRY_DSN isn't configured - init() is simply never called,
# and sentry_sdk.capture_exception (app.api.exception_handlers._handle_unexpected_error) is
# always a safe no-op before init(), by the SDK's own design. traces_sample_rate=0.0: error
# tracking only, no performance tracing - not what was asked for, and a separate cost/quota
# concern. Every exception in this app is already caught by our own registered handlers before
# Starlette would ever see one as truly "unhandled" - the integrations below add request context
# to captured events, they don't provide auto-capture on their own; the explicit
# capture_exception call in _handle_unexpected_error is what actually reports anything.
if get_settings().sentry_dsn:
    sentry_sdk.init(
        dsn=get_settings().sentry_dsn,
        environment=get_settings().environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.0,
    )

app = FastAPI(title="ScholarOS Backend", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=False,  # bearer tokens (Authorization header), never cookies - ADR-010
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
register_exception_handlers(app)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """2026-09-21 production security pass: FastAPI adds none of these by default. This is a
    pure JSON API - it never intends to serve active content or be framed by anything - so the
    CSP is deliberately the strictest possible ('default-src none') rather than an allowlist,
    which only a real HTML-serving app (the separate Vercel frontend) would need.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response
