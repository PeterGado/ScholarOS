from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.ai.providers.factory import create_provider
from app.api.exception_handlers import register_exception_handlers
from app.api.router import api_router
from app.auth.provisioning import sync_configured_user
from app.core.config import get_settings
from app.database import session as db_session_module
from app.database.session import init_db
from app.storage.filesystem import FilesystemStorage
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
        storage = FilesystemStorage(settings.storage_root)
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


app = FastAPI(title="ScholarOS Backend", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)
register_exception_handlers(app)
