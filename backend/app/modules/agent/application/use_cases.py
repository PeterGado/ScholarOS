from dataclasses import dataclass

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentAlreadyExistsForUserError, AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.domain.entities import Project
from app.modules.project.domain.repositories import ProjectRepository


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


class GetAgentWorkspaceUseCase:
    """Retrieves the caller's existing Agent workspace (Agent + its one Project). Added
    resolving a Frontend milestone Stage 1 finding: `POST /agents` only ever reveals the
    workspace's ids/topic once, at creation time - a client that doesn't persist that response
    itself (e.g. after a reload, or a second device) had no way to look it up again. Mirrors
    the exact non-enumeration precedent every other "fetch my own thing" use case already
    follows in this codebase (e.g. ListDraftsUseCase raising AgentNotFoundForUserError).
    """

    def __init__(self, agent_repository: AgentRepository, project_repository: ProjectRepository) -> None:
        self._agents = agent_repository
        self._projects = project_repository

    def execute(self, *, user_id: int) -> AgentWorkspace:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id)

        # Defensive, not expected to fail: an Agent always owns exactly one permanent Project
        # (05_Constraints_and_Integrity.md invariant 15).
        project = self._projects.get_by_agent_id(agent.agent_id)
        assert project is not None, f"Agent {agent.agent_id} has no Project (invariant 15 violated)"

        return AgentWorkspace(agent=agent, project=project)
