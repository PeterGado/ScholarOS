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
    Draft,
    DraftEvidenceLink,
    DraftVersion,
    MemoryProvenanceLink,
    MemoryRecord,
    ProfileCharacteristic,
    ProfileCharacteristicSource,
    Review,
    ReviewDecision,
    WritingProfile,
)
from app.modules.writing.domain.enums import (
    DraftStatus,
    MemoryProvenanceSourceType,
    MemoryRecordType,
    ProfileCharacteristicType,
    ReviewOutcome,
)
from app.modules.writing.infrastructure.models import Draft as DraftModel
from app.modules.writing.infrastructure.models import DraftEvidenceLink as DraftEvidenceLinkModel
from app.modules.writing.infrastructure.models import DraftVersion as DraftVersionModel
from app.modules.writing.infrastructure.models import MemoryProvenanceLink as MemoryProvenanceLinkModel
from app.modules.writing.infrastructure.models import MemoryRecord as MemoryRecordModel
from app.modules.writing.infrastructure.models import Review as ReviewModel
from app.modules.writing.infrastructure.models import ReviewDecision as ReviewDecisionModel
from app.modules.writing.infrastructure.models import WritingProfile as WritingProfileModel
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyDraftEvidenceLinkRepository,
    SqlAlchemyDraftRepository,
    SqlAlchemyDraftVersionRepository,
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyProfileCharacteristicSourceRepository,
    SqlAlchemyReviewDecisionRepository,
    SqlAlchemyReviewRepository,
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


# --- Draft / Draft Version -------------------------------------------------------------------


def test_draft_persists_and_retrieves(session):
    agent = _make_agent(session)
    repo = SqlAlchemyDraftRepository(session)

    draft = repo.add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()

    fetched = repo.get_by_id(draft.draft_id)
    assert fetched is not None
    assert fetched.agent_id == agent.agent_id
    assert fetched.status == DraftStatus.DRAFTING
    assert fetched.deleted_at is None


def test_draft_requires_existing_agent(session):
    session.add(DraftModel(agent_id=999, title="Orphan"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_draft_version_numbering_is_strictly_ordered_and_unique_per_draft(session):
    agent = _make_agent(session)
    drafts = SqlAlchemyDraftRepository(session)
    versions = SqlAlchemyDraftVersionRepository(session)
    draft = drafts.add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()

    v1 = versions.add(DraftVersion(draft_id=draft.draft_id, version_number=1, content="First"))
    session.commit()
    v2 = versions.add(DraftVersion(draft_id=draft.draft_id, version_number=2, content="Second"))
    session.commit()

    latest = versions.get_latest_by_draft_id(draft.draft_id)
    assert latest.version_id == v2.version_id
    all_versions = versions.list_by_draft_id(draft.draft_id)
    assert [v.version_number for v in all_versions] == [1, 2]
    assert v1.version_id != v2.version_id


def test_draft_version_duplicate_version_number_is_rejected(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()

    session.add(DraftVersionModel(draft_id=draft.draft_id, version_number=1, content="A", created_by="user"))
    session.commit()
    session.add(DraftVersionModel(draft_id=draft.draft_id, version_number=1, content="B", created_by="user"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_persistence_failure_rolls_back_without_orphaning_prior_writes(session):
    """Mirrors the Agent/Project atomicity test (test_agent_workspace_integration.py) -
    confirms rollback leaves no partial state, per the project's transaction conventions.
    """
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()

    session.add(DraftVersionModel(draft_id=draft.draft_id, version_number=1, content="A", created_by="user"))
    session.commit()

    session.add(DraftVersionModel(draft_id=999999, version_number=1, content="Orphan", created_by="user"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    versions = SqlAlchemyDraftVersionRepository(session).list_by_draft_id(draft.draft_id)
    assert len(versions) == 1


# --- Review / Review Decision -------------------------------------------------------------------


def test_review_and_decision_persist_with_relationship_to_draft_version(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()

    reviews = SqlAlchemyReviewRepository(session)
    review = reviews.add(Review(draft_version_id=version.version_id))
    session.commit()

    user = _make_user(session, username="reviewer")
    decisions = SqlAlchemyReviewDecisionRepository(session)
    decision = decisions.add(ReviewDecision(review_id=review.review_id, outcome=ReviewOutcome.APPROVED, decided_by=user.user_id))
    session.commit()

    assert decisions.get_by_review_id(review.review_id).decision_id == decision.decision_id


def test_at_most_one_open_review_per_draft_version_is_enforced_at_database_level(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()

    session.add(ReviewModel(draft_version_id=version.version_id, status="open"))
    session.commit()
    session.add(ReviewModel(draft_version_id=version.version_id, status="open"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_one_decision_per_review_is_enforced_at_database_level(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()
    review = SqlAlchemyReviewRepository(session).add(Review(draft_version_id=version.version_id))
    session.commit()
    user = _make_user(session, username="reviewer")

    decisions = SqlAlchemyReviewDecisionRepository(session)
    decisions.add(ReviewDecision(review_id=review.review_id, outcome=ReviewOutcome.APPROVED, decided_by=user.user_id))
    session.commit()

    session.add(ReviewDecisionModel(review_id=review.review_id, outcome="approved", decided_by=user.user_id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# --- Draft Evidence Link -------------------------------------------------------------------


def test_draft_evidence_link_references_existing_knowledge_chunk(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()
    chunk = _make_knowledge_chunk(session, agent)

    links = SqlAlchemyDraftEvidenceLinkRepository(session)
    link = links.add(DraftEvidenceLink.for_knowledge_chunk(draft_version_id=version.version_id, chunk_id=chunk.chunk_id))
    session.commit()

    stored = links.list_by_draft_version_id(version.version_id)
    assert len(stored) == 1
    assert stored[0].chunk_id == chunk.chunk_id
    assert link.link_id == stored[0].link_id


def test_draft_evidence_link_references_existing_research_document(session):
    agent = _make_agent(session)
    project = _make_project(session, agent=agent)
    document = _make_document(session, project=project)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()

    links = SqlAlchemyDraftEvidenceLinkRepository(session)
    link = links.add(
        DraftEvidenceLink.for_research_document(draft_version_id=version.version_id, document_id=document.document_id)
    )
    session.commit()

    assert links.list_by_draft_version_id(version.version_id)[0].document_id == document.document_id


def test_draft_evidence_link_exclusive_target_check_constraint_rejects_both_set(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()
    chunk = _make_knowledge_chunk(session, agent)
    project = _make_project(session, agent=agent)
    document = _make_document(session, project=project)

    session.add(
        DraftEvidenceLinkModel(
            draft_version_id=version.version_id,
            target_type="knowledge_chunk",
            chunk_id=chunk.chunk_id,
            document_id=document.document_id,
            created_by="system",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_draft_evidence_link_duplicate_annotation_is_rejected(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()
    chunk = _make_knowledge_chunk(session, agent)

    links = SqlAlchemyDraftEvidenceLinkRepository(session)
    links.add(DraftEvidenceLink.for_knowledge_chunk(draft_version_id=version.version_id, chunk_id=chunk.chunk_id))
    session.commit()

    with pytest.raises(IntegrityError):
        links.add(DraftEvidenceLink.for_knowledge_chunk(draft_version_id=version.version_id, chunk_id=chunk.chunk_id))
        session.commit()
    session.rollback()


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


def test_memory_provenance_link_traces_to_draft_version(session):
    agent = _make_agent(session)
    draft = SqlAlchemyDraftRepository(session).add(Draft.create(agent_id=agent.agent_id, title="Chapter 1"))
    session.commit()
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="First")
    )
    session.commit()
    record = SqlAlchemyMemoryRecordRepository(session).add(
        MemoryRecord(agent_id=agent.agent_id, record_type=MemoryRecordType.GUIDANCE, content="Prefer active voice.")
    )
    session.commit()

    links = SqlAlchemyMemoryProvenanceLinkRepository(session)
    link = links.add(
        MemoryProvenanceLink(
            record_id=record.record_id,
            source_type=MemoryProvenanceSourceType.DRAFT_VERSION,
            draft_version_id=version.version_id,
        )
    )
    session.commit()

    assert links.list_by_record_id(record.record_id)[0].draft_version_id == version.version_id


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
    real defense in depth, not just a comment - mirrors the equivalent Draft Evidence Link test.
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
    drafts = SqlAlchemyDraftRepository(session)
    drafts.add(Draft.create(agent_id=agent_a.agent_id, title="Agent A's draft"))
    session.commit()
    drafts.add(Draft.create(agent_id=agent_b.agent_id, title="Agent B's draft"))
    session.commit()

    agent_a_drafts = drafts.list_by_agent_id(agent_a.agent_id)
    assert len(agent_a_drafts) == 1
    assert agent_a_drafts[0].title == "Agent A's draft"

    memory = SqlAlchemyMemoryRecordRepository(session)
    memory.add(MemoryRecord(agent_id=agent_a.agent_id, record_type=MemoryRecordType.OBJECTIVE, content="A's objective"))
    memory.add(MemoryRecord(agent_id=agent_b.agent_id, record_type=MemoryRecordType.OBJECTIVE, content="B's objective"))
    session.commit()

    assert len(memory.list_current_by_agent_id(agent_a.agent_id)) == 1
    assert memory.list_current_by_agent_id(agent_a.agent_id)[0].content == "A's objective"
