from app.auth.repository import UserCredentialLookup

__all__ = ["derive_unique_username"]


def derive_unique_username(seed: str, *, users: UserCredentialLookup) -> str:
    """Synthesizes a unique `users.username` value from an email (or any other seed string) -
    shared by Google Sign-In and password registration (2026-10-06, external security review:
    registration now collects an email, not a username, so both paths need this). Not a display
    name - purely the required-unique column's value, derived once at account creation and
    never shown as the account's real identity (see ProfileResponse's own email field for that).
    """
    base = seed.split("@")[0] or "user"
    candidate, suffix = base, 1
    while users.get_by_username(candidate) is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate
