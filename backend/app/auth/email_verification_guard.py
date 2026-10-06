from app.auth.exceptions import EmailNotVerifiedError
from app.auth.repository import UserCredentialLookup

__all__ = ["EmailVerificationGuard"]


class EmailVerificationGuard:
    """The shared checkpoint any use case gating a feature on a verified email goes through
    (2026-10-06, external security review) - currently document upload and sending a chat
    message. Mirrors AiUsageGuard's own shape (a small, injected, per-call-site guard) rather
    than coupling the document/writing modules directly to UserCredentialLookup, an
    Authentication Boundary concept.
    """

    def __init__(self, user_lookup: UserCredentialLookup) -> None:
        self._users = user_lookup

    def require_verified(self, user_id: int) -> None:
        user = self._users.get_by_id(user_id)
        assert user is not None, f"user_id {user_id} came from a verified session but has no User row"
        if not user.email_verified:
            raise EmailNotVerifiedError()
