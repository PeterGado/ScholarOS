from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def normalize_database_url(database_url: str) -> str:
    """A bare "postgresql://" resolves to SQLAlchemy's default driver, psycopg2 - not installed
    here (only psycopg/v3 is, per pyproject.toml). Normalized so DATABASE_URL can be written
    the plain, standard way (what every Postgres host's own connection-string docs show)
    without every caller needing to remember this project's specific driver choice. Used by
    both `build_engine` (real app runtime) and `alembic/env.py` (migrations) - the two must
    never resolve a given DATABASE_URL to different drivers.
    """
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def build_engine(database_url: str) -> Engine:
    """Create an engine for the given URL. SQLite gets thread-sharing and foreign-key
    enforcement (off by default in SQLite); other dialects (PostgreSQL, per ADR-004's
    migration path) get their normal driver defaults.
    """
    database_url = normalize_database_url(database_url)
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
    from app.ai.models import AiUsageRecord  # noqa: F401
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
        MemoryProvenanceLink,
        MemoryRecord,
        ProfileCharacteristic,
        ProfileCharacteristicSource,
        WritingProfile,
    )
    from app.workers.models import WorkItem  # noqa: F401

    Base.metadata.create_all(bind=target_engine if target_engine is not None else engine)

    # ADR-005 Decision 1's lexical branch: on SQLite, an FTS5 virtual table, not representable
    # as an ORM model (no Python-side row class - the real Knowledge Chunk row is the source of
    # truth, this is a derived index kept in sync on write, see SqlAlchemyKnowledgeChunkRepository.
    # add). `rowid` is explicitly set to `chunk_id` on insert (not FTS5's own auto-rowid) so a
    # search hit maps straight back to its Knowledge Chunk with no join table. IF NOT EXISTS
    # mirrors create_all's own idempotency. On Postgres, a generated `search_vector` tsvector
    # column + GIN index (maintained automatically by Postgres itself on every write - no
    # application-side sync needed, unlike the FTS5 branch). This mirrors, and is deliberately
    # kept parallel to (not DRY against), the equivalent DDL in the baseline Alembic migration -
    # this path exists for ephemeral test/dev databases that bootstrap via create_all() rather
    # than a real migration; see that migration's own comment for why both exist.
    active_engine = target_engine if target_engine is not None else engine
    if active_engine.dialect.name == "sqlite":
        with active_engine.connect() as connection:
            connection.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunk_fts "
                    "USING fts5(content, agent_id UNINDEXED)"
                )
            )
            connection.commit()
    elif active_engine.dialect.name == "postgresql":
        with active_engine.connect() as connection:
            has_column = connection.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'knowledge_chunks' AND column_name = 'search_vector'"
                )
            ).first()
            if has_column is None:
                connection.execute(
                    text(
                        "ALTER TABLE knowledge_chunks ADD COLUMN search_vector tsvector "
                        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
                    )
                )
                connection.execute(
                    text("CREATE INDEX knowledge_chunks_search_vector_idx ON knowledge_chunks USING GIN (search_vector)")
                )
            connection.commit()
