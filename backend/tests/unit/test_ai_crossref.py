import httpx

from app.ai.crossref import CrossrefWork, fetch_crossref_work


def _client_for(status: int, body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_returns_a_crossref_work_for_a_known_doi():
    client = _client_for(
        200,
        {
            "message": {
                "title": ["Measured measurement"],
                "author": [{"given": "Markus", "family": "Aspelmeyer"}],
                "published-print": {"date-parts": [[2009, 1]]},
            }
        },
    )

    result = fetch_crossref_work("10.1038/nphys1170", client=client)

    assert result == CrossrefWork(title="Measured measurement", authors=("Aspelmeyer",), year=2009)


def test_returns_none_for_an_unknown_doi():
    client = _client_for(404, {"status": "not-found"})

    result = fetch_crossref_work("10.9999/not-a-real-doi", client=client)

    assert result is None


def test_returns_none_and_never_raises_on_a_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_crossref_work("10.1038/nphys1170", client=client)

    assert result is None


def test_blank_doi_returns_none_without_making_a_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never be called for a blank doi")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = fetch_crossref_work("   ", client=client)

    assert result is None


def test_multiple_authors_are_all_returned_in_order():
    client = _client_for(
        200,
        {
            "message": {
                "title": ["A joint study"],
                "author": [
                    {"given": "Jane", "family": "Smith"},
                    {"given": "John", "family": "Doe"},
                ],
                "published-online": {"date-parts": [[2015]]},
            }
        },
    )

    result = fetch_crossref_work("10.1/joint", client=client)

    assert result.authors == ("Smith", "Doe")
    assert result.year == 2015


def test_falls_back_to_created_date_when_no_published_date_exists():
    client = _client_for(
        200,
        {
            "message": {
                "title": ["Untitled"],
                "author": [],
                "created": {"date-parts": [[2020, 3, 1]]},
            }
        },
    )

    result = fetch_crossref_work("10.1/x", client=client)

    assert result.year == 2020


def test_missing_title_falls_back_to_the_doi_itself():
    client = _client_for(200, {"message": {"author": []}})

    result = fetch_crossref_work("10.1/no-title", client=client)

    assert result.title == "10.1/no-title"
