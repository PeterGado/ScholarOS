from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.router import api_router
from app.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Schema bootstrap for the current SQLite/dev-test scope (ADR-004); create_all is
    # idempotent, so this is safe on every startup. Superseded by real migrations (Alembic)
    # before any PostgreSQL cutover - not needed for this stage (Stage 3's open item).
    init_db()
    yield


app = FastAPI(title="ScholarOS Backend", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)
register_exception_handlers(app)
