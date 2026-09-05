from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage

_BOOTSTRAP_USERNAME = "default-user"


def get_current_user_id(db: Session = Depends(get_db)) -> int:
    """Placeholder for the Authentication Boundary (05_Backend_Architecture.md §15), which is
    not yet built - no such module exists to design against, and building one is explicitly
    out of Stage 5's scope. The MVP is single-user by invariant (05_Constraints_and_Integrity.md
    invariant 9), so this resolves every request to one bootstrap User row created on first
    use, rather than either (a) accepting a client-supplied user_id, which would hard-code an
    insecure model where any caller could act as any user, or (b) implementing
    registration/login, which is explicitly excluded from this stage. Replace this function's
    body, not its call sites, when a real authentication architecture is designed.
    """
    user = db.query(User).filter_by(username=_BOOTSTRAP_USERNAME).one_or_none()
    if user is None:
        user = User(username=_BOOTSTRAP_USERNAME)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user.user_id


def get_content_store() -> FilesystemStorage:
    return FilesystemStorage(get_settings().storage_root)


def get_agent_repository(db: Session = Depends(get_db)) -> SqlAlchemyAgentRepository:
    return SqlAlchemyAgentRepository(db)


def get_project_repository(db: Session = Depends(get_db)) -> SqlAlchemyProjectRepository:
    return SqlAlchemyProjectRepository(db)


def get_document_repository(db: Session = Depends(get_db)) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(db)


def get_unit_of_work(db: Session = Depends(get_db)) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(db)


def get_create_project_use_case(
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
) -> CreateProjectUseCase:
    return CreateProjectUseCase(project_repository)


def get_create_agent_workspace_use_case(
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    create_project: CreateProjectUseCase = Depends(get_create_project_use_case),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> CreateAgentWorkspaceUseCase:
    return CreateAgentWorkspaceUseCase(agent_repository, create_project, unit_of_work)


def get_upload_research_document_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    content_store: FilesystemStorage = Depends(get_content_store),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> UploadResearchDocumentUseCase:
    return UploadResearchDocumentUseCase(document_repository, project_repository, content_store, unit_of_work)
