import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.writing.application.memory_inspection import ListMemoryUseCase, SupersedeMemoryRecordUseCase
from app.modules.writing.domain.entities import MemoryProvenanceLink, MemoryRecord
from app.modules.writing.domain.enums import (
    CreatedBy,
    MemoryProvenanceSourceType,
    MemoryRecordStatus,
    MemoryRecordType,
)
from app.modules.writing.domain.exceptions import MemoryRecordAlreadySupersededError, MemoryRecordNotFoundError


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeAgentRepository:
    def __init__(self, agents: dict[int, Agent]) -> None:
        self._by_user_id = {a.user_id: a for a in agents.values()}
        self._by_id = agents

    def get_by_user_id(self, user_id):
        return self._by_user_id.get(user_id)

    def get_by_id(self, agent_id):
        return self._by_id.get(agent_id)

    def add(self, agent):  # pragma: no cover
        raise NotImplementedError


class FakeMemoryRecordRepository:
    def __init__(self, records: list[MemoryRecord] | None = None) -> None:
        self.saved: list[MemoryRecord] = list(records or [])
        self._next_id = max([r.record_id for r in self.saved], default=0) + 1

    def add(self, record):
        record.record_id = self._next_id
        self._next_id += 1
        self.saved.append(record)
        return record

    def get_by_id(self, record_id):
        return next((r for r in self.saved if r.record_id == record_id), None)

    def list_current_by_agent_id(self, agent_id):
        return [r for r in self.saved if r.agent_id == agent_id and r.status == MemoryRecordStatus.CURRENT]

    def mark_superseded(self, record_id, *, superseded_record_id, superseded_at):
        record = self.get_by_id(record_id)
        record.status = MemoryRecordStatus.SUPERSEDED
        record.superseded_record_id = superseded_record_id
        record.superseded_at = superseded_at


class FakeMemoryProvenanceLinkRepository:
    def __init__(self) -> None:
        self.saved: list[MemoryProvenanceLink] = []
        self._next_id = 1

    def add(self, link):
        link.link_id = self._next_id
        self._next_id += 1
        self.saved.append(link)
        return link

    def list_by_record_id(self, record_id):
        return [link for link in self.saved if link.record_id == record_id]


def _agent(agent_id=1, user_id=1) -> Agent:
    return Agent(user_id=user_id, agent_id=agent_id)


# --- ListMemoryUseCase -----------------------------------------------------------------------


def test_list_memory_returns_only_current_records_with_provenance():
    agent = _agent()
    current = MemoryRecord(
        agent_id=1, record_type=MemoryRecordType.DECISION, content="Use LIDAR data.", record_id=1,
        status=MemoryRecordStatus.CURRENT, created_by=CreatedBy.SYSTEM,
    )
    superseded = MemoryRecord(
        agent_id=1, record_type=MemoryRecordType.DECISION, content="Old content.", record_id=2,
        status=MemoryRecordStatus.SUPERSEDED, created_by=CreatedBy.SYSTEM,
    )
    records = FakeMemoryRecordRepository([current, superseded])
    provenance = FakeMemoryProvenanceLinkRepository()
    provenance.add(MemoryProvenanceLink(record_id=1, source_type=MemoryProvenanceSourceType.CONVERSATION, conversation_id=99))

    use_case = ListMemoryUseCase(records, provenance, FakeAgentRepository({1: agent}))
    result = use_case.execute(user_id=1)

    assert len(result) == 1  # superseded record excluded
    assert result[0].record.record_id == 1
    assert len(result[0].provenance) == 1
    assert result[0].provenance[0].conversation_id == 99


def test_list_memory_for_an_agent_with_none_returns_empty_list():
    agent = _agent()
    use_case = ListMemoryUseCase(FakeMemoryRecordRepository(), FakeMemoryProvenanceLinkRepository(), FakeAgentRepository({1: agent}))

    assert use_case.execute(user_id=1) == []


def test_list_memory_for_a_user_with_no_agent_raises():
    use_case = ListMemoryUseCase(FakeMemoryRecordRepository(), FakeMemoryProvenanceLinkRepository(), FakeAgentRepository({}))

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=1)


# --- SupersedeMemoryRecordUseCase ---------------------------------------------------------


def _supersede_use_case(agent, records, provenance, uow=None):
    return SupersedeMemoryRecordUseCase(records, provenance, FakeAgentRepository({agent.agent_id: agent}), uow or FakeUnitOfWork())


def test_supersede_creates_a_new_record_and_marks_the_old_one_superseded():
    agent = _agent()
    old = MemoryRecord(
        agent_id=1, record_type=MemoryRecordType.DECISION, content="Old content.", record_id=1,
        status=MemoryRecordStatus.CURRENT, created_by=CreatedBy.SYSTEM,
    )
    records = FakeMemoryRecordRepository([old])
    provenance = FakeMemoryProvenanceLinkRepository()
    use_case = _supersede_use_case(agent, records, provenance)

    new_record = use_case.execute(user_id=1, record_id=1, content="Corrected content.", rationale="User correction.")

    assert new_record.content == "Corrected content."
    assert new_record.created_by == CreatedBy.USER
    assert new_record.record_type == MemoryRecordType.DECISION  # inherited from the old record
    assert new_record.status == MemoryRecordStatus.CURRENT

    assert old.status == MemoryRecordStatus.SUPERSEDED
    assert old.superseded_record_id == new_record.record_id

    links = provenance.list_by_record_id(new_record.record_id)
    assert len(links) == 1
    assert links[0].source_type == MemoryProvenanceSourceType.USER_INPUT


def test_supersede_a_record_belonging_to_another_agent_is_reported_as_not_found():
    agent = _agent(agent_id=1, user_id=1)
    other_agents_record = MemoryRecord(
        agent_id=999, record_type=MemoryRecordType.DECISION, content="Not yours.", record_id=1,
        status=MemoryRecordStatus.CURRENT, created_by=CreatedBy.SYSTEM,
    )
    use_case = _supersede_use_case(agent, FakeMemoryRecordRepository([other_agents_record]), FakeMemoryProvenanceLinkRepository())

    with pytest.raises(MemoryRecordNotFoundError):
        use_case.execute(user_id=1, record_id=1, content="Hijacked.")


def test_supersede_a_nonexistent_record_raises_not_found():
    agent = _agent()
    use_case = _supersede_use_case(agent, FakeMemoryRecordRepository(), FakeMemoryProvenanceLinkRepository())

    with pytest.raises(MemoryRecordNotFoundError):
        use_case.execute(user_id=1, record_id=999, content="x")


def test_supersede_an_already_superseded_record_is_rejected():
    agent = _agent()
    old = MemoryRecord(
        agent_id=1, record_type=MemoryRecordType.DECISION, content="Old content.", record_id=1,
        status=MemoryRecordStatus.SUPERSEDED, created_by=CreatedBy.SYSTEM,
    )
    use_case = _supersede_use_case(agent, FakeMemoryRecordRepository([old]), FakeMemoryProvenanceLinkRepository())

    with pytest.raises(MemoryRecordAlreadySupersededError):
        use_case.execute(user_id=1, record_id=1, content="x")
