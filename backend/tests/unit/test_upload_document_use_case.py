import pytest

from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.exceptions import EmptyDocumentContentError
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.entities import Project
from app.modules.project.domain.exceptions import ProjectNotFoundError
from app.modules.project.domain.repositories import ProjectRepository


class FakeDocumentRepository(DocumentRepository):
    def __init__(self):
        self._by_id: dict[int, ResearchDocument] = {}
        self._next_id = 1

    def get_by_id(self, document_id):
        return self._by_id.get(document_id)

    def list_by_project_id(self, project_id):
        return [d for d in self._by_id.values() if d.project_id == project_id]

    def add(self, document: ResearchDocument) -> ResearchDocument:
        document.document_id = self._next_id
        self._next_id += 1
        self._by_id[document.document_id] = document
        return document


class FakeProjectRepository(ProjectRepository):
    def __init__(self, existing_project_id: int | None = 1):
        self._existing_project_id = existing_project_id

    def get_by_agent_id(self, agent_id):
        raise NotImplementedError

    def get_by_id(self, project_id):
        if project_id == self._existing_project_id:
            return Project(project_id=project_id, agent_id=1, title="Thesis", topic="Topic")
        return None

    def add(self, project):
        raise NotImplementedError


class FakeContentStore:
    def __init__(self):
        self.saved: list[bytes] = []

    def save(self, content: bytes, *, extension: str = "") -> str:
        self.saved.append(content)
        return f"ref-{len(self.saved)}{('.' + extension) if extension else ''}"


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _build_use_case(project_id=1):
    documents = FakeDocumentRepository()
    projects = FakeProjectRepository(existing_project_id=project_id)
    content_store = FakeContentStore()
    uow = FakeUnitOfWork()
    use_case = UploadResearchDocumentUseCase(documents, projects, content_store, uow)
    return use_case, documents, content_store, uow


def test_uploads_document_against_an_existing_project():
    use_case, documents, content_store, uow = _build_use_case(project_id=1)

    document = use_case.execute(project_id=1, title="Source A", format="pdf", content=b"hello", extension="pdf")

    assert document.document_id is not None
    assert document.content_reference == "ref-1.pdf"
    assert content_store.saved == [b"hello"]
    assert documents.get_by_id(document.document_id) is not None
    assert uow.committed


def test_upload_against_missing_project_is_rejected_and_nothing_is_committed():
    use_case, documents, content_store, uow = _build_use_case(project_id=1)

    with pytest.raises(ProjectNotFoundError):
        use_case.execute(project_id=999, title="Source A", format="pdf", content=b"hello")

    assert content_store.saved == []
    assert not uow.committed
    assert not documents.list_by_project_id(999)


def test_upload_with_empty_content_is_rejected():
    use_case, documents, content_store, uow = _build_use_case(project_id=1)

    with pytest.raises(EmptyDocumentContentError):
        use_case.execute(project_id=1, title="Source A", format="pdf", content=b"")

    assert content_store.saved == []
    assert not uow.committed
