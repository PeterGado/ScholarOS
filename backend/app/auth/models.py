from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AuthSession(Base):
    """Authentication session persistence (04_Logical_Data_Model.md §3.2 `Session`; named
    `AuthSession` per ADR-010 Decision item 6 to avoid colliding with `sqlalchemy.orm.Session`,
    already imported throughout the rest of this codebase).

    No expiry column exists, by design: ADR-010 Decision item 2 is definitive - a session is
    valid until explicitly ended via logout, full stop. Do not add `expires_at` or any
    timeout-related column; `last_active_at` is activity metadata only.
    """

    __tablename__ = "sessions"

    session_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
