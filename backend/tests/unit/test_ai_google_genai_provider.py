import pytest

from app.ai.exceptions import (
    ProviderConfigurationError,
    ProviderContentBlockedError,
    ProviderRateLimitError,
    ProviderRequestError,
)
from app.ai.providers.failover import FailoverProvider
from app.ai.providers.google_genai import GoogleGenAIProvider, create_google_genai_provider
from app.ai.providers.rate_limited import RateLimitedProvider
from app.core.config import Settings


class FakeGenerateResponse:
    def __init__(self, text):
        self.text = text


class FakePromptFeedback:
    def __init__(self, block_reason):
        self.block_reason = block_reason


class FakeFinishReason:
    """Mimics the SDK's enum member shape (a `.name` attribute), matching real usage where
    `candidates[0].finish_reason` is a `types.FinishReason` member, not a plain string.
    """

    def __init__(self, name):
        self.name = name


class FakeCandidate:
    def __init__(self, finish_reason=None):
        self.finish_reason = finish_reason


class BlockedResponse:
    """No `.text` attribute at all, matching how a real blocked GenerateContentResponse has no
    usable text - `getattr(response, "text", None)` in generate() must fall through to None.
    """

    def __init__(self, *, prompt_feedback=None, candidates=None):
        self.prompt_feedback = prompt_feedback
        self.candidates = candidates or []


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


def test_generate_always_passes_safety_settings_even_with_no_max_output_tokens_configured():
    """2026-09-30: config used to be omitted entirely (None) when max_output_tokens was unset -
    no longer true now that safety_settings (below) must always be applied regardless.
    """
    models = FakeModels(generate_response=FakeGenerateResponse("text"))
    provider = _build_provider(models, max_output_tokens=None)

    provider.generate("prompt")

    config = models.generate_configs[0]
    assert config is not None
    assert config.max_output_tokens is None
    assert len(config.safety_settings) == 4


def test_generate_configures_safety_settings_at_block_medium_and_above():
    """2026-09-30, added after friend testing found violent/harassing/derogatory messages
    passing through with no moderation - the SDK's unset default was never deliberately chosen.
    """
    from google.genai import types

    models = FakeModels(generate_response=FakeGenerateResponse("text"))
    provider = _build_provider(models)

    provider.generate("prompt")

    safety_settings = models.generate_configs[0].safety_settings
    categories = {setting.category for setting in safety_settings}
    assert categories == {
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    }
    assert all(setting.threshold == types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE for setting in safety_settings)


# --- safety-blocked responses (2026-09-30) -------------------------------------------------


def test_generate_raises_content_blocked_error_when_the_whole_prompt_is_blocked():
    models = FakeModels(generate_response=BlockedResponse(prompt_feedback=FakePromptFeedback("SAFETY")))
    provider = _build_provider(models)

    with pytest.raises(ProviderContentBlockedError, match="safety filters"):
        provider.generate("a violent, harassing prompt")


def test_generate_raises_content_blocked_error_when_the_response_is_cut_off_for_safety():
    models = FakeModels(
        generate_response=BlockedResponse(candidates=[FakeCandidate(finish_reason=FakeFinishReason("SAFETY"))])
    )
    provider = _build_provider(models)

    with pytest.raises(ProviderContentBlockedError, match="safety filters"):
        provider.generate("prompt")


def test_generate_raises_content_blocked_error_for_prohibited_content_finish_reason():
    models = FakeModels(
        generate_response=BlockedResponse(
            candidates=[FakeCandidate(finish_reason=FakeFinishReason("PROHIBITED_CONTENT"))]
        )
    )
    provider = _build_provider(models)

    with pytest.raises(ProviderContentBlockedError):
        provider.generate("prompt")


def test_generate_raises_plain_request_error_for_a_malformed_response_not_a_safety_block():
    """No text, no block_reason, no blocked finish_reason - a genuinely malformed response must
    still raise the generic error, not be misreported as a safety block.
    """

    class NoTextResponse:
        pass

    models = FakeModels(generate_response=NoTextResponse())
    provider = _build_provider(models)

    with pytest.raises(ProviderRequestError) as exc_info:
        provider.generate("prompt")
    assert not isinstance(exc_info.value, ProviderContentBlockedError)


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
    one GoogleGenAIProvider per key, each paced by its own RateLimitedProvider, wrapped in
    FailoverProvider.
    """
    settings = Settings(ai_api_keys=["key-a", "key-b", "key-c"])
    provider = create_google_genai_provider(settings)

    assert isinstance(provider, FailoverProvider)
    assert len(provider._providers) == 3
    assert all(isinstance(p, RateLimitedProvider) for p in provider._providers)
    assert all(isinstance(p._provider, GoogleGenAIProvider) for p in provider._providers)
    assert [p._provider._client for p in provider._providers]  # each wraps a real, distinct provider


def test_create_google_genai_provider_ignores_ai_api_key_when_ai_api_keys_is_set():
    settings = Settings(ai_api_key="single-key", ai_api_keys=["key-a", "key-b"])
    provider = create_google_genai_provider(settings)

    assert isinstance(provider, FailoverProvider)
    assert len(provider._providers) == 2
