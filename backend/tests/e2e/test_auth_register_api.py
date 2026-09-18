from app.core.config import get_settings

# `client`/`db_engine` are defined once in conftest.py, shared across every e2e test file
# (Stage 6's own pattern) - this file tests /auth/register (ADR-011) specifically.


def test_registering_a_new_account_returns_a_usable_bearer_token(client):
    response = client.post(
        "/auth/register", json={"username": "new-researcher", "password": "a-real-password"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 0
    assert "password_hash" not in body
    assert set(body.keys()) == {"access_token", "token_type"}


def test_a_freshly_registered_account_can_use_its_token_on_a_real_business_route(client):
    register_response = client.post(
        "/auth/register", json={"username": "new-researcher", "password": "a-real-password"}
    )
    token = register_response.json()["access_token"]

    response = client.post(
        "/agents",
        json={"project_title": "Thesis", "project_topic": "Topic"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


def test_registering_the_same_username_twice_returns_409(client):
    client.post("/auth/register", json={"username": "duplicate-name", "password": "a-real-password"})

    response = client.post("/auth/register", json={"username": "duplicate-name", "password": "another-password"})

    assert response.status_code == 409
    assert response.json()["error_type"] == "UsernameAlreadyTakenError"


def test_a_password_shorter_than_the_minimum_returns_422(client):
    response = client.post("/auth/register", json={"username": "new-researcher", "password": "short"})

    assert response.status_code == 422
    assert response.json()["error_type"] == "WeakPasswordError"


def test_registration_with_missing_fields_returns_422(client):
    response = client.post("/auth/register", json={"username": "new-researcher"})
    assert response.status_code == 422


def test_two_freshly_registered_accounts_never_see_each_others_workspace(client):
    """The real point of ADR-011: registration must produce genuinely isolated accounts, the
    same cross-user isolation Milestone 7's own audit already confirmed generalizes to many
    real accounts, not just the one pre-provisioned one.
    """
    token_a = client.post(
        "/auth/register", json={"username": "researcher-a", "password": "a-real-password"}
    ).json()["access_token"]
    token_b = client.post(
        "/auth/register", json={"username": "researcher-b", "password": "a-real-password"}
    ).json()["access_token"]

    client.post(
        "/agents",
        json={"project_title": "Researcher A's Thesis", "project_topic": "Topic A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # B has no workspace yet - registering never creates one, and B's own request must not
    # somehow reach A's.
    b_workspace = client.get("/agents", headers={"Authorization": f"Bearer {token_b}"})
    assert b_workspace.status_code == 404


# --- Invite-code gate (ADR-011 Decision item 2) --------------------------------------------


def test_registration_is_open_when_no_invite_code_is_configured(client):
    response = client.post(
        "/auth/register", json={"username": "new-researcher", "password": "a-real-password", "invite_code": None}
    )
    assert response.status_code == 201


def test_registration_requires_the_configured_invite_code(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_INVITE_CODE", "friends-2026")
    get_settings.cache_clear()
    try:
        wrong_code = client.post(
            "/auth/register",
            json={"username": "new-researcher", "password": "a-real-password", "invite_code": "wrong"},
        )
        missing_code = client.post(
            "/auth/register", json={"username": "new-researcher", "password": "a-real-password"}
        )
        correct_code = client.post(
            "/auth/register",
            json={"username": "new-researcher", "password": "a-real-password", "invite_code": "friends-2026"},
        )
    finally:
        monkeypatch.delenv("REGISTRATION_INVITE_CODE", raising=False)
        get_settings.cache_clear()

    assert wrong_code.status_code == 401
    assert wrong_code.json()["error_type"] == "InvalidInviteCodeError"
    assert missing_code.status_code == 401
    assert correct_code.status_code == 201
