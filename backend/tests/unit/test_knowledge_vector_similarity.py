import math

import pytest

from app.modules.knowledge.domain.entities import ChunkEmbedding
from app.modules.knowledge.domain.vector_similarity import cosine_similarity, rank_by_similarity


def test_identical_vectors_have_similarity_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_orthogonal_vectors_have_similarity_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_opposite_vectors_have_similarity_negative_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_similarity_is_scale_invariant():
    a = [1.0, 2.0, 3.0]
    b = [2.0, 4.0, 6.0]  # same direction, different magnitude
    assert cosine_similarity(a, b) == pytest.approx(1.0)


def test_zero_magnitude_vector_returns_zero_not_a_division_error():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 1.0], [0.0, 0.0]) == 0.0


def test_dimension_mismatch_raises_value_error():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_similarity_matches_hand_computed_value():
    a = [1.0, 0.0]
    b = [1.0, 1.0]
    expected = 1.0 / math.sqrt(2)
    assert cosine_similarity(a, b) == pytest.approx(expected)


# --- rank_by_similarity ------------------------------------------------------------------


def _embedding(chunk_id: int, vector: list[float]) -> ChunkEmbedding:
    return ChunkEmbedding(chunk_id=chunk_id, embedding_vector=vector, embedding_model_version="test")


def test_ranks_candidates_by_descending_similarity():
    query = [1.0, 0.0]
    candidates = [
        _embedding(1, [0.0, 1.0]),  # orthogonal: 0.0
        _embedding(2, [1.0, 0.0]),  # identical: 1.0
        _embedding(3, [1.0, 1.0]),  # partial match
    ]

    ranked = rank_by_similarity(query, candidates)

    assert [chunk_id for chunk_id, _ in ranked] == [2, 3, 1]
    assert ranked[0][1] == pytest.approx(1.0)


def test_ties_are_broken_by_chunk_id_for_deterministic_ordering():
    query = [1.0, 0.0]
    candidates = [_embedding(5, [1.0, 0.0]), _embedding(2, [1.0, 0.0])]

    ranked = rank_by_similarity(query, candidates)

    assert [chunk_id for chunk_id, _ in ranked] == [2, 5]


def test_empty_candidate_list_returns_empty_ranking():
    assert rank_by_similarity([1.0, 0.0], []) == []


def test_ranking_is_deterministic_across_repeated_calls():
    query = [0.3, 0.7, 0.1]
    candidates = [_embedding(1, [0.2, 0.6, 0.1]), _embedding(2, [0.9, 0.1, 0.0]), _embedding(3, [0.3, 0.7, 0.1])]

    first = rank_by_similarity(query, candidates)
    second = rank_by_similarity(query, candidates)

    assert first == second
