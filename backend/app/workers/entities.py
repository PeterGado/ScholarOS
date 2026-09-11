from dataclasses import dataclass
from datetime import datetime

from app.workers.enums import WorkItemKind, WorkItemState


@dataclass
class WorkItem:
    """The durable outbox record (04_Logical_Data_Model.md §3.20; ADR-006), realized as a
    plain domain dataclass distinct from the ORM model of the same name in `models.py` -
    mirrors the `app.auth.entities.AuthSession` vs `app.auth.models.AuthSession` split.
    """

    work_item_id: int
    kind: WorkItemKind
    state: WorkItemState
    payload_reference: str
    idempotency_key: str
    attempts: int
    last_error: str | None
    created_at: datetime
    executed_at: datetime | None
    completed_at: datetime | None
