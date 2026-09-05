import io

from app.database.session import build_sessionmaker
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository


def _create_workspace(client) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"})
    return response.json()


def test_upload_document_returns_201_with_expected_schema(client):
    workspace = _create_workspace(client)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"pdf bytes"), "application/pdf")},
        data={"title": "Baseline survey", "format": "pdf"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["title"] == "Baseline survey"
    assert body["processing_status"] == "pending"
    assert "content_reference" not in body


def test_upload_document_persists_content_and_database_row(client, db_engine, tmp_path):
    workspace = _create_workspace(client)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"pdf bytes"), "application/pdf")},
        data={"title": "Baseline survey", "format": "pdf"},
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


def test_upload_against_a_nonexistent_project_returns_404(client):
    response = client.post(
        "/projects/999/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Orphan", "format": "pdf"},
    )
    assert response.status_code == 404
    assert response.json()["error_type"] == "ProjectNotFoundError"


def test_upload_missing_required_form_field_is_rejected(client):
    workspace = _create_workspace(client)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Missing format"},
    )
    assert response.status_code == 422


def test_multiple_documents_can_be_uploaded_to_the_same_project(client):
    workspace = _create_workspace(client)
    project_id = workspace["project"]["project_id"]

    first = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("a.pdf", io.BytesIO(b"content A"), "application/pdf")},
        data={"title": "A", "format": "pdf"},
    )
    second = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("b.docx", io.BytesIO(b"content B"), "application/vnd.openxmlformats")},
        data={"title": "B", "format": "docx"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["document_id"] != second.json()["document_id"]
