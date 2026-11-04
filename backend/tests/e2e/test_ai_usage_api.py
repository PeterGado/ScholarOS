import io

import pytest

from app.ai.exceptions import ProviderRequestError
from app.ai.provider_usage import observe_provider_usage
from app.core.config import get_settings
from app.core.dependencies import get_embedding_provider
from app.database.session import build_sessionmaker
from app.main import app
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item

_CONTENT = b"Real content."


class _NoOpEmbeddingProvider:
    """Sending a chat message embeds the search query synchronously even when the Agent has no
    embeddings yet - without an override that resolves the real, unconfigured provider and the
    send fails with 503 before any Work Item is queued (the same workaround
    test_writing_chat_api.py needs).
    """

    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0] for _ in texts]


@pytest.fixture(autouse=True)
def _override_embedding_provider():
    app.dependency_overrides[get_embedding_provider] = lambda: _NoOpEmbeddingProvider()
    yield
    app.dependency_overrides.pop(get_embedding_provider, None)


class ReportingTextProvider:
    """A provider that reports the same exact usage a real one would - proves the executor's
    metered recording path without a network call.
    """

    def generate(self, prompt: str) -> str:
        observe_provider_usage(input_tokens=100, output_tokens=40)
        return '[{"element_type": "concept", "label": "L", "description": "d"}]'


class ReportingChatProvider:
    """Reports the exact usage a real provider would, on every successful generate call - the
    multi-pass reply path calls this three times (draft, critique, revision).
    """

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        observe_provider_usage(input_tokens=100, output_tokens=40)
        return "A considered reply."


class ReportingThenFailingChatProvider(ReportingChatProvider):
    """Succeeds once, then fails on the next pass - a real multi-pass failure mode, where the
    draft was generated (and paid for) before the critique pass died.
    """

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.calls > 1:
            raise ProviderRequestError("AI provider request failed. (Provider detail: simulated outage)")
        observe_provider_usage(input_tokens=100, output_tokens=40)
        return "A considered reply."


class ReportingEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        observe_provider_usage(input_tokens=7, output_tokens=0)
        return [1.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        observe_provider_usage(input_tokens=7, output_tokens=0)
        return [[1.0, 0.0] for _ in texts]


def _create_workspace(client, headers) -> dict:
    return client.post(
        "/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers
    ).json()


def _upload_document(client, headers, project_id: int) -> None:
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(_CONTENT), "text/plain")},
        data={"title": "Doc", "format": "txt"},
        headers=headers,
    )
    assert response.status_code == 201


def _process_next_work_item(db_engine, tmp_path) -> None:
    session = build_sessionmaker(db_engine)()
    try:
        assert process_one_work_item(
            session,
            text_provider=ReportingTextProvider(),
            embedding_provider=ReportingEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=FilesystemStorage(tmp_path / "object-store"),
        ) is True
    finally:
        session.close()


def _process_next_chat_work_item(db_engine, tmp_path, *, text_provider) -> None:
    session = build_sessionmaker(db_engine)()
    try:
        assert process_one_work_item(
            session,
            text_provider=text_provider,
            embedding_provider=ReportingEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=FilesystemStorage(tmp_path / "object-store"),
            # Never make a real Wikipedia/web network call from a test.
            background_knowledge_provider=lambda topic: None,
            web_fetch_provider=lambda url: None,
        ) is True
    finally:
        session.close()


def _send_chat_message(client, headers) -> None:
    _create_workspace(client, headers)
    conversation = client.post("/writing/conversations", json={}, headers=headers).json()
    response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "Hello there."},
        headers=headers,
    )
    assert response.status_code == 202


def test_usage_requires_authentication(client):
    response = client.get("/ai/usage")

    assert response.status_code == 401


def test_a_fresh_account_reports_zero_usage_and_the_full_budget(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 10_000)

    response = client.get("/ai/usage", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "used_tokens": 0,
        "daily_token_cap": 10_000,
        "remaining_tokens": 10_000,
        "window_hours": 24.0,
    }


def test_uploading_a_document_alone_records_nothing(client, auth_headers, monkeypatch):
    """The upload request only *checks* the cap - its estimate is not real usage, and the Work
    Item that actually spends the tokens has not run yet (2026-10-23 split).
    """
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 10_000)
    workspace = _create_workspace(client, auth_headers)
    _upload_document(client, auth_headers, workspace["project"]["project_id"])

    assert client.get("/ai/usage", headers=auth_headers).json()["used_tokens"] == 0


def test_processing_records_the_providers_exact_reported_usage(
    client, db_engine, tmp_path, auth_headers, monkeypatch
):
    """Two provider calls happen during processing (one classification, one embedding batch),
    reporting 140 and 7 tokens - the ledger must hold exactly that, not the upload-time estimate.
    """
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 10_000)
    workspace = _create_workspace(client, auth_headers)
    _upload_document(client, auth_headers, workspace["project"]["project_id"])

    _process_next_work_item(db_engine, tmp_path)

    body = client.get("/ai/usage", headers=auth_headers).json()
    assert body["used_tokens"] == 147
    assert body["remaining_tokens"] == 10_000 - 147


def test_a_chat_reply_records_every_multi_pass_call_against_the_conversation_owner(
    client, db_engine, tmp_path, auth_headers, monkeypatch
):
    """Draft -> critique -> revise is three provider calls, and the worker has no request context
    to read a user from - it resolves the owner through conversation -> agent -> user. Both the
    attribution and the multi-call total are asserted here, since neither is covered by the
    document path.
    """
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 10_000)
    _send_chat_message(client, auth_headers)

    provider = ReportingChatProvider()
    _process_next_chat_work_item(db_engine, tmp_path, text_provider=provider)

    assert provider.calls == 3
    body = client.get("/ai/usage", headers=auth_headers).json()
    assert body["used_tokens"] == 3 * 140
    assert body["remaining_tokens"] == 10_000 - 420


def test_a_chat_reply_that_fails_mid_generation_still_records_the_draft_it_paid_for(
    client, db_engine, tmp_path, auth_headers, monkeypatch
):
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 10_000)
    _send_chat_message(client, auth_headers)

    provider = ReportingThenFailingChatProvider()
    _process_next_chat_work_item(db_engine, tmp_path, text_provider=provider)

    assert provider.calls == 2  # the failing pass reported nothing
    body = client.get("/ai/usage", headers=auth_headers).json()
    assert body["used_tokens"] == 140


def test_no_configured_cap_reports_unlimited_remaining(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", None)

    body = client.get("/ai/usage", headers=auth_headers).json()

    assert body["daily_token_cap"] is None
    assert body["remaining_tokens"] is None


def test_nothing_is_recorded_when_no_cap_is_configured(
    client, db_engine, tmp_path, auth_headers, monkeypatch
):
    """With the cap off the whole feature is off - enforcement *and* bookkeeping - so the
    endpoint reports no tracked usage rather than a partial ledger (2026-10-23).
    """
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", None)
    workspace = _create_workspace(client, auth_headers)
    _upload_document(client, auth_headers, workspace["project"]["project_id"])

    _process_next_work_item(db_engine, tmp_path)

    body = client.get("/ai/usage", headers=auth_headers).json()
    assert body["used_tokens"] == 0
    assert body["remaining_tokens"] is None
