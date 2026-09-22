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


class ProviderRateLimitError(ProviderRequestError):
    """Raised when a provider has rejected a request because its quota is exhausted.

    Retrying a daily quota failure immediately cannot succeed and needlessly consumes worker
    attempts.  It is kept distinct from a transient ``ProviderRequestError`` so the worker can
    leave the item available for an intentional retry after the provider limit resets.
    """
