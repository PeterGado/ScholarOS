import math

from app.modules.knowledge.domain.entities import ChunkEmbedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure, deterministic, no I/O - testable without network access (ADR-005 §AI
    Engineering Implications). Returns 0.0 for a zero-magnitude vector rather than dividing
    by zero - a defensive floor, not a claim that the vectors are actually similar.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")

    dot_product = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))
    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)


def rank_by_similarity(query_vector: list[float], candidates: list[ChunkEmbedding]) -> list[tuple[int, float]]:
    """Brute-force cosine ranking (ADR-004 Decision 3's "in-process vector index",
    Backend_Slice2_Implementation_Plan.md §6) - legitimate at MVP corpus scale, never a
    source of truth (rebuildable from the structured core). Returns (chunk_id, score) pairs,
    descending by score; ties broken by chunk_id for deterministic ordering.
    """
    scored = [(candidate.chunk_id, cosine_similarity(query_vector, candidate.embedding_vector)) for candidate in candidates]
    return sorted(scored, key=lambda pair: (-pair[1], pair[0]))
