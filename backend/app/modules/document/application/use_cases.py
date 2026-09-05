from app.core.unit_of_work import UnitOfWork
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.exceptions import EmptyDocumentContentError
from app.modules.document.domain.ports import ContentStore
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.exceptions import ProjectNotFoundError
from app.modules.project.domain.repositories import ProjectRepository


class UploadResearchDocumentUseCase:
    """Realizes 05_Backend_Architecture.md §10.1: accept and register a Research Document
    within its owning Project (§10.2 - depends on the project service for project
    association). Content is written to the object store first, then the metadata row is
    persisted referencing it - an orphaned file from a failed commit is harmless
    (content-addressed, ADR-004 §5), but a DB row pointing at a missing file is not.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._content_store = content_store
        self._uow = unit_of_work

    def execute(
        self,
        *,
        project_id: int,
        title: str,
        format: str,
        content: bytes,
        author: str | None = None,
        source: str | None = None,
        extension: str = "",
    ) -> ResearchDocument:
        if self._projects.get_by_id(project_id) is None:
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
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return document
