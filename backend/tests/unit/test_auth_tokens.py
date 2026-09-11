from app.auth.tokens import generate_session_token, hash_session_token


def test_two_generated_tokens_differ():
    assert generate_session_token() != generate_session_token()


def test_generated_token_has_meaningful_length():
    token = generate_session_token()
    assert len(token) >= 32


def test_hashing_is_deterministic():
    token = generate_session_token()
    assert hash_session_token(token) == hash_session_token(token)


def test_different_tokens_hash_differently():
    first = generate_session_token()
    second = generate_session_token()
    assert hash_session_token(first) != hash_session_token(second)


def test_hash_is_never_the_raw_token():
    token = generate_session_token()
    assert hash_session_token(token) != token
