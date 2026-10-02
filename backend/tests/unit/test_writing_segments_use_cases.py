import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.application.segments import (
    MAX_WRITING_SEGMENTS_PER_AGENT,
    CreateWritingSegmentUseCase,
    DeleteWritingSegmentUseCase,
    ListWritingSegmentsUseCase,
    UpdateWritingSegmentUseCase,
)
from app.modules.writing.domain.entities import WritingSegment
from app.modules.writing.domain.exceptions import (
    DuplicateWritingSegmentNameError,
    InvalidWritingSegmentInstructionsError,
    InvalidWritingSegmentNameError,
    TooManyWritingSegmentsError,
    WritingSegmentNotFoundError,
)
from app.modules.writing.domain.repositories import WritingSegmentRepository

USER_ID = 1
AGENT_ID = 1


class FakeAgentRepository(AgentRepository):
    def __init__(self, agents: dict[int, Agent] | None = None):
        self._agents = agents if agents is not None else {AGENT_ID: Agent(user_id=USER_ID, agent_id=AGENT_ID)}

    def get_by_user_id(self, user_id):
        return next((a for a in self._agents.values() if a.user_id == user_id), None)

    def get_by_id(self, agent_id):
        return self._agents.get(agent_id)

    def add(self, agent):
        raise NotImplementedError


class FakeWritingSegmentRepository(WritingSegmentRepository):
    def __init__(self, existing: list[WritingSegment] | None = None, *, fail_on_add: bool = False):
        self._next_id = 1
        self._by_id: dict[int, WritingSegment] = {}
        self._fail_on_add = fail_on_add
        for segment in existing or []:
            segment.segment_id = self._next_id
            self._by_id[self._next_id] = segment
            self._next_id += 1

    def add(self, segment: WritingSegment) -> WritingSegment:
        if self._fail_on_add:
            # Simulates the real repository's own IntegrityError -> domain-exception
            # translation (app.modules.writing.infrastructure.repositories) - the application
            # layer never sees a raw IntegrityError, so the fake shouldn't raise one either.
            raise DuplicateWritingSegmentNameError(name=segment.name)
        segment.segment_id = self._next_id
        self._by_id[self._next_id] = segment
        self._next_id += 1
        return segment

    def get_by_id(self, segment_id):
        return self._by_id.get(segment_id)

    def get_by_agent_id_and_name(self, agent_id, name):
        return next(
            (s for s in self._by_id.values() if s.agent_id == agent_id and s.name == name), None
        )

    def list_by_agent_id(self, agent_id):
        return sorted(
            (s for s in self._by_id.values() if s.agent_id == agent_id), key=lambda s: s.name
        )

    def count_by_agent_id(self, agent_id):
        return sum(1 for s in self._by_id.values() if s.agent_id == agent_id)

    def update(self, segment_id, *, name, instructions, updated_at):
        segment = self._by_id[segment_id]
        segment.name = name
        segment.instructions = instructions
        segment.updated_at = updated_at

    def delete(self, segment_id):
        del self._by_id[segment_id]


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


# --- WritingSegment entity validation (exercised through the use case) ---------------------


def test_blank_name_is_rejected():
    use_case = CreateWritingSegmentUseCase(FakeWritingSegmentRepository(), FakeAgentRepository(), FakeUnitOfWork())

    with pytest.raises(InvalidWritingSegmentNameError):
        use_case.execute(user_id=USER_ID, name="   ", instructions="Some instructions.")


def test_blank_instructions_are_rejected():
    use_case = CreateWritingSegmentUseCase(FakeWritingSegmentRepository(), FakeAgentRepository(), FakeUnitOfWork())

    with pytest.raises(InvalidWritingSegmentInstructionsError):
        use_case.execute(user_id=USER_ID, name="Background of the Study", instructions="   ")


# --- CreateWritingSegmentUseCase -------------------------------------------------------------


def test_creates_a_segment_and_commits():
    segments = FakeWritingSegmentRepository()
    uow = FakeUnitOfWork()
    use_case = CreateWritingSegmentUseCase(segments, FakeAgentRepository(), uow)

    segment = use_case.execute(user_id=USER_ID, name="Background of the Study", instructions="Cite two sources.")

    assert segment.segment_id is not None
    assert segment.name == "Background of the Study"
    assert segment.instructions == "Cite two sources."
    assert uow.committed is True


def test_raises_when_the_user_has_no_agent():
    use_case = CreateWritingSegmentUseCase(
        FakeWritingSegmentRepository(), FakeAgentRepository(agents={}), FakeUnitOfWork()
    )

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=USER_ID, name="Background", instructions="Instructions.")


def test_rejects_a_duplicate_name_via_the_precheck():
    existing = WritingSegment(agent_id=AGENT_ID, name="Background", instructions="Existing instructions.")
    use_case = CreateWritingSegmentUseCase(
        FakeWritingSegmentRepository(existing=[existing]), FakeAgentRepository(), FakeUnitOfWork()
    )

    with pytest.raises(DuplicateWritingSegmentNameError):
        use_case.execute(user_id=USER_ID, name="Background", instructions="New instructions.")


def test_rejects_a_duplicate_name_surfaced_by_the_repository_as_a_race():
    """The precheck and the insert are two separate statements - a concurrent duplicate insert
    (translated by the repository, not the use case - see its own comment) must still surface
    as the same domain exception here, roll back, and propagate.
    """
    segments = FakeWritingSegmentRepository(fail_on_add=True)
    uow = FakeUnitOfWork()
    use_case = CreateWritingSegmentUseCase(segments, FakeAgentRepository(), uow)

    with pytest.raises(DuplicateWritingSegmentNameError):
        use_case.execute(user_id=USER_ID, name="Background", instructions="Instructions.")
    assert uow.rolled_back is True


def test_rejects_creation_past_the_segment_limit():
    existing = [
        WritingSegment(agent_id=AGENT_ID, name=f"Segment {i}", instructions="x")
        for i in range(MAX_WRITING_SEGMENTS_PER_AGENT)
    ]
    use_case = CreateWritingSegmentUseCase(
        FakeWritingSegmentRepository(existing=existing), FakeAgentRepository(), FakeUnitOfWork()
    )

    with pytest.raises(TooManyWritingSegmentsError):
        use_case.execute(user_id=USER_ID, name="One too many", instructions="x")


# --- ListWritingSegmentsUseCase ---------------------------------------------------------------


def test_lists_segments_alphabetically():
    existing = [
        WritingSegment(agent_id=AGENT_ID, name="Zeta section", instructions="x"),
        WritingSegment(agent_id=AGENT_ID, name="Alpha section", instructions="y"),
    ]
    use_case = ListWritingSegmentsUseCase(FakeWritingSegmentRepository(existing=existing), FakeAgentRepository())

    result = use_case.execute(user_id=USER_ID)

    assert [s.name for s in result] == ["Alpha section", "Zeta section"]


def test_list_raises_when_the_user_has_no_agent():
    use_case = ListWritingSegmentsUseCase(FakeWritingSegmentRepository(), FakeAgentRepository(agents={}))

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=USER_ID)


# --- UpdateWritingSegmentUseCase --------------------------------------------------------------


def test_updates_name_and_instructions():
    existing = WritingSegment(agent_id=AGENT_ID, name="Background", instructions="Old instructions.")
    segments = FakeWritingSegmentRepository(existing=[existing])
    uow = FakeUnitOfWork()
    use_case = UpdateWritingSegmentUseCase(segments, FakeAgentRepository(), uow)

    updated = use_case.execute(
        user_id=USER_ID, segment_id=existing.segment_id, name="Background of the Study", instructions="New instructions."
    )

    assert updated.name == "Background of the Study"
    assert updated.instructions == "New instructions."
    assert uow.committed is True


def test_update_raises_for_a_segment_belonging_to_a_different_agent():
    existing = WritingSegment(agent_id=999, name="Background", instructions="Instructions.")
    segments = FakeWritingSegmentRepository(existing=[existing])
    use_case = UpdateWritingSegmentUseCase(segments, FakeAgentRepository(), FakeUnitOfWork())

    with pytest.raises(WritingSegmentNotFoundError):
        use_case.execute(user_id=USER_ID, segment_id=existing.segment_id, name="X", instructions="Y")


def test_update_raises_for_a_nonexistent_segment():
    use_case = UpdateWritingSegmentUseCase(FakeWritingSegmentRepository(), FakeAgentRepository(), FakeUnitOfWork())

    with pytest.raises(WritingSegmentNotFoundError):
        use_case.execute(user_id=USER_ID, segment_id=999, name="X", instructions="Y")


def test_update_rejects_renaming_to_another_segments_existing_name():
    first = WritingSegment(agent_id=AGENT_ID, name="Background", instructions="x")
    second = WritingSegment(agent_id=AGENT_ID, name="Methodology", instructions="y")
    segments = FakeWritingSegmentRepository(existing=[first, second])
    use_case = UpdateWritingSegmentUseCase(segments, FakeAgentRepository(), FakeUnitOfWork())

    with pytest.raises(DuplicateWritingSegmentNameError):
        use_case.execute(user_id=USER_ID, segment_id=second.segment_id, name="Background", instructions="y")


def test_update_allows_keeping_its_own_unchanged_name():
    existing = WritingSegment(agent_id=AGENT_ID, name="Background", instructions="Old.")
    segments = FakeWritingSegmentRepository(existing=[existing])
    use_case = UpdateWritingSegmentUseCase(segments, FakeAgentRepository(), FakeUnitOfWork())

    updated = use_case.execute(
        user_id=USER_ID, segment_id=existing.segment_id, name="Background", instructions="New."
    )

    assert updated.instructions == "New."


# --- DeleteWritingSegmentUseCase --------------------------------------------------------------


def test_deletes_a_segment_and_commits():
    existing = WritingSegment(agent_id=AGENT_ID, name="Background", instructions="x")
    segments = FakeWritingSegmentRepository(existing=[existing])
    uow = FakeUnitOfWork()
    use_case = DeleteWritingSegmentUseCase(segments, FakeAgentRepository(), uow)

    use_case.execute(user_id=USER_ID, segment_id=existing.segment_id)

    assert segments.get_by_id(existing.segment_id) is None
    assert uow.committed is True


def test_delete_raises_for_a_segment_belonging_to_a_different_agent():
    existing = WritingSegment(agent_id=999, name="Background", instructions="x")
    segments = FakeWritingSegmentRepository(existing=[existing])
    use_case = DeleteWritingSegmentUseCase(segments, FakeAgentRepository(), FakeUnitOfWork())

    with pytest.raises(WritingSegmentNotFoundError):
        use_case.execute(user_id=USER_ID, segment_id=existing.segment_id)

    # Never deleted - the ownership check must happen before any mutation.
    assert segments.get_by_id(existing.segment_id) is not None
