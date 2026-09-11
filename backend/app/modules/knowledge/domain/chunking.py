import re

from app.modules.knowledge.domain.entities import TextChunkCandidate
from app.modules.knowledge.domain.exceptions import EmptyExtractedTextError

DEFAULT_TARGET_CHUNK_SIZE = 1000
"""Characters, not tokens. An implementation-level default (no approved document specifies
one - Backend_Slice2_Implementation_Plan.md flags chunk size as an implementation choice,
not a product requirement): roughly 150-200 words, small enough to keep a chunk focused
(04_AI_Architecture.md §9.1: "chunks support focused retrieval"), large enough to avoid
fragmenting a typical academic paragraph. No overlap - overlap is a retrieval-quality tuning
knob appropriately deferred until real retrieval exists (ADR-005 Stage 7+), not a Stage 4
concern.
"""

_PARAGRAPH_BOUNDARY = re.compile(r"\n{2,}")


def chunk_text(
    normalized_text: str, *, document_id: int, target_chunk_size: int = DEFAULT_TARGET_CHUNK_SIZE
) -> list[TextChunkCandidate]:
    """Deterministic, paragraph-aware chunking: the same input always produces the same
    chunks, in source order, with no network dependency and no AI involvement.

    Algorithm: split on paragraph boundaries (a blank line); merge consecutive paragraphs
    into one chunk while the combined span stays within `target_chunk_size`; split a single
    paragraph that alone exceeds `target_chunk_size` at whitespace boundaries (never
    mid-word). Every chunk's `text` is an exact substring of `normalized_text` at
    (`start_offset`, `end_offset`) - never a reconstruction - so offsets are always exact and
    directly verifiable.
    """
    if not normalized_text.strip():
        raise EmptyExtractedTextError(document_id=document_id)

    pieces = _expand_long_spans(normalized_text, _paragraph_spans(normalized_text), target_chunk_size)
    return _merge_spans_into_chunks(normalized_text, pieces, document_id, target_chunk_size)


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    pos = 0
    for match in _PARAGRAPH_BOUNDARY.finditer(text):
        if match.start() > pos:
            spans.append((pos, match.start()))
        pos = match.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return [(start, end) for start, end in spans if text[start:end].strip()]


def _expand_long_spans(text: str, spans: list[tuple[int, int]], target_chunk_size: int) -> list[tuple[int, int]]:
    pieces: list[tuple[int, int]] = []
    for start, end in spans:
        if end - start > target_chunk_size:
            pieces.extend(_split_long_span(text, start, end, target_chunk_size))
        else:
            pieces.append((start, end))
    return pieces


def _split_long_span(text: str, start: int, end: int, target_chunk_size: int) -> list[tuple[int, int]]:
    pieces: list[tuple[int, int]] = []
    pos = start
    while end - pos > target_chunk_size:
        split_at = text.rfind(" ", pos, pos + target_chunk_size)
        if split_at <= pos:
            split_at = pos + target_chunk_size  # a single "word" longer than the target: hard split
        pieces.append((pos, split_at))
        pos = split_at
        while pos < end and text[pos] == " ":
            pos += 1
    if pos < end:
        pieces.append((pos, end))
    return pieces


def _merge_spans_into_chunks(
    text: str, pieces: list[tuple[int, int]], document_id: int, target_chunk_size: int
) -> list[TextChunkCandidate]:
    chunks: list[TextChunkCandidate] = []
    buffer_start: int | None = None
    buffer_end: int | None = None

    for start, end in pieces:
        if buffer_start is None:
            buffer_start, buffer_end = start, end
            continue
        if (end - buffer_start) <= target_chunk_size:
            buffer_end = end
        else:
            chunks.append(_make_chunk(text, document_id, len(chunks), buffer_start, buffer_end))
            buffer_start, buffer_end = start, end

    if buffer_start is not None:
        chunks.append(_make_chunk(text, document_id, len(chunks), buffer_start, buffer_end))

    return chunks


def _make_chunk(text: str, document_id: int, sequence_number: int, start: int, end: int) -> TextChunkCandidate:
    return TextChunkCandidate(
        document_id=document_id,
        sequence_number=sequence_number,
        text=text[start:end],
        start_offset=start,
        end_offset=end,
    )
