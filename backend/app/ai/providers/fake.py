import json
import re
import time

from app.ai.exceptions import ProviderRequestError
from app.ai.provider_usage import observe_provider_usage
from app.ai.token_estimate import estimate_tokens

__all__ = ["FakeAIProvider", "create_fake_provider"]

_BATCH_COUNT_RE = re.compile(r"JSON array of exactly (\d+) objects")

_SIMULATED_LATENCY_SECONDS = 0.3
"""A real provider call always has network round-trip latency; an instant fake response broke
chat-reply-failure.spec.ts's retry assertion (found while verifying this provider against that
spec locally) - the retried work item could be claimed and fail again before the frontend's
post-retry status refetch ever observed the brief "queued" state, so the "Thinking..." indicator
never rendered. This keeps the fake provider fast but not suspiciously instantaneous."""


class FakeAIProvider:
    """Deterministic, no-network provider selected via `ai_provider="fake"` (ADR-002's own
    "selected by configuration" pattern) - lets CI run e2e specs that need *a* provider
    response without a real API key or a live billable call, closing the external audit's
    finding that only 2 of 8 Playwright specs ran in CI because the rest assumed a real
    provider was required.

    `generate()` recognizes the few structured-JSON prompt shapes this codebase's own
    use cases parse (semantic_classification.py, style_extraction.py) by sniffing fixed
    literal text that survives each prompt template's `.format()` call, and returns a
    response shaped to satisfy that specific parser - never by understanding the prompt's
    actual content, which a deterministic fake has no way to do. Anything else (chat
    replies, multi-pass critique/revision, memory extraction, conversation summarization)
    gets one fixed plain-text reply, since none of those call sites require the response to
    have any particular shape.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    def generate(self, prompt: str) -> str:
        time.sleep(_SIMULATED_LATENCY_SECONDS)
        if self._fail:
            raise ProviderRequestError(
                "AI provider request failed. (Provider detail: fake provider configured to "
                "fail via AI_FAKE_PROVIDER_FAIL, for e2e failure-path testing)"
            )

        if '"characteristics":' in prompt:
            reply = json.dumps(
                {
                    "characteristics": [
                        {
                            "characteristic_type": "structure",
                            "signal": "Opens paragraphs with a short topic sentence before elaborating.",
                            "confidence": 0.8,
                        }
                    ]
                }
            )
        elif batch_match := _BATCH_COUNT_RE.search(prompt):
            count = int(batch_match.group(1))
            reply = json.dumps(
                [
                    {
                        "element_type": "concept",
                        "label": f"Fake classification {index + 1}",
                        "description": "Deterministic placeholder classification from the fake AI provider.",
                    }
                    for index in range(count)
                ]
            )
        elif '"element_type"' in prompt:
            reply = json.dumps(
                {
                    "element_type": "concept",
                    "label": "Fake classification",
                    "description": "Deterministic placeholder classification from the fake AI provider.",
                }
            )
        else:
            reply = "This is a deterministic reply from the fake AI provider used in CI."

        # Usage reporting (2026-10-23): a deterministic provider has no real token accounting to
        # report, so it reports the same chars/4 estimate a real provider call would have been
        # approximated with before exact usage existed. That keeps e2e specs using this provider
        # exercising the real metering/recording path (app.ai.provider_usage) end-to-end without
        # inventing numbers that would look like something the AI actually billed.
        observe_provider_usage(input_tokens=estimate_tokens(prompt), output_tokens=estimate_tokens(reply))
        return reply

    def embed(self, text: str) -> list[float]:
        time.sleep(_SIMULATED_LATENCY_SECONDS)
        if self._fail:
            raise ProviderRequestError(
                "AI provider request failed. (Provider detail: fake provider configured to "
                "fail via AI_FAKE_PROVIDER_FAIL, for e2e failure-path testing)"
            )
        observe_provider_usage(input_tokens=estimate_tokens(text), output_tokens=0)
        return [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        time.sleep(_SIMULATED_LATENCY_SECONDS)
        if self._fail:
            raise ProviderRequestError(
                "AI provider request failed. (Provider detail: fake provider configured to "
                "fail via AI_FAKE_PROVIDER_FAIL, for e2e failure-path testing)"
            )
        observe_provider_usage(input_tokens=sum(estimate_tokens(text) for text in texts), output_tokens=0)
        return [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8] for _ in texts]


def create_fake_provider(settings) -> FakeAIProvider:
    return FakeAIProvider(fail=settings.ai_fake_provider_fail)
