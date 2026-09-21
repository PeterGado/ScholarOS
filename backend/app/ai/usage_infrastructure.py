from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.models import AiUsageRecord
from app.ai.usage_repository import AiUsageRepository


class SqlAlchemyAiUsageRepository(AiUsageRepository):
    """Concrete AiUsageRepository (app.ai.usage_repository). Owns every SQLAlchemy detail for
    AiUsageRecord persistence - AiUsageGuard never imports this module or SQLAlchemy directly.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, *, user_id: int, tokens: int) -> None:
        self._session.add(AiUsageRecord(user_id=user_id, tokens=tokens))
        self._session.flush()

    def get_usage_since(self, *, user_id: int, since: datetime) -> int:
        total = self._session.execute(
            select(func.sum(AiUsageRecord.tokens)).where(
                AiUsageRecord.user_id == user_id, AiUsageRecord.recorded_at >= since
            )
        ).scalar_one_or_none()
        return total or 0
