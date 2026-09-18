"""Persistent Brain Decision 3: the Agent Workspace chat is a first-class interaction that
never requires creating a Draft. Real HTTP, real async worker processing, real cross-agent
isolation.
"""

import pytest

from app.auth.hashing import hash_password
from app.core.dependencies import get_embedding_provider
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.main import app
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0]


class FakeTextGenerationProvider:
    def __init__(self, response: str = "Hello, how can I help with your project?") -> None:
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


class FailingTextGenerationProvider:
    """Simulates a real, persistent provider failure (e.g. quota exhaustion) - used to drive a
    Work Item to terminal `failed`, the real precondition for the reply-status/retry tests
    below (mirrors `test_document_upload_api.py`'s own `_fail_a_document` pattern).
    """

    def generate(self, prompt: str) -> str:
        raise RuntimeError("Simulated provider outage.")


@pytest.fixture(autouse=True)
def _override_embedding_provider():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    yield
    app.dependency_overrides.pop(get_embedding_provider, None)


def _create_workspace(client, headers, *, topic="Coastal erosion") -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": topic}, headers=headers)
    return response.json()


def _process_next_work_item(db_engine, tmp_path, *, text_provider=None) -> bool:
    session = build_sessionmaker(db_engine)()
    try:
        storage = FilesystemStorage(tmp_path / "object-store")
        return process_one_work_item(
            session,
            text_provider=text_provider or FakeTextGenerationProvider(),
            embedding_provider=FakeEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=storage,
        )
    finally:
        session.close()


def test_start_conversation_returns_the_created_conversation(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/conversations", json={"title": "Planning chat"}, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Planning chat"
    assert body["status"] == "active"


def test_send_message_and_receive_a_reply(client, auth_headers, db_engine, tmp_path):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()

    response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "Remember that the methodology for this project is a LIDAR survey."},
        headers=auth_headers,
    )
    assert response.status_code == 202
    assert response.json()["state"] == "queued"

    assert _process_next_work_item(db_engine, tmp_path, text_provider=FakeTextGenerationProvider("Understood.")) is True

    messages = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/messages", headers=auth_headers
    ).json()["messages"]
    assert len(messages) == 2
    assert messages[0]["direction"] == "user_request"
    assert messages[1]["direction"] == "system_response"
    assert messages[1]["content"] == "Understood."


def test_a_second_message_carries_prior_conversation_into_context(client, auth_headers, db_engine, tmp_path):
    """Verifies bounded conversation context actually reaches the assembled prompt for a real
    second message - a spying FakeTextGenerationProvider captures the real prompt text.
    """

    class SpyingProvider:
        def __init__(self):
            self.prompts = []

        def generate(self, prompt: str) -> str:
            self.prompts.append(prompt)
            return "Reply."

    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()

    client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "The methodology is a LIDAR survey."},
        headers=auth_headers,
    )
    spy = SpyingProvider()
    _process_next_work_item(db_engine, tmp_path, text_provider=spy)

    client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "What methodology did I just mention?"},
        headers=auth_headers,
    )
    _process_next_work_item(db_engine, tmp_path, text_provider=spy)

    assert len(spy.prompts) == 2
    # The second prompt's RELEVANT CONVERSATION CONTEXT section carries the first exchange.
    assert "The methodology is a LIDAR survey." in spy.prompts[1]
    assert "Reply." in spy.prompts[1]


def test_conversations_and_messages_do_not_leak_across_agents(client, auth_headers, db_engine, tmp_path):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "Secret project detail."},
        headers=auth_headers,
    )

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder-chat", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder-chat", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)

    # The intruder cannot read the victim's conversation's messages.
    response = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/messages", headers=intruder_headers
    )
    assert response.status_code == 404

    # The intruder cannot post into the victim's conversation either.
    response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "injected"},
        headers=intruder_headers,
    )
    assert response.status_code == 404

    # The intruder's own conversation listing never includes the victim's conversation.
    intruder_conversations = client.get("/writing/conversations", headers=intruder_headers).json()
    assert intruder_conversations["conversations"] == []


# --- DELETE /writing/conversations/{conversation_id} ----------------------------------------


def test_deleting_a_conversation_returns_204_and_it_disappears_from_listing(client, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()

    response = client.delete(f"/writing/conversations/{conversation['conversation_id']}", headers=auth_headers)

    assert response.status_code == 204
    listing = client.get("/writing/conversations", headers=auth_headers).json()["conversations"]
    assert listing == []


def test_a_deleted_conversation_can_no_longer_be_read_from_or_sent_to(client, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    client.delete(f"/writing/conversations/{conversation['conversation_id']}", headers=auth_headers)

    read_response = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/messages", headers=auth_headers
    )
    assert read_response.status_code == 404

    send_response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "Should be rejected."},
        headers=auth_headers,
    )
    assert send_response.status_code == 404


def test_deleting_an_already_deleted_conversation_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    client.delete(f"/writing/conversations/{conversation['conversation_id']}", headers=auth_headers)

    response = client.delete(f"/writing/conversations/{conversation['conversation_id']}", headers=auth_headers)

    assert response.status_code == 404


def test_deleting_a_nonexistent_conversation_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.delete("/writing/conversations/999999", headers=auth_headers)

    assert response.status_code == 404


def test_deleting_another_users_conversation_is_rejected_as_not_found(client, db_engine, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder-delete-chat", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder-delete-chat", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)

    response = client.delete(f"/writing/conversations/{conversation['conversation_id']}", headers=intruder_headers)

    assert response.status_code == 404
    listing = client.get("/writing/conversations", headers=auth_headers).json()["conversations"]
    assert len(listing) == 1  # untouched


# --- GET/POST /writing/conversations/{conversation_id}/reply-status/{work_item_id} ----------
# The real gap this closes: before this, a genuinely failed chat reply was indistinguishable
# from one that was just slow - the frontend's only signal was a fixed client-side poll window
# expiring with no explanation and no way to recover short of sending the message again.


def _send_and_get_work_item_id(client, auth_headers, conversation_id: int, content: str = "Hello") -> int:
    response = client.post(
        f"/writing/conversations/{conversation_id}/messages",
        json={"content": content},
        headers=auth_headers,
    )
    assert response.status_code == 202
    return response.json()["work_item_id"]


def test_reply_status_is_queued_before_the_worker_runs(client, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    work_item_id = _send_and_get_work_item_id(client, auth_headers, conversation["conversation_id"])

    response = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/reply-status/{work_item_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "queued"
    assert body["last_error"] is None


def test_reply_status_is_succeeded_after_the_worker_runs(client, auth_headers, db_engine, tmp_path):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    work_item_id = _send_and_get_work_item_id(client, auth_headers, conversation["conversation_id"])
    _process_next_work_item(db_engine, tmp_path)

    response = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/reply-status/{work_item_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["state"] == "succeeded"


def _fail_a_reply(client, auth_headers, db_engine, tmp_path, conversation_id: int) -> int:
    work_item_id = _send_and_get_work_item_id(client, auth_headers, conversation_id)
    for _ in range(3):  # DEFAULT_MAX_ATTEMPTS - exhaust retries so it reaches `failed`
        _process_next_work_item(db_engine, tmp_path, text_provider=FailingTextGenerationProvider())
    return work_item_id


def test_reply_status_includes_the_real_failure_reason_once_failed(client, auth_headers, db_engine, tmp_path):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    work_item_id = _fail_a_reply(client, auth_headers, db_engine, tmp_path, conversation["conversation_id"])

    response = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/reply-status/{work_item_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "failed"
    assert "Simulated provider outage" in body["last_error"]


def test_retrying_a_failed_reply_succeeds_and_produces_a_message(client, auth_headers, db_engine, tmp_path):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    conversation_id = conversation["conversation_id"]
    work_item_id = _fail_a_reply(client, auth_headers, db_engine, tmp_path, conversation_id)

    response = client.post(
        f"/writing/conversations/{conversation_id}/reply-status/{work_item_id}/retry",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["state"] == "queued"

    assert _process_next_work_item(db_engine, tmp_path, text_provider=FakeTextGenerationProvider("Recovered.")) is True
    messages = client.get(f"/writing/conversations/{conversation_id}/messages", headers=auth_headers).json()["messages"]
    assert len(messages) == 2
    assert messages[1]["content"] == "Recovered."


def test_retrying_a_queued_reply_returns_409(client, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    work_item_id = _send_and_get_work_item_id(client, auth_headers, conversation["conversation_id"])

    response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/reply-status/{work_item_id}/retry",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error_type"] == "ChatReplyCannotBeRetriedError"


def test_retrying_a_succeeded_reply_returns_409(client, auth_headers, db_engine, tmp_path):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    work_item_id = _send_and_get_work_item_id(client, auth_headers, conversation["conversation_id"])
    _process_next_work_item(db_engine, tmp_path)

    response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/reply-status/{work_item_id}/retry",
        headers=auth_headers,
    )

    assert response.status_code == 409


def test_reply_status_for_a_nonexistent_work_item_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()

    response = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/reply-status/999999",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "ChatReplyWorkItemNotFoundError"


def test_reply_status_for_a_work_item_from_another_conversation_returns_404(client, auth_headers):
    """A real cross-conversation probing risk this closes: without checking that the
    work_item_id's own payload_reference actually names this conversation, any conversation the
    caller owns would have been enough to poll any other conversation's (even another user's)
    generation status - see GetChatReplyStatusUseCase's own docstring.
    """
    _create_workspace(client, auth_headers)
    conversation_a = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    conversation_b = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    work_item_id = _send_and_get_work_item_id(client, auth_headers, conversation_a["conversation_id"])

    response = client.get(
        f"/writing/conversations/{conversation_b['conversation_id']}/reply-status/{work_item_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "ChatReplyWorkItemNotFoundError"


def test_reply_status_for_another_users_conversation_returns_404(client, db_engine, auth_headers):
    _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    work_item_id = _send_and_get_work_item_id(client, auth_headers, conversation["conversation_id"])

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder-reply-status", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder-reply-status", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)

    response = client.get(
        f"/writing/conversations/{conversation['conversation_id']}/reply-status/{work_item_id}",
        headers=intruder_headers,
    )

    assert response.status_code == 404
