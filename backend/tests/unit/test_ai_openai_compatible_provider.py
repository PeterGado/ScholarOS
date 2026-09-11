import httpx
import pytest

from app.ai.exceptions import ProviderConfigurationError, ProviderRequestError
from app.ai.providers.openai_compatible import OpenAICompatibleProvider, create_default_provider
from app.core.config import Settings


def _client_with_handler(handler) -> httpx.Client:
    """A real httpx.Client wired to a MockTransport - no real network call is ever made,
    satisfying the "testable without network access" requirement (ADR-005 §AI Engineering
    Implications) while still exercising the provider's real HTTP request/response handling.
    """
    return httpx.Client(transport=httpx.MockTransport(handler))


def _build_provider(handler, **overrides) -> OpenAICompatibleProvider:
    kwargs = {
        "base_url": "https://example-provider.test/v1",
        "api_key": "test-key",
        "model": "test-model",
        "embedding_model": "test-embedding-model",
        "client": _client_with_handler(handler),
    }
    kwargs.update(overrides)
    return OpenAICompatibleProvider(**kwargs)


# --- Configuration validation -------------------------------------------------------------


def test_missing_api_key_raises_configuration_error():
    with pytest.raises(ProviderConfigurationError):
        OpenAICompatibleProvider(base_url="https://example.test/v1", api_key="", model="m", embedding_model="e")


def test_missing_base_url_raises_configuration_error():
    with pytest.raises(ProviderConfigurationError):
        OpenAICompatibleProvider(base_url="", api_key="key", model="m", embedding_model="e")


def test_api_key_never_appears_in_a_provider_request_error_message():
    secret = "sk-genuinely-secret-value"
    provider = _build_provider(lambda request: httpx.Response(500, json={"error": "boom"}), api_key=secret)

    with pytest.raises(ProviderRequestError) as exc_info:
        provider.generate("prompt")

    assert secret not in str(exc_info.value)


# --- generate() -----------------------------------------------------------------------------


def test_generate_returns_the_response_content():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "the extracted concept"}}]})

    provider = _build_provider(handler)
    assert provider.generate("extract concepts from this text") == "the extracted concept"


def test_generate_raises_provider_request_error_on_non_2xx():
    provider = _build_provider(lambda request: httpx.Response(500, json={"error": "boom"}))
    with pytest.raises(ProviderRequestError):
        provider.generate("prompt")


def test_generate_raises_provider_request_error_on_malformed_response():
    provider = _build_provider(lambda request: httpx.Response(200, json={"unexpected": "shape"}))
    with pytest.raises(ProviderRequestError):
        provider.generate("prompt")


# --- embed() --------------------------------------------------------------------------------


def test_embed_returns_the_embedding_vector():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    provider = _build_provider(handler)
    assert provider.embed("some chunk content") == [0.1, 0.2, 0.3]


def test_embed_raises_provider_request_error_on_non_2xx():
    provider = _build_provider(lambda request: httpx.Response(401, json={"error": "unauthorized"}))
    with pytest.raises(ProviderRequestError):
        provider.embed("text")


def test_embed_raises_provider_request_error_on_malformed_response():
    provider = _build_provider(lambda request: httpx.Response(200, json={"data": []}))
    with pytest.raises(ProviderRequestError):
        provider.embed("text")


# --- create_default_provider() ---------------------------------------------------------------


def test_create_default_provider_builds_from_settings():
    settings = Settings(
        ai_base_url="https://configured-provider.test/v1",
        ai_api_key="configured-key",
        ai_model="configured-model",
        ai_embedding_model="configured-embedding-model",
    )
    provider = create_default_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_create_default_provider_raises_when_api_key_is_unconfigured():
    settings = Settings(ai_api_key=None)
    with pytest.raises(ProviderConfigurationError):
        create_default_provider(settings)
