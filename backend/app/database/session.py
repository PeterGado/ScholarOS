from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(database_url: str) -> Engine:
    """Create an engine for the given URL. SQLite gets thread-sharing and foreign-key
    enforcement (off by default in SQLite); other dialects (PostgreSQL, per ADR-004's
    migration path) get their normal driver defaults.
    """
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(database_url, connect_args=connect_args)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # noqa: ANN001, ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


engine = build_engine(get_settings().database_url)
SessionLocal = build_sessionmaker(engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine: Engine | None = None) -> None:
    """Create every table registered on Base.metadata, against `target_engine` or (if not
    given) this module's current `engine` - read at call time, not bound as a stale default
    parameter, so tests can point the app at an isolated database by patching this module's
    `engine`/`SessionLocal` attributes and still have a bare `init_db()` call (e.g. from the
    app's startup lifespan) follow the patch. Imports each module's models first so they are
    registered on the shared metadata before create_all runs - the model registration
    mechanism for this modular-monolith structure (ADR-003).
    """
    from app.database.base import Base
    from app.database.shared_models import User  # noqa: F401
    from app.modules.agent.infrastructure.models import Agent  # noqa: F401
    from app.modules.document.infrastructure.models import ResearchDocument  # noqa: F401
    from app.modules.project.infrastructure.models import Project  # noqa: F401

    Base.metadata.create_all(bind=target_engine if target_engine is not None else engine)
