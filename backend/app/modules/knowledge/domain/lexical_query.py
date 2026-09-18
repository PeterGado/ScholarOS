"""Builds a safe SQLite FTS5 MATCH expression from a raw user query string (ADR-005 Decision
1's lexical branch). FTS5's query syntax has its own operators (AND/OR/NOT, quoting, column
filters, prefix `*`) - passing a raw user string straight into MATCH risks a syntax error on
stray punctuation or an unintended operator interpretation, not a SQL-injection risk (FTS5
MATCH text is not SQL), but a real correctness/availability one (a malformed MATCH expression
raises `OperationalError`, which would otherwise take lexical search down for the whole hybrid
query, semantic branch included, over something as ordinary as an unmatched quote in the
question). Framework-free: pure string processing, no database dependency.
"""

import re

_TOKEN_PATTERN = re.compile(r"\w+")


def build_fts_match_query(text: str) -> str:
    """Extracts word tokens and OR-joins them as quoted phrase terms (e.g. `"coastal" OR
    "erosion"`), each token treated as a literal string, not lexical query syntax. OR (not AND)
    matches ADR-005's rationale for the lexical branch: precision on exact terms, not a
    requirement that every query word appear together - a natural-language question routinely
    contains words no single chunk will all share, and RRF fusion is what combines this with
    the semantic branch's own recall, not the lexical branch alone. Returns "" for a query with
    no word characters at all (the caller must treat that as "no lexical candidates," not run
    an empty MATCH).
    """
    tokens = _TOKEN_PATTERN.findall(text)
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens)


def build_postgres_tsquery(text: str) -> str:
    """Postgres counterpart to `build_fts_match_query` - same tokenization, same OR semantics
    (`|`, Postgres tsquery's OR operator), for `to_tsquery()`. Deliberately not
    `plainto_tsquery()`/`websearch_to_tsquery()`: both default to ANDing every term together,
    which would make the lexical branch's behavior diverge from the SQLite implementation for
    the same query. No quoting needed (unlike `build_fts_match_query`'s FTS5 tokens): the
    `\\w+` token pattern already excludes every character with tsquery operator meaning
    (`&`, `|`, `!`, `(`, `)`, `:`, whitespace), so a token can never be parsed as anything but a
    literal lexeme.
    """
    tokens = _TOKEN_PATTERN.findall(text)
    if not tokens:
        return ""
    return " | ".join(tokens)
