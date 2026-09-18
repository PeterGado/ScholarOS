import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DocumentPurpose
from app.modules.document.domain.exceptions import EmptyDocumentContentError
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.entities import Project
from app.modules.project.domain.repositories import ProjectRepository
from app.modules.writing.application.style_ingestion import (
    DEFAULT_WRITING_PROFILE_NAME,
    MAX_WRITING_STYLE_SAMPLES,
    ListWritingStyleDocumentsUseCase,
    UploadWritingStyleDocumentUseCase,
)
from app.modules.writing.domain.entities import WritingProfile
from app.modules.writing.domain.exceptions import TooManyWritingStyleSamplesError
from app.modules.writing.domain.repositories import WritingProfileRepository

OWNER_USER_ID = 1
AGENT_ID = 1
PROJECT_ID = 1


class FakeAgentRepository(AgentRepository):
    def __init__(self, agents: dict[int, Agent] | None = None):
        self._agents = agents if agents is not None else {AGENT_ID: Agent(user_id=OWNER_USER_ID, agent_id=AGENT_ID)}

    def get_by_user_id(self, user_id):
        return next((a for a in self._agents.values() if a.user_id == user_id), None)

    def get_by_id(self, agent_id):
        return self._agents.get(agent_id)

    def add(self, agent):
        raise NotImplementedError


class FakeProjectRepository(ProjectRepository):
    def __init__(self):
        self.project = Project(project_id=PROJECT_ID, agent_id=AGENT_ID, title="Thesis", topic="Topic")

    def get_by_agent_id(self, agent_id):
        return self.project if agent_id == AGENT_ID else None

    def get_by_id(self, project_id):
        raise NotImplementedError

    def add(self, project):
        raise NotImplementedError


class FakeDocumentRepository(DocumentRepository):
    def __init__(self):
        self._by_id: dict[int, ResearchDocument] = {}
        self._next_id = 1

    def get_by_id(self, document_id):
        return self._by_id.get(document_id)

    def list_by_project_id(self, project_id, *, purpose=None):
        return [
            d
            for d in self._by_id.values()
            if d.project_id == project_id and (purpose is None or d.purpose == purpose)
        ]

    def add(self, document: ResearchDocument) -> ResearchDocument:
        document.document_id = self._next_id
        self._next_id += 1
        self._by_id[document.document_id] = document
        return document

    def update_processing_status(self, document_id, status, *, processed_at=None):
        raise NotImplementedError

    def mark_deleted(self, document_id, *, deleted_at):
        raise NotImplementedError


class FakeWritingProfileRepository(WritingProfileRepository):
    def __init__(self, existing: WritingProfile | None = None):
        self._next_id = 1
        self._by_id: dict[int, WritingProfile] = {}
        if existing is not None:
            existing.profile_id = self._next_id
            self._by_id[self._next_id] = existing
            self._next_id += 1

    def add(self, profile: WritingProfile) -> WritingProfile:
        profile.profile_id = self._next_id
        self._by_id[self._next_id] = profile
        self._next_id += 1
        return profile

    def get_by_id(self, profile_id):
        return self._by_id.get(profile_id)

    def get_active_by_agent_id(self, agent_id):
        return next((p for p in self._by_id.values() if p.agent_id == agent_id and p.status.value == "active"), None)


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


def _build_use_case(agents=None, existing_profile: WritingProfile | None = None):
    documents = FakeDocumentRepository()
    projects = FakeProjectRepository()
    agent_repository = FakeAgentRepository(agents)
    profiles = FakeWritingProfileRepository(existing=existing_profile)
    content_store = FakeContentStore()
    uow = FakeUnitOfWork()
    use_case = UploadWritingStyleDocumentUseCase(documents, projects, agent_repository, profiles, content_store, uow)
    return use_case, documents, profiles, content_store, uow


def test_uploads_style_document_and_auto_creates_a_writing_profile_when_none_exists():
    use_case, documents, profiles, content_store, uow = _build_use_case()

    result = use_case.execute(user_id=OWNER_USER_ID, title="Sample Essay", format="pdf", content=b"hello", extension="pdf")

    assert result.document.document_id is not None
    assert result.document.project_id == PROJECT_ID
    assert result.document.content_reference == "ref-1.pdf"
    assert content_store.saved == [b"hello"]
    assert result.profile.profile_id is not None
    assert result.profile.name == DEFAULT_WRITING_PROFILE_NAME
    assert result.profile.agent_id == AGENT_ID
    assert result.document.purpose == DocumentPurpose.WRITING_STYLE_SAMPLE
    assert uow.committed


def test_reuses_the_existing_active_writing_profile_instead_of_creating_a_second_one():
    existing = WritingProfile(agent_id=AGENT_ID, user_id=OWNER_USER_ID, name="Custom Name")
    use_case, documents, profiles, content_store, uow = _build_use_case(existing_profile=existing)

    result = use_case.execute(user_id=OWNER_USER_ID, title="Sample Essay", format="pdf", content=b"hello")

    assert result.profile.profile_id == existing.profile_id
    assert result.profile.name == "Custom Name"


def test_does_not_enqueue_any_work_item():
    """Hard scope boundary: style ingestion must never enter the Knowledge Processing
    Pipeline. The use case takes no WorkItemEnqueuer dependency at all - this test documents
    that absence as a positive assertion, not merely an omission.
    """
    use_case, *_ = _build_use_case()
    assert not hasattr(use_case, "_work_items")


def test_upload_with_empty_content_is_rejected_and_nothing_is_committed():
    use_case, documents, profiles, content_store, uow = _build_use_case()

    with pytest.raises(EmptyDocumentContentError):
        use_case.execute(user_id=OWNER_USER_ID, title="Sample Essay", format="pdf", content=b"")

    assert content_store.saved == []
    assert not uow.committed
    assert documents.list_by_project_id(PROJECT_ID) == []


def test_upload_for_a_user_with_no_agent_is_rejected():
    use_case, documents, profiles, content_store, uow = _build_use_case(agents={})

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=OWNER_USER_ID, title="Sample Essay", format="pdf", content=b"hello")

    assert content_store.saved == []
    assert not uow.committed


def test_upload_beyond_the_sample_limit_is_rejected_and_nothing_is_committed():
    use_case, documents, profiles, content_store, uow = _build_use_case()
    for i in range(MAX_WRITING_STYLE_SAMPLES):
        use_case.execute(user_id=OWNER_USER_ID, title=f"Sample {i}", format="txt", content=b"x")
    content_store.saved.clear()

    with pytest.raises(TooManyWritingStyleSamplesError):
        use_case.execute(user_id=OWNER_USER_ID, title="One too many", format="txt", content=b"x")

    assert len(documents.list_by_project_id(PROJECT_ID)) == MAX_WRITING_STYLE_SAMPLES
    assert content_store.saved == []  # rejected before ever writing to storage


def test_upload_at_exactly_the_sample_limit_still_succeeds():
    use_case, documents, profiles, content_store, uow = _build_use_case()
    for i in range(MAX_WRITING_STYLE_SAMPLES - 1):
        use_case.execute(user_id=OWNER_USER_ID, title=f"Sample {i}", format="txt", content=b"x")

    use_case.execute(user_id=OWNER_USER_ID, title="The last one", format="txt", content=b"x")

    assert len(documents.list_by_project_id(PROJECT_ID)) == MAX_WRITING_STYLE_SAMPLES


def test_a_research_document_in_the_same_project_does_not_count_against_the_sample_limit():
    use_case, documents, profiles, content_store, uow = _build_use_case()
    documents.add(
        ResearchDocument.create(
            project_id=PROJECT_ID, title="Unrelated research doc", format="txt", content_reference="ref-research",
            purpose=DocumentPurpose.RESEARCH,
        )
    )

    for i in range(MAX_WRITING_STYLE_SAMPLES):
        use_case.execute(user_id=OWNER_USER_ID, title=f"Sample {i}", format="txt", content=b"x")

    assert len(documents.list_by_project_id(PROJECT_ID, purpose=DocumentPurpose.WRITING_STYLE_SAMPLE)) == MAX_WRITING_STYLE_SAMPLES


# --- ListWritingStyleDocumentsUseCase ---------------------------------------------------------


def test_list_writing_style_documents_returns_only_uploaded_samples():
    """A real gap this closes: research documents in the same project must never bleed into
    this listing, and vice versa (DocumentPurpose's own docstring).
    """
    upload_use_case, documents, *_ = _build_use_case()
    upload_use_case.execute(user_id=OWNER_USER_ID, title="Sample A", format="txt", content=b"a")
    upload_use_case.execute(user_id=OWNER_USER_ID, title="Sample B", format="txt", content=b"b")
    documents.add(
        ResearchDocument.create(
            project_id=PROJECT_ID, title="Unrelated research doc", format="txt", content_reference="ref-research",
            purpose=DocumentPurpose.RESEARCH,
        )
    )

    list_use_case = ListWritingStyleDocumentsUseCase(
        documents, FakeProjectRepository(), FakeAgentRepository()
    )
    result = list_use_case.execute(user_id=OWNER_USER_ID)

    assert {d.title for d in result} == {"Sample A", "Sample B"}


def test_list_writing_style_documents_for_a_user_with_none_uploaded_returns_empty_list():
    documents = FakeDocumentRepository()
    list_use_case = ListWritingStyleDocumentsUseCase(documents, FakeProjectRepository(), FakeAgentRepository())

    assert list_use_case.execute(user_id=OWNER_USER_ID) == []


def test_list_writing_style_documents_for_a_user_with_no_agent_is_rejected():
    documents = FakeDocumentRepository()
    list_use_case = ListWritingStyleDocumentsUseCase(documents, FakeProjectRepository(), FakeAgentRepository(agents={}))

    with pytest.raises(AgentNotFoundForUserError):
        list_use_case.execute(user_id=OWNER_USER_ID)
