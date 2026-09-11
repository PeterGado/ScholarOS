import io

from app.auth.hashing import hash_password
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository


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
