import pytest
from fastapi.testclient import TestClient

from app.auth.hashing import hash_password
from app.core.config import get_settings
from app.database.session import build_engine, build_sessionmaker
import app.database.session as session_module
from app.database.shared_models import User
from app.main import app

VALID_HASH = hash_password("s3cret")


@pytest.fixture()
def db_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "startup_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    session_factory = build_sessionmaker(engine)
    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", session_factory)
    yield engine
    engine.dispose()


@pytest.fixture()
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_startup_without_any_auth_configuration_does_not_provision_a_user_and_still_boots(
    db_engine, clear_settings_cache
):
    """Existing backend functionality (pre-Stage-4) must remain unchanged when auth isn't
    configured - this is the same behavior all 105 prior tests already exercise implicitly;
    this test makes it an explicit, first-class contract.
    """
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

    session = build_sessionmaker(db_engine)()
    try:
        assert session.query(User).count() == 0
    finally:
        session.close()


def test_fresh_app_startup_provisions_the_configured_user(db_engine, clear_settings_cache, monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "researcher")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", VALID_HASH)
    get_settings.cache_clear()

    with TestClient(app):
        pass  # entering/exiting the context runs the real lifespan (startup and shutdown)

    session = build_sessionmaker(db_engine)()
    try:
        user = session.query(User).filter_by(username="researcher").one_or_none()
        assert user is not None
        assert user.password_hash == VALID_HASH
    finally:
        session.close()


def test_repeated_app_startups_still_provision_exactly_one_user(db_engine, clear_settings_cache, monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "researcher")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", VALID_HASH)
    get_settings.cache_clear()

    for _ in range(4):
        with TestClient(app):
            pass

    session = build_sessionmaker(db_engine)()
    try:
        assert session.query(User).count() == 1
    finally:
        session.close()


def test_startup_fails_fast_with_a_malformed_password_hash(db_engine, clear_settings_cache, monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "researcher")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", "not-a-real-bcrypt-hash")
    get_settings.cache_clear()

    with pytest.raises(Exception):  # noqa: B017 - the exact wrapping exception type is FastAPI/Starlette's, not ours
        with TestClient(app):
            pass
