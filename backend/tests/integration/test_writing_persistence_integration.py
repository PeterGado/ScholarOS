import pytest
from sqlalchemy.exc import IntegrityError

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.modules.agent.infrastructure.models import Agent
from app.modules.document.infrastructure.models import ResearchDocument
from app.modules.knowledge.domain.enums import CreatedBy as KnowledgeCreatedBy
from app.modules.knowledge.domain.enums import KnowledgeElementType
from app.modules.knowledge.infrastructure.models import KnowledgeChunk, KnowledgeElement
from app.modules.project.infrastructure.models import Project
from app.modules.writing.domain.entities import (
    Conversation,
    MemoryProvenanceLink,
    MemoryRecord,
    ProfileCharacteristic,
    ProfileCharacteristicSource,
    WritingProfile,
)
from app.modules.writing.domain.enums import (
    MemoryProvenanceSourceType,
    MemoryRecordType,
    ProfileCharacteristicType,
)
from app.modules.writing.infrastructure.models import MemoryProvenanceLink as MemoryProvenanceLinkModel
from app.modules.writing.infrastructure.models import WritingProfile as WritingProfileModel
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyProfileCharacteristicSourceRepository,
    SqlAlchemyWritingProfileRepository,
)


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "writing_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def _make_user(session, username="researcher"):
    user = User(username=username)
    session.add(user)
    session.flush()
    return user


def _make_agent(session, user=None):
    user = user or _make_user(session)
    agent = Agent(user_id=user.user_id)
    session.add(agent)
    session.flush()
    return agent


def _make_project(session, agent=None):
    agent = agent or _make_agent(session)
    project = Project(agent_id=agent.agent_id, title="Thesis", topic="Coastal erosion")
    session.add(project)
    session.flush()
    return project


def _make_document(session, project=None):
    project = project or _make_project(session)
    doc = ResearchDocument(project_id=project.project_id, title="Source A", format="pdf", content_reference="ref-a")
    session.add(doc)
    session.flush()
    return doc


def _make_knowledge_chunk(session, agent):
    element = KnowledgeElement(
        agent_id=agent.agent_id,
        element_type=KnowledgeElementType.CONCEPT,
        label="Erosion rate",
        created_by=KnowledgeCreatedBy.SYSTEM,
    )
    session.add(element)
    session.flush()
    chunk = KnowledgeChunk(agent_id=agent.agent_id, element_id=element.element_id, content="Some content.")
    session.add(chunk)
    session.flush()
    return chunk


# --- Writing Profile / Profile Characteristic -------------------------------------------------------------------


def test_writing_profile_and_characteristics_persist_with_relationship(session):
    user = _make_user(session)
    agent = _make_agent(session, user=user)
    profiles = SqlAlchemyWritingProfileRepository(session)
    profile = profiles.add(WritingProfile(agent_id=agent.agent_id, user_id=user.user_id, name="Primary style"))
    session.commit()

    characteristics = SqlAlchemyProfileCharacteristicRepository(session)
    characteristic = characteristics.add(
        ProfileCharacteristic(
            profile_id=profile.profile_id, characteristic_type=ProfileCharacteristicType.VOCABULARY, signal="Formal tone"
        )
    )
    session.commit()

    assert characteristics.list_by_profile_id(profile.profile_id)[0].characteristic_id == characteristic.characteristic_id


def test_profile_characteristic_source_traces_to_research_document(session):
    user = _make_user(session)
    agent = _make_agent(session, user=user)
    project = _make_project(session, agent=agent)
    document = _make_document(session, project=project)
    profile = SqlAlchemyWritingProfileRepository(session).add(
        WritingProfile(agent_id=agent.agent_id, user_id=user.user_id, name="Primary style")
    )
    session.commit()
    characteristic = SqlAlchemyProfileCharacteristicRepository(session).add(
        ProfileCharacteristic(
            profile_id=profile.profile_id, characteristic_type=ProfileCharacteristicType.STRUCTURE, signal="Short paragraphs"
        )
    )
    session.commit()

    sources = SqlAlchemyProfileCharacteristicSourceRepository(session)
    source = sources.add(
        ProfileCharacteristicSource(characteristic_id=characteristic.characteristic_id, document_id=document.document_id)
    )
    session.commit()

    assert sources.list_by_characteristic_id(characteristic.characteristic_id)[0].link_id == source.link_id


def test_at_most_one_active_writing_profile_per_agent_is_enforced_at_database_level(session):
    user = _make_user(session)
    agent = _make_agent(session, user=user)
    session.add(WritingProfileModel(agent_id=agent.agent_id, user_id=user.user_id, name="A", status="active"))
    session.commit()
    session.add(WritingProfileModel(agent_id=agent.agent_id, user_id=user.user_id, name="B", status="active"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# --- Memory Record / Memory Provenance Link -------------------------------------------------------------------


def test_memory_record_persists_and_lists_current_by_agent(session):
    agent = _make_agent(session)
    records = SqlAlchemyMemoryRecordRepository(session)
    record = records.add(
        MemoryRecord(agent_id=agent.agent_id, record_type=MemoryRecordType.DECISION, content="Use IMRaD structure.")
    )
    session.commit()

    current = records.list_current_by_agent_id(agent.agent_id)
    assert len(current) == 1
    assert current[0].record_id == record.record_id


def test_memory_provenance_link_traces_to_conversation(session):
    agent = _make_agent(session)
    conversation = SqlAlchemyConversationRepository(session).add(Conversation(agent_id=agent.agent_id))
    session.commit()
    record = SqlAlchemyMemoryRecordRepository(session).add(
        MemoryRecord(agent_id=agent.agent_id, record_type=MemoryRecordType.GUIDANCE, content="Prefer active voice.")
    )
    session.commit()

    links = SqlAlchemyMemoryProvenanceLinkRepository(session)
    link = links.add(
        MemoryProvenanceLink(
            record_id=record.record_id,
            source_type=MemoryProvenanceSourceType.CONVERSATION,
            conversation_id=conversation.conversation_id,
        )
    )
    session.commit()

    assert links.list_by_record_id(record.record_id)[0].conversation_id == conversation.conversation_id


def test_memory_record_supersession_chain_is_traceable(session):
    agent = _make_agent(session)
    records = SqlAlchemyMemoryRecordRepository(session)
    original = records.add(
        MemoryRecord(agent_id=agent.agent_id, record_type=MemoryRecordType.DECISION, content="Use APA citations.")
    )
    session.commit()

    successor = records.add(
        MemoryRecord(
            agent_id=agent.agent_id,
            record_type=MemoryRecordType.DECISION,
            content="Use MLA citations.",
            superseded_record_id=original.record_id,
        )
    )
    session.commit()

    fetched_successor = records.get_by_id(successor.record_id)
    assert fetched_successor.superseded_record_id == original.record_id


def test_memory_provenance_link_exclusive_target_check_constraint_rejects_mismatched_source_type(session):
    """Bypasses the domain layer's own validation to confirm the database CHECK constraint is
    real defense in depth, not just a comment.
    """
    agent = _make_agent(session)
    record = SqlAlchemyMemoryRecordRepository(session).add(
        MemoryRecord(agent_id=agent.agent_id, record_type=MemoryRecordType.GUIDANCE, content="Prefer active voice.")
    )
    session.commit()

    session.add(MemoryProvenanceLinkModel(record_id=record.record_id, source_type="user_input", document_id=1))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_memory_provenance_link_exclusive_target_check_constraint_rejects_zero_targets_for_document_source(session):
    agent = _make_agent(session)
    record = SqlAlchemyMemoryRecordRepository(session).add(
        MemoryRecord(agent_id=agent.agent_id, record_type=MemoryRecordType.GUIDANCE, content="Prefer active voice.")
    )
    session.commit()

    session.add(MemoryProvenanceLinkModel(record_id=record.record_id, source_type="document"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# --- Cross-agent isolation -------------------------------------------------------------------


def test_writing_entities_do_not_leak_across_agents(session):
    """05_Constraints_and_Integrity.md invariant 1 (Agent scoping), applied to Writing -
    mirrors Stage 8's cross-agent authorization test for Knowledge search.
    """
    agent_a = _make_agent(session, user=_make_user(session, username="user-a"))
    agent_b = _make_agent(session, user=_make_user(session, username="user-b"))

    memory = SqlAlchemyMemoryRecordRepository(session)
    memory.add(MemoryRecord(agent_id=agent_a.agent_id, record_type=MemoryRecordType.OBJECTIVE, content="A's objective"))
    memory.add(MemoryRecord(agent_id=agent_b.agent_id, record_type=MemoryRecordType.OBJECTIVE, content="B's objective"))
    session.commit()

    assert len(memory.list_current_by_agent_id(agent_a.agent_id)) == 1
    assert memory.list_current_by_agent_id(agent_a.agent_id)[0].content == "A's objective"
