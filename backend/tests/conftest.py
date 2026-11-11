import pytest

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolate_settings_from_local_env_file(monkeypatch):
    """Test hygiene guard, not a production behavior change.

    `Settings.model_config` points at ".env" unconditionally (by design, for real
    deployments run from `backend/`). But pytest's cwd is also `backend/`, so a developer's
    real `backend/.env` (e.g. real AUTH_USERNAME/AUTH_PASSWORD_HASH, created for manual
    verification per backend/README.md) would otherwise be read by every fresh `Settings()`
    in the suite, silently provisioning real credentials into ephemeral per-test databases.
    Tests must be hermetic regardless of what local file happens to exist in the cwd -
    disabling dotenv loading here does not affect `monkeypatch.setenv`, which each
    provisioning test already uses to set real process env vars explicitly.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    # ENVIRONMENT=test (2026-11-06): the app's startup lifespan creates the schema with
    # create_all() only for test databases (see app/main.py's lifespan), so ephemeral
    # per-test databases still bootstrap themselves the way every fixture expects. Real
    # environments - development included - now bootstrap through `alembic upgrade head`
    # instead, which is what keeps a local dev database from silently drifting from the
    # models. Set before the cache clear below so every Settings() built during the test
    # sees it; a test that needs a different environment still overrides it itself.
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
