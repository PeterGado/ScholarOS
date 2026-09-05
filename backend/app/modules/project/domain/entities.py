from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.modules.project.domain.enums import ProjectStatus
from app.modules.project.domain.exceptions import InvalidProjectTitleError, InvalidProjectTopicError


@dataclass
class Project:
    """The raw input material of a research undertaking - identity, topic, source documents
    (04_Logical_Data_Model.md §3.3; narrowed by ADR-009). Nested 1:1, permanently, inside one Agent.

    `project_id`, `topic`, and `agent_id` are immutable after creation
    (05_Constraints_and_Integrity.md §5) - no method here exposes changing any of them.
    """

    agent_id: int
    title: str
    topic: str
    project_id: int | None = None
    description: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidProjectTitleError()
        if not self.topic or not self.topic.strip():
            raise InvalidProjectTopicError()

    @classmethod
    def create(cls, *, agent_id: int, title: str, topic: str, description: str | None = None) -> "Project":
        return cls(agent_id=agent_id, title=title, topic=topic, description=description)
