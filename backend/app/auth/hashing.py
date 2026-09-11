import re

import bcrypt

_BCRYPT_PATTERN = re.compile(r"^\$2[abxy]\$\d{2}\$[./A-Za-z0-9]{53}$")


def hash_password(plain_password: str) -> str:
    """Bcrypt-hash a password for storage (ADR-010 Decision item 3). Note: bcrypt only
    considers the first 72 bytes of its input - an established, accepted property of the
    algorithm itself, not something this function works around.
    """
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Timing-safe comparison via bcrypt's own check - never compare hashes with `==`."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def looks_like_bcrypt_hash(value: str) -> bool:
    """Format check only (prefix, cost factor, 60-char total length) - used to validate
    configuration (AUTH_PASSWORD_HASH) before ever trusting it, not to verify a password.
    """
    return bool(_BCRYPT_PATTERN.match(value))
