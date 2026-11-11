"""Guards the one failure the rest of the suite structurally cannot see.

Every other backend test builds its database with `init_db()` (`Base.metadata.create_all()`),
which materialises the *current* models. That makes those tests correct and fast, and it also
means they can never notice that the Alembic chain and the models have drifted apart - a
migration was edited without its model, or a model gained a column with no migration. Production
does not use `create_all()` at all: it runs `alembic upgrade head` (fly.toml's release_command),
so a drift that every test passes over becomes a startup crash on deploy.

The two specific shapes this catches, both of which have really happened here:

  * models ahead of migrations - a column added to a model with no revision adding it, so a
    migrated database is missing it (2026-11-06: `users.email`, `users.google_subject`,
    `users.email_verified`, `research_documents.publication_year`/`doi`/`doi_verification_status`
    - present in every test database, absent from the local dev database that bootstrapped
    before those revisions existed).
  * migrations ahead of models - a revision adding a table/column no model describes, which
    `alembic upgrade head` creates but the app never uses.

Run in a subprocess deliberately: it exercises exactly the command a developer and the
deploy pipeline run, and keeps Alembic's own logging configuration (env.py calls `fileConfig`)
out of the test process, where it would otherwise reconfigure pytest's loggers.
"""

import os
import subprocess
import sys
from pathlib import Path

from app.database.session import build_engine, find_schema_drift

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _run_migrations(database_url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"


def test_migrations_produce_the_schema_the_models_describe(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migrated.db'}"

    _run_migrations(database_url)

    engine = build_engine(database_url)
    try:
        assert find_schema_drift(engine) == {}
    finally:
        engine.dispose()


def test_migrations_are_idempotent_against_a_database_that_already_has_the_schema(tmp_path):
    """`alembic upgrade head` must be able to adopt a database that `create_all()` built.

    This is the recovery path a developer in the 2026-11-06 situation is pointed at by the
    startup error, so it has to work rather than abort with "table ... already exists": the
    database already has every table the chain would create, but none of the columns later
    revisions add. Building that state with `init_db()` first, then migrating, reproduces it.
    """
    db_path = tmp_path / "bootstrapped.db"
    database_url = f"sqlite:///{db_path}"

    # create_all() state: every current table, but no alembic_version row.
    from app.database.session import init_db

    engine = build_engine(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()

    _run_migrations(database_url)

    engine = build_engine(database_url)
    try:
        assert find_schema_drift(engine) == {}
    finally:
        engine.dispose()
