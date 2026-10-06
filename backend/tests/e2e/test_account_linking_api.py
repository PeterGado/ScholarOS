from app.core.dependencies import get_google_token_verifier
from app.main import app
from tests.e2e.conftest import AUTH_PASSWORD, AUTH_USERNAME

GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


def _verifier(sub: str, *, error: bool = False):
    def verify(id_token: str, *, client_id: str):
        if error:
            raise ValueError("invalid token")
        return {"sub": sub, "email": "researcher@example.com", "email_verified": True}

    return verify


def _set_verifier(sub: str, *, error: bool = False):
    app.dependency_overrides[get_google_token_verifier] = lambda: _verifier(sub, error=error)


def _login_headers(client):
    token = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": AUTH_PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _google_only_account(client, sub="google-subject-link-1"):
    """Registers a fresh Google-origin account (no password) and returns its bearer headers."""
    from app.core.config import get_settings

    get_settings().google_oauth_client_id = GOOGLE_CLIENT_ID
    _set_verifier(sub)
    token = client.post("/auth/google", json={"id_token": "raw"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_connecting_google_to_a_password_account_links_it(client, provisioned_user, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", GOOGLE_CLIENT_ID)
    _set_verifier("google-subject-link-2")
    try:
        headers = _login_headers(client)
        assert client.get("/auth/profile", headers=headers).json()["google_connected"] is False

        response = client.post("/auth/google/connect", json={"id_token": "raw"}, headers=headers)

        assert response.status_code == 204
        profile = client.get("/auth/profile", headers=headers).json()
        assert profile["google_connected"] is True
        assert profile["has_password"] is True
    finally:
        app.dependency_overrides.pop(get_google_token_verifier, None)


def test_a_google_identity_already_linked_to_another_account_is_rejected(client, provisioned_user, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", GOOGLE_CLIENT_ID)
    _set_verifier("google-subject-shared")
    try:
        other_headers = _google_only_account(client, sub="google-subject-shared")
        headers = _login_headers(client)

        response = client.post("/auth/google/connect", json={"id_token": "raw"}, headers=headers)

        assert response.status_code == 409
        assert response.json()["error_type"] == "GoogleAccountAlreadyLinkedError"
        assert other_headers  # the owning account is untouched
    finally:
        app.dependency_overrides.pop(get_google_token_verifier, None)


def test_connecting_with_an_invalid_google_token_returns_401(client, provisioned_user, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", GOOGLE_CLIENT_ID)
    _set_verifier("unused", error=True)
    try:
        headers = _login_headers(client)

        response = client.post("/auth/google/connect", json={"id_token": "garbage"}, headers=headers)

        assert response.status_code == 401
        assert response.json()["error_type"] == "InvalidGoogleTokenError"
    finally:
        app.dependency_overrides.pop(get_google_token_verifier, None)


def test_a_google_only_account_can_set_a_password_and_then_sign_in_with_it(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", GOOGLE_CLIENT_ID)
    try:
        headers = _google_only_account(client, sub="google-subject-setpw")
        assert client.get("/auth/profile", headers=headers).json()["has_password"] is False

        response = client.post("/auth/password/set", json={"password": "a-brand-new-password"}, headers=headers)

        assert response.status_code == 204
        assert client.get("/auth/profile", headers=headers).json()["has_password"] is True
        login = client.post(
            "/auth/login", json={"username": "researcher@example.com", "password": "a-brand-new-password"}
        )
        assert login.status_code == 200
    finally:
        app.dependency_overrides.pop(get_google_token_verifier, None)


def test_setting_a_too_short_password_returns_422(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_oauth_client_id", GOOGLE_CLIENT_ID)
    try:
        headers = _google_only_account(client, sub="google-subject-short")

        response = client.post("/auth/password/set", json={"password": "short"}, headers=headers)

        assert response.status_code == 422
        assert response.json()["error_type"] == "WeakPasswordError"
    finally:
        app.dependency_overrides.pop(get_google_token_verifier, None)
