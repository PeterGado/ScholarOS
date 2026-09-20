import pytest

from app.core.dependencies import get_google_token_verifier
from app.main import app

GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


def _fake_verifier(claims: dict | None = None, *, error: bool = False):
    def verify(id_token: str, *, client_id: str):
        if error:
            raise ValueError("invalid token")
        return claims or {"sub": "google-subject-1", "email": "alice@example.com", "email_verified": True, "name": "Alice"}

    return verify


@pytest.fixture()
def google_client_id(monkeypatch):
    """Every test in this file needs GOOGLE_OAUTH_CLIENT_ID configured - real e2e tests for the
    not-configured (503) case override it back to None explicitly instead.
    """
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", GOOGLE_CLIENT_ID)


@pytest.fixture()
def fake_google_verifier():
    """Overrides the one dependency that would otherwise call Google's real network
    (app.core.dependencies.get_google_token_verifier) - swapped per-test via the returned setter.
    """

    def _set(claims: dict | None = None, *, error: bool = False):
        app.dependency_overrides[get_google_token_verifier] = lambda: _fake_verifier(claims, error=error)

    yield _set
    app.dependency_overrides.pop(get_google_token_verifier, None)


def test_a_brand_new_google_user_gets_a_usable_bearer_token(client, google_client_id, fake_google_verifier):
    fake_google_verifier()

    response = client.post("/auth/google", json={"id_token": "raw-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_the_returned_token_authenticates_against_a_protected_route(client, google_client_id, fake_google_verifier):
    fake_google_verifier()
    token = client.post("/auth/google", json={"id_token": "raw-token"}).json()["access_token"]

    response = client.post(
        "/agents",
        json={"project_title": "Thesis", "project_topic": "Topic"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


def test_signing_in_twice_with_the_same_google_identity_returns_the_same_account(
    client, google_client_id, fake_google_verifier
):
    fake_google_verifier()
    first_token = client.post("/auth/google", json={"id_token": "raw-token"}).json()["access_token"]
    second_token = client.post("/auth/google", json={"id_token": "raw-token"}).json()["access_token"]

    first_agent = client.post(
        "/agents",
        json={"project_title": "Thesis", "project_topic": "Topic"},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    second_agent_conflict = client.post(
        "/agents",
        json={"project_title": "Second", "project_topic": "Topic"},
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert first_agent.status_code == 201
    # Same underlying account -> the one-Agent-per-User invariant (ADR-009) rejects a second
    # workspace, proving both tokens really do resolve to the same User row.
    assert second_agent_conflict.status_code == 409


def test_an_invalid_google_token_returns_401(client, google_client_id, fake_google_verifier):
    fake_google_verifier(error=True)

    response = client.post("/auth/google", json={"id_token": "garbage"})

    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidGoogleTokenError"


def test_a_verified_email_conflicting_with_an_existing_password_account_returns_409(
    client, db_engine, google_client_id, fake_google_verifier
):
    from app.auth.hashing import hash_password
    from app.database.session import build_sessionmaker
    from app.database.shared_models import User

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="alice-password", email="alice@example.com", password_hash=hash_password("s3cret123")))
        session.commit()
    finally:
        session.close()
    fake_google_verifier()

    response = client.post("/auth/google", json={"id_token": "raw-token"})

    assert response.status_code == 409
    assert response.json()["error_type"] == "GoogleAccountEmailConflictError"


def test_google_sign_in_without_configuration_returns_503(client, fake_google_verifier):
    fake_google_verifier()

    response = client.post("/auth/google", json={"id_token": "raw-token"})

    assert response.status_code == 503
    assert response.json()["error_type"] == "GoogleSignInNotConfiguredError"


def test_a_brand_new_user_needs_the_configured_invite_code(client, google_client_id, fake_google_verifier, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "registration_invite_code", "friends-2026")
    fake_google_verifier()

    rejected = client.post("/auth/google", json={"id_token": "raw-token"})
    accepted = client.post("/auth/google", json={"id_token": "raw-token", "invite_code": "friends-2026"})

    assert rejected.status_code == 401
    assert rejected.json()["error_type"] == "InvalidInviteCodeError"
    assert accepted.status_code == 200
