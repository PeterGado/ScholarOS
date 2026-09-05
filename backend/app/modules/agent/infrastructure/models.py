from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.modules.agent.domain.enums import AgentStatus

__all__ = ["Agent", "AgentStatus"]


class Agent(Base):
    """Agent Service persistence (05_Backend_Architecture.md §22; 04_Logical_Data_Model.md §3.21; ADR-009)."""

    __tablename__ = "agents"

    agent_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, unique=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, native_enum=False, length=16), nullable=False, default=AgentStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
