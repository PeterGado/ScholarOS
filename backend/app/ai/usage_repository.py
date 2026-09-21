from datetime import datetime
from typing import Protocol


class AiUsageRepository(Protocol):
    """Persistence port for the AI usage cap ledger (app.ai.models.AiUsageRecord). Mirrors
    app.auth.repository's own Protocol-per-port style.
    """

    def record(self, *, user_id: int, tokens: int) -> None: ...

    def get_usage_since(self, *, user_id: int, since: datetime) -> int:
        """Sum of `tokens` recorded for this user at or after `since`. Returns 0, never None,
        when the user has no usage in that window."""
        ...
