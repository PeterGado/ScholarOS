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

        is_memory_sqlite = ":memory:" in database_url

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # noqa: ANN001, ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # SQLite allows only one writer at a time; without a busy timeout, a writer that
            # finds the database locked (e.g. the background Work Item executor committing at
            # the same moment as an incoming HTTP request's own commit - a real, expected
            # occurrence once transactions are correctly demarcated, see the explicit-BEGIN fix
            # below) fails immediately with "database is locked" instead of waiting briefly for
            # the other writer to finish. Found via the Frontend milestone's real manual
            # workflow the moment the explicit-BEGIN fix made this app's first genuine
            # concurrent-writer scenario possible; 30s comfortably covers a single Work Item
            # commit, which is never AI-call-bound (the AI call happens before persistence
            # begins - see ExtractDocumentKnowledgeUseCase's own docstring).
            cursor.execute("PRAGMA busy_timeout=30000")
            if not is_memory_sqlite:
                # busy_timeout alone was not enough: every authenticated request also writes
                # (AuthService.verify_token's session-activity "touch", committed on every
                # request - app/auth/service.py), so two genuinely concurrent authenticated
                # requests (the frontend routinely fires several in parallel, e.g.
                # DraftDetailPage's two simultaneous queries) are two real, concurrent writers.
                # In SQLite's default rollback-journal mode that can surface as "database is
                # locked" (SQLITE_LOCKED) even with a busy_timeout set - that PRAGMA only backs
                # off SQLITE_BUSY, a different condition, so it does not reliably help here.
                # WAL mode is the standard, documented fix for exactly this "many small
                # concurrent writers" pattern: readers never block writers and vice versa, and
                # writer-vs-writer contention becomes genuine SQLITE_BUSY, which busy_timeout
                # does correctly resolve. Skipped for `:memory:` databases (tests only), which
                # cannot use WAL at all (it requires a real file for the separate -wal file).
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        # pysqlite's own implicit transaction handling is well-documented to interfere with
        # SQLAlchemy's transaction demarcation (see SQLAlchemy's SQLite dialect docs, "Serializable
        # isolation / Savepoints / Transactional DDL"): left at its default, a pooled connection
        # that previously only read can keep an old implicit transaction open indefinitely, so a
        # later query on that same connection can miss a write another connection already
        # committed - found via the Frontend milestone's real manual workflow (real AI processing
        # completing and committing, immediately followed by a real search on a different pooled
        # connection returning stale/empty results; never surfaced by any fake-provider automated
        # test, which never has enough real wall-clock time between the write and the read for two
        # different pooled connections to be involved). Disabling pysqlite's own isolation_level
        # and issuing BEGIN explicitly on SQLAlchemy's own "begin" hook makes every new
        # SQLAlchemy-level transaction start a fresh read view, eliminating the staleness.
        @event.listens_for(engine, "connect")
        def _disable_pysqlite_implicit_transactions(dbapi_connection, connection_record):  # noqa: ANN001, ARG001
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def _emit_explicit_sqlite_begin(conn):  # noqa: ANN001
            conn.exec_driver_sql("BEGIN")

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
    from app.auth.models import AuthSession  # noqa: F401
    from app.database.base import Base
    from app.database.shared_models import User  # noqa: F401
    from app.modules.agent.infrastructure.models import Agent  # noqa: F401
    from app.modules.document.infrastructure.models import ResearchDocument  # noqa: F401
    from app.modules.knowledge.infrastructure.models import (  # noqa: F401
        ChunkEvidenceLink,
        KnowledgeChunk,
        KnowledgeElement,
    )
    from app.modules.knowledge.infrastructure.vector_models import KnowledgeChunkEmbedding  # noqa: F401
    from app.modules.project.infrastructure.models import Project  # noqa: F401
    from app.modules.writing.infrastructure.models import (  # noqa: F401
        Draft,
        DraftEvidenceLink,
        DraftVersion,
        MemoryProvenanceLink,
        MemoryRecord,
        ProfileCharacteristic,
        ProfileCharacteristicSource,
        Review,
        ReviewDecision,
        WritingProfile,
    )
    from app.workers.models import WorkItem  # noqa: F401

    Base.metadata.create_all(bind=target_engine if target_engine is not None else engine)
