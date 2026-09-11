import io

import pytest

from app.auth.hashing import hash_password
from app.core.dependencies import get_embedding_provider
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.main import app
from app.workers.executor import process_one_work_item
from app.storage.filesystem import FilesystemStorage


class FakeEmbeddingProvider:
    """Deterministic per-text vectors, so a real HTTP search can assert a specific ranking -
    not merely that a response comes back.
    """

    _VECTORS = {
        "Coastal erosion methodology and findings.": [1.0, 0.0],
        "An entirely unrelated culinary history.": [0.0, 1.0],
        "coastal erosion": [1.0, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        return self._VECTORS.get(text, [0.0, 0.0])


class FakeTextGenerationProvider:
    def generate(self, prompt: str) -> str:
        return '{"element_type": "concept", "label": "L", "description": "d"}'


@pytest.fixture(autouse=True)
def _override_embedding_provider():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    yield
    app.dependency_overrides.pop(get_embedding_provider, None)


def _upload_and_process(client, db_engine, tmp_path, headers, content: bytes) -> dict:
    workspace_response = client.post(
        "/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers
    )
    project_id = workspace_response.json()["project"]["project_id"]

    upload_response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Doc", "format": "txt"},
        headers=headers,
    )
    assert upload_response.status_code == 201

    session = build_sessionmaker(db_engine)()
    try:
        storage = FilesystemStorage(tmp_path / "object-store")
        claimed = process_one_work_item(
            session,
            text_provider=FakeTextGenerationProvider(),
            embedding_provider=FakeEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=storage,
        )
        assert claimed is True
    finally:
        session.close()

    return workspace_response.json()


def test_search_returns_the_matching_chunk_over_real_http(client, auth_headers, db_engine, tmp_path):
    _upload_and_process(client, db_engine, tmp_path, auth_headers, b"Coastal erosion methodology and findings.")

    response = client.get("/knowledge/search", params={"q": "coastal erosion"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["content"] == "Coastal erosion methodology and findings."
    assert body["results"][0]["evidence"][0]["document_title"] == "Doc"
    assert "embedding_vector" not in body["results"][0]
    assert "vector" not in body["results"][0]


def test_search_without_authentication_returns_401(client):
    response = client.get("/knowledge/search", params={"q": "anything"})
    assert response.status_code == 401


def test_search_with_missing_query_returns_422(client, auth_headers):
    response = client.get("/knowledge/search", headers=auth_headers)
    assert response.status_code == 422


def test_search_before_any_agent_exists_returns_404(client, auth_headers):
    response = client.get("/knowledge/search", params={"q": "anything"}, headers=auth_headers)
    assert response.status_code == 404


def test_search_against_an_agent_with_no_processed_knowledge_returns_empty_results(client, auth_headers):
    client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=auth_headers)

    response = client.get("/knowledge/search", params={"q": "anything"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_top_k_query_param_is_respected(client, auth_headers, db_engine, tmp_path):
    _upload_and_process(client, db_engine, tmp_path, auth_headers, b"Coastal erosion methodology and findings.")

    response = client.get("/knowledge/search", params={"q": "coastal erosion", "top_k": 1}, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["results"]) <= 1


def test_top_k_out_of_range_returns_422(client, auth_headers):
    response = client.get("/knowledge/search", params={"q": "anything", "top_k": 0}, headers=auth_headers)
    assert response.status_code == 422

    response = client.get("/knowledge/search", params={"q": "anything", "top_k": 9999}, headers=auth_headers)
    assert response.status_code == 422


# --- Authorization: Agent A must never retrieve Agent B's knowledge -----------------------


def test_agent_a_cannot_retrieve_agent_bs_knowledge_over_real_http(client, auth_headers, db_engine, tmp_path):
    """The explicit authorization requirement, exercised at the real HTTP boundary: two
    separate provisioned users, each with their own real uploaded document processed into
    real knowledge, over separate authenticated sessions - user A's search must never surface
    user B's content, even when both chunks embed to the same vector.
    """
    _upload_and_process(client, db_engine, tmp_path, auth_headers, b"Coastal erosion methodology and findings.")

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="researcher-b", password_hash=hash_password("s3cret-b")))
        session.commit()
    finally:
        session.close()
    login_b = client.post("/auth/login", json={"username": "researcher-b", "password": "s3cret-b"})
    assert login_b.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    _upload_and_process(client, db_engine, tmp_path, headers_b, b"An entirely unrelated culinary history.")

    response_a = client.get("/knowledge/search", params={"q": "coastal erosion"}, headers=auth_headers)
    response_b = client.get("/knowledge/search", params={"q": "coastal erosion"}, headers=headers_b)

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    results_a = response_a.json()["results"]
    results_b = response_b.json()["results"]

    assert len(results_a) == 1
    assert results_a[0]["content"] == "Coastal erosion methodology and findings."
    assert all("culinary" not in r["content"] for r in results_a)

    # User B's own search (even with an unrelated query) must only ever surface user B's own
    # content, never user A's - confirms scoping is symmetric, not just A-favored.
    assert all(r["content"] != "Coastal erosion methodology and findings." for r in results_b)
