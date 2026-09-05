import pytest
from fastapi.testclient import TestClient

import app.database.session as session_module
from app.core.dependencies import get_content_store
from app.database.session import build_engine, build_sessionmaker
from app.main import app
from app.storage.filesystem import FilesystemStorage


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
