import pytest
from fastapi.testclient import TestClient

import app.database.session as session_module
import app.main as main_module
from app.auth.hashing import hash_password
from app.core.dependencies import get_content_store, get_password_breach_checker
from app.core.rate_limit import limiter
from app.database.session import build_engine, build_sessionmaker
from app.database.shared_models import User
from app.main import app
from app.storage.filesystem import FilesystemStorage

AUTH_USERNAME = "researcher"
AUTH_PASSWORD = "s3cret"


class _NoOpExecutorLoop:
    """Stands in for the real WorkItemExecutorLoop for the duration of an e2e test (2026-09-23).

    Before the "AI Unavailable provider" change, the real executor only ever started when
    `AI_API_KEY` was configured - never true in tests, so it was silently a no-op here. It now
    always starts (by design: a queued item should reach a visible terminal failure instead of
    hanging forever with no provider configured), which means it also always starts during e2e
    tests - genuinely polling and writing to the test's own SQLite database in the background,
    racing the test's own foreground requests. SQLite allows only one writer at a time; even
    with WAL mode and a busy_timeout (see build_engine), a background writer with real work to
    do (repeatedly retrying a Work Item it can never complete without a real AI provider)
    collides often enough to produce genuine "database is locked" errors in tests that never
    needed the executor to be running at all - they either don't create Work Items, or process
    the one they do via `process_one_work_item` directly, deterministically, in the test's own
    thread. Restores the old, effectively-always-off behavior for tests specifically, without
    touching the real (and correct) production default.
    """

    def __init__(self, *args, **kwargs) -> None:
        pass

    def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


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
def client(db_engine, tmp_path, monkeypatch):
    """A TestClient wired to an isolated per-test database (via the db_engine monkeypatch)
    and object store (via a dependency override) - never the real configured `scholaros.db`
    / `data/documents`.

    Rate limiting (2026-09-19 production security pass) is disabled here: every request from
    this TestClient shares one IP (`testclient`), so business-flow tests that legitimately make
    more than a handful of requests to the same rate-limited route (e.g. uploading up to
    MAX_RESEARCH_DOCUMENTS_PER_PROJECT documents) would otherwise be throttled by an unrelated
    concern. Rate limiting itself is exercised separately in test_rate_limiting_api.py, which
    re-enables it for the duration of its own tests.

    The background Work Item executor (2026-09-23) is replaced with a no-op for the same
    reason - see `_NoOpExecutorLoop`'s own docstring. Tests that need a Work Item actually
    processed call `process_one_work_item` directly (e.g. via each test file's own
    `_process_next_work_item` helper), deterministically, rather than relying on the real
    background poll loop's timing.
    """

    def override_get_content_store() -> FilesystemStorage:
        return FilesystemStorage(tmp_path / "object-store")

    app.dependency_overrides[get_content_store] = override_get_content_store
    # Never known-breached by default - individual tests exercising the rejection path override
    # this back to a fake returning True, the same per-test-override pattern
    # test_google_sign_in_api.py already uses for get_google_token_verifier. Without this, every
    # e2e test that registers or resets a password would make a real network call to HIBP.
    app.dependency_overrides[get_password_breach_checker] = lambda: (lambda password: False)
    limiter.enabled = False
    monkeypatch.setattr(main_module, "WorkItemExecutorLoop", _NoOpExecutorLoop)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        limiter.enabled = True


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
