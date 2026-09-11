from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.exceptions import EmptyDocumentContentError
from app.modules.document.domain.ports import ContentStore
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.exceptions import ProjectNotFoundError
from app.modules.project.domain.repositories import ProjectRepository
from app.workers.enums import WorkItemKind
from app.workers.payloads import build_process_document_idempotency_key, build_process_document_payload_reference
from app.workers.ports import WorkItemEnqueuer


class UploadResearchDocumentUseCase:
    """Realizes 05_Backend_Architecture.md §10.1: accept and register a Research Document
    within its owning Project (§10.2 - depends on the project service for project
    association). Content is written to the object store first, then the metadata row is
    persisted referencing it - an orphaned file from a failed commit is harmless
    (content-addressed, ADR-004 §5), but a DB row pointing at a missing file is not.

    Enforces ownership (§15.1 API-036/API-037; Constraints invariant 15) transitively:
    Project has no user_id of its own, so ownership is proven via the Project's owning Agent.
    A mismatch is reported as the same ProjectNotFoundError as a genuinely missing project -
    deliberately indistinguishable, the same principle Stage 5's login already applies to
    unknown-username vs wrong-password, so a caller cannot use this endpoint to probe which
    project IDs exist.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
        work_item_enqueuer: WorkItemEnqueuer,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._content_store = content_store
        self._uow = unit_of_work
        self._work_items = work_item_enqueuer

    def execute(
        self,
        *,
        project_id: int,
        user_id: int,
        title: str,
        format: str,
        content: bytes,
        author: str | None = None,
        source: str | None = None,
        extension: str = "",
    ) -> ResearchDocument:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        if not content:
            raise EmptyDocumentContentError()

        content_reference = self._content_store.save(content, extension=extension)

        try:
            document = ResearchDocument.create(
                project_id=project_id,
                title=title,
                format=format,
                content_reference=content_reference,
                author=author,
                source=source,
            )
            document = self._documents.add(document)
            self._work_items.enqueue(
                kind=WorkItemKind.PIPELINE_STAGE,
                payload_reference=build_process_document_payload_reference(document.document_id),
                idempotency_key=build_process_document_idempotency_key(document.document_id),
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return document
