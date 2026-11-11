import httpx
import pytest

from app.ai.openalex import (
    SourceSearchUnavailableError,
    get_openalex_work_by_id,
    search_openalex_works,
)

_RAW_WORK = {
    "id": "https://openalex.org/W123",
    "doi": "https://doi.org/10.1000/example",
    "title": "A Real Paper Title",
    "publication_year": 2023,
    "authorships": [
        {"author": {"display_name": "Ada Lovelace"}},
        {"author": {"display_name": "Alan Turing"}},
        {"author": {}},  # missing display_name - must be skipped, not crash
    ],
    "primary_location": {
        "pdf_url": "https://example.com/paper.pdf",
        "source": {"display_name": "Journal of Examples"},
    },
    "open_access": {"is_oa": True, "oa_url": "https://example.com/landing"},
    "abstract_inverted_index": {"This": [0], "is": [1], "an": [2], "abstract.": [3]},
}


def _client_for(status: int, body: dict | list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_parses_a_real_shaped_result():
    client = _client_for(200, {"results": [_RAW_WORK]})

    results = search_openalex_works("query", api_key="key", client=client)

    assert len(results) == 1
    work = results[0]
    assert work.openalex_id == "https://openalex.org/W123"
    assert work.doi == "10.1000/example"
    assert work.title == "A Real Paper Title"
    assert work.authors == ("Ada Lovelace", "Alan Turing")
    assert work.publication_year == 2023
    assert work.source_name == "Journal of Examples"
    assert work.is_open_access is True
    assert work.fetchable_url == "https://example.com/paper.pdf"
    assert work.abstract == "This is an abstract."


def test_search_prefers_pdf_url_over_oa_url():
    assert _RAW_WORK["primary_location"]["pdf_url"] == "https://example.com/paper.pdf"


def test_search_falls_back_to_oa_url_when_no_pdf_url():
    raw = dict(_RAW_WORK)
    raw["primary_location"] = {"source": {"display_name": "Journal of Examples"}}
    client = _client_for(200, {"results": [raw]})

    results = search_openalex_works("query", api_key="key", client=client)

    assert results[0].fetchable_url == "https://example.com/landing"


def test_search_handles_no_open_access_location_at_all():
    raw = dict(_RAW_WORK)
    raw["primary_location"] = {}
    raw["open_access"] = {"is_oa": False}
    client = _client_for(200, {"results": [raw]})

    results = search_openalex_works("query", api_key="key", client=client)

    assert results[0].fetchable_url is None
    assert results[0].is_open_access is False


def test_search_handles_no_abstract():
    raw = dict(_RAW_WORK)
    raw["abstract_inverted_index"] = None
    client = _client_for(200, {"results": [raw]})

    results = search_openalex_works("query", api_key="key", client=client)

    assert results[0].abstract is None


def test_search_strips_the_doi_org_prefix():
    client = _client_for(200, {"results": [_RAW_WORK]})

    results = search_openalex_works("query", api_key="key", client=client)

    assert results[0].doi == "10.1000/example"
    assert "doi.org" not in results[0].doi


def test_search_returns_empty_list_for_zero_results():
    client = _client_for(200, {"results": []})

    results = search_openalex_works("query", api_key="key", client=client)

    assert results == []


def test_search_raises_on_non_200_status():
    client = _client_for(500, {})

    with pytest.raises(SourceSearchUnavailableError):
        search_openalex_works("query", api_key="key", client=client)


def test_search_raises_on_a_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(SourceSearchUnavailableError):
        search_openalex_works("query", api_key="key", client=client)


def test_search_raises_on_a_malformed_response_body():
    client = _client_for(200, ["not", "a", "dict"])

    with pytest.raises(SourceSearchUnavailableError):
        search_openalex_works("query", api_key="key", client=client)


def test_get_work_by_id_returns_the_parsed_work():
    client = _client_for(200, _RAW_WORK)

    work = get_openalex_work_by_id("W123", api_key="key", client=client)

    assert work is not None
    assert work.title == "A Real Paper Title"


def test_get_work_by_id_accepts_a_full_openalex_url():
    client = _client_for(200, _RAW_WORK)

    work = get_openalex_work_by_id("https://openalex.org/W123", api_key="key", client=client)

    assert work is not None


def test_get_work_by_id_returns_none_for_a_404():
    client = _client_for(404)

    work = get_openalex_work_by_id("W999", api_key="key", client=client)

    assert work is None


def test_get_work_by_id_raises_on_a_real_failure():
    client = _client_for(500, {})

    with pytest.raises(SourceSearchUnavailableError):
        get_openalex_work_by_id("W123", api_key="key", client=client)
