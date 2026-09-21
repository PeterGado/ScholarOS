from app.ai.token_estimate import estimate_tokens


def test_empty_string_estimates_at_least_one_token():
    assert estimate_tokens("") == 1


def test_estimate_is_roughly_length_over_four():
    assert estimate_tokens("x" * 400) == 100


def test_a_short_string_still_estimates_at_least_one_token():
    assert estimate_tokens("hi") == 1
