import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.application.profile_view import ResetWritingProfileUseCase
from app.modules.writing.domain.entities import WritingProfile
from app.modules.writing.domain.enums import WritingProfileStatus
from app.modules.writing.domain.exceptions import WritingProfileNotFoundError
from app.modules.writing.domain.repositories import WritingProfileRepository

USER_ID = 1
AGENT_ID = 1
PROFILE_ID = 1


class FakeAgentRepository(AgentRepository):
    def __init__(self, agents: dict[int, Agent] | None = None):
        self._agents = agents if agents is not None else {AGENT_ID: Agent(user_id=USER_ID, agent_id=AGENT_ID)}

    def get_by_user_id(self, user_id):
        return next((a for a in self._agents.values() if a.user_id == user_id), None)

    def get_by_id(self, agent_id):
        return self._agents.get(agent_id)

    def add(self, agent):
        raise NotImplementedError


class FakeWritingProfileRepository(WritingProfileRepository):
    def __init__(self, existing: WritingProfile | None = None):
        self._by_id: dict[int, WritingProfile] = {}
        if existing is not None:
            self._by_id[existing.profile_id] = existing
        self.deactivate_calls: list[tuple[int, object]] = []

    def add(self, profile):
        raise NotImplementedError

    def get_by_id(self, profile_id):
        return self._by_id.get(profile_id)

    def get_active_by_agent_id(self, agent_id):
        return next(
            (p for p in self._by_id.values() if p.agent_id == agent_id and p.status == WritingProfileStatus.ACTIVE),
            None,
        )

    def deactivate(self, profile_id, *, updated_at):
        self.deactivate_calls.append((profile_id, updated_at))
        profile = self._by_id[profile_id]
        profile.status = WritingProfileStatus.INACTIVE
        profile.updated_at = updated_at


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _active_profile() -> WritingProfile:
    return WritingProfile(agent_id=AGENT_ID, user_id=USER_ID, name="Default", profile_id=PROFILE_ID)


def test_deactivates_the_active_profile_and_commits():
    profile = _active_profile()
    profiles = FakeWritingProfileRepository(existing=profile)
    uow = FakeUnitOfWork()
    use_case = ResetWritingProfileUseCase(profiles, FakeAgentRepository(), uow)

    use_case.execute(user_id=USER_ID)

    assert profile.status == WritingProfileStatus.INACTIVE
    assert profiles.deactivate_calls == [(PROFILE_ID, profile.updated_at)]
    assert uow.committed is True


def test_a_deactivated_profile_is_no_longer_returned_as_active():
    profile = _active_profile()
    profiles = FakeWritingProfileRepository(existing=profile)
    use_case = ResetWritingProfileUseCase(profiles, FakeAgentRepository(), FakeUnitOfWork())

    use_case.execute(user_id=USER_ID)

    assert profiles.get_active_by_agent_id(AGENT_ID) is None
    # Preserved, not deleted - still retrievable by id.
    assert profiles.get_by_id(PROFILE_ID) is not None


def test_raises_when_the_user_has_no_agent():
    use_case = ResetWritingProfileUseCase(FakeWritingProfileRepository(), FakeAgentRepository(agents={}), FakeUnitOfWork())

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=USER_ID)


def test_raises_when_there_is_no_active_profile():
    use_case = ResetWritingProfileUseCase(FakeWritingProfileRepository(), FakeAgentRepository(), FakeUnitOfWork())

    with pytest.raises(WritingProfileNotFoundError):
        use_case.execute(user_id=USER_ID)


def test_rolls_back_on_a_repository_failure():
    class FailingWritingProfileRepository(FakeWritingProfileRepository):
        def deactivate(self, profile_id, *, updated_at):
            raise RuntimeError("simulated failure")

    profiles = FailingWritingProfileRepository(existing=_active_profile())
    uow = FakeUnitOfWork()
    use_case = ResetWritingProfileUseCase(profiles, FakeAgentRepository(), uow)

    with pytest.raises(RuntimeError):
        use_case.execute(user_id=USER_ID)

    assert uow.rolled_back is True
    assert uow.committed is False
