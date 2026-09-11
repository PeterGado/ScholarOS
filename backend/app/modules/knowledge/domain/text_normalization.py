import re

_BLANK_LINE_RUN = re.compile(r"\n{3,}")


def normalize_text(raw_text: str) -> str:
    """Deterministic normalization - the same input always produces the same output.

    Does exactly three things, and nothing more, per Stage 4's explicit instruction not to
    aggressively clean the source (academic documents carry meaningful headings, lists,
    quotations, and section boundaries):

    1. Unifies line endings (CRLF/CR -> LF) - a physical-encoding detail, never meaningful.
    2. Strips trailing whitespace from each line - trailing whitespace is never meaningful.
    3. Collapses a run of 2+ blank lines down to exactly one blank line - preserves the fact
       that a paragraph/section boundary existed without treating "3 blank lines" as
       meaningfully different from "1 blank line".

    Leading whitespace (list/quote indentation), single line breaks (soft-wrapped lines
    within a paragraph), and all other content are left untouched.
    """
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = _BLANK_LINE_RUN.sub("\n\n", text)
    return text.strip("\n")
