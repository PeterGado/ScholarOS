import pytest

from app.ai.tavily import WebSearchResult, WebSearchUnavailableError
from app.ai.web_fetch import WebSource
from app.core.dependencies import (
    get_import_content_fetch_provider,
    get_tavily_search_provider,
)
from app.main import app
from app.modules.document.application.use_cases import (
    MAX_RESEARCH_DOCUMENTS_PER_PROJECT,
)

_SAMPLE_RESULT = WebSearchResult(
    url="https://example.com/article",
    title="A Real Article",
    snippet="A real snippet.",
)


@pytest.fixture()
def tavily_api_key(monkeypatch):
    """Every test in this file needs TAVILY_API_KEY configured - the not-configured (503) case
    overrides it back to None explicitly instead.
    """
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "tavily_api_key", "real-key")


@pytest.fixture()
def fake_tavily_search():
    def _set(results: list[WebSearchResult] | None = None, *, error: bool = False):
        def fake_search(query, *, api_key, limit=10):
            if error:
                raise WebSearchUnavailableError("simulated")
            return results if results is not None else [_SAMPLE_RESULT]

        app.dependency_overrides[get_tavily_search_provider] = lambda: fake_search

    yield _set
    app.dependency_overrides.pop(get_tavily_search_provider, None)


_UNSET = object()
_DEFAULT_FETCHED_SOURCE = WebSource(url="https://example.com/article", content="Full fetched text.")


@pytest.fixture()
def fake_import_content_fetch():
    """`web_source=None` genuinely simulates a failed fetch - distinct from the default,
    successful case, which the sentinel `_UNSET` (not a bare default parameter value) makes
    possible. Mirrors test_external_source_search_api.py's own fixture exactly - this is the
    same underlying DI seam (get_import_content_fetch_provider), reused by
    ImportWebSearchResultUseCase.
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


# --- GET /projects/web-search -------------------------------------------------------------------


def test_search_returns_real_shaped_results(client, auth_headers, tavily_api_key, fake_tavily_search):
    fake_tavily_search()

    response = client.get("/projects/web-search", params={"query": "test"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["url"] == "https://example.com/article"
    assert result["title"] == "A Real Article"
    assert result["snippet"] == "A real snippet."


def test_search_without_configuration_returns_503(client, auth_headers, fake_tavily_search):
    fake_tavily_search()

    response = client.get("/projects/web-search", params={"query": "test"}, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["error_type"] == "SourceSearchNotConfiguredError"


def test_search_when_tavily_fails_returns_503(client, auth_headers, tavily_api_key, fake_tavily_search):
    fake_tavily_search(error=True)

    response = client.get("/projects/web-search", params={"query": "test"}, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["error_type"] == "SourceSearchFailedError"


def test_search_requires_authentication(client, tavily_api_key, fake_tavily_search):
    fake_tavily_search()

    response = client.get("/projects/web-search", params={"query": "test"})

    assert response.status_code == 401


def test_search_with_an_empty_query_is_rejected(client, auth_headers, tavily_api_key, fake_tavily_search):
    fake_tavily_search()

    response = client.get("/projects/web-search", params={"query": ""}, headers=auth_headers)

    assert response.status_code == 422


# --- POST /projects/{project_id}/documents/import-web -------------------------------------------


def test_import_creates_a_real_research_document(client, auth_headers, fake_import_content_fetch):
    fake_import_content_fetch()
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import-web",
        json={"url": "https://example.com/article", "title": "A Real Article"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "A Real Article"
    assert body["source"] == "https://example.com/article"
    assert body["format"] == "txt"
    assert body["processing_status"] == "pending"

    listing = client.get(f"/projects/{project_id}/documents", headers=auth_headers).json()["documents"]
    assert len(listing) == 1


def test_import_of_an_unfetchable_page_is_rejected(client, auth_headers, fake_import_content_fetch):
    fake_import_content_fetch(web_source=None)
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import-web",
        json={"url": "https://example.com/dead", "title": "Dead Page"},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert response.json()["error_type"] == "WebPageFetchFailedError"


def test_import_requires_a_non_empty_url(client, auth_headers, fake_import_content_fetch):
    fake_import_content_fetch()
    workspace = _create_workspace(client, auth_headers)
    project_id = workspace["project"]["project_id"]

    response = client.post(
        f"/projects/{project_id}/documents/import-web",
        json={"url": "", "title": "Title"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_import_against_a_project_not_owned_by_the_caller_returns_404(
    client, auth_headers, fake_import_content_fetch
):
    fake_import_content_fetch()

    response = client.post(
        "/projects/999/documents/import-web",
        json={"url": "https://example.com/article", "title": "Title"},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_import_beyond_the_per_project_limit_returns_409(client, auth_headers, fake_import_content_fetch):
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
        f"/projects/{project_id}/documents/import-web",
        json={"url": "https://example.com/article", "title": "Title"},
        headers=auth_headers,
    )

    assert response.status_code == 409
