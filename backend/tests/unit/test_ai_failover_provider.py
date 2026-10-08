import pytest

from app.ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderRequestError,
)
from app.ai.providers.failover import FailoverProvider


class FakeProvider:
    """A minimal stand-in satisfying TextGenerationProvider + EmbeddingProvider - FailoverProvider
    is provider-agnostic, so these tests never need a real GoogleGenAIProvider/
    OpenAICompatibleProvider.
    """

    def __init__(self, *, name: str, error: Exception | None = None) -> None:
        self.name = name
        self._error = error
        self.generate_calls = 0
        self.embed_calls = 0
        self.embed_batch_calls = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        if self._error:
            raise self._error
        return f"{self.name}: {prompt}"

    def embed(self, text: str) -> list[float]:
        self.embed_calls += 1
        if self._error:
            raise self._error
        return [1.0, 2.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_batch_calls += 1
        if self._error:
            raise self._error
        return [[1.0, 2.0] for _ in texts]


def _fixed_start(index: int):
    """FailoverProvider (2026-09-30) picks a random starting provider on every call by default,
    to spread load once the key list grows past a handful - see its own docstring. Most tests
    here care about the fallback order itself, not the randomization, so they pin the start back
    to a specific index; a couple of tests below exercise the randomization directly.
    """
    return lambda _num_providers: index


def test_uses_the_first_provider_when_it_succeeds():
    first = FakeProvider(name="key-a")
    second = FakeProvider(name="key-b")
    provider = FailoverProvider([first, second], start_index_fn=_fixed_start(0))

    result = provider.generate("hello")

    assert result == "key-a: hello"
    assert first.generate_calls == 1
    assert second.generate_calls == 0


def test_falls_through_to_the_next_provider_on_a_rate_limit_error():
    first = FakeProvider(name="key-a", error=ProviderRateLimitError("exhausted"))
    second = FakeProvider(name="key-b")
    provider = FailoverProvider([first, second], start_index_fn=_fixed_start(0))

    result = provider.generate("hello")

    assert result == "key-b: hello"
    assert first.generate_calls == 1
    assert second.generate_calls == 1


def test_falls_through_across_three_or_more_providers():
    first = FakeProvider(name="key-a", error=ProviderRateLimitError("exhausted"))
    second = FakeProvider(name="key-b", error=ProviderRateLimitError("exhausted"))
    third = FakeProvider(name="key-c")
    provider = FailoverProvider([first, second, third], start_index_fn=_fixed_start(0))

    result = provider.generate("hello")

    assert result == "key-c: hello"
    assert first.generate_calls == 1
    assert second.generate_calls == 1
    assert third.generate_calls == 1


def test_raises_the_last_rate_limit_error_when_every_provider_is_exhausted():
    first = FakeProvider(name="key-a", error=ProviderRateLimitError("key-a exhausted"))
    second = FakeProvider(name="key-b", error=ProviderRateLimitError("key-b exhausted"))
    provider = FailoverProvider([first, second], start_index_fn=_fixed_start(0))

    with pytest.raises(ProviderRateLimitError, match="key-b exhausted"):
        provider.generate("hello")


def test_a_non_rate_limit_error_is_not_masked_by_trying_another_key():
    """A malformed response or genuinely invalid key is a real problem with that request, not
    a quota issue - failing over to a different account would hide the actual bug.
    """
    first = FakeProvider(name="key-a", error=ProviderRequestError("malformed response"))
    second = FakeProvider(name="key-b")
    provider = FailoverProvider([first, second], start_index_fn=_fixed_start(0))

    with pytest.raises(ProviderRequestError, match="malformed response"):
        provider.generate("hello")

    assert second.generate_calls == 0


def test_embed_and_embed_batch_also_fail_over():
    first = FakeProvider(name="key-a", error=ProviderRateLimitError("exhausted"))
    second = FakeProvider(name="key-b")
    provider = FailoverProvider([first, second], start_index_fn=_fixed_start(0))

    assert provider.embed("text") == [1.0, 2.0]
    assert provider.embed_batch(["a", "b"]) == [[1.0, 2.0], [1.0, 2.0]]
    assert second.embed_calls == 1
    assert second.embed_batch_calls == 1


def test_requires_at_least_one_provider():
    with pytest.raises(ProviderConfigurationError):
        FailoverProvider([])


def test_each_call_independently_retries_from_the_same_start_index():
    """Deliberately stateless between calls (see FailoverProvider's own docstring) - an
    already-exhausted key is retried first on every call (from whatever start index that call's
    start_index_fn picks), not skipped based on a prior failure, since a rate-limited request
    costs no quota and this keeps the class free of any shared mutable state across the
    executor's concurrent worker threads.
    """
    first = FakeProvider(name="key-a", error=ProviderRateLimitError("exhausted"))
    second = FakeProvider(name="key-b")
    provider = FailoverProvider([first, second], start_index_fn=_fixed_start(0))

    provider.generate("one")
    provider.generate("two")

    assert first.generate_calls == 2
    assert second.generate_calls == 2


# --- randomized starting provider (2026-09-30) ------------------------------------------------


def test_default_start_index_fn_is_random_randrange():
    import random

    provider = FailoverProvider([FakeProvider(name="key-a")])

    assert provider._start_index_fn is random.randrange


def test_a_nonzero_start_index_tries_that_provider_first_in_circular_order():
    first = FakeProvider(name="key-a")
    second = FakeProvider(name="key-b")
    third = FakeProvider(name="key-c")
    provider = FailoverProvider([first, second, third], start_index_fn=_fixed_start(1))

    result = provider.generate("hello")

    assert result == "key-b: hello"
    assert first.generate_calls == 0
    assert second.generate_calls == 1
    assert third.generate_calls == 0


def test_a_nonzero_start_index_still_wraps_around_to_every_provider_on_failover():
    first = FakeProvider(name="key-a")
    second = FakeProvider(name="key-b", error=ProviderRateLimitError("exhausted"))
    third = FakeProvider(name="key-c", error=ProviderRateLimitError("exhausted"))
    provider = FailoverProvider([first, second, third], start_index_fn=_fixed_start(1))

    result = provider.generate("hello")

    assert result == "key-a: hello"
    assert second.generate_calls == 1
    assert third.generate_calls == 1
    assert first.generate_calls == 1


def test_start_index_fn_is_called_with_the_provider_count():
    calls: list[int] = []

    def recording_start(num_providers: int) -> int:
        calls.append(num_providers)
        return 0

    provider = FailoverProvider(
        [FakeProvider(name="key-a"), FakeProvider(name="key-b"), FakeProvider(name="key-c")],
        start_index_fn=recording_start,
    )

    provider.generate("hello")

    assert calls == [3]
