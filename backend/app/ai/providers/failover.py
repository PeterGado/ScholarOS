import logging
import random
from collections.abc import Callable
from typing import Protocol

from app.ai.exceptions import ProviderConfigurationError, ProviderRateLimitError
from app.ai.providers.base import EmbeddingProvider, TextGenerationProvider

__all__ = ["FailoverProvider"]

logger = logging.getLogger(__name__)


class _GenerationAndEmbeddingProvider(TextGenerationProvider, EmbeddingProvider, Protocol):
    """Every concrete provider in this package (GoogleGenAIProvider, OpenAICompatibleProvider)
    already implements both capability Protocols in one class - this just names that combined
    shape so `FailoverProvider` can type its underlying providers precisely.
    """


class FailoverProvider:
    """Wraps several same-shaped providers - one per API key/account - trying each in order and
    moving to the next only when the current one reports its quota is exhausted (2026-09-30,
    for personal use across multiple free-tier accounts, each with its own separate daily
    quota). Satisfies the same `TextGenerationProvider`/`EmbeddingProvider` Protocols as any
    single concrete provider, so it's a drop-in replacement wherever one provider is expected -
    no calling code (chat generation, document processing) needs to know multiple keys exist.

    Only `ProviderRateLimitError` triggers moving to the next key. Any other failure (a
    malformed response, a network error, a genuinely invalid key) is a real problem with that
    specific request, not a quota issue, and is raised immediately rather than masked by
    silently trying a different account - that kind of failure won't be fixed by a different
    key, and hiding it would make a real bug look like intermittent flakiness.

    Deliberately stateless between calls - no memory of "key 0 was exhausted an hour ago, skip
    it". A rate-limited request costs no quota on the provider's side (that's the entire point
    of the provider rejecting it before doing any work), so this keeps the class trivially
    thread-safe: no shared mutable state at all, which matters now that the Work Item executor
    runs several worker threads calling the same provider instance concurrently.

    Each call picks its own random starting provider (2026-09-30, added once the key list grew
    past a handful) rather than always starting from index 0 - with a fixed order, every
    concurrent caller piles onto the same first key, so a burst exhausts it before any of the
    later keys absorb load, and every request pays for walking past the same dead key first.
    Randomizing the start spreads load evenly instead. `start_index_fn` is injectable (defaults
    to `random.randrange`) so tests can force a specific, deterministic order.

    Every failover is logged (2026-10-23): before this, a single exhausted key and a completely
    exhausted pool looked identical from the outside - the user-visible error was the same
    generic rate-limit message either way, and the only log line came from the Work Item
    executor after all keys had already failed. Logging the switch is what makes "how healthy
    is the pool" answerable at all, without changing which errors trigger it (still only
    ProviderRateLimitError - see above). Never logs a key, only its 1-based position and the
    provider's own already-truncated, secret-free error text.
    """

    def __init__(
        self,
        providers: list[_GenerationAndEmbeddingProvider],
        *,
        start_index_fn: Callable[[int], int] = random.randrange,
    ) -> None:
        if not providers:
            raise ProviderConfigurationError("FailoverProvider requires at least one underlying provider.")
        self._providers = providers
        self._start_index_fn = start_index_fn

    def generate(self, prompt: str) -> str:
        return self._try_each(lambda provider: provider.generate(prompt))

    def embed(self, text: str) -> list[float]:
        return self._try_each(lambda provider: provider.embed(text))

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._try_each(lambda provider: provider.embed_batch(texts))

    def _try_each(self, call):
        last_error: ProviderRateLimitError | None = None
        provider_count = len(self._providers)
        start = self._start_index_fn(provider_count)
        ordered = self._providers[start:] + self._providers[:start]
        for position, provider in enumerate(ordered):
            try:
                return call(provider)
            except ProviderRateLimitError as exc:
                last_error = exc
                logger.warning(
                    "AI provider key %d of %d is rate limited, failing over to the next key. (%s)",
                    (start + position) % provider_count + 1,
                    provider_count,
                    exc,
                )
                continue
        assert last_error is not None  # unreachable with providers non-empty (checked in __init__)
        logger.error("All %d configured AI provider keys are rate limited.", provider_count)
        raise last_error
