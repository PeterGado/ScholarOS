import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.application.segment_templates import (
    ApplySegmentTemplateUseCase,
    ListSegmentTemplatesUseCase,
)
from app.modules.writing.application.segments import (
    MAX_WRITING_SEGMENTS_PER_AGENT,
    CreateWritingSegmentUseCase,
)
from app.modules.writing.domain.entities import WritingSegment
from app.modules.writing.domain.exceptions import SegmentTemplateNotFoundError
from app.modules.writing.domain.repositories import WritingSegmentRepository
from app.modules.writing.domain.segment_templates import (
    FYP1_WRITING_GUIDE_TEMPLATE,
    SEGMENT_TEMPLATES,
)

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
    def __init__(self, existing: list[WritingSegment] | None = None):
        self._next_id = 1
        self._by_id: dict[int, WritingSegment] = {}
        for segment in existing or []:
            segment.segment_id = self._next_id
            self._by_id[self._next_id] = segment
            self._next_id += 1

    def add(self, segment: WritingSegment) -> WritingSegment:
        segment.segment_id = self._next_id
        self._by_id[self._next_id] = segment
        self._next_id += 1
        return segment

    def get_by_id(self, segment_id):
        return self._by_id.get(segment_id)

    def get_by_agent_id_and_name(self, agent_id, name):
        return next((s for s in self._by_id.values() if s.agent_id == agent_id and s.name == name), None)

    def list_by_agent_id(self, agent_id):
        return [s for s in self._by_id.values() if s.agent_id == agent_id]

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


def _build_apply_use_case(segments: FakeWritingSegmentRepository, agents: FakeAgentRepository | None = None):
    create_use_case = CreateWritingSegmentUseCase(segments, agents or FakeAgentRepository(), FakeUnitOfWork())
    return ApplySegmentTemplateUseCase(create_use_case)


# --- ListSegmentTemplatesUseCase --------------------------------------------------------------


def test_lists_the_built_in_templates():
    result = ListSegmentTemplatesUseCase().execute()

    assert result == SEGMENT_TEMPLATES
    assert FYP1_WRITING_GUIDE_TEMPLATE in result


# --- ApplySegmentTemplateUseCase --------------------------------------------------------------


def test_raises_for_an_unknown_template_id():
    use_case = _build_apply_use_case(FakeWritingSegmentRepository())

    with pytest.raises(SegmentTemplateNotFoundError):
        use_case.execute(user_id=USER_ID, template_id="not-a-real-template")


def test_raises_when_the_user_has_no_agent():
    use_case = _build_apply_use_case(FakeWritingSegmentRepository(), agents=FakeAgentRepository(agents={}))

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=USER_ID, template_id=FYP1_WRITING_GUIDE_TEMPLATE.template_id)


def test_applying_a_template_creates_every_entry():
    segments = FakeWritingSegmentRepository()
    use_case = _build_apply_use_case(segments)

    result = use_case.execute(user_id=USER_ID, template_id=FYP1_WRITING_GUIDE_TEMPLATE.template_id)

    assert len(result.created) == len(FYP1_WRITING_GUIDE_TEMPLATE.entries)
    assert result.skipped_existing == []
    assert result.limit_reached is False
    assert len(segments.list_by_agent_id(AGENT_ID)) == len(FYP1_WRITING_GUIDE_TEMPLATE.entries)
    created_names = {s.name for s in result.created}
    expected_names = {e.name for e in FYP1_WRITING_GUIDE_TEMPLATE.entries}
    assert created_names == expected_names


def test_applying_a_template_twice_skips_everything_the_second_time():
    segments = FakeWritingSegmentRepository()
    use_case = _build_apply_use_case(segments)
    use_case.execute(user_id=USER_ID, template_id=FYP1_WRITING_GUIDE_TEMPLATE.template_id)

    second_result = use_case.execute(user_id=USER_ID, template_id=FYP1_WRITING_GUIDE_TEMPLATE.template_id)

    assert second_result.created == []
    assert len(second_result.skipped_existing) == len(FYP1_WRITING_GUIDE_TEMPLATE.entries)
    # Re-applying never duplicates rows.
    assert len(segments.list_by_agent_id(AGENT_ID)) == len(FYP1_WRITING_GUIDE_TEMPLATE.entries)


def test_applying_a_template_on_top_of_a_manually_created_same_named_segment_skips_just_that_one():
    manual = WritingSegment(
        agent_id=AGENT_ID,
        name=FYP1_WRITING_GUIDE_TEMPLATE.entries[0].name,
        instructions="My own instructions, written before applying the template.",
    )
    segments = FakeWritingSegmentRepository(existing=[manual])
    use_case = _build_apply_use_case(segments)

    result = use_case.execute(user_id=USER_ID, template_id=FYP1_WRITING_GUIDE_TEMPLATE.template_id)

    assert result.skipped_existing == [FYP1_WRITING_GUIDE_TEMPLATE.entries[0].name]
    assert len(result.created) == len(FYP1_WRITING_GUIDE_TEMPLATE.entries) - 1
    # The user's own pre-existing instructions for that one segment are left untouched.
    untouched = segments.get_by_agent_id_and_name(AGENT_ID, FYP1_WRITING_GUIDE_TEMPLATE.entries[0].name)
    assert untouched.instructions == "My own instructions, written before applying the template."


def test_applying_a_template_stops_cleanly_once_the_segment_limit_is_reached():
    existing = [
        WritingSegment(agent_id=AGENT_ID, name=f"Pre-existing {i}", instructions="x")
        for i in range(MAX_WRITING_SEGMENTS_PER_AGENT - 2)
    ]
    segments = FakeWritingSegmentRepository(existing=existing)
    use_case = _build_apply_use_case(segments)

    result = use_case.execute(user_id=USER_ID, template_id=FYP1_WRITING_GUIDE_TEMPLATE.template_id)

    assert result.limit_reached is True
    assert len(result.created) == 2
    # Whatever was created before hitting the cap is real, not rolled back.
    assert len(segments.list_by_agent_id(AGENT_ID)) == MAX_WRITING_SEGMENTS_PER_AGENT
