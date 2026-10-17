from unittest.mock import MagicMock, patch

from app.ai.web_fetch import (
    WebSource,
    _is_safe_to_fetch,
    extract_urls,
    fetch_web_source,
)


def test_extract_urls_finds_a_single_url():
    assert extract_urls("Check this out: https://example.com for details.") == ["https://example.com"]


def test_extract_urls_strips_trailing_punctuation():
    assert extract_urls("See https://example.com/page.") == ["https://example.com/page"]
    assert extract_urls("(https://example.com/page)") == ["https://example.com/page"]
    assert extract_urls("https://example.com/page, and more") == ["https://example.com/page"]


def test_extract_urls_dedupes_and_preserves_order():
    text = "https://a.example.com then https://b.example.com then https://a.example.com again"
    assert extract_urls(text) == ["https://a.example.com", "https://b.example.com"]


def test_extract_urls_caps_at_three():
    text = " ".join(f"https://site{i}.example.com" for i in range(10))
    assert len(extract_urls(text)) == 3


def test_extract_urls_returns_empty_for_no_url():
    assert extract_urls("just a plain message, no links here") == []


def test_is_safe_to_fetch_rejects_loopback():
    assert _is_safe_to_fetch("http://127.0.0.1/") is False
    assert _is_safe_to_fetch("http://[::1]/") is False


def test_is_safe_to_fetch_rejects_link_local_metadata_endpoint():
    assert _is_safe_to_fetch("http://169.254.169.254/latest/meta-data/") is False


def test_is_safe_to_fetch_rejects_private_ranges():
    assert _is_safe_to_fetch("http://192.168.1.1/") is False
    assert _is_safe_to_fetch("http://10.0.0.5/") is False


def test_is_safe_to_fetch_rejects_non_http_schemes():
    assert _is_safe_to_fetch("ftp://example.com/") is False
    assert _is_safe_to_fetch("file:///etc/passwd") is False


def test_is_safe_to_fetch_rejects_an_unresolvable_host():
    assert _is_safe_to_fetch("http://this-does-not-resolve.invalid/") is False


def test_is_safe_to_fetch_accepts_a_real_public_host():
    assert _is_safe_to_fetch("https://example.com/") is True


def test_fetch_web_source_never_calls_fetcher_for_an_unsafe_url():
    with patch("app.ai.web_fetch.Fetcher") as mock_fetcher:
        result = fetch_web_source("http://127.0.0.1/")

    assert result is None
    mock_fetcher.get.assert_not_called()


def test_fetch_web_source_returns_a_web_source_on_success():
    mock_response = MagicMock(status=200)
    mock_response.get_all_text.return_value = "  Some extracted page text.  "
    with patch("app.ai.web_fetch.Fetcher") as mock_fetcher:
        mock_fetcher.get.return_value = mock_response
        result = fetch_web_source("https://example.com/article")

    assert result == WebSource(url="https://example.com/article", content="Some extracted page text.")
    mock_fetcher.get.assert_called_once()
    call_kwargs = mock_fetcher.get.call_args.kwargs
    assert call_kwargs["follow_redirects"] is False
    assert call_kwargs["retries"] == 0


def test_fetch_web_source_returns_none_on_non_200_status():
    mock_response = MagicMock(status=404)
    with patch("app.ai.web_fetch.Fetcher") as mock_fetcher:
        mock_fetcher.get.return_value = mock_response
        result = fetch_web_source("https://example.com/missing")

    assert result is None


def test_fetch_web_source_returns_none_on_a_redirect_status():
    # follow_redirects=False means a 3xx comes back as-is, never silently followed.
    mock_response = MagicMock(status=301)
    with patch("app.ai.web_fetch.Fetcher") as mock_fetcher:
        mock_fetcher.get.return_value = mock_response
        result = fetch_web_source("https://example.com/moved")

    assert result is None


def test_fetch_web_source_returns_none_on_empty_extracted_text():
    mock_response = MagicMock(status=200)
    mock_response.get_all_text.return_value = "   "
    with patch("app.ai.web_fetch.Fetcher") as mock_fetcher:
        mock_fetcher.get.return_value = mock_response
        result = fetch_web_source("https://example.com/blank")

    assert result is None


def test_fetch_web_source_truncates_long_content():
    long_text = "word " * 2000
    mock_response = MagicMock(status=200)
    mock_response.get_all_text.return_value = long_text
    with patch("app.ai.web_fetch.Fetcher") as mock_fetcher:
        mock_fetcher.get.return_value = mock_response
        result = fetch_web_source("https://example.com/long")

    assert result is not None
    assert len(result.content) <= 3003  # _MAX_CONTENT_LENGTH + "..."
    assert result.content.endswith("...")


def test_fetch_web_source_never_raises_on_an_exception():
    with patch("app.ai.web_fetch.Fetcher") as mock_fetcher:
        mock_fetcher.get.side_effect = RuntimeError("simulated failure")
        result = fetch_web_source("https://example.com/boom")

    assert result is None
