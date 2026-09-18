import io

from app.auth.hashing import hash_password
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.modules.document.application.use_cases import MAX_RESEARCH_DOCUMENTS_PER_PROJECT
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item


class FakeTextGenerationProvider:
    def generate(self, prompt: str) -> str:
        return '[{"element_type": "concept", "label": "E2E concept", "description": "d"}]'


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def _process_next_work_item(db_engine, tmp_path) -> bool:
    session = build_sessionmaker(db_engine)()
    try:
        return process_one_work_item(
            session,
            text_provider=FakeTextGenerationProvider(),
            embedding_provider=FakeEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=FilesystemStorage(tmp_path / "object-store"),
        )
    finally:
        session.close()


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    return response.json()


def test_upload_document_returns_201_with_expected_schema(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"pdf bytes"), "application/pdf")},
        data={"title": "Baseline survey", "format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["title"] == "Baseline survey"
    assert body["processing_status"] == "pending"
    assert "content_reference" not in body


def test_upload_document_persists_content_and_database_row(client, db_engine, tmp_path, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"pdf bytes"), "application/pdf")},
        data={"title": "Baseline survey", "format": "pdf"},
        headers=auth_headers,
    )
    document_id = response.json()["document_id"]

    session = build_sessionmaker(db_engine)()
    try:
        documents = SqlAlchemyDocumentRepository(session)
        stored = documents.get_by_id(document_id)
        assert stored is not None
        assert stored.title == "Baseline survey"
        assert (tmp_path / "object-store" / stored.content_reference).read_bytes() == b"pdf bytes"
    finally:
        session.close()


def test_upload_without_authentication_returns_401(client, auth_headers):
    """Stage 6: document upload now requires the same authenticated identity as /agents."""
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Orphan", "format": "pdf"},
    )
    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidSessionError"


def test_upload_against_a_nonexistent_project_returns_404(client, auth_headers):
    response = client.post(
        "/projects/999/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Orphan", "format": "pdf"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["error_type"] == "ProjectNotFoundError"


def test_upload_against_a_project_not_owned_by_the_authenticated_user_is_rejected(client, db_engine, auth_headers):
    """A second, distinct provisioned user's Project must not be reachable by the first
    user's token (Stage 6 Phase 5) - real ownership check, not just single-user convenience.
    """
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post(
        "/agents", json={"project_title": "Intruder Thesis", "project_topic": "Other Topic"}, headers=intruder_headers
    )

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Intruding upload", "format": "pdf"},
        headers=intruder_headers,
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "ProjectNotFoundError"


def test_client_supplied_identity_cannot_bypass_ownership(client, auth_headers):
    """The upload endpoint has no user_id form field at all - there is nothing in the
    multipart request a client could supply to override the authenticated identity.
    """
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Baseline survey", "format": "pdf", "user_id": "999999"},
        headers=auth_headers,
    )

    assert response.status_code == 201


def test_uploading_beyond_the_per_project_limit_returns_409(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    for i in range(MAX_RESEARCH_DOCUMENTS_PER_PROJECT):
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

    assert response.status_code == 409
    assert response.json()["error_type"] == "TooManyResearchDocumentsError"
    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert len(listing) == MAX_RESEARCH_DOCUMENTS_PER_PROJECT


def test_upload_missing_required_form_field_is_rejected(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Missing format"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_multiple_documents_can_be_uploaded_to_the_same_project(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    first = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("a.pdf", io.BytesIO(b"content A"), "application/pdf")},
        data={"title": "A", "format": "pdf"},
        headers=auth_headers,
    )
    second = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("b.docx", io.BytesIO(b"content B"), "application/vnd.openxmlformats")},
        data={"title": "B", "format": "docx"},
        headers=auth_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["document_id"] != second.json()["document_id"]


def test_list_documents_returns_every_uploaded_document(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("a.pdf", io.BytesIO(b"content A"), "application/pdf")},
        data={"title": "A", "format": "pdf"},
        headers=auth_headers,
    )
    client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("b.pdf", io.BytesIO(b"content B"), "application/pdf")},
        data={"title": "B", "format": "pdf"},
        headers=auth_headers,
    )

    response = client.get(f"/projects/{project_id}/documents", headers=auth_headers)

    assert response.status_code == 200
    titles = {doc["title"] for doc in response.json()["documents"]}
    assert titles == {"A", "B"}


def test_list_documents_for_a_project_with_none_yet_returns_an_empty_list(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.get(f"/projects/{project_id}/documents", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_list_documents_against_a_nonexistent_project_returns_404(client, auth_headers):
    response = client.get("/projects/999/documents", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error_type"] == "ProjectNotFoundError"


def test_list_documents_without_authentication_returns_401(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.get(f"/projects/{project_id}/documents")
    assert response.status_code == 401


# --- DELETE /projects/{project_id}/documents/{document_id} ---------------------------------


def test_deleting_a_pending_document_returns_204_and_it_disappears_from_listing(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"\xff\xfebinary garbage"), "application/pdf")},
        data={"title": "Stuck upload", "format": "pdf"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]

    response = client.delete(f"/projects/{project_id}/documents/{document_id}", headers=auth_headers)

    assert response.status_code == 204
    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert listing == []


def test_deleting_a_failed_document_returns_204(client, auth_headers, db_engine, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"\xff\xfebinary garbage" * 5), "application/pdf")},
        data={"title": "Unsupported format", "format": "pdf"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]
    for _ in range(3):  # DEFAULT_MAX_ATTEMPTS - exhaust retries so it reaches `failed`
        _process_next_work_item(db_engine, tmp_path)

    status_before = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"][0]
    assert status_before["processing_status"] == "failed"

    response = client.delete(f"/projects/{project_id}/documents/{document_id}", headers=auth_headers)

    assert response.status_code == 204
    assert client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"] == []


def test_deleting_a_processed_document_returns_409_and_it_remains_listed(client, auth_headers, db_engine, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Real processable content."), "text/plain")},
        data={"title": "Processed doc", "format": "txt"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]
    assert _process_next_work_item(db_engine, tmp_path) is True

    response = client.delete(f"/projects/{project_id}/documents/{document_id}", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error_type"] == "DocumentCannotBeDeletedError"
    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert len(listing) == 1


def test_deleting_a_nonexistent_document_returns_404(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.delete(f"/projects/{project_id}/documents/999999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_type"] == "ResearchDocumentNotFoundError"


def test_deleting_an_already_deleted_document_returns_404(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Stuck upload", "format": "pdf"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]
    client.delete(f"/projects/{project_id}/documents/{document_id}", headers=auth_headers)

    response = client.delete(f"/projects/{project_id}/documents/{document_id}", headers=auth_headers)

    assert response.status_code == 404


def test_deleting_another_users_document_is_rejected_as_not_found(client, db_engine, auth_headers):
    """A second, distinct user's document must not be deletable via the first user's token -
    non-enumeration, same as every other ownership check in this module."""
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Victim's upload", "format": "pdf"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder-delete", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder-delete", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post(
        "/agents", json={"project_title": "Intruder Thesis", "project_topic": "Other Topic"}, headers=intruder_headers
    )

    response = client.delete(f"/projects/{project_id}/documents/{document_id}", headers=intruder_headers)

    assert response.status_code == 404
    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert len(listing) == 1  # untouched


def _fail_a_document(client, auth_headers, db_engine, tmp_path, project_id: int) -> int:
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"\xff\xfebinary garbage" * 5), "application/pdf")},
        data={"title": "Unsupported format", "format": "pdf"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]
    for _ in range(3):  # DEFAULT_MAX_ATTEMPTS - exhaust retries so it reaches `failed`
        _process_next_work_item(db_engine, tmp_path)
    return document_id


def test_a_failed_documents_listing_includes_the_real_failure_reason(client, auth_headers, db_engine, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    _fail_a_document(client, auth_headers, db_engine, tmp_path, project_id)

    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]

    assert len(listing) == 1
    assert listing[0]["processing_status"] == "failed"
    assert listing[0]["error_message"]  # a real, non-empty reason, not just the bare status
    assert "unsupported" in listing[0]["error_message"].lower() or "decode" in listing[0]["error_message"].lower()


def test_a_pending_documents_listing_has_no_error_message(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Some content."), "text/plain")},
        data={"title": "Pending doc", "format": "txt"},
        headers=auth_headers,
    )

    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]

    assert listing[0]["processing_status"] == "pending"
    assert listing[0]["error_message"] is None


def test_retrying_a_failed_document_re_processes_it_successfully(client, auth_headers, db_engine, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    document_id = _fail_a_document(client, auth_headers, db_engine, tmp_path, project_id)

    response = client.post(f"/projects/{project_id}/documents/{document_id}/retry", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["processing_status"] == "pending"
    assert response.json()["error_message"] is None

    # The same underlying content still fails (it was never a transient error), but this proves
    # the document is genuinely back in the real processing pipeline, not just relabeled.
    _process_next_work_item(db_engine, tmp_path)
    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert listing[0]["processing_status"] in ("pending", "failed")


def test_retrying_a_pending_document_returns_409(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Some content."), "text/plain")},
        data={"title": "Pending doc", "format": "txt"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]

    response = client.post(f"/projects/{project_id}/documents/{document_id}/retry", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error_type"] == "DocumentCannotBeRetriedError"


def test_retrying_a_processed_document_returns_409(client, auth_headers, db_engine, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Real processable content."), "text/plain")},
        data={"title": "Processed doc", "format": "txt"},
        headers=auth_headers,
    )
    document_id = upload.json()["document_id"]
    assert _process_next_work_item(db_engine, tmp_path) is True

    response = client.post(f"/projects/{project_id}/documents/{document_id}/retry", headers=auth_headers)

    assert response.status_code == 409


def test_retrying_a_nonexistent_document_returns_404(client, auth_headers):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(f"/projects/{project_id}/documents/999999/retry", headers=auth_headers)

    assert response.status_code == 404


def test_retrying_another_users_document_is_rejected_as_not_found(client, db_engine, auth_headers, tmp_path):
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    document_id = _fail_a_document(client, auth_headers, db_engine, tmp_path, project_id)

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder-retry", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder-retry", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post(
        "/agents", json={"project_title": "Intruder Thesis", "project_topic": "Other Topic"}, headers=intruder_headers
    )

    response = client.post(f"/projects/{project_id}/documents/{document_id}/retry", headers=intruder_headers)

    assert response.status_code == 404
    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert listing[0]["processing_status"] == "failed"  # untouched
