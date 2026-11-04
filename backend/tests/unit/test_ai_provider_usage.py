import httpx

from app.ai.provider_usage import (
    ProviderTokenUsage,
    ProviderUsageMeter,
    metering_provider_usage,
    observe_provider_usage,
)
from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.google_genai import GoogleGenAIProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.ai.token_estimate import estimate_tokens

# --- the meter itself -----------------------------------------------------------------------


def test_observations_outside_a_metering_block_are_ignored():
    """Every existing provider unit test calls a provider directly, with no meter open - this
    must stay a silent no-op rather than raising or requiring every call site to opt in.
    """
    observe_provider_usage(input_tokens=100, output_tokens=50)  # no meter open


def test_a_meter_accumulates_across_calls():
    with metering_provider_usage() as meter:
        observe_provider_usage(input_tokens=100, output_tokens=20)
        observe_provider_usage(input_tokens=5, output_tokens=7)

    assert meter.input_tokens == 105
    assert meter.output_tokens == 27
    assert meter.total_tokens == 132
    assert meter.observed_calls == 2


def test_an_empty_meter_observed_no_calls():
    with metering_provider_usage() as meter:
        pass

    assert meter.observed_calls == 0
    assert meter.total_tokens == 0


def test_nested_blocks_restore_the_outer_meter():
    with metering_provider_usage() as outer:
        observe_provider_usage(input_tokens=10, output_tokens=0)
        with metering_provider_usage() as inner:
            observe_provider_usage(input_tokens=999, output_tokens=0)
        observe_provider_usage(input_tokens=5, output_tokens=0)

    assert inner.total_tokens == 999
    assert outer.total_tokens == 15


def test_negative_reported_counts_never_reduce_the_total():
    meter = ProviderUsageMeter()
    meter.observe(ProviderTokenUsage(input_tokens=10, output_tokens=5))
    meter.observe(ProviderTokenUsage(input_tokens=-100, output_tokens=-100))

    assert meter.total_tokens == 15


# --- Google GenAI ---------------------------------------------------------------------------


class _UsageMetadata:
    def __init__(self, prompt_token_count=None, candidates_token_count=None):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


class _GenerateResponse:
    def __init__(self, text, usage_metadata=None):
        self.text = text
        if usage_metadata is not None:
            self.usage_metadata = usage_metadata


class _EmbedResponse:
    def __init__(self, values):
        self.embeddings = [type("E", (), {"values": values})()]


class _BatchEmbedResponse:
    def __init__(self, count):
        self.embeddings = [type("E", (), {"values": [0.1, 0.2]})() for _ in range(count)]


class _Models:
    def __init__(self, *, generate_response=None, embed_response=None):
        self._generate_response = generate_response
        self._embed_response = embed_response

    def generate_content(self, **kwargs):
        return self._generate_response

    def embed_content(self, **kwargs):
        return self._embed_response


def _google_provider(models) -> GoogleGenAIProvider:
    return GoogleGenAIProvider(
        api_key="test-key",
        model="test-model",
        embedding_model="test-embedding-model",
        client=type("Client", (), {"models": models})(),
    )


def test_google_generate_reports_the_providers_exact_token_counts():
    models = _Models(
        generate_response=_GenerateResponse(
            "a reply", usage_metadata=_UsageMetadata(prompt_token_count=1200, candidates_token_count=340)
        )
    )

    with metering_provider_usage() as meter:
        _google_provider(models).generate("prompt")

    assert meter.input_tokens == 1200
    assert meter.output_tokens == 340
    assert meter.observed_calls == 1


def test_google_generate_reports_nothing_when_the_response_has_no_usage_metadata():
    models = _Models(generate_response=_GenerateResponse("a reply"))

    with metering_provider_usage() as meter:
        _google_provider(models).generate("prompt")

    # No metadata and no numbers must not be reported as a 0/0 observation, which would mask
    # AiUsageGuard.record_metered's estimate fallback.
    assert meter.observed_calls == 0


def test_google_embeddings_report_nothing_because_the_sdk_has_no_token_counts():
    single = _Models(embed_response=_EmbedResponse([0.1, 0.2]))
    batch = _Models(embed_response=_BatchEmbedResponse(2))

    with metering_provider_usage() as meter:
        _google_provider(single).embed("some text")
        _google_provider(batch).embed_batch(["a", "b"])

    assert meter.observed_calls == 0


# --- OpenAI-compatible ----------------------------------------------------------------------


def _openai_provider(response_body: dict) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="https://example-provider.test/v1",
        api_key="test-key",
        model="test-model",
        embedding_model="test-embedding-model",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response_body))),
    )


def test_openai_compatible_generate_reports_chat_token_counts():
    provider = _openai_provider(
        {
            "choices": [{"message": {"content": "a reply"}}],
            "usage": {"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 1000},
        }
    )

    with metering_provider_usage() as meter:
        provider.generate("prompt")

    assert meter.input_tokens == 800
    assert meter.output_tokens == 200


def test_openai_compatible_embeddings_report_token_counts():
    provider = _openai_provider({"data": [{"index": 0, "embedding": [0.1]}], "usage": {"prompt_tokens": 42}})

    with metering_provider_usage() as meter:
        provider.embed("some text")

    assert meter.input_tokens == 42
    assert meter.output_tokens == 0


def test_openai_compatible_batch_embeddings_report_token_counts():
    provider = _openai_provider(
        {
            "data": [{"index": 0, "embedding": [0.1]}, {"index": 1, "embedding": [0.2]}],
            "usage": {"prompt_tokens": 90},
        }
    )

    with metering_provider_usage() as meter:
        provider.embed_batch(["a", "b"])

    assert meter.input_tokens == 90


def test_openai_compatible_generate_without_a_usage_block_reports_nothing():
    provider = _openai_provider({"choices": [{"message": {"content": "a reply"}}]})

    with metering_provider_usage() as meter:
        provider.generate("prompt")

    assert meter.observed_calls == 0


# --- fake provider (test infrastructure) ----------------------------------------------------


def test_fake_provider_reports_a_deterministic_estimate_so_e2e_specs_exercise_metering():
    provider = FakeAIProvider()

    with metering_provider_usage() as meter:
        reply = provider.generate("tell me about coastal erosion")

    assert meter.input_tokens == estimate_tokens("tell me about coastal erosion")
    assert meter.output_tokens == estimate_tokens(reply)
    assert meter.observed_calls == 1
