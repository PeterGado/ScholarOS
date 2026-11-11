from dataclasses import dataclass
from datetime import UTC, datetime

from app.ai.usage_guard import USAGE_WINDOW
from app.ai.usage_repository import AiUsageRepository

__all__ = ["AiUsageSnapshot", "GetAiUsageSnapshotUseCase"]


@dataclass(frozen=True)
class AiUsageSnapshot:
    """Read-only view of one user's AI usage over the same rolling window
    AiUsageGuard enforces the cap against - the data behind "how much AI budget do I have
    left", which until now existed only as rows nothing could read back.

    `remaining_tokens` is None when no cap is configured (Settings.
    ai_daily_token_cap_per_user is None), which means "unlimited" rather than "zero left" -
    that distinction is the whole reason this isn't just a plain subtraction at the call site.
    """

    used_tokens: int
    daily_token_cap: int | None

    @property
    def remaining_tokens(self) -> int | None:
        if self.daily_token_cap is None:
            return None
        return max(0, self.daily_token_cap - self.used_tokens)

    @property
    def window_hours(self) -> float:
        return USAGE_WINDOW.total_seconds() / 3600


class GetAiUsageSnapshotUseCase:
    """Reads the AI usage ledger for one user - the read-only counterpart of AiUsageGuard
    (app.ai.usage_guard). Both share USAGE_WINDOW so a reported
    figure always matches what the guard would actually accept, and neither owns any SQL:
    the window sum comes from AiUsageRepository (app.ai.usage_repository), the same port the
    guard already goes through.
    """

    def __init__(self, repository: AiUsageRepository, *, daily_token_cap: int | None) -> None:
        self._repository = repository
        self._daily_token_cap = daily_token_cap

    def execute(self, *, user_id: int) -> AiUsageSnapshot:
        since = datetime.now(UTC) - USAGE_WINDOW
        return AiUsageSnapshot(
            used_tokens=self._repository.get_usage_since(user_id=user_id, since=since),
            daily_token_cap=self._daily_token_cap,
        )
