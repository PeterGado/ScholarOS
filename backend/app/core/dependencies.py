from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai.providers.base import EmbeddingProvider
from app.ai.providers.factory import create_provider
from app.auth.dependencies import extract_bearer_token
from app.auth.infrastructure import SqlAlchemyAuthSessionRepository, SqlAlchemyUserCredentialLookup
from app.auth.service import AuthService
from app.core.config import get_settings
from app.database.session import get_db
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
)
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.repository import WorkItemRepository


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


def get_work_item_repository(db: Session = Depends(get_db)) -> WorkItemRepository:
    return WorkItemRepository(db)


def get_upload_research_document_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    content_store: FilesystemStorage = Depends(get_content_store),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    work_item_repository: WorkItemRepository = Depends(get_work_item_repository),
) -> UploadResearchDocumentUseCase:
    return UploadResearchDocumentUseCase(
        document_repository, project_repository, agent_repository, content_store, unit_of_work, work_item_repository
    )


def get_auth_session_repository(db: Session = Depends(get_db)) -> SqlAlchemyAuthSessionRepository:
    return SqlAlchemyAuthSessionRepository(db)


def get_user_credential_lookup(db: Session = Depends(get_db)) -> SqlAlchemyUserCredentialLookup:
    return SqlAlchemyUserCredentialLookup(db)


def get_auth_service(
    session_repository: SqlAlchemyAuthSessionRepository = Depends(get_auth_session_repository),
    user_lookup: SqlAlchemyUserCredentialLookup = Depends(get_user_credential_lookup),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> AuthService:
    return AuthService(session_repository, user_lookup, unit_of_work)


def get_current_user_id(
    raw_token: str = Depends(extract_bearer_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> int:
    """The Authentication Boundary's identity dependency (ADR-010, Milestone 7 Stage 6).

    Composes the existing bearer-token extraction and AuthService.verify_token - no
    SQLAlchemy, no token/session logic of its own. Every rejection (missing/malformed
    Authorization, wrong scheme, empty/unknown token, ended session) is raised by those
    composed pieces as InvalidSessionError, translated to 401 by the handler already
    registered in app.api.exception_handlers. There is exactly one identity source: the
    authenticated session. No bootstrap fallback, no client-supplied user_id.
    """
    return auth_service.verify_token(raw_token).user_id


def get_embedding_provider() -> EmbeddingProvider:
    """Constructed fresh per request, mirroring `get_content_store`'s own pattern - no
    caching. Raises `ProviderConfigurationError` (mapped to 503) if `AI_API_KEY` is not
    configured, the first time an AI provider exception becomes reachable through a route.
    """
    return create_provider(get_settings())


def get_knowledge_chunk_repository(db: Session = Depends(get_db)) -> SqlAlchemyKnowledgeChunkRepository:
    return SqlAlchemyKnowledgeChunkRepository(db)


def get_chunk_evidence_link_repository(db: Session = Depends(get_db)) -> SqlAlchemyChunkEvidenceLinkRepository:
    return SqlAlchemyChunkEvidenceLinkRepository(db)


def get_knowledge_chunk_embedding_repository(db: Session = Depends(get_db)) -> SqlAlchemyKnowledgeChunkEmbeddingRepository:
    return SqlAlchemyKnowledgeChunkEmbeddingRepository(db)


def get_search_knowledge_use_case(
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    embedding_repository: SqlAlchemyKnowledgeChunkEmbeddingRepository = Depends(get_knowledge_chunk_embedding_repository),
    chunk_repository: SqlAlchemyKnowledgeChunkRepository = Depends(get_knowledge_chunk_repository),
    evidence_link_repository: SqlAlchemyChunkEvidenceLinkRepository = Depends(get_chunk_evidence_link_repository),
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> SearchKnowledgeUseCase:
    return SearchKnowledgeUseCase(
        agent_repository, embedding_provider, embedding_repository, chunk_repository, evidence_link_repository, document_repository
    )
