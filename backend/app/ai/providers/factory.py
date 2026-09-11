from app.ai.exceptions import ProviderConfigurationError
from app.ai.providers.google_genai import create_google_genai_provider
from app.ai.providers.openai_compatible import create_default_provider as create_openai_compatible_provider

__all__ = ["create_provider"]

_FACTORIES = {
    "google_genai": create_google_genai_provider,
    "openai_compatible": create_openai_compatible_provider,
}


def create_provider(settings):
    """Dispatches to the configured concrete provider by `settings.ai_provider` (ADR-002:
    "selected by configuration, never by business logic"). The only place that reads
    `ai_provider` to make this choice - callers depend on the returned object satisfying
    `TextGenerationProvider`/`EmbeddingProvider` (app.ai.providers.base), never on which
    concrete class it is.
    """
    factory = _FACTORIES.get(settings.ai_provider)
    if factory is None:
        raise ProviderConfigurationError(f"Unknown AI provider: {settings.ai_provider!r}")
    return factory(settings)
