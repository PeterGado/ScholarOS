import hashlib
import secrets


def generate_session_token() -> str:
    """A cryptographically random opaque session token (256 bits via the stdlib CSPRNG,
    ADR-010 Decision item 2) - never `uuid4`, never `random`.
    """
    return secrets.token_urlsafe(32)


def hash_session_token(raw_token: str) -> str:
    """SHA-256 of the raw token, for at-rest storage and lookup. Deliberately a fast,
    deterministic hash - not bcrypt: a session token already carries full entropy (unlike a
    human password), and a deterministic hash allows an indexed lookup by value, which a
    bcrypt hash (unique-salted per call) cannot support. See the Stage 1 plan §6 for the full
    reasoning; flagged there for confirmation as a physical-realization detail, not a new ADR.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
