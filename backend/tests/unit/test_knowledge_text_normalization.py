from app.modules.knowledge.domain.text_normalization import normalize_text


def test_normalizes_crlf_line_endings_to_lf():
    assert normalize_text("line one\r\nline two\r\n") == "line one\nline two"


def test_normalizes_bare_cr_line_endings_to_lf():
    assert normalize_text("line one\rline two") == "line one\nline two"


def test_strips_trailing_whitespace_per_line():
    assert normalize_text("line one   \nline two\t\n") == "line one\nline two"


def test_preserves_leading_whitespace_for_indentation():
    """Leading whitespace can be meaningful (list items, quotations) - never stripped."""
    text = "Heading\n\n  - item one\n  - item two"
    assert normalize_text(text) == "Heading\n\n  - item one\n  - item two"


def test_collapses_a_run_of_three_or_more_newlines_to_exactly_two():
    assert normalize_text("paragraph one\n\n\n\nparagraph two") == "paragraph one\n\nparagraph two"


def test_leaves_a_single_blank_line_between_paragraphs_untouched():
    assert normalize_text("paragraph one\n\nparagraph two") == "paragraph one\n\nparagraph two"


def test_leaves_a_single_line_break_within_a_paragraph_untouched():
    """A single newline is a soft-wrapped line within one paragraph, not a boundary."""
    assert normalize_text("line one\nline two") == "line one\nline two"


def test_strips_leading_and_trailing_blank_lines_only():
    assert normalize_text("\n\n\ncontent\n\n\n") == "content"


def test_preserves_meaningful_content_like_headings_and_references():
    text = "1. Introduction\n\nThis study examines X [1].\n\nReferences\n\n[1] Author, Year."
    assert normalize_text(text) == text


def test_normalization_is_deterministic():
    text = "Some\r\ntext\n\n\n\nwith   trailing   \nvariation.\r"
    assert normalize_text(text) == normalize_text(text)


def test_empty_string_normalizes_to_empty_string():
    assert normalize_text("") == ""


def test_whitespace_only_input_normalizes_to_empty_string():
    assert normalize_text("   \n\n\t\n   ") == ""
