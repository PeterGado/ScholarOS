from typing import Protocol

from google import genai
from google.genai import types

from app.ai.exceptions import (
    ProviderConfigurationError,
    ProviderContentBlockedError,
    ProviderRateLimitError,
    ProviderRequestError,
)
from app.ai.providers.failover import FailoverProvider
from app.ai.providers.rate_limited import RateLimitedProvider

__all__ = ["GoogleGenAIProvider", "create_google_genai_provider"]

_SAFETY_SETTINGS = [
    types.SafetySetting(category=category, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)
    for category in (
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    )
]
"""2026-09-30: added after friend testing found violent/harassing/derogatory chat messages
passing straight through with no moderation at all - the SDK applies its own default
thresholds when safety_settings is left unset, but that default was never deliberately chosen
here and wasn't catching what friends actually tried. BLOCK_MEDIUM_AND_ABOVE (Google's own
general-purpose recommendation) blocks medium-and-higher-probability harmful content while
still allowing a thesis or research project to discuss difficult topics (violence, abuse,
hate) at a factual, non-graphic register - a stricter BLOCK_LOW_AND_ABOVE risks false-positive
blocking legitimate academic writing. HARM_CATEGORY_CIVIC_INTEGRITY/JAILBREAK and the IMAGE_*
categories are left at the SDK default - out of scope for a text-only writing assistant.
"""


class _GenAIClient(Protocol):
    """The minimal slice of `google.genai.Client` this provider depends on - lets tests
    inject a fake without needing to construct a real SDK client (mirrors
    OpenAICompatibleProvider's injectable `httpx.Client` for the same reason).
    """

    models: object


class GoogleGenAIProvider:
    """Second concrete realization of the Provider Abstraction gateway (ADR-002), using
    Google's native `google-genai` SDK. Selected as Slice 2's actual first concrete provider
    (Stage 9 finding: the originally-recorded OpenAI-compatible-shim choice in
    Backend_Slice2_Implementation_Plan.md §4 depended on Gemini's OpenAI-compatibility layer,
    which required guessing at model names and endpoint quirks live during validation; the
    native SDK is the more robust choice for this provider).

    Implements the same `TextGenerationProvider`/`EmbeddingProvider` protocols (app.ai.
    providers.base) as `OpenAICompatibleProvider` - swapping providers costs one new file,
    not a redesign of anything that depends on the gateway.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        embedding_model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        client: _GenAIClient | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("AI provider API key is not configured.")

        self._model = model
        self._embedding_model = embedding_model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._client = client if client is not None else genai.Client(api_key=api_key)

    def generate(self, prompt: str) -> str:
        config = types.GenerateContentConfig(
            max_output_tokens=self._max_output_tokens,
            temperature=self._temperature,
            safety_settings=_SAFETY_SETTINGS,
        )
        try:
            response = self._client.models.generate_content(model=self._model, contents=prompt, config=config)
        except Exception as exc:  # noqa: BLE001 - the SDK's exception hierarchy is not part of our contract
            if _is_rate_limit_error(exc):
                raise ProviderRateLimitError(
                    "AI provider rate limit reached. Please retry after the provider quota resets."
                    f" {_provider_detail(exc)}"
                ) from exc
            raise ProviderRequestError(f"AI provider request failed. {_provider_detail(exc)}") from exc

        text = getattr(response, "text", None)
        if not text:
            if _is_safety_blocked(response):
                raise ProviderContentBlockedError()
            raise ProviderRequestError("Provider response did not contain expected generated content.")
        return text

    def embed(self, text: str) -> list[float]:
        try:
            response = self._client.models.embed_content(model=self._embedding_model, contents=text)
        except Exception as exc:  # noqa: BLE001 - the SDK's exception hierarchy is not part of our contract
            if _is_rate_limit_error(exc):
                raise ProviderRateLimitError(
                    "AI provider rate limit reached. Please retry after the provider quota resets."
                    f" {_provider_detail(exc)}"
                ) from exc
            raise ProviderRequestError(f"AI provider request failed. {_provider_detail(exc)}") from exc

        try:
            return list(response.embeddings[0].values)
        except (IndexError, AttributeError, TypeError) as exc:
            raise ProviderRequestError("Provider response did not contain an expected embedding.") from exc

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = self._client.models.embed_content(model=self._embedding_model, contents=texts)
        except Exception as exc:  # noqa: BLE001 - the SDK's exception hierarchy is not part of our contract
            if _is_rate_limit_error(exc):
                raise ProviderRateLimitError(
                    "AI provider rate limit reached. Please retry after the provider quota resets."
                    f" {_provider_detail(exc)}"
                ) from exc
            raise ProviderRequestError(f"AI provider request failed. {_provider_detail(exc)}") from exc

        try:
            embeddings = [list(item.values) for item in response.embeddings]
        except (AttributeError, TypeError) as exc:
            raise ProviderRequestError("Provider response did not contain an expected embedding.") from exc

        if len(embeddings) != len(texts):
            raise ProviderRequestError("Provider returned a different number of embeddings than requested.")
        return embeddings


def create_google_genai_provider(settings) -> GoogleGenAIProvider | FailoverProvider:
    """Constructs the configured provider (ADR-002: "selected by configuration, never by
    business logic"). The only place `Settings.ai_*` fields are read for this provider's wiring.

    `settings.ai_api_keys` (2026-09-30, multi-account failover), when set, takes priority over
    the single `ai_api_key` - one `GoogleGenAIProvider` is constructed per key, each paced by its
    own `RateLimitedProvider` (settings.ai_max_calls_per_minute_per_key), and the whole set is
    wrapped in a `FailoverProvider`, which moves to the next key only when the current one's
    quota is exhausted (see that class's own docstring). Every existing single-key deployment
    leaves `ai_api_keys` unset and is completely unaffected - pacing is only applied on this
    multi-key path.
    """
    if settings.ai_api_keys:
        return FailoverProvider(
            [
                RateLimitedProvider(
                    GoogleGenAIProvider(
                        api_key=api_key,
                        model=settings.ai_model,
                        embedding_model=settings.ai_embedding_model,
                        max_output_tokens=settings.ai_max_output_tokens,
                        temperature=settings.ai_temperature,
                    ),
                    max_calls_per_minute=settings.ai_max_calls_per_minute_per_key,
                )
                for api_key in settings.ai_api_keys
            ]
        )

    return GoogleGenAIProvider(
        api_key=settings.ai_api_key or "",
        model=settings.ai_model,
        embedding_model=settings.ai_embedding_model,
        max_output_tokens=settings.ai_max_output_tokens,
        temperature=settings.ai_temperature,
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    """Recognize the native SDK's quota error without coupling to its unstable exception API."""
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status_code == 429:
        return True
    return "resource_exhausted" in str(exc).lower() or "rate limit" in str(exc).lower()


_BLOCKED_FINISH_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "IMAGE_SAFETY"}


def _is_safety_blocked(response) -> bool:
    """A safety block never raises from the SDK call itself - the request succeeds and comes
    back with no usable text, either because the whole prompt was rejected before generation
    started (`prompt_feedback.block_reason` set, no candidates) or the response was cut off
    mid-generation (`candidates[0].finish_reason` is SAFETY/PROHIBITED_CONTENT/etc). Distinguishing
    this from a genuinely malformed response is what lets `generate()` raise
    ProviderContentBlockedError's clear message instead of a generic "no content" error.
    Reads every field via getattr with a default so a test double missing these SDK-specific
    attributes (as every existing FakeGenerateResponse does) is correctly treated as not blocked.
    """
    prompt_feedback = getattr(response, "prompt_feedback", None)
    if getattr(prompt_feedback, "block_reason", None):
        return True

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return False
    finish_reason = getattr(candidates[0], "finish_reason", None)
    reason_name = getattr(finish_reason, "name", finish_reason)
    return reason_name in _BLOCKED_FINISH_REASONS


_MAX_PROVIDER_DETAIL_LENGTH = 500
"""2026-09-30, found while diagnosing a real rate-limit incident: every raise site here used to
discard the SDK's own exception text entirely, leaving only a generic "rate limit reached"/
"request failed" message - both in what's shown to the user (`WorkItem.last_error`, surfaced via
mark_failed(error=str(exc))) and in server logs (which only ever logged that same generic
`str(exc)`, since `exc` there is already this wrapped exception, not the original one). The
SDK's own message is genuinely useful here - Google's 429 responses typically name the specific
quota exceeded (e.g. a free-tier per-day request limit vs. per-minute) - and contains no secret
(never the API key; confirmed by inspection of what these errors actually contain, and this
provider's own contract already promises never to leak it). Truncated defensively in case an
unusually verbose SDK error body ever shows up."""


def _provider_detail(exc: Exception) -> str:
    detail = str(exc).strip()
    if len(detail) > _MAX_PROVIDER_DETAIL_LENGTH:
        detail = detail[:_MAX_PROVIDER_DETAIL_LENGTH] + "..."
    return f"(Provider detail: {detail})" if detail else ""
