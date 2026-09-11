from app.core.exceptions import ScholarOSError


class AuthDomainError(ScholarOSError):
    """Base class for Authentication Boundary errors."""


class InvalidCredentialsError(AuthDomainError):
    """Raised for both an unknown username and a wrong password - deliberately the same
    error and message for both, to avoid revealing which one was wrong (username enumeration).
    """

    def __init__(self) -> None:
        super().__init__("Invalid username or password.")


class InvalidSessionError(AuthDomainError):
    """Raised for a missing, unknown, or already-ended session token. Deliberately not named
    or worded around "expiry" - there is none in this milestone (ADR-010 Decision item 2).
    """

    def __init__(self) -> None:
        super().__init__("Invalid or ended session.")


class InvalidAuthConfigurationError(AuthDomainError):
    """Raised when AUTH_USERNAME/AUTH_PASSWORD_HASH are partially set, blank, or malformed.
    Never includes the offending value in its message - configuration meant to be secret is
    never echoed back, even when rejecting it.
    """
