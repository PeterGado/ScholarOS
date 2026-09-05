import pytest

from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentAlreadyExistsForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.domain.entities import Project
from app.modules.project.domain.repositories import ProjectRepository


class FakeAgentRepository(AgentRepository):
    def __init__(self):
        self._by_id: dict[int, Agent] = {}
        self._next_id = 1

    def get_by_user_id(self, user_id):
        return next((a for a in self._by_id.values() if a.user_id == user_id), None)

    def get_by_id(self, agent_id):
        return self._by_id.get(agent_id)

    def add(self, agent: Agent) -> Agent:
        agent.agent_id = self._next_id
        self._next_id += 1
        self._by_id[agent.agent_id] = agent
        return agent


class FakeProjectRepository(ProjectRepository):
    def __init__(self, fail_on_create: bool = False):
        self._by_id: dict[int, Project] = {}
        self._next_id = 1
        self._fail_on_create = fail_on_create

    def get_by_agent_id(self, agent_id):
        return next((p for p in self._by_id.values() if p.agent_id == agent_id), None)

    def get_by_id(self, project_id):
        return self._by_id.get(project_id)

    def add(self, project: Project) -> Project:
        if self._fail_on_create:
            raise RuntimeError("simulated persistence failure")
        project.project_id = self._next_id
        self._next_id += 1
        self._by_id[project.project_id] = project
        return project


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _build_use_case(project_repo=None, uow=None):
    agent_repo = FakeAgentRepository()
    project_repo = project_repo or FakeProjectRepository()
    uow = uow or FakeUnitOfWork()
    create_project = CreateProjectUseCase(project_repo)
    use_case = CreateAgentWorkspaceUseCase(agent_repo, create_project, uow)
    return use_case, agent_repo, project_repo, uow


def test_creates_agent_and_its_one_project_together():
    use_case, agent_repo, project_repo, uow = _build_use_case()

    workspace = use_case.execute(
        user_id=1, project_title="Thesis", project_topic="Coastal erosion", project_description="Notes"
    )

    assert workspace.agent.user_id == 1
    assert workspace.project.agent_id == workspace.agent.agent_id
    assert workspace.project.topic == "Coastal erosion"
    assert agent_repo.get_by_user_id(1) is not None
    assert project_repo.get_by_agent_id(workspace.agent.agent_id) is not None
    assert uow.committed
    assert not uow.rolled_back


def test_second_agent_for_same_user_is_rejected():
    use_case, _, _, _ = _build_use_case()
    use_case.execute(user_id=1, project_title="Thesis", project_topic="Topic A")

    with pytest.raises(AgentAlreadyExistsForUserError):
        use_case.execute(user_id=1, project_title="Second", project_topic="Topic B")


def test_different_users_each_get_their_own_agent():
    use_case, agent_repo, _, _ = _build_use_case()

    workspace_1 = use_case.execute(user_id=1, project_title="Thesis A", project_topic="Topic A")
    workspace_2 = use_case.execute(user_id=2, project_title="Thesis B", project_topic="Topic B")

    assert workspace_1.agent.agent_id != workspace_2.agent.agent_id
    assert agent_repo.get_by_user_id(1).agent_id == workspace_1.agent.agent_id
    assert agent_repo.get_by_user_id(2).agent_id == workspace_2.agent.agent_id


def test_project_creation_failure_rolls_back_and_does_not_leave_a_committed_agent():
    failing_project_repo = FakeProjectRepository(fail_on_create=True)
    use_case, agent_repo, _, uow = _build_use_case(project_repo=failing_project_repo)

    with pytest.raises(RuntimeError):
        use_case.execute(user_id=1, project_title="Thesis", project_topic="Topic")

    assert uow.rolled_back
    assert not uow.committed
