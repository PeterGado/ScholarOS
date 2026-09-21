from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AiUsageRecord(Base):
    """AI usage cap ledger (2026-09-21 security pass, ADR-011's deferred per-user quota item).
    One row per checked AI-triggering action, not a running counter - "usage in the last 24h"
    is just `SUM(tokens) WHERE user_id = ? AND recorded_at >= now - 24h`
    (app.ai.usage_repository), so the daily window needs no separate reset logic; old rows
    simply fall outside the range as time passes.

    `tokens` is an estimate (app.ai.token_estimate.estimate_tokens), not an exact count from
    the provider - see app.ai.usage_guard.AiUsageGuard's own docstring for why.
    """

    __tablename__ = "ai_usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    tokens: Mapped[int] = mapped_column(nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (Index("ix_ai_usage_records_user_id_recorded_at", "user_id", "recorded_at"),)
