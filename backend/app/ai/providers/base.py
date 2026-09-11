from typing import Protocol


class TextGenerationProvider(Protocol):
    """The Provider Abstraction gateway's text-generation capability (ADR-002; 04_AI_
    Architecture.md §23). Application code depends on this interface only - never on a
    concrete provider or an HTTP client directly (04 §23.1).
    """

    def generate(self, prompt: str) -> str: ...


class EmbeddingProvider(Protocol):
    """The Provider Abstraction gateway's embedding capability (ADR-002; ADR-005 Decision 5)."""

    def embed(self, text: str) -> list[float]: ...
