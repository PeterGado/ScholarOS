from app.ai.exceptions import ProviderConfigurationError


class UnavailableAIProvider:
    """Provider used when processing is enabled but required AI configuration is absent."""

    def _raise(self) -> None:
        raise ProviderConfigurationError(
            "AI document processing is unavailable because AI_API_KEY is not configured."
        )

    def generate(self, prompt: str) -> str:
        self._raise()

    def embed(self, text: str) -> list[float]:
        self._raise()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._raise()