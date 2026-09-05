import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.domain.exceptions import ProjectNotFoundError
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "document_test.db"
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


def _make_workspace(session):
    user = User(username="researcher")
    session.add(user)
    session.flush()

    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    create_project = CreateProjectUseCase(projects)
    workspace_use_case = CreateAgentWorkspaceUseCase(agents, create_project, uow)
    return workspace_use_case.execute(user_id=user.user_id, project_title="Thesis", project_topic="Topic")


def test_upload_persists_document_and_writes_content_to_storage(session, storage, tmp_path):
    workspace = _make_workspace(session)
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    use_case = UploadResearchDocumentUseCase(documents, projects, storage, uow)

    document = use_case.execute(
        project_id=workspace.project.project_id,
        title="Baseline survey",
        format="pdf",
        content=b"survey content",
        extension="pdf",
    )

    session.expire_all()
    stored = documents.get_by_id(document.document_id)
    assert stored is not None
    assert stored.processing_status == DocumentProcessingStatus.PENDING
    assert storage.exists(stored.content_reference)
    assert storage.read(stored.content_reference) == b"survey content"


def test_upload_against_a_nonexistent_project_writes_nothing(session, storage, tmp_path):
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    use_case = UploadResearchDocumentUseCase(documents, projects, storage, uow)

    with pytest.raises(ProjectNotFoundError):
        use_case.execute(project_id=999, title="Orphan", format="pdf", content=b"data")

    assert documents.list_by_project_id(999) == []
    assert list((tmp_path / "object-store").iterdir()) == []


def test_multiple_documents_can_be_uploaded_to_the_same_project(session, storage):
    workspace = _make_workspace(session)
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    use_case = UploadResearchDocumentUseCase(documents, projects, storage, uow)

    use_case.execute(project_id=workspace.project.project_id, title="A", format="pdf", content=b"content A")
    use_case.execute(project_id=workspace.project.project_id, title="B", format="docx", content=b"content B")

    stored = documents.list_by_project_id(workspace.project.project_id)
    assert len(stored) == 2
