from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai.providers.base import EmbeddingProvider, TextGenerationProvider
from app.ai.providers.factory import create_provider
from app.auth.dependencies import extract_bearer_token
from app.auth.infrastructure import (
    SqlAlchemyAuthSessionRepository,
    SqlAlchemyUserCredentialLookup,
    SqlAlchemyUserRegistrationRepository,
)
from app.auth.google_oauth import verify_google_id_token
from app.auth.google_sign_in import GoogleSignInUseCase
from app.auth.registration import RegisterUserUseCase
from app.auth.service import AuthService
from app.core.config import get_settings
from app.database.session import get_db
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.reset_workspace import ResetAgentWorkspaceUseCase
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase, GetAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import (
    DeleteResearchDocumentUseCase,
    ListProjectDocumentsUseCase,
    RetryDocumentProcessingUseCase,
    UploadResearchDocumentUseCase,
)
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyLexicalSearchRepository,
)
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.chat import (
    DeleteConversationUseCase,
    GetChatReplyStatusUseCase,
    ListConversationMessagesUseCase,
    ListConversationsUseCase,
    RetryChatReplyUseCase,
    SendChatMessageUseCase,
    StartConversationUseCase,
)
from app.modules.writing.application.memory_inspection import ListMemoryUseCase, SupersedeMemoryRecordUseCase
from app.modules.writing.application.profile_view import GetWritingProfileUseCase
from app.modules.writing.application.style_extraction import ExtractWritingStyleProfileUseCase
from app.modules.writing.application.style_ingestion import (
    ListWritingStyleDocumentsUseCase,
    UploadWritingStyleDocumentUseCase,
)
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyProfileCharacteristicSourceRepository,
    SqlAlchemyWritingProfileRepository,
)
from app.modules.document.domain.ports import ContentStore
from app.storage.exceptions import InvalidStorageConfigurationError
from app.storage.filesystem import FilesystemStorage
from app.storage.s3_compatible import S3CompatibleStorage
from app.workers.repository import WorkItemRepository


def get_content_store() -> ContentStore:
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise InvalidStorageConfigurationError("storage_backend is 's3' but s3_bucket is not configured.")
        return S3CompatibleStorage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
        )
    return FilesystemStorage(settings.storage_root)


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


def get_get_agent_workspace_use_case(
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
) -> GetAgentWorkspaceUseCase:
    return GetAgentWorkspaceUseCase(agent_repository, project_repository)


def get_reset_agent_workspace_use_case(
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    db: Session = Depends(get_db),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> ResetAgentWorkspaceUseCase:
    return ResetAgentWorkspaceUseCase(agent_repository, db, unit_of_work)


def get_work_item_repository(db: Session = Depends(get_db)) -> WorkItemRepository:
    return WorkItemRepository(db)


def get_upload_research_document_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    content_store: ContentStore = Depends(get_content_store),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    work_item_repository: WorkItemRepository = Depends(get_work_item_repository),
) -> UploadResearchDocumentUseCase:
    return UploadResearchDocumentUseCase(
        document_repository, project_repository, agent_repository, content_store, unit_of_work, work_item_repository
    )


def get_list_project_documents_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    work_item_repository: WorkItemRepository = Depends(get_work_item_repository),
) -> ListProjectDocumentsUseCase:
    return ListProjectDocumentsUseCase(document_repository, project_repository, agent_repository, work_item_repository)


def get_delete_research_document_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> DeleteResearchDocumentUseCase:
    return DeleteResearchDocumentUseCase(document_repository, project_repository, agent_repository, unit_of_work)


def get_retry_document_processing_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    work_item_repository: WorkItemRepository = Depends(get_work_item_repository),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> RetryDocumentProcessingUseCase:
    return RetryDocumentProcessingUseCase(
        document_repository, project_repository, agent_repository, work_item_repository, unit_of_work
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


def get_user_registration_repository(db: Session = Depends(get_db)) -> SqlAlchemyUserRegistrationRepository:
    return SqlAlchemyUserRegistrationRepository(db)


def get_register_user_use_case(
    user_lookup: SqlAlchemyUserCredentialLookup = Depends(get_user_credential_lookup),
    user_registration: SqlAlchemyUserRegistrationRepository = Depends(get_user_registration_repository),
    auth_service: AuthService = Depends(get_auth_service),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> RegisterUserUseCase:
    return RegisterUserUseCase(
        user_lookup,
        user_registration,
        auth_service,
        unit_of_work,
        required_invite_code=get_settings().registration_invite_code,
    )


def get_google_token_verifier():
    """A dependency-injected seam around the one function that actually calls Google's network
    (app.auth.google_oauth.verify_google_id_token) - overridden in e2e tests with a fake, the
    same pattern get_content_store/get_embedding_provider already use, so no test ever needs a
    real Google ID token or hits Google's real cert-fetching endpoint.
    """
    return verify_google_id_token


def get_google_sign_in_use_case(
    user_lookup: SqlAlchemyUserCredentialLookup = Depends(get_user_credential_lookup),
    user_registration: SqlAlchemyUserRegistrationRepository = Depends(get_user_registration_repository),
    auth_service: AuthService = Depends(get_auth_service),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    verify_id_token=Depends(get_google_token_verifier),
) -> GoogleSignInUseCase:
    return GoogleSignInUseCase(
        user_lookup,
        user_registration,
        auth_service,
        unit_of_work,
        verify_id_token,
        required_invite_code=get_settings().registration_invite_code,
        google_client_id=get_settings().google_oauth_client_id,
    )


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


def get_text_generation_provider() -> TextGenerationProvider:
    """Same factory call as `get_embedding_provider` - `create_provider` returns one object
    satisfying both Protocols (ADR-002) - given its own typed accessor because callers that
    only generate text (e.g. style extraction) should depend on the narrower Protocol.
    """
    return create_provider(get_settings())


def get_knowledge_chunk_repository(db: Session = Depends(get_db)) -> SqlAlchemyKnowledgeChunkRepository:
    return SqlAlchemyKnowledgeChunkRepository(db)


def get_chunk_evidence_link_repository(db: Session = Depends(get_db)) -> SqlAlchemyChunkEvidenceLinkRepository:
    return SqlAlchemyChunkEvidenceLinkRepository(db)


def get_knowledge_chunk_embedding_repository(db: Session = Depends(get_db)) -> SqlAlchemyKnowledgeChunkEmbeddingRepository:
    return SqlAlchemyKnowledgeChunkEmbeddingRepository(db)


def get_lexical_search_repository(db: Session = Depends(get_db)) -> SqlAlchemyLexicalSearchRepository:
    return SqlAlchemyLexicalSearchRepository(db)


def get_writing_profile_repository(db: Session = Depends(get_db)) -> SqlAlchemyWritingProfileRepository:
    return SqlAlchemyWritingProfileRepository(db)


def get_upload_writing_style_document_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    writing_profile_repository: SqlAlchemyWritingProfileRepository = Depends(get_writing_profile_repository),
    content_store: ContentStore = Depends(get_content_store),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> UploadWritingStyleDocumentUseCase:
    return UploadWritingStyleDocumentUseCase(
        document_repository, project_repository, agent_repository, writing_profile_repository, content_store, unit_of_work
    )


def get_list_writing_style_documents_use_case(
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
) -> ListWritingStyleDocumentsUseCase:
    return ListWritingStyleDocumentsUseCase(document_repository, project_repository, agent_repository)


def get_profile_characteristic_repository(db: Session = Depends(get_db)) -> SqlAlchemyProfileCharacteristicRepository:
    return SqlAlchemyProfileCharacteristicRepository(db)


def get_profile_characteristic_source_repository(
    db: Session = Depends(get_db),
) -> SqlAlchemyProfileCharacteristicSourceRepository:
    return SqlAlchemyProfileCharacteristicSourceRepository(db)


def get_extract_writing_style_profile_use_case(
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    content_store: ContentStore = Depends(get_content_store),
    writing_profile_repository: SqlAlchemyWritingProfileRepository = Depends(get_writing_profile_repository),
    profile_characteristic_repository: SqlAlchemyProfileCharacteristicRepository = Depends(
        get_profile_characteristic_repository
    ),
    profile_characteristic_source_repository: SqlAlchemyProfileCharacteristicSourceRepository = Depends(
        get_profile_characteristic_source_repository
    ),
    text_provider: TextGenerationProvider = Depends(get_text_generation_provider),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> ExtractWritingStyleProfileUseCase:
    return ExtractWritingStyleProfileUseCase(
        agent_repository,
        project_repository,
        document_repository,
        content_store,
        writing_profile_repository,
        profile_characteristic_repository,
        profile_characteristic_source_repository,
        text_provider,
        unit_of_work,
    )


def get_search_knowledge_use_case(
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    embedding_repository: SqlAlchemyKnowledgeChunkEmbeddingRepository = Depends(get_knowledge_chunk_embedding_repository),
    chunk_repository: SqlAlchemyKnowledgeChunkRepository = Depends(get_knowledge_chunk_repository),
    evidence_link_repository: SqlAlchemyChunkEvidenceLinkRepository = Depends(get_chunk_evidence_link_repository),
    document_repository: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    lexical_search_repository: SqlAlchemyLexicalSearchRepository = Depends(get_lexical_search_repository),
) -> SearchKnowledgeUseCase:
    return SearchKnowledgeUseCase(
        agent_repository,
        embedding_provider,
        embedding_repository,
        chunk_repository,
        evidence_link_repository,
        document_repository,
        lexical_search_repository,
    )


# --- Stage 7: Writing API -------------------------------------------------------------------


def get_memory_record_repository(db: Session = Depends(get_db)) -> SqlAlchemyMemoryRecordRepository:
    return SqlAlchemyMemoryRecordRepository(db)


def get_conversation_repository(db: Session = Depends(get_db)) -> SqlAlchemyConversationRepository:
    return SqlAlchemyConversationRepository(db)


def get_memory_provenance_link_repository(db: Session = Depends(get_db)) -> SqlAlchemyMemoryProvenanceLinkRepository:
    return SqlAlchemyMemoryProvenanceLinkRepository(db)


def get_message_repository(db: Session = Depends(get_db)) -> SqlAlchemyMessageRepository:
    return SqlAlchemyMessageRepository(db)


def get_start_conversation_use_case(
    conversation_repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> StartConversationUseCase:
    return StartConversationUseCase(conversation_repository, agent_repository, unit_of_work)


def get_list_conversations_use_case(
    conversation_repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
) -> ListConversationsUseCase:
    return ListConversationsUseCase(conversation_repository, agent_repository)


def get_delete_conversation_use_case(
    conversation_repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> DeleteConversationUseCase:
    return DeleteConversationUseCase(conversation_repository, agent_repository, unit_of_work)


def get_list_conversation_messages_use_case(
    conversation_repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
    message_repository: SqlAlchemyMessageRepository = Depends(get_message_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
) -> ListConversationMessagesUseCase:
    return ListConversationMessagesUseCase(conversation_repository, message_repository, agent_repository)


def get_send_chat_message_use_case(
    conversation_repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
    message_repository: SqlAlchemyMessageRepository = Depends(get_message_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    project_repository: SqlAlchemyProjectRepository = Depends(get_project_repository),
    writing_profile_repository: SqlAlchemyWritingProfileRepository = Depends(get_writing_profile_repository),
    profile_characteristic_repository: SqlAlchemyProfileCharacteristicRepository = Depends(
        get_profile_characteristic_repository
    ),
    memory_record_repository: SqlAlchemyMemoryRecordRepository = Depends(get_memory_record_repository),
    search_knowledge_use_case: SearchKnowledgeUseCase = Depends(get_search_knowledge_use_case),
    work_item_repository: WorkItemRepository = Depends(get_work_item_repository),
    content_store: ContentStore = Depends(get_content_store),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> SendChatMessageUseCase:
    return SendChatMessageUseCase(
        conversation_repository,
        message_repository,
        agent_repository,
        project_repository,
        writing_profile_repository,
        profile_characteristic_repository,
        memory_record_repository,
        search_knowledge_use_case,
        work_item_repository,
        content_store,
        unit_of_work,
    )


def get_get_chat_reply_status_use_case(
    conversation_repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    work_item_repository: WorkItemRepository = Depends(get_work_item_repository),
) -> GetChatReplyStatusUseCase:
    return GetChatReplyStatusUseCase(conversation_repository, agent_repository, work_item_repository)


def get_retry_chat_reply_use_case(
    conversation_repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    work_item_repository: WorkItemRepository = Depends(get_work_item_repository),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> RetryChatReplyUseCase:
    return RetryChatReplyUseCase(conversation_repository, agent_repository, work_item_repository, unit_of_work)


def get_list_memory_use_case(
    memory_record_repository: SqlAlchemyMemoryRecordRepository = Depends(get_memory_record_repository),
    memory_provenance_link_repository: SqlAlchemyMemoryProvenanceLinkRepository = Depends(
        get_memory_provenance_link_repository
    ),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
) -> ListMemoryUseCase:
    return ListMemoryUseCase(memory_record_repository, memory_provenance_link_repository, agent_repository)


def get_supersede_memory_record_use_case(
    memory_record_repository: SqlAlchemyMemoryRecordRepository = Depends(get_memory_record_repository),
    memory_provenance_link_repository: SqlAlchemyMemoryProvenanceLinkRepository = Depends(
        get_memory_provenance_link_repository
    ),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
) -> SupersedeMemoryRecordUseCase:
    return SupersedeMemoryRecordUseCase(
        memory_record_repository, memory_provenance_link_repository, agent_repository, unit_of_work
    )


def get_get_writing_profile_use_case(
    writing_profile_repository: SqlAlchemyWritingProfileRepository = Depends(get_writing_profile_repository),
    profile_characteristic_repository: SqlAlchemyProfileCharacteristicRepository = Depends(
        get_profile_characteristic_repository
    ),
    agent_repository: SqlAlchemyAgentRepository = Depends(get_agent_repository),
) -> GetWritingProfileUseCase:
    return GetWritingProfileUseCase(writing_profile_repository, profile_characteristic_repository, agent_repository)
