import io

import pytest

from app.auth.hashing import hash_password
from app.core.dependencies import get_text_generation_provider
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.main import app

VALID_RESPONSE = """{"characteristics": [
  {"characteristic_type": "structure", "signal": "Short declarative sentences.", "confidence": 0.8},
  {"characteristic_type": "vocabulary", "signal": "Frequent technical terminology."}
]}"""


class FakeTextGenerationProvider:
    def __init__(self, response: str | None = None, exception: Exception | None = None):
        self.response = response if response is not None else VALID_RESPONSE
        self.exception = exception

    def generate(self, prompt: str) -> str:
        if self.exception is not None:
            raise self.exception
        return self.response


@pytest.fixture()
def fake_provider():
    provider = FakeTextGenerationProvider()
    app.dependency_overrides[get_text_generation_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_text_generation_provider, None)


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    return response.json()


def _upload_style_document(client, headers, *, filename="essay.txt", title="Essay", content=b"authored sample") -> dict:
    response = client.post(
        "/writing/style-profile/documents",
        files={"file": (filename, io.BytesIO(content), "text/plain")},
        data={"title": title, "format": "txt"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_extraction_returns_201_with_expected_schema(client, auth_headers, fake_provider):
    _create_workspace(client, auth_headers)
    uploaded = _upload_style_document(client, auth_headers)

    response = client.post(
        "/writing/style-profile/extract",
        json={"document_ids": [uploaded["document_id"]]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["profile_id"] == uploaded["profile_id"]
    assert len(body["characteristics"]) == 2
    for characteristic in body["characteristics"]:
        assert characteristic["source_document_ids"] == [uploaded["document_id"]]
        assert characteristic["characteristic_type"] in {"structure", "vocabulary", "transitions", "explanation", "citation"}


def test_extraction_without_authentication_returns_401(client, auth_headers, fake_provider):
    _create_workspace(client, auth_headers)
    uploaded = _upload_style_document(client, auth_headers)

    response = client.post("/writing/style-profile/extract", json={"document_ids": [uploaded["document_id"]]})

    assert response.status_code == 401


def test_extraction_with_no_document_ids_returns_422(client, auth_headers, fake_provider):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/style-profile/extract", json={"document_ids": []}, headers=auth_headers)

    assert response.status_code == 422


def test_extraction_with_a_document_id_belonging_to_another_user_returns_404(client, db_engine, auth_headers, fake_provider):
    _create_workspace(client, auth_headers)
    uploaded = _upload_style_document(client, auth_headers)

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Intruder Thesis", "project_topic": "Other"}, headers=intruder_headers)

    response = client.post(
        "/writing/style-profile/extract", json={"document_ids": [uploaded["document_id"]]}, headers=intruder_headers
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "InvalidStyleSampleReferenceError"


def test_extraction_for_user_with_no_agent_returns_404(client, auth_headers, fake_provider):
    response = client.post("/writing/style-profile/extract", json={"document_ids": [1]}, headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_type"] == "AgentNotFoundForUserError"


def test_provider_failure_returns_502(client, auth_headers):
    from app.ai.exceptions import ProviderRequestError

    app.dependency_overrides[get_text_generation_provider] = lambda: FakeTextGenerationProvider(
        exception=ProviderRequestError("simulated outage")
    )
    try:
        _create_workspace(client, auth_headers)
        uploaded = _upload_style_document(client, auth_headers)

        response = client.post(
            "/writing/style-profile/extract", json={"document_ids": [uploaded["document_id"]]}, headers=auth_headers
        )

        assert response.status_code == 502
    finally:
        app.dependency_overrides.pop(get_text_generation_provider, None)


def test_second_extraction_returns_409(client, auth_headers, fake_provider):
    _create_workspace(client, auth_headers)
    uploaded = _upload_style_document(client, auth_headers)

    first = client.post(
        "/writing/style-profile/extract", json={"document_ids": [uploaded["document_id"]]}, headers=auth_headers
    )
    assert first.status_code == 201

    second = client.post(
        "/writing/style-profile/extract", json={"document_ids": [uploaded["document_id"]]}, headers=auth_headers
    )
    assert second.status_code == 409
    assert second.json()["error_type"] == "WritingProfileAlreadyExtractedError"


def test_malformed_provider_response_returns_400(client, auth_headers):
    app.dependency_overrides[get_text_generation_provider] = lambda: FakeTextGenerationProvider(response="not json")
    try:
        _create_workspace(client, auth_headers)
        uploaded = _upload_style_document(client, auth_headers)

        response = client.post(
            "/writing/style-profile/extract", json={"document_ids": [uploaded["document_id"]]}, headers=auth_headers
        )

        assert response.status_code == 400
        assert response.json()["error_type"] == "StyleExtractionError"
    finally:
        app.dependency_overrides.pop(get_text_generation_provider, None)
