from dataclasses import dataclass

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentAlreadyExistsForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.domain.entities import Project


@dataclass
class AgentWorkspace:
    """The result of creating an Agent workspace: the Agent and its one, permanent Project (ADR-009)."""

    agent: Agent
    project: Project


class CreateAgentWorkspaceUseCase:
    """Realizes 05_Backend_Architecture.md §22.1: create an Agent together with its one,
    permanent Project from the user-supplied topic. Enforces the one-Agent-per-user MVP
    boundary (§22.1; ADR-009) and the Agent-Project atomicity invariant (invariant 15) by
    committing both writes as a single transaction - if Project creation fails, the Agent
    write is rolled back rather than left orphaned.
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        create_project: CreateProjectUseCase,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._agents = agent_repository
        self._create_project = create_project
        self._uow = unit_of_work

    def execute(
        self,
        *,
        user_id: int,
        project_title: str,
        project_topic: str,
        project_description: str | None = None,
    ) -> AgentWorkspace:
        if self._agents.get_by_user_id(user_id) is not None:
            raise AgentAlreadyExistsForUserError(user_id)

        try:
            agent = self._agents.add(Agent.create(user_id=user_id))
            project = self._create_project.execute(
                agent_id=agent.agent_id,
                title=project_title,
                topic=project_topic,
                description=project_description,
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return AgentWorkspace(agent=agent, project=project)
