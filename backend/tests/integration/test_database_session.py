from sqlalchemy import inspect

from app.database.session import build_engine, build_sessionmaker, init_db


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


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "idempotent_test.db"
    engine = build_engine(f"sqlite:///{db_path}")

    init_db(engine)
    init_db(engine)  # must not raise on a second call

    tables = set(inspect(engine).get_table_names())
    assert {"users", "agents", "projects", "research_documents"} <= tables
    engine.dispose()
