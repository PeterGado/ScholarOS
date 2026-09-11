import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.exceptions import ResearchDocumentNotFoundError
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.knowledge.application.use_cases import ExtractDocumentKnowledgeUseCase, ProcessDocumentUseCase
from app.modules.knowledge.domain.entities import ChunkEmbedding, ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.knowledge.domain.exceptions import AgentResolutionError, SemanticExtractionError
from app.modules.knowledge.domain.repositories import (
    ChunkEvidenceLinkRepository,
    KnowledgeChunkEmbeddingRepository,
    KnowledgeChunkRepository,
    KnowledgeElementRepository,
)
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.project.domain.entities import Project
from app.modules.project.domain.repositories import ProjectRepository

AGENT_ID = 1
PROJECT_ID = 1
DOCUMENT_ID = 1


class FakeDocumentRepository(DocumentRepository):
    def __init__(self, documents=None):
        self._documents = documents or {}

    def get_by_id(self, document_id):
        return self._documents.get(document_id)

    def list_by_project_id(self, project_id):
        raise NotImplementedError

    def add(self, document):
        raise NotImplementedError

    def update_processing_status(self, document_id, status, *, processed_at=None):
        raise NotImplementedError


class FakeContentStore:
    def __init__(self, files=None):
        self._files = files or {}

    def save(self, content, *, extension=""):
        raise NotImplementedError

    def read(self, reference):
        return self._files[reference]

    def exists(self, reference):
        return reference in self._files


class FakeProjectRepository(ProjectRepository):
    def __init__(self, projects=None):
        self._projects = projects or {}

    def get_by_agent_id(self, agent_id):
        raise NotImplementedError

    def get_by_id(self, project_id):
        return self._projects.get(project_id)

    def add(self, project):
        raise NotImplementedError


class FakeAgentRepository(AgentRepository):
    def __init__(self, agents=None):
        self._agents = agents or {}

    def get_by_user_id(self, user_id):
        raise NotImplementedError

    def get_by_id(self, agent_id):
        return self._agents.get(agent_id)

    def add(self, agent):
        raise NotImplementedError


class FakeKnowledgeElementRepository(KnowledgeElementRepository):
    def __init__(self):
        self.saved: list[KnowledgeElement] = []
        self._next_id = 1

    def add(self, element):
        element.element_id = self._next_id
        self._next_id += 1
        self.saved.append(element)
        return element


class FakeKnowledgeChunkRepository(KnowledgeChunkRepository):
    def __init__(self):
        self.saved: dict[int, KnowledgeChunk] = {}
        self._next_id = 1

    def add(self, chunk):
        chunk.chunk_id = self._next_id
        self._next_id += 1
        self.saved[chunk.chunk_id] = chunk
        return chunk

    def get_by_id(self, chunk_id):
        return self.saved.get(chunk_id)


class FakeChunkEvidenceLinkRepository(ChunkEvidenceLinkRepository):
    def __init__(self):
        self.saved: list[ChunkEvidenceLink] = []
        self._next_id = 1

    def add(self, link):
        link.link_id = self._next_id
        self._next_id += 1
        self.saved.append(link)
        return link

    def exists_for_document(self, document_id):
        return any(link.document_id == document_id for link in self.saved)

    def list_by_document_id(self, document_id):
        return [link for link in self.saved if link.document_id == document_id]

    def list_by_chunk_id(self, chunk_id):
        return [link for link in self.saved if link.chunk_id == chunk_id]


class FakeKnowledgeChunkEmbeddingRepository(KnowledgeChunkEmbeddingRepository):
    def __init__(self):
        self.saved: list[ChunkEmbedding] = []

    def add(self, embedding):
        self.saved.append(embedding)
        return embedding

    def list_by_agent_id(self, agent_id):
        raise NotImplementedError


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeTextGenerationProvider:
    def __init__(self, responses=None, fail_after: int | None = None):
        self._responses = responses or []
        self._call_count = 0
        self._fail_after = fail_after

    def generate(self, prompt: str) -> str:
        self._call_count += 1
        if self._fail_after is not None and self._call_count > self._fail_after:
            raise RuntimeError("simulated provider failure")
        if self._responses:
            return self._responses.pop(0)
        return '{"element_type": "concept", "label": "Default label", "description": "d"}'

    @property
    def call_count(self):
        return self._call_count


class FakeEmbeddingProvider:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.call_count = 0
        self.texts_embedded: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        self.texts_embedded.append(text)
        if self.fail:
            raise RuntimeError("simulated embedding failure")
        return [0.1, 0.2, 0.3]


def _document(document_id=DOCUMENT_ID, project_id=PROJECT_ID, content_reference="ref-1") -> ResearchDocument:
    return ResearchDocument(
        document_id=document_id, project_id=project_id, title="Doc", format="txt", content_reference=content_reference
    )


def _build_use_case(
    *,
    documents=None,
    content_store=None,
    projects=None,
    agents=None,
    provider=None,
    embedding_provider=None,
    knowledge_elements=None,
    knowledge_chunks=None,
    evidence_links=None,
    embeddings=None,
    uow=None,
):
    documents = documents or FakeDocumentRepository({DOCUMENT_ID: _document()})
    content_store = content_store or FakeContentStore({"ref-1": b"Paragraph one.\n\nParagraph two."})
    projects = projects or FakeProjectRepository({PROJECT_ID: Project(project_id=PROJECT_ID, agent_id=AGENT_ID, title="T", topic="Topic")})
    agents = agents or FakeAgentRepository({AGENT_ID: Agent(agent_id=AGENT_ID, user_id=1)})
    process_document = ProcessDocumentUseCase(documents, content_store, PlainTextExtractor())
    provider = provider or FakeTextGenerationProvider()
    embedding_provider = embedding_provider or FakeEmbeddingProvider()
    knowledge_elements = knowledge_elements or FakeKnowledgeElementRepository()
    knowledge_chunks = knowledge_chunks or FakeKnowledgeChunkRepository()
    evidence_links = evidence_links or FakeChunkEvidenceLinkRepository()
    embeddings = embeddings or FakeKnowledgeChunkEmbeddingRepository()
    uow = uow or FakeUnitOfWork()

    use_case = ExtractDocumentKnowledgeUseCase(
        documents,
        projects,
        agents,
        process_document,
        provider,
        embedding_provider,
        "test-embedding-model",
        knowledge_elements,
        knowledge_chunks,
        evidence_links,
        embeddings,
        uow,
    )
    return use_case, knowledge_elements, knowledge_chunks, evidence_links, uow, provider, embeddings, embedding_provider


def test_successful_extraction_persists_element_chunk_and_evidence_link():
    use_case, elements, chunks, links, uow, provider, embeddings, embedding_provider = _build_use_case()

    result = use_case.execute(document_id=DOCUMENT_ID)

    assert len(result) == 1
    assert len(elements.saved) == 1
    assert len(chunks.saved) == 1
    assert len(links.saved) == 1
    assert links.saved[0].document_id == DOCUMENT_ID
    assert links.saved[0].chunk_id == result[0].chunk_id
    assert chunks.saved[result[0].chunk_id].element_id == elements.saved[0].element_id
    assert elements.saved[0].agent_id == AGENT_ID
    assert uow.committed
    assert not uow.rolled_back

    assert len(embeddings.saved) == 1
    assert embeddings.saved[0].chunk_id == result[0].chunk_id
    assert embeddings.saved[0].embedding_vector == [0.1, 0.2, 0.3]
    assert embeddings.saved[0].embedding_model_version == "test-embedding-model"
    assert embedding_provider.texts_embedded == ["Paragraph one.\n\nParagraph two."]


def test_persisted_element_uses_the_providers_classification():
    provider = FakeTextGenerationProvider(
        responses=['{"element_type": "claim", "label": "Key claim", "description": "The study finds X."}']
    )
    use_case, elements, *_ = _build_use_case(provider=provider)

    use_case.execute(document_id=DOCUMENT_ID)

    assert elements.saved[0].element_type.value == "claim"
    assert elements.saved[0].label == "Key claim"


def test_reprocessing_returns_existing_chunks_without_calling_the_provider_again():
    use_case, elements, chunks, links, uow, provider, embeddings, embedding_provider = _build_use_case()

    first = use_case.execute(document_id=DOCUMENT_ID)
    calls_after_first = provider.call_count
    embed_calls_after_first = embedding_provider.call_count
    second = use_case.execute(document_id=DOCUMENT_ID)

    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert provider.call_count == calls_after_first  # no new provider calls on reprocessing
    assert embedding_provider.call_count == embed_calls_after_first  # no new embedding calls either
    assert len(elements.saved) == 1  # no duplicate element created
    assert len(chunks.saved) == 1
    assert len(embeddings.saved) == 1


def test_a_provider_failure_persists_nothing_for_that_document():
    provider = FakeTextGenerationProvider(fail_after=0)
    use_case, elements, chunks, links, uow, _, embeddings, _ = _build_use_case(
        content_store=FakeContentStore({"ref-1": b"Paragraph one.\n\nParagraph two."}), provider=provider
    )

    with pytest.raises(RuntimeError):
        use_case.execute(document_id=DOCUMENT_ID)

    assert elements.saved == []
    assert chunks.saved == {}
    assert links.saved == []
    assert embeddings.saved == []
    assert not uow.committed


def test_a_malformed_provider_response_persists_nothing():
    provider = FakeTextGenerationProvider(responses=["not valid json"])
    use_case, elements, chunks, links, uow, _, embeddings, _ = _build_use_case(provider=provider)

    with pytest.raises(SemanticExtractionError):
        use_case.execute(document_id=DOCUMENT_ID)

    assert elements.saved == []
    assert chunks.saved == {}
    assert embeddings.saved == []
    assert not uow.committed


def test_an_embedding_failure_persists_nothing_for_that_document():
    embedding_provider = FakeEmbeddingProvider(fail=True)
    use_case, elements, chunks, links, uow, _, embeddings, _ = _build_use_case(embedding_provider=embedding_provider)

    with pytest.raises(RuntimeError):
        use_case.execute(document_id=DOCUMENT_ID)

    assert elements.saved == []
    assert chunks.saved == {}
    assert links.saved == []
    assert embeddings.saved == []
    assert not uow.committed


def test_document_not_found_raises():
    use_case, *_ = _build_use_case(documents=FakeDocumentRepository({}))
    with pytest.raises(ResearchDocumentNotFoundError):
        use_case.execute(document_id=999)


def test_unresolvable_agent_raises_agent_resolution_error():
    use_case, *_ = _build_use_case(projects=FakeProjectRepository({}))
    with pytest.raises(AgentResolutionError):
        use_case.execute(document_id=DOCUMENT_ID)


def test_multiple_chunks_each_get_their_own_element_and_evidence_link():
    long_content = ("A" * 600 + "\n\n" + "B" * 600).encode()
    use_case, elements, chunks, links, uow, provider, embeddings, _ = _build_use_case(
        content_store=FakeContentStore({"ref-1": long_content}),
        provider=FakeTextGenerationProvider(
            responses=[
                '{"element_type": "concept", "label": "First", "description": "d1"}',
                '{"element_type": "theme", "label": "Second", "description": "d2"}',
            ]
        ),
    )

    result = use_case.execute(document_id=DOCUMENT_ID)

    assert len(result) == 2
    assert len(elements.saved) == 2
    assert len(links.saved) == 2
    assert len(embeddings.saved) == 2
    assert all(link.document_id == DOCUMENT_ID for link in links.saved)
