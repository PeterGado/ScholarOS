import pytest
from sqlalchemy import inspect, text

from app.database.session import (
    build_engine,
    build_sessionmaker,
    find_schema_drift,
    init_db,
    verify_schema,
)


def test_build_engine_and_sessionmaker_produce_a_working_session(tmp_path):
    db_path = tmp_path / "engine_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)

    with session_factory() as session:
        assert session.is_active

    engine.dispose()


def test_init_db_creates_every_expected_table(tmp_path):
    db_path = tmp_path / "schema_test.db"
    engine = build_engine(f"sqlite:///{db_path}")

    init_db(engine)

    tables = set(inspect(engine).get_table_names())
    assert {"users", "agents", "projects", "research_documents"} <= tables
    engine.dispose()


def test_find_schema_drift_reports_nothing_for_a_freshly_created_schema(tmp_path):
    db_path = tmp_path / "clean_schema.db"
    engine = build_engine(f"sqlite:///{db_path}")

    init_db(engine)

    assert find_schema_drift(engine) == {}
    engine.dispose()


def test_verify_schema_accepts_a_freshly_created_schema(tmp_path):
    db_path = tmp_path / "clean_verify.db"
    engine = build_engine(f"sqlite:///{db_path}")

    init_db(engine)
    verify_schema(engine)  # must not raise

    engine.dispose()


def test_find_schema_drift_reports_columns_missing_from_a_stale_table(tmp_path):
    """Reproduces the 2026-11-06 startup crash: a `users` table created before the
    google-signin/email-verification migrations. `init_db` creates the remaining tables but
    cannot add a column to a table that already exists, so the drift has to be detectable.
    """
    db_path = tmp_path / "stale_schema.db"
    engine = build_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (user_id INTEGER PRIMARY KEY)"))

    init_db(engine)

    drift = find_schema_drift(engine)
    assert set(drift) == {"users"}
    assert {"email", "email_verified", "google_subject"} <= set(drift["users"])
    engine.dispose()


def test_verify_schema_raises_an_actionable_error_when_the_schema_is_stale(tmp_path):
    db_path = tmp_path / "stale_verify.db"
    engine = build_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (user_id INTEGER PRIMARY KEY)"))
    init_db(engine)

    with pytest.raises(RuntimeError) as error:
        verify_schema(engine)

    message = str(error.value)
    assert "users" in message
    assert "email" in message
    # The operator-facing fix has to be in the message, not just the symptom.
    assert "alembic upgrade head" in message
    engine.dispose()


def test_find_schema_drift_reports_an_entirely_missing_table(tmp_path):
    db_path = tmp_path / "missing_table.db"
    engine = build_engine(f"sqlite:///{db_path}")

    # Nothing created at all - every model table should be reported as absent.
    drift = find_schema_drift(engine)

    assert "users" in drift
    assert "email" in drift["users"]
    engine.dispose()


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "idempotent_test.db"
    engine = build_engine(f"sqlite:///{db_path}")

    init_db(engine)
    init_db(engine)  # must not raise on a second call

    tables = set(inspect(engine).get_table_names())
    assert {"users", "agents", "projects", "research_documents"} <= tables
    engine.dispose()
