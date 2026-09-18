"""Reciprocal Rank Fusion (ADR-005 Decision 2): merges the lexical and semantic rankings into
one candidate set. Rank-based, not score-based, so it never needs to normalize BM25 scores
against cosine similarities - two systems whose raw scores are not comparable, exactly the
problem RRF is chosen to avoid (ADR-005's own rationale).

Framework-free, mirrors `vector_similarity.rank_by_similarity`'s own pattern: pure function
over already-ranked id lists, no database or provider dependency.
"""

DEFAULT_RRF_K = 60
"""The standard RRF damping constant (e.g. Elasticsearch's own default) - dampens the
contribution of low-ranked items without needing empirical tuning, matching ADR-005's framing
of RRF as "parameter-light." Per-retrieval-context weight tuning is explicitly deferred
(ADR-005 Future Considerations #3) until there is more than one real retrieval context to tune
against - today `SearchKnowledgeUseCase` is the only caller.
"""


def reciprocal_rank_fusion(
    lexical_ranking: list[int],
    semantic_ranking: list[int],
    *,
    k: int = DEFAULT_RRF_K,
) -> list[tuple[int, float]]:
    """Fuses two rankings (each a list of chunk_id, best first) into one, by summing
    1/(k + rank) for every ranking a chunk_id appears in (rank is 1-based). A chunk_id present
    in only one ranking still contributes - hybrid retrieval's whole point is that lexical-only
    and semantic-only matches both surface, not just their intersection.

    Returns (chunk_id, fused_score) pairs, descending by score, ties broken by chunk_id for
    deterministic ordering (mirrors `rank_by_similarity`'s own tie-break).
    """
    scores: dict[int, float] = {}
    for ranking in (lexical_ranking, semantic_ranking):
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
