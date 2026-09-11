import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.knowledge.application.retrieval import MAX_TOP_K, SearchKnowledgeUseCase, SearchResultEvidence
from app.modules.knowledge.domain.entities import ChunkEmbedding, ChunkEvidenceLink, KnowledgeChunk
from app.modules.knowledge.domain.repositories import (
    ChunkEvidenceLinkRepository,
    KnowledgeChunkEmbeddingRepository,
    KnowledgeChunkRepository,
)

OWNER_USER_ID = 1
OWNER_AGENT_ID = 1
OTHER_USER_ID = 2
OTHER_AGENT_ID = 2


class FakeAgentRepository(AgentRepository):
    def __init__(self, agents=None):
        self._agents = agents if agents is not None else {OWNER_AGENT_ID: Agent(agent_id=OWNER_AGENT_ID, user_id=OWNER_USER_ID)}

    def get_by_user_id(self, user_id):
        return next((a for a in self._agents.values() if a.user_id == user_id), None)

    def get_by_id(self, agent_id):
        return self._agents.get(agent_id)

    def add(self, agent):
        raise NotImplementedError


class FakeEmbeddingProvider:
    def __init__(self, vector=None):
        self.vector = vector or [1.0, 0.0]
        self.texts_embedded: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts_embedded.append(text)
        return self.vector


class FakeEmbeddingRepository(KnowledgeChunkEmbeddingRepository):
    def __init__(self, embeddings_by_agent: dict[int, list[ChunkEmbedding]] | None = None):
        self._embeddings_by_agent = embeddings_by_agent or {}

    def add(self, embedding):
        raise NotImplementedError

    def list_by_agent_id(self, agent_id):
        return self._embeddings_by_agent.get(agent_id, [])


class FakeChunkRepository(KnowledgeChunkRepository):
    def __init__(self, chunks: dict[int, KnowledgeChunk] | None = None):
        self._chunks = chunks or {}

    def add(self, chunk):
        raise NotImplementedError

    def get_by_id(self, chunk_id):
        return self._chunks.get(chunk_id)


class FakeEvidenceLinkRepository(ChunkEvidenceLinkRepository):
    def __init__(self, links_by_chunk: dict[int, list[ChunkEvidenceLink]] | None = None):
        self._links_by_chunk = links_by_chunk or {}

    def add(self, link):
        raise NotImplementedError

    def exists_for_document(self, document_id):
        raise NotImplementedError

    def list_by_document_id(self, document_id):
        raise NotImplementedError

    def list_by_chunk_id(self, chunk_id):
        return self._links_by_chunk.get(chunk_id, [])


class FakeDocumentRepository(DocumentRepository):
    def __init__(self, documents: dict[int, ResearchDocument] | None = None):
        self._documents = documents or {}

    def get_by_id(self, document_id):
        return self._documents.get(document_id)

    def list_by_project_id(self, project_id):
        raise NotImplementedError

    def add(self, document):
        raise NotImplementedError

    def update_processing_status(self, document_id, status, *, processed_at=None):
        raise NotImplementedError


def _chunk(chunk_id, agent_id=OWNER_AGENT_ID, content="chunk content") -> KnowledgeChunk:
    return KnowledgeChunk(chunk_id=chunk_id, agent_id=agent_id, element_id=1, content=content, summary="a summary")


def _embedding(chunk_id, vector) -> ChunkEmbedding:
    return ChunkEmbedding(chunk_id=chunk_id, embedding_vector=vector, embedding_model_version="test")


def _build_use_case(
    *,
    agents=None,
    embedding_provider=None,
    embeddings=None,
    chunks=None,
    evidence_links=None,
    documents=None,
):
    return SearchKnowledgeUseCase(
        agents or FakeAgentRepository(),
        embedding_provider or FakeEmbeddingProvider(),
        embeddings or FakeEmbeddingRepository(),
        chunks or FakeChunkRepository(),
        evidence_links or FakeEvidenceLinkRepository(),
        documents or FakeDocumentRepository(),
    )


def test_user_with_no_agent_raises_agent_not_found():
    use_case = _build_use_case(agents=FakeAgentRepository({}))
    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=OWNER_USER_ID, query="anything")


def test_agent_with_no_knowledge_returns_empty_results_not_an_error():
    use_case = _build_use_case(embeddings=FakeEmbeddingRepository({}))
    results = use_case.execute(user_id=OWNER_USER_ID, query="anything")
    assert results == []


def test_returns_ranked_results_with_provenance():
    embeddings = FakeEmbeddingRepository({OWNER_AGENT_ID: [_embedding(1, [1.0, 0.0]), _embedding(2, [0.0, 1.0])]})
    chunks = FakeChunkRepository({1: _chunk(1, content="matching chunk"), 2: _chunk(2, content="unrelated chunk")})
    evidence_links = FakeEvidenceLinkRepository(
        {1: [ChunkEvidenceLink(chunk_id=1, document_id=42)], 2: [ChunkEvidenceLink(chunk_id=2, document_id=43)]}
    )
    documents = FakeDocumentRepository(
        {
            42: ResearchDocument(document_id=42, project_id=1, title="Doc A", format="txt", content_reference="r1"),
            43: ResearchDocument(document_id=43, project_id=1, title="Doc B", format="txt", content_reference="r2"),
        }
    )
    use_case = _build_use_case(
        embedding_provider=FakeEmbeddingProvider(vector=[1.0, 0.0]),
        embeddings=embeddings,
        chunks=chunks,
        evidence_links=evidence_links,
        documents=documents,
    )

    results = use_case.execute(user_id=OWNER_USER_ID, query="find the matching chunk")

    assert len(results) == 2
    assert results[0].chunk_id == 1  # exact match ranks first
    assert results[0].content == "matching chunk"
    assert results[0].score > results[1].score
    assert results[0].evidence == [SearchResultEvidence(document_id=42, document_title="Doc A")]


def test_no_raw_embedding_vector_appears_anywhere_on_the_result():
    embeddings = FakeEmbeddingRepository({OWNER_AGENT_ID: [_embedding(1, [1.0, 0.0])]})
    chunks = FakeChunkRepository({1: _chunk(1)})
    use_case = _build_use_case(embeddings=embeddings, chunks=chunks)

    results = use_case.execute(user_id=OWNER_USER_ID, query="q")

    result_fields = vars(results[0])
    assert "embedding_vector" not in result_fields
    assert "vector" not in result_fields


def test_top_k_limits_the_number_of_results():
    embeddings = FakeEmbeddingRepository(
        {OWNER_AGENT_ID: [_embedding(i, [1.0, float(i)]) for i in range(5)]}
    )
    chunks = FakeChunkRepository({i: _chunk(i) for i in range(5)})
    use_case = _build_use_case(embeddings=embeddings, chunks=chunks)

    results = use_case.execute(user_id=OWNER_USER_ID, query="q", top_k=2)

    assert len(results) == 2


def test_top_k_larger_than_available_candidates_returns_all_available():
    embeddings = FakeEmbeddingRepository({OWNER_AGENT_ID: [_embedding(1, [1.0, 0.0])]})
    chunks = FakeChunkRepository({1: _chunk(1)})
    use_case = _build_use_case(embeddings=embeddings, chunks=chunks)

    results = use_case.execute(user_id=OWNER_USER_ID, query="q", top_k=50)

    assert len(results) == 1


def test_top_k_is_defensively_clamped_to_max_even_if_a_caller_requests_more():
    embeddings = FakeEmbeddingRepository(
        {OWNER_AGENT_ID: [_embedding(i, [1.0, float(i)]) for i in range(MAX_TOP_K + 10)]}
    )
    chunks = FakeChunkRepository({i: _chunk(i) for i in range(MAX_TOP_K + 10)})
    use_case = _build_use_case(embeddings=embeddings, chunks=chunks)

    results = use_case.execute(user_id=OWNER_USER_ID, query="q", top_k=MAX_TOP_K + 10)

    assert len(results) == MAX_TOP_K


def test_a_chunk_with_no_evidence_link_still_returns_with_empty_evidence():
    """Defensive: should never happen given Stage 5's own atomicity, but must not crash."""
    embeddings = FakeEmbeddingRepository({OWNER_AGENT_ID: [_embedding(1, [1.0, 0.0])]})
    chunks = FakeChunkRepository({1: _chunk(1)})
    use_case = _build_use_case(embeddings=embeddings, chunks=chunks, evidence_links=FakeEvidenceLinkRepository({}))

    results = use_case.execute(user_id=OWNER_USER_ID, query="q")

    assert results[0].evidence == []


# --- Agent isolation (the explicit authorization requirement) -----------------------------


def test_agent_a_never_receives_agent_bs_knowledge():
    agents = FakeAgentRepository(
        {OWNER_AGENT_ID: Agent(agent_id=OWNER_AGENT_ID, user_id=OWNER_USER_ID), OTHER_AGENT_ID: Agent(agent_id=OTHER_AGENT_ID, user_id=OTHER_USER_ID)}
    )
    embeddings = FakeEmbeddingRepository(
        {
            OWNER_AGENT_ID: [_embedding(1, [1.0, 0.0])],
            OTHER_AGENT_ID: [_embedding(2, [1.0, 0.0])],
        }
    )
    chunks = FakeChunkRepository(
        {1: _chunk(1, agent_id=OWNER_AGENT_ID, content="Agent A's secret"), 2: _chunk(2, agent_id=OTHER_AGENT_ID, content="Agent B's secret")}
    )
    use_case = _build_use_case(agents=agents, embeddings=embeddings, chunks=chunks)

    results_for_a = use_case.execute(user_id=OWNER_USER_ID, query="secret")

    assert len(results_for_a) == 1
    assert results_for_a[0].chunk_id == 1
    assert results_for_a[0].content == "Agent A's secret"
    assert all(r.chunk_id != 2 for r in results_for_a)
