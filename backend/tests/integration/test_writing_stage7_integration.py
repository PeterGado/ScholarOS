import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.knowledge.domain.enums import CreatedBy as KnowledgeCreatedBy
from app.modules.knowledge.domain.enums import KnowledgeElementType
from app.modules.knowledge.infrastructure.models import KnowledgeChunk, KnowledgeElement
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.reviews import SubmitDraftReviewUseCase
from app.modules.writing.application.use_cases import (
    CreateDraftUseCase,
    DraftVersionWithEvidence,
    GetDraftUseCase,
    ListDraftsUseCase,
    ListDraftVersionsUseCase,
)
from app.modules.writing.domain.entities import Draft, DraftEvidenceLink, DraftVersion
from app.modules.writing.domain.enums import DraftStatus, ReviewOutcome
from app.modules.writing.domain.exceptions import DraftNotFoundError
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyDraftEvidenceLinkRepository,
    SqlAlchemyDraftRepository,
    SqlAlchemyDraftVersionRepository,
    SqlAlchemyReviewDecisionRepository,
    SqlAlchemyReviewRepository,
)


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "writing_stage7_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def _make_workspace(session, username="researcher"):
    user = User(username=username)
    session.add(user)
    session.flush()
    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic="Topic"
    )
    return workspace


def _create_draft(session, agent, *, title="Chapter 1"):
    use_case = CreateDraftUseCase(
        SqlAlchemyDraftRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    )
    return use_case.execute(user_id=agent.user_id, title=title)


# --- CreateDraftUseCase / ListDraftsUseCase / GetDraftUseCase -------------------------------------------------------------------


def test_create_draft_use_case_resolves_agent_from_user_id_against_real_sqlite(session):
    workspace = _make_workspace(session)

    draft = _create_draft(session, workspace.agent)

    session.expire_all()
    stored = SqlAlchemyDraftRepository(session).get_by_id(draft.draft_id)
    assert stored.agent_id == workspace.agent.agent_id


def test_create_draft_for_a_user_with_no_agent_is_rejected(session):
    user = User(username="no-agent")
    session.add(user)
    session.flush()
    use_case = CreateDraftUseCase(
        SqlAlchemyDraftRepository(session), SqlAlchemyAgentRepository(session), SqlAlchemyUnitOfWork(session)
    )

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=user.user_id, title="Orphan")


def test_drafts_do_not_leak_across_agents(session):
    workspace_a = _make_workspace(session, username="user-a")
    workspace_b = _make_workspace(session, username="user-b")
    _create_draft(session, workspace_a.agent, title="A's draft")
    _create_draft(session, workspace_b.agent, title="B's draft")

    list_use_case = ListDraftsUseCase(SqlAlchemyDraftRepository(session), SqlAlchemyAgentRepository(session))
    a_drafts = list_use_case.execute(user_id=workspace_a.agent.user_id)
    assert [d.title for d in a_drafts] == ["A's draft"]


def test_get_draft_rejects_another_users_draft_against_real_sqlite(session):
    workspace_a = _make_workspace(session, username="user-a")
    workspace_b = _make_workspace(session, username="user-b")
    draft = _create_draft(session, workspace_a.agent)

    get_use_case = GetDraftUseCase(SqlAlchemyDraftRepository(session), SqlAlchemyAgentRepository(session))
    with pytest.raises(DraftNotFoundError):
        get_use_case.execute(user_id=workspace_b.agent.user_id, draft_id=draft.draft_id)


# --- ListDraftVersionsUseCase -------------------------------------------------------------------


def test_list_draft_versions_includes_persisted_evidence(session):
    workspace = _make_workspace(session)
    draft = _create_draft(session, workspace.agent)

    element = KnowledgeElement(
        agent_id=workspace.agent.agent_id,
        element_type=KnowledgeElementType.CONCEPT,
        label="Evidence",
        created_by=KnowledgeCreatedBy.SYSTEM,
    )
    session.add(element)
    session.flush()
    chunk = KnowledgeChunk(agent_id=workspace.agent.agent_id, element_id=element.element_id, content="Evidence content.")
    session.add(chunk)
    session.flush()

    versions = SqlAlchemyDraftVersionRepository(session)
    version = versions.add(DraftVersion(draft_id=draft.draft_id, version_number=1, content="Body"))
    evidence_links = SqlAlchemyDraftEvidenceLinkRepository(session)
    evidence_links.add(DraftEvidenceLink.for_knowledge_chunk(draft_version_id=version.version_id, chunk_id=chunk.chunk_id))
    session.commit()

    use_case = ListDraftVersionsUseCase(
        SqlAlchemyDraftRepository(session), versions, evidence_links, SqlAlchemyAgentRepository(session)
    )
    result = use_case.execute(user_id=workspace.agent.user_id, draft_id=draft.draft_id)

    assert len(result) == 1
    assert isinstance(result[0], DraftVersionWithEvidence)
    assert result[0].evidence[0].chunk_id == chunk.chunk_id


# --- SubmitDraftReviewUseCase -------------------------------------------------------------------


def _submit_review_use_case(session):
    return SubmitDraftReviewUseCase(
        SqlAlchemyDraftRepository(session),
        SqlAlchemyDraftVersionRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyReviewDecisionRepository(session),
        SqlAlchemyAgentRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def test_submit_review_persists_decided_review_with_decided_at_set(session):
    """Regression test for a real pre-existing gap found during Stage 7 reconnaissance:
    SqlAlchemyReviewRepository.add() never wrote decided_at to the database row at all, even
    when the domain object carried one - status would be 'decided' but decided_at would stay
    NULL. Fixed in infrastructure/repositories.py.
    """
    workspace = _make_workspace(session)
    draft = _create_draft(session, workspace.agent)
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="Body")
    )
    session.commit()
    use_case = _submit_review_use_case(session)

    decision = use_case.execute(
        user_id=workspace.agent.user_id,
        draft_id=draft.draft_id,
        version_id=version.version_id,
        outcome=ReviewOutcome.APPROVED,
        rationale="Ready.",
    )

    session.expire_all()
    from app.modules.writing.infrastructure.models import Review as ReviewModel

    stored_review = session.get(ReviewModel, decision.review_id)
    assert stored_review.status.value == "decided"
    assert stored_review.decided_at is not None

    stored_draft = SqlAlchemyDraftRepository(session).get_by_id(draft.draft_id)
    assert stored_draft.status == DraftStatus.APPROVED


def test_submit_review_rejects_a_version_from_a_different_draft(session):
    workspace = _make_workspace(session)
    draft_a = _create_draft(session, workspace.agent, title="A")
    draft_b = _create_draft(session, workspace.agent, title="B")
    version_b = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft_b.draft_id, version_number=1, content="Body")
    )
    session.commit()
    use_case = _submit_review_use_case(session)

    from app.modules.writing.domain.exceptions import DraftVersionNotFoundError

    with pytest.raises(DraftVersionNotFoundError):
        use_case.execute(
            user_id=workspace.agent.user_id,
            draft_id=draft_a.draft_id,
            version_id=version_b.version_id,
            outcome=ReviewOutcome.APPROVED,
        )


def test_second_review_after_a_decided_one_is_permitted_and_independently_persisted(session):
    """The frozen 'at most one open Review per Draft Version' invariant only restricts
    concurrently-open Reviews; since every Review this use case creates is already decided,
    it is never at risk, and multiple sequential reviews for the same version are allowed.
    """
    workspace = _make_workspace(session)
    draft = _create_draft(session, workspace.agent)
    version = SqlAlchemyDraftVersionRepository(session).add(
        DraftVersion(draft_id=draft.draft_id, version_number=1, content="Body")
    )
    session.commit()
    use_case = _submit_review_use_case(session)

    first = use_case.execute(
        user_id=workspace.agent.user_id, draft_id=draft.draft_id, version_id=version.version_id,
        outcome=ReviewOutcome.REVISIONS_REQUESTED,
    )
    second = use_case.execute(
        user_id=workspace.agent.user_id, draft_id=draft.draft_id, version_id=version.version_id,
        outcome=ReviewOutcome.APPROVED,
    )

    assert first.review_id != second.review_id
    session.expire_all()
    assert SqlAlchemyDraftRepository(session).get_by_id(draft.draft_id).status == DraftStatus.APPROVED
