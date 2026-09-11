from tests.e2e.conftest import AUTH_PASSWORD as PASSWORD
from tests.e2e.conftest import AUTH_USERNAME as USERNAME

# `provisioned_user` is defined once in conftest.py and shared across every e2e test file
# that needs a real, known account (Stage 6) - this file tests the login/logout routes
# themselves, not provisioning (already covered in Stage 4's tests).


# --- Scenario A -------------------------------------------------------------------


def test_scenario_a_successful_login_returns_a_bearer_token(client, provisioned_user):
    response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 0
    assert "password_hash" not in body
    assert "session_id" not in body
    assert set(body.keys()) == {"access_token", "token_type"}


# --- Scenario B -------------------------------------------------------------------


def test_scenario_b_wrong_password_returns_401(client, provisioned_user):
    response = client.post("/auth/login", json={"username": USERNAME, "password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidCredentialsError"


# --- Scenario C -------------------------------------------------------------------


def test_scenario_c_unknown_username_returns_the_identical_401_as_wrong_password(client, provisioned_user):
    unknown_user = client.post("/auth/login", json={"username": "nobody", "password": "whatever"})
    wrong_password = client.post("/auth/login", json={"username": USERNAME, "password": "wrong-password"})

    assert unknown_user.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown_user.json() == wrong_password.json()


def test_login_with_missing_fields_returns_422(client, provisioned_user):
    response = client.post("/auth/login", json={"username": USERNAME})
    assert response.status_code == 422


# --- Scenario D -------------------------------------------------------------------


def test_scenario_d_a_valid_token_is_accepted_when_presented(client, provisioned_user):
    """Demonstrated against a real protected business route (POST /agents), now that Stage 6
    wires get_current_user_id to AuthService.verify_token - not just against logout.
    """
    login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    token = login_response.json()["access_token"]

    response = client.post(
        "/agents",
        json={"project_title": "Thesis", "project_topic": "Topic"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


# --- Scenario E -------------------------------------------------------------------


def test_scenario_e_logout_succeeds_for_a_valid_session(client, provisioned_user):
    login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    token = login_response.json()["access_token"]

    response = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert response.content == b""


# --- Scenario F -------------------------------------------------------------------


def test_scenario_f_reusing_a_logged_out_token_fails(client, provisioned_user):
    login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/auth/logout", headers=headers)

    reuse_response = client.post("/auth/logout", headers=headers)

    assert reuse_response.status_code == 401
    assert reuse_response.json()["error_type"] == "InvalidSessionError"


# --- Logout edge cases -------------------------------------------------------------------


def test_logout_without_an_authorization_header_returns_401(client, provisioned_user):
    response = client.post("/auth/logout")
    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidSessionError"


def test_logout_with_a_non_bearer_scheme_returns_401(client, provisioned_user):
    response = client.post("/auth/logout", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidSessionError"


def test_logout_with_an_unknown_token_returns_401(client, provisioned_user):
    response = client.post("/auth/logout", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidSessionError"


# --- Existing surface unaffected -------------------------------------------------------------------


def test_health_remains_public(client):
    assert client.get("/health").status_code == 200


def test_business_routes_now_require_authentication(client):
    """Stage 6: the bootstrap identity is gone - /agents requires a real bearer token."""
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"})
    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidSessionError"


def test_token_reused_against_a_business_route_after_logout_returns_401(client, provisioned_user):
    """Full lifecycle over separate HTTP requests: login, logout, then reuse the same token
    against a protected business route (not just /auth/logout itself) - Stage 6.
    """
    login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = client.post("/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    reuse_response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    assert reuse_response.status_code == 401
    assert reuse_response.json()["error_type"] == "InvalidSessionError"
