from app.auth.hashing import hash_password, verify_password


def test_correct_password_verifies_true():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_wrong_password_verifies_false():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_hash_is_never_the_plaintext():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_hashing_the_same_password_twice_produces_different_hashes():
    """Bcrypt salts per call - confirms we aren't accidentally using a deterministic scheme."""
    first = hash_password("same password")
    second = hash_password("same password")
    assert first != second
    assert verify_password("same password", first) is True
    assert verify_password("same password", second) is True
