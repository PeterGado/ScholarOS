from collections import defaultdict
from dataclasses import dataclass, field

from app.ai.providers.base import EmbeddingProvider
from app.ai.token_estimate import estimate_tokens
from app.ai.usage_guard import AiUsageGuard
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.knowledge.domain.repositories import (
    ChunkEvidenceLinkRepository,
    KnowledgeChunkEmbeddingRepository,
    KnowledgeChunkRepository,
    LexicalSearchRepository,
)
from app.modules.knowledge.domain.retrieval_fusion import reciprocal_rank_fusion
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
    """ADR-005 Decision 1: hybrid retrieval over the caller's own Knowledge Chunks
    (04_AI_Architecture.md §16) - semantic (vector) search fused with lexical (BM25-style, via
    SQLite FTS5) search by Reciprocal Rank Fusion (ADR-005 Decision 2). Realized 2026-09-18,
    closing the "vector-only" gap this docstring previously flagged since Stage 8 (see the
    Risks table in `docs/Project_Status.md`).

    Reuses the existing Provider Abstraction (`EmbeddingProvider`, unchanged since Stage 3),
    the existing deterministic `rank_by_similarity` (unchanged since Stage 7), and the new,
    equally deterministic `reciprocal_rank_fusion` - no reranking (ADR-005 Decision 4,
    deliberately deferred), no per-retrieval-context fusion-weight configuration (ADR-005
    Future Considerations #3 - this is still the only retrieval context that exists).

    Agent-scoped by construction on both branches: resolves the caller's own Agent from
    `user_id` and never accepts an agent_id from the caller - the same ownership principle
    Stage 6 already established for document upload. An Agent that exists but owns no
    knowledge yet returns an empty result list (200); a user with no Agent at all is a
    different condition and raises `AgentNotFoundForUserError` (404) - the two must not be
    conflated.
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        embedding_provider: EmbeddingProvider,
        embedding_repository: KnowledgeChunkEmbeddingRepository,
        chunk_repository: KnowledgeChunkRepository,
        evidence_link_repository: ChunkEvidenceLinkRepository,
        document_repository: DocumentRepository,
        lexical_search_repository: LexicalSearchRepository,
        ai_usage_guard: AiUsageGuard,
    ) -> None:
        self._agents = agent_repository
        self._embedding_provider = embedding_provider
        self._embeddings = embedding_repository
        self._chunks = chunk_repository
        self._evidence_links = evidence_link_repository
        self._documents = document_repository
        self._lexical_search = lexical_search_repository
        self._ai_usage_guard = ai_usage_guard

    def execute(self, *, user_id: int, query: str, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        bounded_top_k = max(1, min(top_k, MAX_TOP_K))

        # The semantic branch's own candidate set doubles as its full ranking (an MVP-scale
        # brute-force scan, ADR-004 Decision 3) - skipped entirely (no provider call) when the
        # Agent has no embeddings yet, the same short-circuit this use case always had. Lexical
        # search runs regardless: a chunk can be found by exact term even before/without
        # embeddings existing for it, and RRF naturally folds a single-branch match in rather
        # than requiring both branches to agree (see reciprocal_rank_fusion's own docstring).
        semantic_ranking: list[int] = []
        candidates = self._embeddings.list_by_agent_id(agent.agent_id)
        if candidates:
            # AI usage cap (2026-09-21 security pass): checked only on this branch - when there
            # are no embeddings yet, no provider call happens at all (the short-circuit above),
            # so charging usage unconditionally would bill searches that never actually cost
            # anything.
            self._ai_usage_guard.check_and_record(user_id=user_id, estimated_tokens=estimate_tokens(query))
            query_vector = self._embedding_provider.embed(query)
            semantic_ranking = [chunk_id for chunk_id, _ in rank_by_similarity(query_vector, candidates)]

        lexical_ranking = self._lexical_search.search(agent_id=agent.agent_id, query=query, limit=MAX_TOP_K)

        if not semantic_ranking and not lexical_ranking:
            return []

        fused = reciprocal_rank_fusion(lexical_ranking, semantic_ranking)[:bounded_top_k]
        return self._to_results(fused)

    def _to_results(self, fused: list[tuple[int, float]]) -> list[SearchResult]:
        """Batched (2026-09-23, real-traffic audit): the original version called `get_by_id`/
        `list_by_chunk_id`/`get_by_id` once PER result - up to ~3 queries per chunk, 30-50+
        total for a full top_k=10 result set, paid on every search call and therefore on every
        chat reply (SendChatMessageUseCase calls this use case directly). Fixed to a flat 3
        queries total regardless of top_k: one for every chunk, one for every evidence link
        across the whole set, one for every document those links reference - assembled into
        results in Python instead of round-tripping the database per result.
        """
        chunk_ids = [chunk_id for chunk_id, _ in fused]
        if not chunk_ids:
            return []

        chunks_by_id = {chunk.chunk_id: chunk for chunk in self._chunks.get_by_ids(chunk_ids)}

        links = self._evidence_links.list_by_chunk_ids(chunk_ids)
        links_by_chunk_id: dict[int, list] = defaultdict(list)
        for link in links:
            links_by_chunk_id[link.chunk_id].append(link)

        document_ids = list({link.document_id for link in links})
        documents_by_id = {document.document_id: document for document in self._documents.get_by_ids(document_ids)}

        results = []
        for chunk_id, score in fused:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                # Defensive: should never happen given Stage 5's own atomicity, but must not
                # crash - the same guarantee the pre-batching version gave implicitly via
                # get_by_id returning None only ever being dereferenced by evidence lookups,
                # never chunk.content itself. Kept explicit here since it's now a real branch.
                continue
            evidence = [
                SearchResultEvidence(document_id=document.document_id, document_title=document.title)
                for link in links_by_chunk_id.get(chunk_id, [])
                if (document := documents_by_id.get(link.document_id)) is not None
            ]
            results.append(
                SearchResult(chunk_id=chunk_id, content=chunk.content, summary=chunk.summary, score=score, evidence=evidence)
            )
        return results
