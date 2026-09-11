import pytest

from app.modules.knowledge.domain.chunking import chunk_text
from app.modules.knowledge.domain.exceptions import EmptyExtractedTextError


def test_short_document_produces_a_single_chunk():
    text = "A short research note."
    chunks = chunk_text(text, document_id=1, target_chunk_size=1000)

    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].document_id == 1
    assert chunks[0].sequence_number == 0
    assert chunks[0].start_offset == 0
    assert chunks[0].end_offset == len(text)


def test_chunk_text_is_always_an_exact_substring_of_the_input():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = chunk_text(text, document_id=1, target_chunk_size=1000)

    for chunk in chunks:
        assert text[chunk.start_offset : chunk.end_offset] == chunk.text


def test_multiple_paragraphs_merge_into_one_chunk_when_they_fit_the_target_size():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = chunk_text(text, document_id=1, target_chunk_size=1000)
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_document_requiring_multiple_chunks_splits_at_paragraph_boundaries():
    para_a = "A" * 600
    para_b = "B" * 600
    text = f"{para_a}\n\n{para_b}"

    chunks = chunk_text(text, document_id=1, target_chunk_size=1000)

    assert len(chunks) == 2
    assert chunks[0].text == para_a
    assert chunks[1].text == para_b
    assert chunks[0].sequence_number == 0
    assert chunks[1].sequence_number == 1


def test_exact_boundary_document_does_not_produce_an_extra_empty_chunk():
    text = "X" * 1000
    chunks = chunk_text(text, document_id=1, target_chunk_size=1000)
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_a_paragraph_longer_than_the_target_size_is_split_at_whitespace_not_mid_word():
    long_paragraph = " ".join(["word"] * 300)  # far longer than target_chunk_size=1000
    chunks = chunk_text(long_paragraph, document_id=1, target_chunk_size=1000)

    assert len(chunks) > 1
    for chunk in chunks:
        assert not chunk.text.startswith(" ")
        assert not chunk.text.endswith(" ")
        # every chunk boundary lands on a whole word, never inside "word"
        for token in chunk.text.split(" "):
            assert token == "" or token == "word"


def test_a_single_word_longer_than_target_size_is_hard_split_without_crashing():
    huge_word = "x" * 2500
    chunks = chunk_text(huge_word, document_id=1, target_chunk_size=1000)

    assert len(chunks) == 3
    assert "".join(c.text for c in chunks) == huge_word


def test_empty_input_raises_empty_extracted_text_error():
    with pytest.raises(EmptyExtractedTextError):
        chunk_text("", document_id=1)


def test_whitespace_only_input_raises_empty_extracted_text_error():
    with pytest.raises(EmptyExtractedTextError):
        chunk_text("   \n\n   ", document_id=1)


def test_chunking_is_deterministic_across_repeated_calls():
    text = "Para one.\n\n" + ("word " * 400) + "\n\nPara three."
    first = chunk_text(text, document_id=1, target_chunk_size=500)
    second = chunk_text(text, document_id=1, target_chunk_size=500)

    assert [c.text for c in first] == [c.text for c in second]
    assert [(c.start_offset, c.end_offset) for c in first] == [(c.start_offset, c.end_offset) for c in second]


def test_chunk_sequence_numbers_are_ordered_and_match_source_order():
    text = "\n\n".join(f"Paragraph number {i}." + ("z" * 200) for i in range(5))
    chunks = chunk_text(text, document_id=1, target_chunk_size=250)

    sequence_numbers = [c.sequence_number for c in chunks]
    assert sequence_numbers == list(range(len(chunks)))
    offsets = [c.start_offset for c in chunks]
    assert offsets == sorted(offsets)


def test_all_chunks_carry_the_given_document_id():
    text = "Para one.\n\nPara two."
    chunks = chunk_text(text, document_id=99, target_chunk_size=5)
    assert all(c.document_id == 99 for c in chunks)
