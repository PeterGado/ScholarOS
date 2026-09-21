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
