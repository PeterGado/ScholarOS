import pytest

from app.ai.openalex import OpenAlexWork, SourceSearchUnavailableError
from app.ai.web_fetch import WebSource
from app.core.dependencies import (
    get_import_content_fetch_provider,
    get_openalex_search_provider,
    get_openalex_work_lookup_provider,
)
from app.main import app
from app.modules.document.application.use_cases import (
    MAX_RESEARCH_DOCUMENTS_PER_PROJECT,
)

_SAMPLE_WORK = OpenAlexWork(
    openalex_id="https://openalex.org/W1",
    doi="10.1000/example",
    title="A Real Paper",
    authors=("Ada Lovelace",),
    publication_year=2020,
    source_name="Journal of Examples",
    is_open_access=True,
    fetchable_url="https://example.com/paper.pdf",
    abstract="An abstract.",
)


@pytest.fixture()
def openalex_api_key(monkeypatch):
    """Every test in this file needs OPENALEX_API_KEY configured - the not-configured (503)
    case overrides it back to None explicitly instead.
    """
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "openalex_api_key", "real-key")


@pytest.fixture()
def fake_openalex_search():
    def _set(results: list[OpenAlexWork] | None = None, *, error: bool = False):
        def fake_search(query, *, api_key, limit=10):
            if error:
                raise SourceSearchUnavailableError("simulated")
            return results if results is not None else [_SAMPLE_WORK]

        app.dependency_overrides[get_openalex_search_provider] = lambda: fake_search

    yield _set
    app.dependency_overrides.pop(get_openalex_search_provider, None)


@pytest.fixture()
def fake_openalex_work_lookup():
    def _set(work: OpenAlexWork | None = _SAMPLE_WORK, *, error: bool = False):
        def fake_lookup(openalex_id, *, api_key):
            if error:
                raise SourceSearchUnavailableError("simulated")
            return work

        app.dependency_overrides[get_openalex_work_lookup_provider] = lambda: fake_lookup

    yield _set
    app.dependency_overrides.pop(get_openalex_work_lookup_provider, None)


_UNSET = object()
_DEFAULT_FETCHED_SOURCE = WebSource(url="https://example.com/paper.pdf", content="Full fetched text.")


@pytest.fixture()
def fake_import_content_fetch():
    """`web_source=None` genuinely simulates a failed fetch (the real fetch_web_source's own
    "never raise, return None on failure" contract) - distinct from the default, successful
    case, which the sentinel `_UNSET` (not a bare default parameter value) makes possible.
    """

    def _set(web_source: WebSource | object | None = _UNSET):
        result = _DEFAULT_FETCHED_SOURCE if web_source is _UNSET else web_source

        def fake_fetch(url, *, max_content_length=50_000):
            return result

        app.dependency_overrides[get_import_content_fetch_provider] = lambda: fake_fetch

    yield _set
    app.dependency_overrides.pop(get_import_content_fetch_provider, None)


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    return response.json()


# --- GET /projects/source-search ---------------------------------------------------------------


def test_search_returns_real_shaped_results(client, auth_headers, openalex_api_key, fake_openalex_search):
    fake_openalex_search()

    response = client.get("/projects/source-search", params={"query": "test"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["openalex_id"] == "https://openalex.org/W1"
    assert result["title"] == "A Real Paper"
    assert result["authors"] == ["Ada Lovelace"]
    assert result["has_fetchable_full_text"] is True


def test_search_without_configuration_returns_503(client, auth_headers, fake_openalex_search):
    fake_openalex_search()

    response = client.get("/projects/source-search", params={"query": "test"}, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["error_type"] == "SourceSearchNotConfiguredError"


def test_search_when_openalex_fails_returns_503(client, auth_headers, openalex_api_key, fake_openalex_search):
    fake_openalex_search(error=True)

    response = client.get("/projects/source-search", params={"query": "test"}, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["error_type"] == "SourceSearchFailedError"


def test_search_requires_authentication(client, openalex_api_key, fake_openalex_search):
    fake_openalex_search()

    response = client.get("/projects/source-search", params={"query": "test"})

    assert response.status_code == 401


def test_search_with_an_empty_query_is_rejected(client, auth_headers, openalex_api_key, fake_openalex_search):
    fake_openalex_search()

    response = client.get("/projects/source-search", params={"query": ""}, headers=auth_headers)

    assert response.status_code == 422


# --- POST /projects/{project_id}/documents/import -----------------------------------------------


def test_import_creates_a_real_research_document(
    client, auth_headers, openalex_api_key, fake_openalex_work_lookup, fake_import_content_fetch
):
    fake_openalex_work_lookup()
    fake_import_content_fetch()
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import", json={"openalex_id": "W1"}, headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "A Real Paper"
    assert body["author"] == "Ada Lovelace"
    assert body["publication_year"] == 2020
    assert body["doi"] == "10.1000/example"
    assert body["format"] == "txt"
    assert body["processing_status"] == "pending"

    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert len(listing) == 1


def test_import_falls_back_to_abstract_when_fetch_fails(
    client, auth_headers, openalex_api_key, fake_openalex_work_lookup, fake_import_content_fetch
):
    fake_openalex_work_lookup()
    fake_import_content_fetch(web_source=None)
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import", json={"openalex_id": "W1"}, headers=auth_headers
    )

    assert response.status_code == 201


def test_import_of_a_source_with_nothing_available_is_rejected(
    client, auth_headers, openalex_api_key, fake_openalex_work_lookup
):
    empty_work = OpenAlexWork(
        openalex_id="https://openalex.org/W2",
        doi=None,
        title="Nothing Available",
        authors=(),
        publication_year=None,
        source_name=None,
        is_open_access=False,
        fetchable_url=None,
        abstract=None,
    )
    fake_openalex_work_lookup(work=empty_work)
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import", json={"openalex_id": "W2"}, headers=auth_headers
    )

    assert response.status_code == 422
    assert response.json()["error_type"] == "ExternalSourceHasNoContentError"


def test_import_of_an_unresolvable_source_returns_404(
    client, auth_headers, openalex_api_key, fake_openalex_work_lookup
):
    fake_openalex_work_lookup(work=None)
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import", json={"openalex_id": "W-missing"}, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error_type"] == "ExternalSourceNotFoundError"


def test_import_without_configuration_returns_503(client, auth_headers, fake_openalex_work_lookup):
    fake_openalex_work_lookup()
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import", json={"openalex_id": "W1"}, headers=auth_headers
    )

    assert response.status_code == 503
    assert response.json()["error_type"] == "SourceSearchNotConfiguredError"


def test_import_against_a_project_not_owned_by_the_caller_returns_404(
    client, auth_headers, openalex_api_key, fake_openalex_work_lookup, fake_import_content_fetch
):
    fake_openalex_work_lookup()
    fake_import_content_fetch()

    response = client.post("/projects/999/documents/import", json={"openalex_id": "W1"}, headers=auth_headers)

    assert response.status_code == 404


def test_import_beyond_the_per_project_limit_returns_409(
    client, auth_headers, openalex_api_key, fake_openalex_work_lookup, fake_import_content_fetch
):
    fake_openalex_work_lookup()
    fake_import_content_fetch()
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]
    for i in range(MAX_RESEARCH_DOCUMENTS_PER_PROJECT):
        client.post(
            f"/projects/{project_id}/documents",
            files={"file": (f"doc{i}.txt", f"content {i}".encode())},
            data={"title": f"Doc {i}", "format": "txt"},
            headers=auth_headers,
        )

    response = client.post(
        f"/projects/{project_id}/documents/import", json={"openalex_id": "W1"}, headers=auth_headers
    )

    assert response.status_code == 409
