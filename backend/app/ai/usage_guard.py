from datetime import datetime, timedelta, timezone

from app.ai.exceptions import AiUsageQuotaExceededError
from app.ai.usage_repository import AiUsageRepository
from app.core.unit_of_work import UnitOfWork

_USAGE_WINDOW = timedelta(hours=24)


class AiUsageGuard:
    """The one shared checkpoint every AI-triggering use case goes through (2026-09-21 security
    pass, ADR-011's deferred per-user quota item) - no duplicated sum/threshold logic across
    call sites.

    Deliberately estimates cost from the *input* text at the point an action is initiated
    (a chat message, a search query, a document upload, a style-extraction request), not from
    the provider's own real usage_metadata captured after the fact. Capturing exact provider
    usage would mean changing both TextGenerationProvider/EmbeddingProvider's return types and
    every call site and test fake that mocks them - a large, invasive change for a cap that
    only needs to be roughly right, not billing-grade exact. This also means two of the seven
    real AI call sites (_summarize_if_needed/_extract_memory_if_needed, both executor-internal
    "bonus" costs that piggyback on an already-approved chat reply) are not separately metered -
    a deliberate, documented simplification, not an oversight.
    """

    def __init__(self, repository: AiUsageRepository, unit_of_work: UnitOfWork, *, daily_token_cap: int | None) -> None:
        self._repository = repository
        self._uow = unit_of_work
        self._daily_token_cap = daily_token_cap

    def check_and_record(self, *, user_id: int, estimated_tokens: int) -> None:
        """Takes an already-computed estimate rather than raw input, so each call site can
        estimate however fits its own input shape (app.ai.token_estimate.estimate_tokens for
        text - a prompt, a query, pooled sample text - or a direct byte-length calc for raw
        uploaded content) without this guard needing to know or care which.

        No-ops entirely when no cap is configured (Settings.ai_daily_token_cap_per_user is
        None) - matches registration_invite_code's own "unset disables the gate" convention.
        """
        if self._daily_token_cap is None:
            return

        since = datetime.now(timezone.utc) - _USAGE_WINDOW
        usage_so_far = self._repository.get_usage_since(user_id=user_id, since=since)
        if usage_so_far + estimated_tokens > self._daily_token_cap:
            raise AiUsageQuotaExceededError()

        try:
            self._repository.record(user_id=user_id, tokens=estimated_tokens)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
