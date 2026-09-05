from app.modules.project.domain.entities import Project
from app.modules.project.domain.exceptions import ProjectAlreadyExistsForAgentError
from app.modules.project.domain.repositories import ProjectRepository


class CreateProjectUseCase:
    """Realizes 05_Backend_Architecture.md §11.1: create the research project nested inside
    its owning Agent. Invoked as a collaborator of the Agent module's workspace-creation use
    case (§22.1) - there is no standalone "create a Project without an Agent" flow in the MVP.
    Does not commit; the caller controls the transaction boundary.
    """

    def __init__(self, project_repository: ProjectRepository) -> None:
        self._projects = project_repository

    def execute(self, *, agent_id: int, title: str, topic: str, description: str | None = None) -> Project:
        if self._projects.get_by_agent_id(agent_id) is not None:
            raise ProjectAlreadyExistsForAgentError(agent_id)

        project = Project.create(agent_id=agent_id, title=title, topic=topic, description=description)
        return self._projects.add(project)
