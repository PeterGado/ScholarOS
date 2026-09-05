from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.modules.agent.domain.enums import AgentStatus


@dataclass
class Agent:
    """The user's permanent, specialized research workspace (04_Logical_Data_Model.md §3.21; ADR-009).

    `agent_id` and `user_id` are immutable after creation (05_Constraints_and_Integrity.md §5) -
    no method here exposes changing either.
    """

    user_id: int
    agent_id: int | None = None
    status: AgentStatus = AgentStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    @classmethod
    def create(cls, *, user_id: int) -> "Agent":
        return cls(user_id=user_id)

    @property
    def is_active(self) -> bool:
        return self.status == AgentStatus.ACTIVE and self.deleted_at is None
