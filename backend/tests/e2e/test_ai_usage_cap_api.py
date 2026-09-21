import io

import pytest

from app.core.config import get_settings
from app.core.dependencies import get_embedding_provider, get_text_generation_provider
from app.database.session import build_sessionmaker
from app.main import app
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item

STYLE_EXTRACTION_RESPONSE = """{"characteristics": [
  {"characteristic_type": "structure", "signal": "Short declarative sentences.", "confidence": 0.8}
]}"""


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeTextGenerationProvider:
    def generate(self, prompt: str) -> str:
        if "compacting an ongoing conversation" in prompt or "extracting durable project memory" in prompt:
            return ""
        return '[{"element_type": "concept", "label": "L", "description": "d"}]'


class FakeStyleTextGenerationProvider:
    def generate(self, prompt: str) -> str:
        return STYLE_EXTRACTION_RESPONSE


@pytest.fixture()
def fake_style_provider():
    app.dependency_overrides[get_text_generation_provider] = lambda: FakeStyleTextGenerationProvider()
    yield
    app.dependency_overrides.pop(get_text_generation_provider, None)


@pytest.fixture(autouse=True)
def _override_embedding_provider():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    yield
    app.dependency_overrides.pop(get_embedding_provider, None)


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    return response.json()


def _upload_and_process(client, db_engine, tmp_path, headers, project_id: int, content: bytes = b"Real content.") -> None:
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Doc", "format": "txt"},
        headers=headers,
    )
    assert upload.status_code == 201

    session = build_sessionmaker(db_engine)()
    try:
        assert process_one_work_item(
            session,
            text_provider=FakeTextGenerationProvider(),
            embedding_provider=FakeEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=FilesystemStorage(tmp_path / "object-store"),
        ) is True
    finally:
        session.close()


def test_document_upload_over_the_cap_returns_429(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 5)
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Content long enough to exceed a tiny cap."), "text/plain")},
        data={"title": "Doc", "format": "txt"},
        headers=auth_headers,
    )

    assert response.status_code == 429
    assert response.json()["error_type"] == "AiUsageQuotaExceededError"
    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert listing == []  # rejected before ever being stored or queued


def test_document_upload_under_the_cap_succeeds(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 1_000_000)
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Small content."), "text/plain")},
        data={"title": "Doc", "format": "txt"},
        headers=auth_headers,
    )

    assert response.status_code == 201


def test_sending_a_chat_message_over_the_cap_returns_429(client, auth_headers, monkeypatch):
    workspace = _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 5)

    response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "A message long enough that its assembled prompt exceeds a tiny cap."},
        headers=auth_headers,
    )

    assert response.status_code == 429
    assert response.json()["error_type"] == "AiUsageQuotaExceededError"


def test_sending_a_chat_message_under_the_cap_succeeds(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 1_000_000)
    workspace = _create_workspace(client, auth_headers)
    conversation = client.post("/writing/conversations", json={}, headers=auth_headers).json()

    response = client.post(
        f"/writing/conversations/{conversation['conversation_id']}/messages",
        json={"content": "Hello."},
        headers=auth_headers,
    )

    assert response.status_code == 202


def test_search_over_the_cap_returns_429(client, db_engine, tmp_path, auth_headers, monkeypatch):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    _upload_and_process(client, db_engine, tmp_path, auth_headers, project_id)
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 5)

    response = client.get(
        "/knowledge/search", params={"q": "a query long enough to exceed a tiny cap"}, headers=auth_headers
    )

    assert response.status_code == 429
    assert response.json()["error_type"] == "AiUsageQuotaExceededError"


def test_search_under_the_cap_succeeds(client, db_engine, tmp_path, auth_headers, monkeypatch):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    _upload_and_process(client, db_engine, tmp_path, auth_headers, project_id)
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 1_000_000)

    response = client.get("/knowledge/search", params={"q": "coastal erosion"}, headers=auth_headers)

    assert response.status_code == 200


def test_search_against_an_agent_with_no_embeddings_never_checks_the_cap(client, auth_headers, monkeypatch):
    """The embed() call is skipped entirely when the Agent has no embeddings yet (an existing
    short-circuit) - the usage cap must not be checked/charged for a search that never actually
    calls the AI provider.
    """
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 1)
    _create_workspace(client, auth_headers)

    response = client.get("/knowledge/search", params={"q": "anything"}, headers=auth_headers)

    assert response.status_code == 200


def test_style_extraction_over_the_cap_returns_429(client, auth_headers, monkeypatch, fake_style_provider):
    _create_workspace(client, auth_headers)
    upload = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.txt", io.BytesIO(b"A real writing sample long enough to matter."), "text/plain")},
        data={"title": "Essay", "format": "txt"},
        headers=auth_headers,
    )
    assert upload.status_code == 201
    document_id = upload.json()["document_id"]
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 5)

    response = client.post(
        "/writing/style-profile/extract", json={"document_ids": [document_id]}, headers=auth_headers
    )

    assert response.status_code == 429
    assert response.json()["error_type"] == "AiUsageQuotaExceededError"


def test_style_extraction_under_the_cap_succeeds(client, auth_headers, monkeypatch, fake_style_provider):
    _create_workspace(client, auth_headers)
    upload = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.txt", io.BytesIO(b"A real writing sample."), "text/plain")},
        data={"title": "Essay", "format": "txt"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", 1_000_000)

    response = client.post(
        "/writing/style-profile/extract", json={"document_ids": [document_id]}, headers=auth_headers
    )

    assert response.status_code == 201


def test_no_cap_configured_disables_the_check_entirely(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_daily_token_cap_per_user", None)
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"x" * 100), "text/plain")},
        data={"title": "Doc", "format": "txt"},
        headers=auth_headers,
    )

    assert response.status_code == 201
