import io

import pytest

from app.auth.hashing import hash_password
from app.core.dependencies import get_embedding_provider
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.main import app
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item
from app.workers.models import WorkItem as WorkItemModel


class FakeEmbeddingProvider:
    """Deterministic per-text vectors - mirrors test_knowledge_search_api.py's own fake, so a
    real query text reliably retrieves a specific, real, persisted Knowledge Chunk.
    """

    _VECTORS = {
        "Coastal erosion accelerates near unprotected shorelines.": [1.0, 0.0],
        "Write the introduction.": [1.0, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        return self._VECTORS.get(text, [0.0, 0.0])


class FakeTextGenerationProvider:
    def __init__(self, response: str = "Generated introduction paragraph.") -> None:
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


@pytest.fixture(autouse=True)
def _override_embedding_provider():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    yield
    app.dependency_overrides.pop(get_embedding_provider, None)


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Coastal erosion"}, headers=headers)
    return response.json()


def _upload_and_process_research_document(client, db_engine, tmp_path, headers, project_id, content: bytes) -> None:
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Survey", "format": "txt"},
        headers=headers,
    )
    assert upload.status_code == 201

    session = build_sessionmaker(db_engine)()
    try:
        storage = FilesystemStorage(tmp_path / "object-store")
        claimed = process_one_work_item(
            session,
            text_provider=FakeTextGenerationProvider(response='{"element_type": "concept", "label": "L", "description": "d"}'),
            embedding_provider=FakeEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=storage,
        )
        assert claimed is True
    finally:
        session.close()


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


# --- Draft creation / retrieval -------------------------------------------------------------------


def test_create_draft_returns_201_with_expected_schema(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/drafts", json={"title": "Chapter 1", "target": "Chapter 1"}, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Chapter 1"
    assert body["status"] == "drafting"
    assert "agent_id" not in body


def test_create_draft_without_authentication_returns_401(client):
    response = client.post("/writing/drafts", json={"title": "Chapter 1"})
    assert response.status_code == 401


def test_create_draft_with_blank_title_returns_422(client, auth_headers):
    _create_workspace(client, auth_headers)
    response = client.post("/writing/drafts", json={"title": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_create_draft_before_any_agent_exists_returns_404(client, auth_headers):
    response = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers)
    assert response.status_code == 404


def test_list_drafts_returns_only_the_callers_own_drafts(client, auth_headers, db_engine):
    _create_workspace(client, auth_headers)
    client.post("/writing/drafts", json={"title": "Mine"}, headers=auth_headers)

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)
    client.post("/writing/drafts", json={"title": "Not mine"}, headers=intruder_headers)

    response = client.get("/writing/drafts", headers=auth_headers)

    assert response.status_code == 200
    assert [d["title"] for d in response.json()["drafts"]] == ["Mine"]


def test_get_draft_returns_the_requested_draft(client, auth_headers):
    _create_workspace(client, auth_headers)
    created = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    response = client.get(f"/writing/drafts/{created['draft_id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["draft_id"] == created["draft_id"]


def test_get_nonexistent_draft_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)
    response = client.get("/writing/drafts/999999", headers=auth_headers)
    assert response.status_code == 404


def test_get_another_users_draft_returns_404(client, auth_headers, db_engine):
    _create_workspace(client, auth_headers)
    created = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder2", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder2", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)

    response = client.get(f"/writing/drafts/{created['draft_id']}", headers=intruder_headers)
    assert response.status_code == 404


# --- Full generation loop: enqueue -> Work Item -> executor -> version + evidence -------------------------------------------------------------------


def test_full_generation_loop_over_real_http_and_a_separate_worker_step(client, auth_headers, db_engine, tmp_path):
    """1. POST /agents, upload+process a real research document (real HTTP + a separate
    worker step, exactly like test_knowledge_search_api.py's own convention).
    2. POST /writing/drafts (real HTTP).
    3. POST /writing/drafts/{id}/generate (real HTTP) - enqueues a Work Item; no provider
       generation call happens inside this request (only a cheap embedding call for retrieval,
       the same thing GET /knowledge/search already does synchronously).
    4. A separate worker step (exactly what the background executor would do) claims and
       processes that Work Item against the same real database.
    5. GET /writing/drafts/{id}/versions confirms a real, evidence-linked Draft Version.
    """
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    _upload_and_process_research_document(
        client, db_engine, tmp_path, auth_headers, project_id, b"Coastal erosion accelerates near unprotected shorelines."
    )

    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    generate_response = client.post(
        f"/writing/drafts/{draft['draft_id']}/generate",
        json={"instructions": "Write the introduction."},
        headers=auth_headers,
    )
    assert generate_response.status_code == 202
    body = generate_response.json()
    assert body["draft_id"] == draft["draft_id"]
    assert body["state"] == "queued"

    session = build_sessionmaker(db_engine)()
    try:
        queued_items = session.query(WorkItemModel).filter_by(state="QUEUED").all()
        writing_items = [i for i in queued_items if i.payload_reference.startswith("generate_draft_version:")]
        assert len(writing_items) == 1
    finally:
        session.close()

    claimed = _process_next_work_item(
        db_engine, tmp_path, text_provider=FakeTextGenerationProvider(response="Generated introduction paragraph.")
    )
    assert claimed is True

    versions_response = client.get(f"/writing/drafts/{draft['draft_id']}/versions", headers=auth_headers)
    assert versions_response.status_code == 200
    versions = versions_response.json()["versions"]
    assert len(versions) == 1
    assert versions[0]["content"] == "Generated introduction paragraph."
    assert versions[0]["created_by"] == "system"
    assert len(versions[0]["evidence"]) == 1
    assert versions[0]["evidence"][0]["target_type"] == "knowledge_chunk"


def test_generate_without_authentication_returns_401(client, auth_headers):
    _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    response = client.post(f"/writing/drafts/{draft['draft_id']}/generate", json={"instructions": "Write it."})
    assert response.status_code == 401


def test_generate_against_a_draft_with_no_supporting_evidence_returns_422(client, auth_headers):
    _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    response = client.post(
        f"/writing/drafts/{draft['draft_id']}/generate", json={"instructions": "Write it."}, headers=auth_headers
    )
    assert response.status_code == 422


def test_generate_with_blank_instructions_returns_422(client, auth_headers):
    _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    response = client.post(f"/writing/drafts/{draft['draft_id']}/generate", json={"instructions": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_generate_against_a_nonexistent_draft_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)
    response = client.post(
        "/writing/drafts/999999/generate", json={"instructions": "Write it."}, headers=auth_headers
    )
    assert response.status_code == 404


def test_versions_of_a_never_generated_draft_returns_empty_list(client, auth_headers):
    _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    response = client.get(f"/writing/drafts/{draft['draft_id']}/versions", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["versions"] == []


def test_versions_of_another_users_draft_returns_404(client, auth_headers, db_engine):
    _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder3", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder3", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)

    response = client.get(f"/writing/drafts/{draft['draft_id']}/versions", headers=intruder_headers)
    assert response.status_code == 404


# --- Reviews -------------------------------------------------------------------


def _generate_one_version(client, db_engine, tmp_path, auth_headers, project_id, draft_id) -> dict:
    _upload_and_process_research_document(
        client, db_engine, tmp_path, auth_headers, project_id, b"Coastal erosion accelerates near unprotected shorelines."
    )
    client.post(f"/writing/drafts/{draft_id}/generate", json={"instructions": "Write the introduction."}, headers=auth_headers)
    _process_next_work_item(db_engine, tmp_path)
    versions = client.get(f"/writing/drafts/{draft_id}/versions", headers=auth_headers).json()["versions"]
    return versions[0]


def test_submit_review_approves_and_returns_201(client, auth_headers, db_engine, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()
    version = _generate_one_version(client, db_engine, tmp_path, auth_headers, workspace["project"]["project_id"], draft["draft_id"])

    response = client.post(
        f"/writing/drafts/{draft['draft_id']}/versions/{version['version_id']}/reviews",
        json={"outcome": "approved", "rationale": "Ready to submit."},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["outcome"] == "approved"

    draft_after = client.get(f"/writing/drafts/{draft['draft_id']}", headers=auth_headers).json()
    assert draft_after["status"] == "approved"


def test_submit_review_with_invalid_outcome_returns_422(client, auth_headers):
    _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    response = client.post(
        f"/writing/drafts/{draft['draft_id']}/versions/1/reviews",
        json={"outcome": "not-a-real-outcome"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_submit_review_against_a_nonexistent_version_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()

    response = client.post(
        f"/writing/drafts/{draft['draft_id']}/versions/999999/reviews",
        json={"outcome": "approved"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_submit_review_against_another_users_draft_returns_404(client, auth_headers, db_engine, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    draft = client.post("/writing/drafts", json={"title": "Chapter 1"}, headers=auth_headers).json()
    version = _generate_one_version(client, db_engine, tmp_path, auth_headers, workspace["project"]["project_id"], draft["draft_id"])

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder4", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder4", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)

    response = client.post(
        f"/writing/drafts/{draft['draft_id']}/versions/{version['version_id']}/reviews",
        json={"outcome": "approved"},
        headers=intruder_headers,
    )
    assert response.status_code == 404


# --- Writing-style profile view -------------------------------------------------------------------


def test_get_style_profile_before_any_upload_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)
    response = client.get("/writing/style-profile", headers=auth_headers)
    assert response.status_code == 404


def test_get_style_profile_without_authentication_returns_401(client):
    response = client.get("/writing/style-profile")
    assert response.status_code == 401


def test_get_style_profile_returns_extracted_characteristics(client, auth_headers, monkeypatch):
    from app.core import dependencies as deps

    class FakeStyleProvider:
        def generate(self, prompt: str) -> str:
            return (
                '{"characteristics": [{"characteristic_type": "structure", '
                '"signal": "Short paragraphs.", "confidence": 0.8}]}'
            )

    app.dependency_overrides[deps.get_text_generation_provider] = lambda: FakeStyleProvider()
    try:
        _create_workspace(client, auth_headers)
        upload = client.post(
            "/writing/style-profile/documents",
            files={"file": ("essay.txt", io.BytesIO(b"An authored essay."), "text/plain")},
            data={"title": "Essay", "format": "txt"},
            headers=auth_headers,
        )
        assert upload.status_code == 201
        document_id = upload.json()["document_id"]

        extract = client.post(
            "/writing/style-profile/extract", json={"document_ids": [document_id]}, headers=auth_headers
        )
        assert extract.status_code == 201

        response = client.get("/writing/style-profile", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["profile_name"] == "Primary Writing Profile"
        assert len(body["characteristics"]) == 1
        assert body["characteristics"][0]["signal"] == "Short paragraphs."
    finally:
        app.dependency_overrides.pop(deps.get_text_generation_provider, None)
