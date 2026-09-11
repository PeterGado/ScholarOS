from typing import Protocol

from google import genai

from app.ai.exceptions import ProviderConfigurationError, ProviderRequestError

__all__ = ["GoogleGenAIProvider", "create_google_genai_provider"]


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

    def __init__(self, *, api_key: str, model: str, embedding_model: str, client: _GenAIClient | None = None) -> None:
        if not api_key:
            raise ProviderConfigurationError("AI provider API key is not configured.")

        self._model = model
        self._embedding_model = embedding_model
        self._client = client if client is not None else genai.Client(api_key=api_key)

    def generate(self, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(model=self._model, contents=prompt)
        except Exception as exc:  # noqa: BLE001 - the SDK's exception hierarchy is not part of our contract
            raise ProviderRequestError("AI provider request failed.") from exc

        text = getattr(response, "text", None)
        if not text:
            raise ProviderRequestError("Provider response did not contain expected generated content.")
        return text

    def embed(self, text: str) -> list[float]:
        try:
            response = self._client.models.embed_content(model=self._embedding_model, contents=text)
        except Exception as exc:  # noqa: BLE001 - the SDK's exception hierarchy is not part of our contract
            raise ProviderRequestError("AI provider request failed.") from exc

        try:
            return list(response.embeddings[0].values)
        except (IndexError, AttributeError, TypeError) as exc:
            raise ProviderRequestError("Provider response did not contain an expected embedding.") from exc


def create_google_genai_provider(settings) -> GoogleGenAIProvider:
    """Constructs the configured provider (ADR-002: "selected by configuration, never by
    business logic"). The only place `Settings.ai_*` fields are read for this provider's wiring.
    """
    return GoogleGenAIProvider(
        api_key=settings.ai_api_key or "",
        model=settings.ai_model,
        embedding_model=settings.ai_embedding_model,
    )
