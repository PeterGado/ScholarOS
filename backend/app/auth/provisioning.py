from sqlalchemy.orm import Session

from app.auth.exceptions import InvalidAuthConfigurationError
from app.auth.hashing import looks_like_bcrypt_hash
from app.database.shared_models import User


def sync_configured_user(db: Session, *, username: str | None, password_hash: str | None) -> None:
    """Provision the one pre-provisioned owner account from configuration (ADR-010 Decision
    item 1: "synced into the User table on every application startup [...] configuration is
    the source of truth, the database row is a cache of it"). Create-if-missing,
    update-if-changed.

    Looks the row up by the *configured* username specifically, rather than assuming it is the
    only User row in the table (2026-09-19 production security pass: this used to raise
    whenever more than one User row existed at all, which crash-looped the real deployed app
    the moment ADR-011's self-service registration produced its first second account - the
    exact, desired outcome of opening the app to friend-testing). Any other row - a
    self-registered account, or one left behind by a since-changed AUTH_USERNAME - is left
    untouched; this function only ever creates or updates the one row matching `username`.

    A no-op if neither value is configured - acceptable during the Stage 4-5 transition,
    before Stage 6 makes authentication mandatory on any route. Fails fast (raises, preventing
    startup) on partial or malformed configuration; never silently invents, falls back to, or
    skips a genuinely broken credential.

    Provisioning-only: no registration, no account creation endpoint, no user administration.
    """
    if username is None and password_hash is None:
        return

    _validate(username, password_hash)
    assert username is not None and password_hash is not None  # narrowed by _validate

    existing = db.query(User).filter(User.username == username).one_or_none()
    if existing is None:
        db.add(User(username=username, password_hash=password_hash))
    else:
        existing.password_hash = password_hash

    db.commit()


def _validate(username: str | None, password_hash: str | None) -> None:
    if username is None or password_hash is None:
        raise InvalidAuthConfigurationError(
            "AUTH_USERNAME and AUTH_PASSWORD_HASH must both be set, or both left unset."
        )
    if not username.strip():
        raise InvalidAuthConfigurationError("AUTH_USERNAME must not be blank.")
    if not password_hash.strip():
        raise InvalidAuthConfigurationError("AUTH_PASSWORD_HASH must not be blank.")
    if not looks_like_bcrypt_hash(password_hash):
        raise InvalidAuthConfigurationError("AUTH_PASSWORD_HASH does not look like a valid bcrypt hash.")
