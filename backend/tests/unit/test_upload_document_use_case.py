import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.exceptions import EmptyDocumentContentError
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.entities import Project
from app.modules.project.domain.exceptions import ProjectNotFoundError
from app.modules.project.domain.repositories import ProjectRepository

OWNER_USER_ID = 1
OTHER_USER_ID = 2
OWNING_AGENT_ID = 1


class FakeAgentRepository(AgentRepository):
    def __init__(self, agents: dict[int, Agent] | None = None):
        self._agents = agents if agents is not None else {OWNING_AGENT_ID: Agent(user_id=OWNER_USER_ID, agent_id=OWNING_AGENT_ID)}

    def get_by_user_id(self, user_id):
        return next((a for a in self._agents.values() if a.user_id == user_id), None)

    def get_by_id(self, agent_id):
        return self._agents.get(agent_id)

    def add(self, agent):
        raise NotImplementedError


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

    def update_processing_status(self, document_id, status, *, processed_at=None):
        document = self._by_id[document_id]
        document.processing_status = status
        if processed_at is not None:
            document.processed_at = processed_at


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


class FakeWorkItemEnqueuer:
    def __init__(self):
        self.enqueued: list[dict] = []

    def enqueue(self, *, kind, payload_reference, idempotency_key):
        self.enqueued.append({"kind": kind, "payload_reference": payload_reference, "idempotency_key": idempotency_key})
        return None


def _build_use_case(project_id=1, agents: dict[int, Agent] | None = None):
    documents = FakeDocumentRepository()
    projects = FakeProjectRepository(existing_project_id=project_id)
    agent_repository = FakeAgentRepository(agents)
    content_store = FakeContentStore()
    uow = FakeUnitOfWork()
    work_items = FakeWorkItemEnqueuer()
    use_case = UploadResearchDocumentUseCase(documents, projects, agent_repository, content_store, uow, work_items)
    return use_case, documents, content_store, uow, work_items


def test_uploads_document_against_an_existing_project_owned_by_the_caller():
    use_case, documents, content_store, uow, work_items = _build_use_case(project_id=1)

    document = use_case.execute(
        project_id=1, user_id=OWNER_USER_ID, title="Source A", format="pdf", content=b"hello", extension="pdf"
    )

    assert document.document_id is not None
    assert document.content_reference == "ref-1.pdf"
    assert content_store.saved == [b"hello"]
    assert documents.get_by_id(document.document_id) is not None
    assert uow.committed
    assert len(work_items.enqueued) == 1
    assert work_items.enqueued[0]["payload_reference"] == f"process_document:{document.document_id}"


def test_upload_against_missing_project_is_rejected_and_nothing_is_committed():
    use_case, documents, content_store, uow, work_items = _build_use_case(project_id=1)

    with pytest.raises(ProjectNotFoundError):
        use_case.execute(project_id=999, user_id=OWNER_USER_ID, title="Source A", format="pdf", content=b"hello")

    assert content_store.saved == []
    assert not uow.committed
    assert not documents.list_by_project_id(999)
    assert work_items.enqueued == []


def test_upload_with_empty_content_is_rejected():
    use_case, documents, content_store, uow, work_items = _build_use_case(project_id=1)

    with pytest.raises(EmptyDocumentContentError):
        use_case.execute(project_id=1, user_id=OWNER_USER_ID, title="Source A", format="pdf", content=b"")

    assert content_store.saved == []
    assert not uow.committed
    assert work_items.enqueued == []


def test_upload_against_a_project_not_owned_by_the_caller_is_rejected_as_not_found():
    """Ownership violation is indistinguishable from a genuinely missing project - same
    exception, same 404 - so this endpoint can't be used to probe which project IDs exist
    (Stage 6; mirrors the login endpoint's unknown-username-vs-wrong-password precedent).
    """
    use_case, documents, content_store, uow, work_items = _build_use_case(project_id=1)

    with pytest.raises(ProjectNotFoundError):
        use_case.execute(project_id=1, user_id=OTHER_USER_ID, title="Source A", format="pdf", content=b"hello")

    assert content_store.saved == []
    assert not uow.committed
    assert not documents.list_by_project_id(1)
    assert work_items.enqueued == []


def test_upload_when_the_owning_agent_cannot_be_found_is_rejected():
    """Defensive: a Project whose Agent row is somehow missing must not silently authorize
    anyone - treated the same as ownership mismatch, not a 500.
    """
    use_case, documents, content_store, uow, work_items = _build_use_case(project_id=1, agents={})

    with pytest.raises(ProjectNotFoundError):
        use_case.execute(project_id=1, user_id=OWNER_USER_ID, title="Source A", format="pdf", content=b"hello")

    assert content_store.saved == []
    assert not uow.committed
    assert work_items.enqueued == []
