from dataclasses import dataclass, field

from app.ai.providers.base import EmbeddingProvider
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.knowledge.domain.repositories import (
    ChunkEvidenceLinkRepository,
    KnowledgeChunkEmbeddingRepository,
    KnowledgeChunkRepository,
)
from app.modules.knowledge.domain.vector_similarity import rank_by_similarity

DEFAULT_TOP_K = 10
MAX_TOP_K = 50


@dataclass(frozen=True)
class SearchResultEvidence:
    document_id: int
    document_title: str


@dataclass(frozen=True)
class SearchResult:
    chunk_id: int
    content: str
    summary: str | None
    score: float
    evidence: list[SearchResultEvidence] = field(default_factory=list)


class SearchKnowledgeUseCase:
    """Stage 8: vector search over the caller's own Knowledge Chunks (04_AI_Architecture.md
    §16), realized at vector-only fidelity - lexical search and RRF fusion (ADR-005 Decision
    1) are not implemented yet. This is a flagged, deliberate partial realization of ADR-005
    for the smallest testable retrieval slice, not a silent deviation - see Stage 8's
    completion report.

    Reuses the existing Provider Abstraction (`EmbeddingProvider`, unchanged since Stage 3)
    and the existing deterministic `rank_by_similarity` (unchanged since Stage 7) - no new AI
    abstraction, no new ranking algorithm.

    Agent-scoped by construction: resolves the caller's own Agent from `user_id` and never
    accepts an agent_id from the caller - the same ownership principle Stage 6 already
    established for document upload. An Agent that exists but owns no knowledge yet returns
    an empty result list (200); a user with no Agent at all is a different condition and
    raises `AgentNotFoundForUserError` (404) - the two must not be conflated.
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        embedding_provider: EmbeddingProvider,
        embedding_repository: KnowledgeChunkEmbeddingRepository,
        chunk_repository: KnowledgeChunkRepository,
        evidence_link_repository: ChunkEvidenceLinkRepository,
        document_repository: DocumentRepository,
    ) -> None:
        self._agents = agent_repository
        self._embedding_provider = embedding_provider
        self._embeddings = embedding_repository
        self._chunks = chunk_repository
        self._evidence_links = evidence_link_repository
        self._documents = document_repository

    def execute(self, *, user_id: int, query: str, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        candidates = self._embeddings.list_by_agent_id(agent.agent_id)
        if not candidates:
            return []

        query_vector = self._embedding_provider.embed(query)
        bounded_top_k = max(1, min(top_k, MAX_TOP_K))
        ranked = rank_by_similarity(query_vector, candidates)[:bounded_top_k]

        return [self._to_result(chunk_id, score) for chunk_id, score in ranked]

    def _to_result(self, chunk_id: int, score: float) -> SearchResult:
        chunk = self._chunks.get_by_id(chunk_id)
        evidence = []
        for link in self._evidence_links.list_by_chunk_id(chunk_id):
            document = self._documents.get_by_id(link.document_id)
            if document is not None:
                evidence.append(SearchResultEvidence(document_id=document.document_id, document_title=document.title))
        return SearchResult(chunk_id=chunk_id, content=chunk.content, summary=chunk.summary, score=score, evidence=evidence)
