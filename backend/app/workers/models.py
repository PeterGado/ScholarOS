from datetime import datetime, timezone

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.workers.enums import WorkItemKind, WorkItemState

__all__ = ["WorkItem", "WorkItemKind", "WorkItemState"]


class WorkItem(Base):
    """The durable outbox (04_Logical_Data_Model.md §3.20; ADR-006). A unit of asynchronous
    work recorded before execution, so intent survives a process restart (06_Physical_Design_
    Strategy.md §4/§11).

    `kind` is fixed to the two values the Logical Data Model specifies - `payload_reference`
    identifies the specific unit of work (e.g. "process_document:<document_id>"), not `kind`
    itself.
    """

    __tablename__ = "work_items"

    work_item_id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[WorkItemKind] = mapped_column(Enum(WorkItemKind, native_enum=False, length=16), nullable=False)
    state: Mapped[WorkItemState] = mapped_column(
        Enum(WorkItemState, native_enum=False, length=16), nullable=False, default=WorkItemState.QUEUED
    )
    payload_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
