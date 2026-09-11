from sqlalchemy.orm import Session

from app.auth.exceptions import InvalidAuthConfigurationError
from app.auth.hashing import looks_like_bcrypt_hash
from app.database.shared_models import User


def sync_configured_user(db: Session, *, username: str | None, password_hash: str | None) -> None:
    """Provision the single pre-provisioned account from configuration (ADR-010 Decision
    item 1: "synced into the User table on every application startup [...] configuration is
    the source of truth, the database row is a cache of it"). Create-if-missing,
    update-if-changed - including a changed username, since the row is a *cache* of whatever
    configuration currently says, not a record keyed by a specific username.

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

    existing_users = db.query(User).all()
    if len(existing_users) > 1:
        # A genuine ambiguity ADR-010 does not resolve (it assumes exactly one row, "a cache
        # of" configuration) - reported, not silently guessed at.
        raise InvalidAuthConfigurationError(
            f"Expected at most one User row for single-user provisioning; found "
            f"{len(existing_users)}. Resolve manually before startup can provision safely."
        )

    if not existing_users:
        db.add(User(username=username, password_hash=password_hash))
    else:
        user = existing_users[0]
        user.username = username
        user.password_hash = password_hash

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
