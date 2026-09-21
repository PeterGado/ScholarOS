from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Registers every module's ORM models on the shared Base.metadata before autogenerate/upgrade
# runs - the exact same import list `app.database.session.init_db` uses, kept in sync
# deliberately (a model missing from one but not the other would silently diverge what
# `create_all` and Alembic each believe the schema is).
from app.ai.models import AiUsageRecord  # noqa: E402,F401
from app.auth.models import AuthSession  # noqa: E402,F401
from app.core.rate_limit_models import RateLimitCounter  # noqa: E402,F401
from app.database.base import Base  # noqa: E402
from app.database.shared_models import User  # noqa: E402,F401
from app.modules.agent.infrastructure.models import Agent  # noqa: E402,F401
from app.modules.document.infrastructure.models import ResearchDocument  # noqa: E402,F401
from app.modules.knowledge.infrastructure.models import (  # noqa: E402,F401
    ChunkEvidenceLink,
    KnowledgeChunk,
    KnowledgeElement,
)
from app.modules.knowledge.infrastructure.vector_models import KnowledgeChunkEmbedding  # noqa: E402,F401
from app.modules.project.infrastructure.models import Project  # noqa: E402,F401
from app.modules.writing.infrastructure.models import (  # noqa: E402,F401
    Conversation,
    MemoryProvenanceLink,
    MemoryRecord,
    Message,
    MessageContextLink,
    ProfileCharacteristic,
    ProfileCharacteristicSource,
    WritingProfile,
)
from app.workers.models import WorkItem  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.database.session import normalize_database_url  # noqa: E402

target_metadata = Base.metadata

# The app's own Settings (DATABASE_URL env var / .env) is the single source of truth for the
# connection string - alembic.ini's own sqlalchemy.url is left as a placeholder (see
# alembic.ini's own comment) so a real migration never runs against the wrong database just
# because someone forgot to update two config files in step. Normalized the same way
# `build_engine` normalizes it for the real app runtime - Alembic and the app must never
# resolve the same DATABASE_URL to two different drivers.
#
# `%` is escaped to `%%` before handing the URL to configparser (what `set_main_option`
# stores into) - configparser's default interpolation treats a bare `%` as the start of a
# `%(name)s` reference and raises on anything else, a real failure found live against a
# genuine Postgres password containing a URL-percent-encoded character (`@` -> `%40`).
_database_url = normalize_database_url(get_settings().database_url)
config.set_main_option("sqlalchemy.url", _database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
