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


class ProviderContentBlockedError(ProviderRequestError):
    """Raised when the AI provider's own safety filtering blocked a prompt or its response
    (2026-09-30, added after friend testing found violent/harassing/derogatory input passing
    straight through with no moderation at all). A subclass of ProviderRequestError, not a
    sibling, so it automatically gets the same HTTP 502 handling as any other provider request
    failure (app.api.exception_handlers) without a separate registration - the same reasoning
    ProviderRateLimitError already uses.

    Retrying the same message unmodified cannot succeed any more than a rate limit can, so the
    worker treats this the same way: fail permanently on the first attempt rather than burning
    through the normal retry budget (see app.workers.executor's `isinstance(exc, ...)` checks).
    """

    def __init__(self) -> None:
        super().__init__(
            "This message couldn't be processed because it was flagged by the AI provider's "
            "safety filters. Please rephrase and try again."
        )


class AiUsageQuotaExceededError(AIProviderError):
    """Raised by AiUsageGuard (app.ai.usage_guard, 2026-09-21 security pass) when a user's
    estimated AI usage over the last 24 hours would exceed Settings.ai_daily_token_cap_per_user.
    Distinct from a rate-limit 429 (too fast) - this means "out of budget for today", not
    "slow down". Never includes the cap or usage numbers in the message - not sensitive, but
    the specific figures aren't this error's job to communicate; a client that wants them reads
    Settings.ai_daily_token_cap_per_user's own documented default.
    """

    def __init__(self) -> None:
        super().__init__("Daily AI usage limit reached. Try again after it resets.")
