import pytest
from sqlalchemy.exc import IntegrityError

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.domain.exceptions import EmptyDocumentContentError
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.style_ingestion import (
    DEFAULT_WRITING_PROFILE_NAME,
    UploadWritingStyleDocumentUseCase,
)
from app.modules.writing.infrastructure.models import WritingProfile as WritingProfileModel
from app.modules.writing.infrastructure.repositories import SqlAlchemyWritingProfileRepository
from app.storage.filesystem import FilesystemStorage


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "writing_style_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


@pytest.fixture()
def storage(tmp_path):
    return FilesystemStorage(tmp_path / "object-store")


def _make_workspace(session, username="researcher"):
    user = User(username=username)
    session.add(user)
    session.flush()

    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    create_project = CreateProjectUseCase(projects)
    workspace_use_case = CreateAgentWorkspaceUseCase(agents, create_project, uow)
    return workspace_use_case.execute(user_id=user.user_id, project_title="Thesis", project_topic="Topic")


def _build_use_case(session, storage):
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    agents = SqlAlchemyAgentRepository(session)
    profiles = SqlAlchemyWritingProfileRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    return UploadWritingStyleDocumentUseCase(documents, projects, agents, profiles, storage, uow), documents, profiles


def test_upload_persists_document_and_profile_and_writes_content_to_storage(session, storage):
    workspace = _make_workspace(session)
    use_case, documents, profiles = _build_use_case(session, storage)

    result = use_case.execute(
        user_id=workspace.agent.user_id, title="Sample Essay", format="pdf", content=b"style sample", extension="pdf"
    )

    session.expire_all()
    stored_document = documents.get_by_id(result.document.document_id)
    assert stored_document is not None
    assert stored_document.project_id == workspace.project.project_id
    assert stored_document.processing_status == DocumentProcessingStatus.PENDING
    assert storage.exists(stored_document.content_reference)
    assert storage.read(stored_document.content_reference) == b"style sample"

    stored_profile = profiles.get_active_by_agent_id(workspace.agent.agent_id)
    assert stored_profile is not None
    assert stored_profile.profile_id == result.profile.profile_id
    assert stored_profile.name == DEFAULT_WRITING_PROFILE_NAME


def test_second_upload_reuses_the_same_writing_profile_not_a_second_one(session, storage):
    workspace = _make_workspace(session)
    use_case, documents, profiles = _build_use_case(session, storage)

    first = use_case.execute(user_id=workspace.agent.user_id, title="Essay 1", format="pdf", content=b"sample one")
    second = use_case.execute(user_id=workspace.agent.user_id, title="Essay 2", format="pdf", content=b"sample two")

    assert first.profile.profile_id == second.profile.profile_id
    assert len(documents.list_by_project_id(workspace.project.project_id)) == 2


def test_style_document_never_enqueues_a_knowledge_processing_work_item(session, storage):
    """Confirms the hard scope boundary at the persistence level, not just by code
    inspection: no Work Item row exists after a style-document upload.
    """
    workspace = _make_workspace(session)
    use_case, documents, profiles = _build_use_case(session, storage)

    use_case.execute(user_id=workspace.agent.user_id, title="Essay", format="pdf", content=b"sample")

    from app.workers.models import WorkItem as WorkItemModel

    assert session.query(WorkItemModel).all() == []


def test_upload_with_empty_content_writes_nothing(session, storage, tmp_path):
    workspace = _make_workspace(session)
    use_case, documents, profiles = _build_use_case(session, storage)

    with pytest.raises(EmptyDocumentContentError):
        use_case.execute(user_id=workspace.agent.user_id, title="Essay", format="pdf", content=b"")

    assert documents.list_by_project_id(workspace.project.project_id) == []
    assert list((tmp_path / "object-store").iterdir()) == []
    assert profiles.get_active_by_agent_id(workspace.agent.agent_id) is None


def test_upload_for_a_user_with_no_agent_is_rejected_and_writes_nothing(session, storage, tmp_path):
    other_user = User(username="no-agent-yet")
    session.add(other_user)
    session.flush()
    use_case, documents, profiles = _build_use_case(session, storage)

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=other_user.user_id, title="Essay", format="pdf", content=b"sample")

    assert list((tmp_path / "object-store").iterdir()) == []


def test_style_documents_do_not_leak_across_agents(session, storage):
    workspace_a = _make_workspace(session, username="user-a")
    workspace_b = _make_workspace(session, username="user-b")
    use_case, documents, profiles = _build_use_case(session, storage)

    use_case.execute(user_id=workspace_a.agent.user_id, title="A's essay", format="pdf", content=b"a")
    use_case.execute(user_id=workspace_b.agent.user_id, title="B's essay", format="pdf", content=b"b")

    a_documents = documents.list_by_project_id(workspace_a.project.project_id)
    b_documents = documents.list_by_project_id(workspace_b.project.project_id)
    assert [d.title for d in a_documents] == ["A's essay"]
    assert [d.title for d in b_documents] == ["B's essay"]

    profile_a = profiles.get_active_by_agent_id(workspace_a.agent.agent_id)
    profile_b = profiles.get_active_by_agent_id(workspace_b.agent.agent_id)
    assert profile_a.profile_id != profile_b.profile_id


def test_concurrent_active_profile_creation_is_rejected_at_the_database_level(session):
    """Belt-and-suspenders: even if application logic were bypassed, Stage 2's partial unique
    index (at most one active Writing Profile per Agent) still holds.
    """
    workspace = _make_workspace(session)
    session.add(
        WritingProfileModel(agent_id=workspace.agent.agent_id, user_id=workspace.agent.user_id, name="A", status="active")
    )
    session.commit()

    session.add(
        WritingProfileModel(agent_id=workspace.agent.agent_id, user_id=workspace.agent.user_id, name="B", status="active")
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
