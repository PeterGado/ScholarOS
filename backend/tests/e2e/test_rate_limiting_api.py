import io

import pytest

from app.core.dependencies import get_embedding_provider
from app.core.rate_limit import limiter
from app.main import app
from tests.e2e.conftest import AUTH_PASSWORD, AUTH_USERNAME

# The shared `client` fixture (tests/e2e/conftest.py) disables rate limiting for every other
# e2e test, since they legitimately make more requests to a route than a real client should in
# one minute (e.g. uploading up to MAX_RESEARCH_DOCUMENTS_PER_PROJECT documents). This file is
# the one place rate limiting itself is exercised, so it re-enables the shared Limiter and
# resets its in-memory hit counters before and after every test here, so tests in this file
# never see hits left over from each other or leak an enabled limiter into the rest of the suite.


@pytest.fixture(autouse=True)
def _rate_limiting_enabled(client):
    """Depends on `client` (not just autouse) so its setup runs after the shared `client`
    fixture has already set `limiter.enabled = False` - otherwise fixture ordering between two
    same-scope fixtures is unspecified, and this one could run first only to have `client`
    immediately disable the limiter it just turned on.
    """
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()
    limiter.enabled = False


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0]


@pytest.fixture(autouse=True)
def _override_embedding_provider():
    """Sending a chat message embeds the query synchronously for retrieval (ADR-005) even
    before any Work Item runs - without this override that hits the real, unconfigured AI
    embedding provider and fails with 503 before the rate limit is ever reached, exactly as
    tests/e2e/test_writing_chat_api.py already has to work around.
    """
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    yield
    app.dependency_overrides.pop(get_embedding_provider, None)


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    return response.json()


def test_login_beyond_the_per_minute_limit_returns_429(client, provisioned_user):
    for _ in range(10):
        response = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": "wrong-password"})
        assert response.status_code == 401

    response = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": "wrong-password"})

    assert response.status_code == 429
    assert response.json()["error_type"] == "RateLimitExceeded"


def test_login_within_the_limit_is_unaffected(client, provisioned_user):
    for _ in range(5):
        response = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": AUTH_PASSWORD})
        assert response.status_code == 200


def test_register_beyond_the_per_minute_limit_returns_429(client):
    for i in range(5):
        response = client.post(
            "/auth/register", json={"email": f"friend-{i}@example.com", "password": "s3cret-password"}
        )
        assert response.status_code == 201

    response = client.post(
        "/auth/register", json={"email": "one-too-many@example.com", "password": "s3cret-password"}
    )

    assert response.status_code == 429
    assert response.json()["error_type"] == "RateLimitExceeded"


def test_document_upload_beyond_the_per_minute_limit_returns_429(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    for i in range(20):
        response = client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("source.txt", io.BytesIO(b"content"), "text/plain")},
            data={"title": f"Source {i}", "format": "txt"},
            headers=auth_headers,
        )
        assert response.status_code == 201

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("one-too-many.txt", io.BytesIO(b"content"), "text/plain")},
        data={"title": "One too many", "format": "txt"},
        headers=auth_headers,
    )

    assert response.status_code == 429
    assert response.json()["error_type"] == "RateLimitExceeded"


def test_send_chat_message_beyond_the_per_minute_limit_returns_429(client, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={"title": "Chat"}, headers=auth_headers).json()
    conversation_id = conversation["conversation_id"]
    for i in range(20):
        response = client.post(
            f"/writing/conversations/{conversation_id}/messages",
            json={"content": f"message {i}"},
            headers=auth_headers,
        )
        assert response.status_code == 202

    response = client.post(
        f"/writing/conversations/{conversation_id}/messages",
        json={"content": "one too many"},
        headers=auth_headers,
    )

    assert response.status_code == 429
    assert response.json()["error_type"] == "RateLimitExceeded"


def test_search_beyond_the_per_minute_limit_returns_429(client, auth_headers):
    """2026-09-21: found with no rate limit at all while mapping AI call sites for the usage-cap
    work - now fixed, same 20/minute tier as the other AI-adjacent routes.
    """
    _create_workspace(client, auth_headers)
    for _ in range(20):
        response = client.get("/knowledge/search", params={"q": "anything"}, headers=auth_headers)
        assert response.status_code == 200

    response = client.get("/knowledge/search", params={"q": "one too many"}, headers=auth_headers)

    assert response.status_code == 429
    assert response.json()["error_type"] == "RateLimitExceeded"


def test_each_authenticated_user_gets_its_own_rate_limit(client, auth_headers):
    """2026-10-23, per-user keying: before this, every request from one IP shared a bucket, so
    two researchers behind the same campus/office NAT starved each other - and one user could
    reset their budget by switching networks.
    """
    _create_workspace(client, auth_headers)
    for _ in range(20):
        assert client.get("/knowledge/search", params={"q": "anything"}, headers=auth_headers).status_code == 200
    assert client.get("/knowledge/search", params={"q": "one too many"}, headers=auth_headers).status_code == 429

    # A different user, from the very same client IP - must not inherit the exhausted budget.
    register_response = client.post(
        "/auth/register", json={"email": "second-researcher@example.com", "password": "a-real-password"}
    )
    assert register_response.status_code == 201
    other_headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}
    _create_workspace(client, other_headers)

    response = client.get("/knowledge/search", params={"q": "anything"}, headers=other_headers)

    assert response.status_code == 200


def test_a_second_session_for_the_same_user_shares_the_same_limit(client, auth_headers):
    """Keying is per user, not per bearer token - logging in again must not hand out a fresh
    budget, otherwise the limit is trivially bypassed.
    """
    _create_workspace(client, auth_headers)
    for _ in range(20):
        assert client.get("/knowledge/search", params={"q": "anything"}, headers=auth_headers).status_code == 200

    second_login = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": AUTH_PASSWORD})
    assert second_login.status_code == 200
    second_session = {"Authorization": f"Bearer {second_login.json()['access_token']}"}

    response = client.get("/knowledge/search", params={"q": "anything"}, headers=second_session)

    assert response.status_code == 429


def test_a_429_response_includes_a_retry_after_header(client, provisioned_user):
    for _ in range(10):
        client.post("/auth/login", json={"username": AUTH_USERNAME, "password": "wrong-password"})

    response = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": "wrong-password"})

    assert response.status_code == 429
    assert "retry-after" in {k.lower() for k in response.headers}
