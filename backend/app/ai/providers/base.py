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

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embeds several texts in one provider call, in the same order as `texts`. Exists
        alongside `embed` (rather than replacing it) because most callers genuinely need only
        one text (e.g. a single search query); document knowledge extraction needs many at
        once and one-call-per-text was blowing through free-tier daily request quotas on a
        single real multi-page document."""
        ...
