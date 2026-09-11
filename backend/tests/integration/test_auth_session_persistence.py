from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.auth.infrastructure import SqlAlchemyAuthSessionRepository
from app.auth.models import AuthSession as AuthSessionModel
from app.auth.tokens import generate_session_token, hash_session_token
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "auth_session_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_user(session, username="researcher"):
    user = User(username=username, password_hash="irrelevant-for-these-tests")
    session.add(user)
    session.flush()
    return user


# --- Database initialization -------------------------------------------------------------------


def test_fresh_database_creates_the_sessions_table_alongside_every_existing_table(tmp_path):
    db_path = tmp_path / "fresh_init_test.db"
    engine = build_engine(f"sqlite:///{db_path}")

    init_db(engine)

    tables = set(inspect(engine).get_table_names())
    assert {"users", "agents", "projects", "research_documents", "sessions"} <= tables
    engine.dispose()


def test_users_table_has_the_password_hash_column(tmp_path):
    db_path = tmp_path / "fresh_init_columns_test.db"
    engine = build_engine(f"sqlite:///{db_path}")

    init_db(engine)

    columns = {col["name"] for col in inspect(engine).get_columns("users")}
    assert "password_hash" in columns
    engine.dispose()


def test_sessions_table_requires_an_existing_user(db_session):
    db_session.add(AuthSessionModel(user_id=999, token_hash="a" * 64))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- Session persistence -------------------------------------------------------------------


def test_create_persists_and_retrieves_a_session(db_session):
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)

    created = repo.create(user_id=user.user_id, token_hash="a" * 64)
    db_session.commit()

    assert created.session_id is not None
    assert created.user_id == user.user_id
    assert created.started_at is not None
    assert created.last_active_at is None
    assert created.ended_at is None
    assert created.is_active is True


def test_get_by_token_hash_finds_the_matching_session(db_session):
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)
    repo.create(user_id=user.user_id, token_hash="b" * 64)
    db_session.commit()

    found = repo.get_by_token_hash("b" * 64)

    assert found is not None
    assert found.user_id == user.user_id


def test_get_by_token_hash_returns_none_for_an_unknown_hash(db_session):
    repo = SqlAlchemyAuthSessionRepository(db_session)
    assert repo.get_by_token_hash("never-created" * 5) is None


def test_end_sets_ended_at_and_it_persists_across_a_fresh_lookup(db_session):
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)
    session = repo.create(user_id=user.user_id, token_hash="c" * 64)
    db_session.commit()

    repo.end(session)
    db_session.commit()

    refetched = repo.get_by_token_hash("c" * 64)
    assert refetched.ended_at is not None
    assert refetched.is_active is False


def test_touch_updates_last_active_at(db_session):
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)
    session = repo.create(user_id=user.user_id, token_hash="d" * 64)
    db_session.commit()
    assert session.last_active_at is None

    repo.touch(session)
    db_session.commit()

    refetched = repo.get_by_token_hash("d" * 64)
    assert refetched.last_active_at is not None


# --- Token handling -------------------------------------------------------------------


def test_the_raw_token_is_never_persisted_only_its_hash(db_session):
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)
    raw_token = generate_session_token()

    repo.create(user_id=user.user_id, token_hash=hash_session_token(raw_token))
    db_session.commit()

    row = db_session.query(AuthSessionModel).one()
    assert row.token_hash != raw_token
    assert row.token_hash == hash_session_token(raw_token)


def test_the_correct_raw_token_resolves_to_its_session(db_session):
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)
    raw_token = generate_session_token()
    repo.create(user_id=user.user_id, token_hash=hash_session_token(raw_token))
    db_session.commit()

    found = repo.get_by_token_hash(hash_session_token(raw_token))
    assert found is not None


def test_an_incorrect_raw_token_does_not_resolve(db_session):
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)
    repo.create(user_id=user.user_id, token_hash=hash_session_token(generate_session_token()))
    db_session.commit()

    wrong_token = generate_session_token()
    assert repo.get_by_token_hash(hash_session_token(wrong_token)) is None


# --- No-expiry rule (mandatory - ADR-010 Decision item 2) -------------------------------------------------------------------


def test_a_session_with_a_very_stale_last_active_at_remains_active_at_the_persistence_layer(db_session):
    """Regression guard: automatic session expiry was explicitly and permanently rejected for
    this milestone (ADR-010). A session is valid until explicit logout - never by staleness.
    """
    user = _make_user(db_session)
    repo = SqlAlchemyAuthSessionRepository(db_session)
    session = repo.create(user_id=user.user_id, token_hash="e" * 64)
    db_session.commit()

    row = db_session.get(AuthSessionModel, session.session_id)
    row.last_active_at = datetime.now(timezone.utc) - timedelta(days=365)
    row.started_at = datetime.now(timezone.utc) - timedelta(days=365)
    db_session.commit()

    refetched = repo.get_by_token_hash("e" * 64)
    assert refetched.is_active is True
