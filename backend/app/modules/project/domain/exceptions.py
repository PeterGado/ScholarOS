from app.core.exceptions import ScholarOSError


class ProjectDomainError(ScholarOSError):
    """Base class for Project domain errors."""


class InvalidProjectTitleError(ProjectDomainError):
    def __init__(self) -> None:
        super().__init__("Project title must be a non-empty string.")


class InvalidProjectTopicError(ProjectDomainError):
    """Topic is the single source of truth for the owning Agent's specialization (MVP-002; ADR-009)."""

    def __init__(self) -> None:
        super().__init__("Project topic must be a non-empty string (MVP-002).")


class ProjectAlreadyExistsForAgentError(ProjectDomainError):
    """An Agent owns exactly one Project for its entire life (05_Constraints_and_Integrity.md invariant 15; ADR-009)."""

    def __init__(self, agent_id: int) -> None:
        super().__init__(f"Agent {agent_id} already owns a Project (one Project per Agent, permanent).")
        self.agent_id = agent_id


class ProjectNotFoundError(ProjectDomainError):
    def __init__(self, *, project_id: int | None = None, agent_id: int | None = None) -> None:
        super().__init__(f"Project not found (project_id={project_id}, agent_id={agent_id}).")
        self.project_id = project_id
        self.agent_id = agent_id
