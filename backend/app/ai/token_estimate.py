def estimate_tokens(text: str) -> int:
    """Rough chars-per-token heuristic (~4 chars/token, a common approximation) - not exact
    tokenization. Used only to bound the AI usage cap (app.ai.usage_guard), where being roughly
    right at zero extra API cost matters more than exact per-provider tokenization, which would
    require capturing usage_metadata from every provider response (a much larger change - see
    app/ai/usage_guard.py's own docstring for why that tradeoff wasn't taken).
    """
    return max(1, len(text) // 4)
