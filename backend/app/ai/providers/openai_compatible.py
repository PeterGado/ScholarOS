import httpx

from app.ai.exceptions import ProviderConfigurationError, ProviderRateLimitError, ProviderRequestError
from app.core.config import Settings

__all__ = ["OpenAICompatibleProvider", "create_default_provider"]


class OpenAICompatibleProvider:
    """First concrete realization of the Provider Abstraction gateway (ADR-002 Decision 3;
    Backend_Slice2_Implementation_Plan.md §4). Implements both `TextGenerationProvider` and
    `EmbeddingProvider` (app.ai.providers.base) against an OpenAI-compatible HTTP API - no
    provider SDK is installed, keeping the swap cost to one file if a different provider is
    ever selected.

    Never logs or returns the API key; `httpx.Client` is injectable so tests can supply a
    `MockTransport` instead of making real network calls (ADR-005 §AI Engineering
    Implications: retrieval-adjacent components must be testable without network access).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        embedding_model: str,
        max_output_tokens: int | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise ProviderConfigurationError("AI provider base URL is not configured.")
        if not api_key:
            raise ProviderConfigurationError("AI provider API key is not configured.")

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._embedding_model = embedding_model
        self._max_output_tokens = max_output_tokens
        self._client = client if client is not None else httpx.Client(timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def generate(self, prompt: str) -> str:
        request_body = {"model": self._model, "messages": [{"role": "user", "content": prompt}]}
        if self._max_output_tokens is not None:
            request_body["max_tokens"] = self._max_output_tokens
        body = self._post("/chat/completions", request_body)
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderRequestError("Provider response did not contain expected generated content.") from exc

    def embed(self, text: str) -> list[float]:
        body = self._post("/embeddings", {"model": self._embedding_model, "input": text})
        try:
            return body["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderRequestError("Provider response did not contain an expected embedding.") from exc

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        body = self._post("/embeddings", {"model": self._embedding_model, "input": texts})
        try:
            items = sorted(body["data"], key=lambda item: item["index"])
            embeddings = [item["embedding"] for item in items]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderRequestError("Provider response did not contain an expected embedding.") from exc

        if len(embeddings) != len(texts):
            raise ProviderRequestError("Provider returned a different number of embeddings than requested.")
        return embeddings

    def _post(self, path: str, json_body: dict) -> dict:
        try:
            response = self._client.post(f"{self._base_url}{path}", json=json_body, headers=self._headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _response_detail(exc.response)
            if exc.response.status_code == 429:
                raise ProviderRateLimitError(
                    "AI provider rate limit reached. Please retry after the provider quota resets."
                    f" {detail}"
                ) from exc
            raise ProviderRequestError(
                f"AI provider request failed with status {exc.response.status_code}. {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"AI provider request failed. (Provider detail: {exc})") from exc
        return response.json()


_MAX_PROVIDER_DETAIL_LENGTH = 500
"""2026-09-30, found while diagnosing a real rate-limit incident: every raise site here used to
discard the provider's own response body entirely, leaving only a generic "rate limit reached"/
"request failed" message in both `WorkItem.last_error` and server logs. The response body is
genuinely useful - an OpenAI-compatible 429 typically names the specific quota exceeded - and
contains no secret (never the API key; this provider's own contract already promises never to
leak it, confirmed by inspection of what these bodies actually contain). Truncated defensively
in case an unusually verbose error body ever shows up."""


def _response_detail(response: httpx.Response) -> str:
    try:
        detail = response.text.strip()
    except Exception:  # noqa: BLE001 - reading the body must never itself raise here
        return ""
    if len(detail) > _MAX_PROVIDER_DETAIL_LENGTH:
        detail = detail[:_MAX_PROVIDER_DETAIL_LENGTH] + "..."
    return f"(Provider detail: {detail})" if detail else ""


def create_default_provider(settings: Settings) -> OpenAICompatibleProvider:
    """Constructs the configured provider (ADR-002: "selected by configuration, never by
    business logic"). The only place `Settings.ai_*` fields are read for provider wiring.
    """
    return OpenAICompatibleProvider(
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key or "",
        model=settings.ai_model,
        embedding_model=settings.ai_embedding_model,
        max_output_tokens=settings.ai_max_output_tokens,
    )
