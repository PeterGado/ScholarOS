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


class UsernameAlreadyTakenError(AuthDomainError):
    """Raised by registration (ADR-011) when the requested username already belongs to
    another account. Unlike InvalidCredentialsError, this is deliberately NOT non-enumerating
    - a registration form telling you "that username is taken" is standard, expected UX and
    reveals nothing an attacker couldn't already learn by attempting to log in as that name
    with a wrong password (which InvalidCredentialsError already declines to distinguish).
    """

    def __init__(self) -> None:
        super().__init__("That username is already taken.")


class WeakPasswordError(AuthDomainError):
    """Raised by registration (ADR-011) when the supplied password is shorter than the
    minimum length. Never includes the offending password in the message.
    """

    def __init__(self, *, minimum_length: int) -> None:
        super().__init__(f"Password must be at least {minimum_length} characters.")
        self.minimum_length = minimum_length


class InvalidInviteCodeError(AuthDomainError):
    """Raised by registration (ADR-011) when REGISTRATION_INVITE_CODE is configured and the
    supplied invite_code does not match. Deliberately worded like InvalidCredentialsError -
    never reveals whether the configured code exists, only that this attempt didn't match.
    """

    def __init__(self) -> None:
        super().__init__("Invalid invite code.")
