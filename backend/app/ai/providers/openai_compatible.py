import httpx

from app.ai.exceptions import ProviderConfigurationError, ProviderRequestError
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
        self._client = client if client is not None else httpx.Client(timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def generate(self, prompt: str) -> str:
        body = self._post("/chat/completions", {"model": self._model, "messages": [{"role": "user", "content": prompt}]})
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

    def _post(self, path: str, json_body: dict) -> dict:
        try:
            response = self._client.post(f"{self._base_url}{path}", json=json_body, headers=self._headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderRequestError(f"AI provider request failed with status {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError("AI provider request failed.") from exc
        return response.json()


def create_default_provider(settings: Settings) -> OpenAICompatibleProvider:
    """Constructs the configured provider (ADR-002: "selected by configuration, never by
    business logic"). The only place `Settings.ai_*` fields are read for provider wiring.
    """
    return OpenAICompatibleProvider(
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key or "",
        model=settings.ai_model,
        embedding_model=settings.ai_embedding_model,
    )
