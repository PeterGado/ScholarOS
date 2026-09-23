from app.core.exceptions import ScholarOSError


class AIProviderError(ScholarOSError):
    """Base class for AI Provider Abstraction errors (ADR-002)."""


class ProviderConfigurationError(AIProviderError):
    """Raised when required provider configuration (e.g. an API key or base URL) is missing
    or invalid. Never includes the offending secret value in its message.
    """


class ProviderRequestError(AIProviderError):
    """Raised when a provider call fails: network error, non-2xx response, or a response
    missing the expected content. Never includes the API key in its message.
    """
