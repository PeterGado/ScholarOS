from datetime import UTC, datetime, timedelta

from app.ai.exceptions import AiUsageQuotaExceededError
from app.ai.provider_usage import ProviderUsageMeter
from app.ai.usage_repository import AiUsageRepository
from app.core.unit_of_work import UnitOfWork

USAGE_WINDOW = timedelta(hours=24)
"""The rolling window the cap is enforced over. Public (not `_`-prefixed) because
app.ai.usage_snapshot.GetAiUsageSnapshotUseCase reads the same window to report usage - a
read-only view that used a different length than the guard enforcing the cap would show the
user numbers that don't match what actually gets rejected."""


class AiUsageGuard:
    """The one shared checkpoint every AI-triggering use case goes through (2026-09-21 security
    pass, ADR-011's deferred per-user quota item) - no duplicated sum/threshold logic across
    call sites.

    Two separate operations, deliberately not combined (2026-10-23):

    - `check` is the cap gate, called *before* the work, from an estimate of the input the
      action is about to send. It cannot be exact - the output does not exist yet - so it
      remains a chars/4-style estimate (app.ai.token_estimate), enough to bound a user's daily
      spend without a provider round trip.
    - `record` (usually via `record_metered`) writes what actually happened, *after* the work,
      from the provider's own reported token counts (app.ai.provider_usage). Splitting them is
      what stops the old single `check_and_record` from double-counting a request: the gate no
      longer writes an estimate row that the real usage would then have to be added on top of.

    Both no-op entirely when no cap is configured (Settings.ai_daily_token_cap_per_user is
    None): unset turns the whole feature off, enforcement *and* bookkeeping, exactly as it did
    before the split. That is the same "unset disables the feature" convention
    registration_invite_code/turnstile_secret_key already follow - a deployment that opted out
    of the cap does not get ledger rows written for it either. GET /ai/usage
    (app.api.routes.ai_usage) therefore reports 0/unlimited in that configuration, which is
    accurate: nothing is being tracked.
    """

    def __init__(self, repository: AiUsageRepository, unit_of_work: UnitOfWork, *, daily_token_cap: int | None) -> None:
        self._repository = repository
        self._uow = unit_of_work
        self._daily_token_cap = daily_token_cap

    def check(self, *, user_id: int, estimated_tokens: int) -> None:
        """Raises AiUsageQuotaExceededError if this action would take the user over the cap.
        Records nothing - see this class's own docstring for why the write is separate.

        No-ops entirely when no cap is configured (Settings.ai_daily_token_cap_per_user is
        None) - matches registration_invite_code's own "unset disables the gate" convention.
        """
        if self._daily_token_cap is None:
            return

        since = datetime.now(UTC) - USAGE_WINDOW
        usage_so_far = self._repository.get_usage_since(user_id=user_id, since=since)
        if usage_so_far + estimated_tokens > self._daily_token_cap:
            raise AiUsageQuotaExceededError()

    def record(self, *, user_id: int, tokens: int) -> None:
        """Writes one ledger row for usage that has actually been consumed. Never checks the
        cap: this is the after-the-fact truth, and refusing to record it would make the ledger
        understate what the user really spent.
        """
        if self._daily_token_cap is None or tokens <= 0:
            return
        try:
            self._repository.record(user_id=user_id, tokens=tokens)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

    def record_metered(
        self,
        *,
        user_id: int,
        meter: ProviderUsageMeter,
        fallback_estimate: int | None = None,
    ) -> None:
        """Records a metered block's exact provider-reported total.

        `fallback_estimate` covers the one real gap in exact counts: a provider that exposes no
        token usage at all. Gemini's embedding endpoint is the concrete case - it returns
        embeddings and an optional `billable_character_count` aimed at a different product, so
        an embedding-only metered block observes zero calls and would otherwise record nothing
        (silently understating usage, not overstating it). The fallback is used *only* when
        nothing at all was observed; a block where some calls reported and others did not keeps
        the real numbers rather than mixing an estimate in.
        """
        if meter.observed_calls:
            self.record(user_id=user_id, tokens=meter.total_tokens)
        elif fallback_estimate is not None:
            self.record(user_id=user_id, tokens=fallback_estimate)
