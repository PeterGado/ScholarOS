import io

from app.auth.hashing import hash_password
from app.core.config import get_settings
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.writing.application.style_ingestion import MAX_WRITING_STYLE_SAMPLES
from app.modules.writing.infrastructure.repositories import SqlAlchemyWritingProfileRepository


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    return response.json()


def test_upload_style_document_returns_201_with_expected_schema(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"authored essay bytes"), "application/pdf")},
        data={"title": "Sample Essay", "format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Sample Essay"
    assert body["processing_status"] == "pending"
    assert body["profile_name"] == "Primary Writing Profile"
    assert "content_reference" not in body
    assert "agent_id" not in body
    assert "project_id" not in body


def test_upload_style_document_persists_content_document_and_profile(client, db_engine, tmp_path, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"authored essay bytes"), "application/pdf")},
        data={"title": "Sample Essay", "format": "pdf"},
        headers=auth_headers,
    )
    body = response.json()

    session = build_sessionmaker(db_engine)()
    try:
        documents = SqlAlchemyDocumentRepository(session)
        stored_document = documents.get_by_id(body["document_id"])
        assert stored_document is not None
        assert stored_document.title == "Sample Essay"
        assert (tmp_path / "object-store" / stored_document.content_reference).read_bytes() == b"authored essay bytes"

        profiles = SqlAlchemyWritingProfileRepository(session)
        stored_profile = profiles.get_by_id(body["profile_id"])
        assert stored_profile is not None
        assert stored_profile.name == "Primary Writing Profile"
    finally:
        session.close()


def test_second_style_upload_reuses_the_same_profile(client, auth_headers):
    _create_workspace(client, auth_headers)

    first = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay1.pdf", io.BytesIO(b"sample one"), "application/pdf")},
        data={"title": "Essay 1", "format": "pdf"},
        headers=auth_headers,
    )
    second = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay2.pdf", io.BytesIO(b"sample two"), "application/pdf")},
        data={"title": "Essay 2", "format": "pdf"},
        headers=auth_headers,
    )

    assert first.json()["profile_id"] == second.json()["profile_id"]
    assert first.json()["document_id"] != second.json()["document_id"]


def test_upload_style_document_without_authentication_returns_401(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Sample Essay", "format": "pdf"},
    )

    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidSessionError"


def test_uploading_a_style_document_over_the_size_limit_returns_413(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_size_bytes", 10)
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("too-big.pdf", io.BytesIO(b"x" * 11), "application/pdf")},
        data={"title": "Too big", "format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 413
    assert response.json()["error_type"] == "UploadTooLargeError"


def test_uploading_an_unsupported_style_document_type_returns_422(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"\xff\xfebinary garbage"), "application/pdf")},
        data={"title": "Not a real document", "format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert response.json()["error_type"] == "UnsupportedUploadFormatError"


def test_upload_style_document_for_a_user_with_no_agent_returns_404(client, auth_headers):
    """No /agents call was made for this authenticated user - AgentNotFoundForUserError, not a
    generic 500, matching the same pattern already established for GET /knowledge/search.
    """
    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Sample Essay", "format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "AgentNotFoundForUserError"


def test_style_document_upload_cannot_be_bypassed_with_another_users_ownership(client, db_engine, auth_headers):
    """Two distinct provisioned users, two distinct Writing Profiles - the second user's
    upload must never associate with the first user's profile (mirrors the document-upload
    cross-user e2e test).
    """
    _create_workspace(client, auth_headers)
    first_upload = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"owner sample"), "application/pdf")},
        data={"title": "Owner Essay", "format": "pdf"},
        headers=auth_headers,
    )

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

    intruder_upload = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"intruder sample"), "application/pdf")},
        data={"title": "Intruder Essay", "format": "pdf"},
        headers=intruder_headers,
    )

    assert intruder_upload.status_code == 201
    assert intruder_upload.json()["profile_id"] != first_upload.json()["profile_id"]
    assert intruder_upload.json()["document_id"] != first_upload.json()["document_id"]


def test_client_supplied_identity_cannot_bypass_ownership(client, auth_headers):
    """No agent_id/user_id/profile_id form field exists on this endpoint at all."""
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Sample Essay", "format": "pdf", "agent_id": "999999", "profile_id": "999999"},
        headers=auth_headers,
    )

    assert response.status_code == 201


def test_uploading_beyond_the_sample_limit_returns_409(client, auth_headers):
    _create_workspace(client, auth_headers)
    for i in range(MAX_WRITING_STYLE_SAMPLES):
        response = client.post(
            "/writing/style-profile/documents",
            files={"file": (f"essay{i}.pdf", io.BytesIO(b"sample"), "application/pdf")},
            data={"title": f"Essay {i}", "format": "pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 201

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("one-too-many.pdf", io.BytesIO(b"sample"), "application/pdf")},
        data={"title": "One too many", "format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error_type"] == "TooManyWritingStyleSamplesError"
    listing = client.get("/writing/style-profile/documents", headers=auth_headers).json()["documents"]
    assert len(listing) == MAX_WRITING_STYLE_SAMPLES


def test_deleting_a_style_sample_frees_a_slot_under_the_limit(client, auth_headers):
    """The generic document-delete endpoint is purpose-agnostic (DeleteResearchDocumentUseCase
    never checks DocumentPurpose) - this proves that reuse actually works end-to-end for style
    samples specifically, closing the one gap the live Playwright run couldn't verify reliably
    (that test's delete step was starved by an unrelated, separately-running heavy test in the
    same file contending for the single SQLite writer).
    """
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    uploaded = []
    for i in range(MAX_WRITING_STYLE_SAMPLES):
        response = client.post(
            "/writing/style-profile/documents",
            files={"file": (f"essay{i}.pdf", io.BytesIO(b"sample"), "application/pdf")},
            data={"title": f"Essay {i}", "format": "pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        uploaded.append(response.json()["document_id"])

    blocked = client.post(
        "/writing/style-profile/documents",
        files={"file": ("one-too-many.pdf", io.BytesIO(b"sample"), "application/pdf")},
        data={"title": "One too many", "format": "pdf"},
        headers=auth_headers,
    )
    assert blocked.status_code == 409

    delete_response = client.delete(f"/projects/{project_id}/documents/{uploaded[0]}", headers=auth_headers)
    assert delete_response.status_code == 204

    listing = client.get("/writing/style-profile/documents", headers=auth_headers).json()["documents"]
    assert len(listing) == MAX_WRITING_STYLE_SAMPLES - 1
    assert uploaded[0] not in {d["document_id"] for d in listing}

    retried = client.post(
        "/writing/style-profile/documents",
        files={"file": ("makes-room.pdf", io.BytesIO(b"sample"), "application/pdf")},
        data={"title": "Makes Room", "format": "pdf"},
        headers=auth_headers,
    )
    assert retried.status_code == 201


def test_upload_style_document_missing_required_form_field_is_rejected(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"data"), "application/pdf")},
        data={"title": "Missing format"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_list_style_documents_returns_previously_uploaded_samples(client, auth_headers):
    """The real gap this closes: a page reload must not lose track of what was already
    uploaded (ListWritingStyleDocumentsUseCase's own docstring).
    """
    _create_workspace(client, auth_headers)
    client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay1.pdf", io.BytesIO(b"sample one"), "application/pdf")},
        data={"title": "Essay 1", "format": "pdf"},
        headers=auth_headers,
    )
    client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay2.pdf", io.BytesIO(b"sample two"), "application/pdf")},
        data={"title": "Essay 2", "format": "pdf"},
        headers=auth_headers,
    )

    response = client.get("/writing/style-profile/documents", headers=auth_headers)

    assert response.status_code == 200
    titles = {d["title"] for d in response.json()["documents"]}
    assert titles == {"Essay 1", "Essay 2"}


def test_list_style_documents_for_a_user_with_none_uploaded_returns_empty_list(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.get("/writing/style-profile/documents", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_style_documents_never_appear_on_the_research_documents_listing(client, auth_headers):
    """The other real gap this closes: a style sample must never sit forever at `pending` on
    the Research Documents page (DocumentPurpose's own docstring).
    """
    workspace = _create_workspace(client, auth_headers)
    client.post(
        "/writing/style-profile/documents",
        files={"file": ("essay.pdf", io.BytesIO(b"sample"), "application/pdf")},
        data={"title": "Style Sample", "format": "pdf"},
        headers=auth_headers,
    )

    response = client.get(f"/projects/{workspace['project']['project_id']}/documents", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_list_style_documents_without_authentication_returns_401(client, auth_headers):
    response = client.get("/writing/style-profile/documents")

    assert response.status_code == 401


def test_list_style_documents_for_a_user_with_no_agent_returns_404(client, auth_headers):
    response = client.get("/writing/style-profile/documents", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_type"] == "AgentNotFoundForUserError"
