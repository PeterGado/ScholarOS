from app.auth.hashing import hash_password, looks_like_bcrypt_hash


def test_a_real_generated_hash_is_accepted():
    assert looks_like_bcrypt_hash(hash_password("s3cret")) is True


def test_an_empty_string_is_rejected():
    assert looks_like_bcrypt_hash("") is False


def test_plain_garbage_is_rejected():
    assert looks_like_bcrypt_hash("not-a-bcrypt-hash") is False


def test_a_sha256_hex_digest_is_rejected():
    """A common mistake: pasting a sha256 hash where a bcrypt hash belongs."""
    assert looks_like_bcrypt_hash("a" * 64) is False


def test_a_truncated_bcrypt_hash_is_rejected():
    real_hash = hash_password("s3cret")
    assert looks_like_bcrypt_hash(real_hash[:-5]) is False
