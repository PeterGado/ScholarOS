import pytest

from app.ai.exceptions import ProviderConfigurationError, ProviderRateLimitError, ProviderRequestError
from app.ai.providers.failover import FailoverProvider
from app.ai.providers.google_genai import GoogleGenAIProvider, create_google_genai_provider
from app.core.config import Settings


class FakeGenerateResponse:
    def __init__(self, text):
        self.text = text


class FakeEmbeddingValue:
    def __init__(self, values):
        self.values = values


class FakeEmbedResponse:
    def __init__(self, values):
        self.embeddings = [FakeEmbeddingValue(values)]


class FakeModels:
    def __init__(self, *, generate_response=None, generate_error=None, embed_response=None, embed_error=None):
        self._generate_response = generate_response
        self._generate_error = generate_error
        self._embed_response = embed_response
        self._embed_error = embed_error
        self.generate_calls: list[tuple[str, str]] = []
        self.generate_configs: list[object] = []
        self.embed_calls: list[tuple[str, str]] = []

    def generate_content(self, *, model, contents, config=None):
        self.generate_calls.append((model, contents))
        self.generate_configs.append(config)
        if self._generate_error:
            raise self._generate_error
        return self._generate_response

    def embed_content(self, *, model, contents):
        self.embed_calls.append((model, contents))
        if self._embed_error:
            raise self._embed_error
        return self._embed_response


class FakeGenAIClient:
    def __init__(self, models: FakeModels):
        self.models = models


def _build_provider(models: FakeModels, **overrides) -> GoogleGenAIProvider:
    kwargs = {"api_key": "test-key", "model": "test-model", "embedding_model": "test-embedding-model", "client": FakeGenAIClient(models)}
    kwargs.update(overrides)
    return GoogleGenAIProvider(**kwargs)


# --- Configuration validation -------------------------------------------------------------


def test_missing_api_key_raises_configuration_error():
    with pytest.raises(ProviderConfigurationError):
        GoogleGenAIProvider(api_key="", model="m", embedding_model="e")


# --- generate() -----------------------------------------------------------------------------


def test_generate_returns_the_response_text():
    models = FakeModels(generate_response=FakeGenerateResponse("the extracted concept"))
    provider = _build_provider(models)

    assert provider.generate("extract concepts") == "the extracted concept"
    assert models.generate_calls == [("test-model", "extract concepts")]


def test_generate_passes_max_output_tokens_to_the_provider_config():
    models = FakeModels(generate_response=FakeGenerateResponse("text"))
    provider = _build_provider(models, max_output_tokens=4096)

    provider.generate("prompt")

    assert models.generate_configs[0].max_output_tokens == 4096


def test_generate_omits_config_entirely_when_no_max_output_tokens_is_configured():
    models = FakeModels(generate_response=FakeGenerateResponse("text"))
    provider = _build_provider(models, max_output_tokens=None)

    provider.generate("prompt")

    assert models.generate_configs[0] is None


def test_generate_raises_provider_request_error_when_the_sdk_raises():
    models = FakeModels(generate_error=RuntimeError("sdk failure"))
    provider = _build_provider(models)

    with pytest.raises(ProviderRequestError):
        provider.generate("prompt")


def test_generate_quota_error_includes_the_providers_own_detail():
    """2026-09-30, found while diagnosing a real rate-limit incident: the raised error used to
    discard the SDK's own message entirely, leaving only a generic "rate limit reached" string
    in both WorkItem.last_error and server logs - useless for telling a per-minute limit apart
    from an exhausted daily quota, or knowing which quota was hit at all. The SDK's own text is
    safe to include (never the API key - see test_api_key_never_appears_in_a_provider_request_
    error_message below, which covers that guarantee separately) and is the only place this
    diagnostic detail exists.
    """
    models = FakeModels(generate_error=RuntimeError("429 RESOURCE_EXHAUSTED: daily quota"))
    provider = _build_provider(models)

    with pytest.raises(ProviderRateLimitError, match="rate limit") as exc_info:
        provider.generate("prompt")

    assert "RESOURCE_EXHAUSTED" in str(exc_info.value)
    assert "daily quota" in str(exc_info.value)


def test_generate_raises_provider_request_error_on_empty_text():
    models = FakeModels(generate_response=FakeGenerateResponse(""))
    provider = _build_provider(models)

    with pytest.raises(ProviderRequestError):
        provider.generate("prompt")


def test_generate_raises_provider_request_error_on_missing_text_attribute():
    class NoTextResponse:
        pass

    models = FakeModels(generate_response=NoTextResponse())
    provider = _build_provider(models)

    with pytest.raises(ProviderRequestError):
        provider.generate("prompt")


# --- embed() --------------------------------------------------------------------------------


def test_embed_returns_the_embedding_vector():
    models = FakeModels(embed_response=FakeEmbedResponse([0.1, 0.2, 0.3]))
    provider = _build_provider(models)

    assert provider.embed("some chunk content") == [0.1, 0.2, 0.3]
    assert models.embed_calls == [("test-embedding-model", "some chunk content")]


def test_embed_raises_provider_request_error_when_the_sdk_raises():
    models = FakeModels(embed_error=RuntimeError("sdk failure"))
    provider = _build_provider(models)

    with pytest.raises(ProviderRequestError):
        provider.embed("text")


def test_embed_raises_provider_request_error_on_malformed_response():
    class EmptyEmbeddingsResponse:
        embeddings = []

    models = FakeModels(embed_response=EmptyEmbeddingsResponse())
    provider = _build_provider(models)

    with pytest.raises(ProviderRequestError):
        provider.embed("text")


def test_api_key_never_appears_in_a_provider_request_error_message():
    secret = "sk-genuinely-secret-value"
    models = FakeModels(generate_error=RuntimeError("failure"))
    provider = _build_provider(models, api_key=secret)

    with pytest.raises(ProviderRequestError) as exc_info:
        provider.generate("prompt")

    assert secret not in str(exc_info.value)


# --- create_google_genai_provider() -----------------------------------------------------------


def test_create_google_genai_provider_raises_when_api_key_is_unconfigured():
    settings = Settings(ai_api_key=None)
    with pytest.raises(ProviderConfigurationError):
        create_google_genai_provider(settings)


def test_create_google_genai_provider_wires_max_output_tokens_from_settings():
    settings = Settings(ai_api_key="test-key", ai_max_output_tokens=1234)
    provider = create_google_genai_provider(settings)

    assert provider._max_output_tokens == 1234


def test_create_google_genai_provider_returns_a_failover_provider_when_multiple_keys_are_set():
    """2026-09-30, multi-account failover: ai_api_keys takes priority over ai_api_key when set -
    one GoogleGenAIProvider per key, wrapped in FailoverProvider.
    """
    settings = Settings(ai_api_keys=["key-a", "key-b", "key-c"])
    provider = create_google_genai_provider(settings)

    assert isinstance(provider, FailoverProvider)
    assert len(provider._providers) == 3
    assert [p._client for p in provider._providers]  # each is a real, distinct GoogleGenAIProvider
    assert all(isinstance(p, GoogleGenAIProvider) for p in provider._providers)


def test_create_google_genai_provider_ignores_ai_api_key_when_ai_api_keys_is_set():
    settings = Settings(ai_api_key="single-key", ai_api_keys=["key-a", "key-b"])
    provider = create_google_genai_provider(settings)

    assert isinstance(provider, FailoverProvider)
    assert len(provider._providers) == 2
