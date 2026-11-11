from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

__all__ = [
    "ProviderTokenUsage",
    "ProviderUsageMeter",
    "metering_provider_usage",
    "observe_provider_usage",
]


@dataclass(frozen=True)
class ProviderTokenUsage:
    """One provider call's usage, exactly as the provider reported it - never estimated here.

    `input_tokens` is the prompt/embedding input the provider billed; `output_tokens` is what
    it generated (0 for embeddings). Providers that expose no token counts at all (Gemini's
    embedding endpoint reports only an optional `billable_character_count`) simply report
    nothing, leaving the meter's `observed_calls` untouched rather than inventing a number -
    see AiUsageGuard.record_metered (app.ai.usage_guard) for how a site with no observations
    falls back to its own estimate instead.
    """

    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ProviderUsageMeter:
    """Accumulates the provider-reported usage of every AI call made while its
    `metering_provider_usage()` block is active.

    Deliberately read from a ContextVar rather than threaded through every provider and use
    case signature: `TextGenerationProvider`/`EmbeddingProvider` (app.ai.providers.base) are
    implemented by four real providers plus every test fake in the suite, and changing their
    method signatures or return types to carry usage would have been an invasive change for a
    number the caller only needs once, at the end of the whole operation. A provider call
    outside any metering block is a silent no-op (`observe_provider_usage`), which is exactly
    what every existing unit test - and production code paths that never wanted accounting -
    keeps getting.

    ContextVar semantics fit the two places this is used: a sync FastAPI endpoint's body and a
    Work Item executor thread both run their provider calls on the same thread that opened the
    block, so the value set here is the value observed there (nested blocks restore the outer
    meter on exit, so a metered use case called from another metered one cannot swallow the
    outer block's totals).
    """

    def __init__(self) -> None:
        self._input_tokens = 0
        self._output_tokens = 0
        self.observed_calls = 0

    def observe(self, usage: ProviderTokenUsage) -> None:
        # Negative counts would mean a provider reported something nonsensical; clamping keeps
        # the ledger monotonic instead of letting one bad response reduce a user's recorded usage.
        self._input_tokens += max(0, usage.input_tokens)
        self._output_tokens += max(0, usage.output_tokens)
        self.observed_calls += 1

    @property
    def input_tokens(self) -> int:
        return self._input_tokens

    @property
    def output_tokens(self) -> int:
        return self._output_tokens

    @property
    def total_tokens(self) -> int:
        return self._input_tokens + self._output_tokens


_current_meter: ContextVar[ProviderUsageMeter | None] = ContextVar(
    "ai_provider_usage_meter", default=None
)


@contextmanager
def metering_provider_usage() -> Iterator[ProviderUsageMeter]:
    """Collect exact, provider-reported usage for the duration of the block."""
    meter = ProviderUsageMeter()
    token = _current_meter.set(meter)
    try:
        yield meter
    finally:
        _current_meter.reset(token)


def observe_provider_usage(*, input_tokens: int, output_tokens: int) -> None:
    """Called by a concrete provider right after a successful call. A no-op outside any
    metering block - see ProviderUsageMeter's own docstring for why that is the default.
    """
    if input_tokens <= 0 and output_tokens <= 0:
        # An all-zero report carries no information (a response with no usage block, or an
        # embedding endpoint that has no token counts to give). Counting it as an observation
        # would mask AiUsageGuard.record_metered's estimate fallback with a meaningless zero.
        return
    meter = _current_meter.get()
    if meter is not None:
        meter.observe(ProviderTokenUsage(input_tokens=input_tokens, output_tokens=output_tokens))
