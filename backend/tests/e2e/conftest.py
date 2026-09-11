import pytest
from fastapi.testclient import TestClient

import app.database.session as session_module
from app.auth.hashing import hash_password
from app.core.dependencies import get_content_store
from app.database.session import build_engine, build_sessionmaker
from app.database.shared_models import User
from app.main import app
from app.storage.filesystem import FilesystemStorage

AUTH_USERNAME = "researcher"
AUTH_PASSWORD = "s3cret"


@pytest.fixture()
def db_engine(tmp_path, monkeypatch):
    """Points the app's module-level engine/session at an isolated per-test database, so the
    app's startup lifespan (which calls the bare `init_db()`) initializes the test database
    rather than the real configured one - not just `get_db()`'s dependency-injected callers.
    """
    db_path = tmp_path / "api_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    session_factory = build_sessionmaker(engine)

    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", session_factory)

    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine, tmp_path):
    """A TestClient wired to an isolated per-test database (via the db_engine monkeypatch)
    and object store (via a dependency override) - never the real configured `scholaros.db`
    / `data/documents`.
    """

    def override_get_content_store() -> FilesystemStorage:
        return FilesystemStorage(tmp_path / "object-store")

    app.dependency_overrides[get_content_store] = override_get_content_store
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def provisioned_user(db_engine):
    """Inserts a known, provisioned user directly - independent of Stage 4's startup
    provisioning (already covered by its own tests), so business-flow e2e tests only need
    to authenticate, not configure AUTH_USERNAME/AUTH_PASSWORD_HASH and the real lifespan.
    """
    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username=AUTH_USERNAME, password_hash=hash_password(AUTH_PASSWORD)))
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def auth_headers(client, provisioned_user):
    """A real bearer token for `provisioned_user`, obtained via an actual POST /auth/login
    call - not a fabricated header - so every authenticated e2e test exercises the real
    Stage 5 login path plus Stage 6's get_current_user_id in one continuous flow.
    """
    response = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": AUTH_PASSWORD})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
