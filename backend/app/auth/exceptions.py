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


class WeakPasswordError(AuthDomainError):
    """Raised by registration (ADR-011) when the supplied password is shorter than the
    minimum length. Never includes the offending password in the message.
    """

    def __init__(self, *, minimum_length: int) -> None:
        super().__init__(f"Password must be at least {minimum_length} characters.")
        self.minimum_length = minimum_length


class PasswordCompromisedError(AuthDomainError):
    """Raised by registration and password reset (2026-10-06, external security review) when
    the supplied password appears in a known data breach corpus - checked via HIBP's
    k-anonymity Pwned Passwords API (app.auth.password_strength). Never includes the offending
    password in the message.
    """

    def __init__(self) -> None:
        super().__init__("This password has appeared in a known data breach. Choose a different one.")


class InvalidInviteCodeError(AuthDomainError):
    """Raised by registration (ADR-011) when REGISTRATION_INVITE_CODE is configured and the
    supplied invite_code does not match. Deliberately worded like InvalidCredentialsError -
    never reveals whether the configured code exists, only that this attempt didn't match.
    """

    def __init__(self) -> None:
        super().__init__("Invalid invite code.")


class InvalidGoogleTokenError(AuthDomainError):
    """Raised by Google Sign-In (2026-09-20) when the supplied ID token fails Google's own
    signature/audience/expiry verification. Worded like InvalidCredentialsError for the same
    reason - a forged or expired token and a well-formed-but-untrusted one look the same to the
    caller either way.
    """

    def __init__(self) -> None:
        super().__init__("Invalid Google sign-in token.")


class GoogleAccountEmailConflictError(AuthDomainError):
    """Raised by Google Sign-In (2026-09-20) when a *brand-new* Google sign-in's verified email
    already belongs to an existing (password-based) account. Deliberately never auto-links the
    two - silently merging identities on an email match is a real account-takeover surface if
    that email were ever unverified elsewhere; the user is told to use their password instead.
    """

    def __init__(self) -> None:
        super().__init__(
            "An account with this email already exists. Sign in with your password, then connect "
            "your Google account from Settings -> Security to use it next time."
        )


class GoogleSignInNotConfiguredError(AuthDomainError):
    """Raised by Google Sign-In (2026-09-20) when GOOGLE_OAUTH_CLIENT_ID isn't set yet - mirrors
    ProviderConfigurationError's existing 503 pattern for the AI provider, so the route fails
    cleanly instead of crashing if the button is reachable before Google Cloud setup is done.
    """

    def __init__(self) -> None:
        super().__init__("Google sign-in is not configured.")


class InvalidResetTokenError(AuthDomainError):
    """Raised for a missing, unknown, expired, or already-used password reset token (2026-10-06)
    - deliberately one error for all four reasons, the same non-distinguishing style
    InvalidSessionError already uses, so a confirm attempt never reveals *why* a token didn't
    work (e.g. "expired" vs "already used" could help an attacker time a guessing attempt).
    """

    def __init__(self) -> None:
        super().__init__("This password reset link is invalid or has expired.")


class EmailNotVerifiedError(AuthDomainError):
    """Raised when an unverified password account attempts a feature gated on a confirmed
    email - currently uploading a research document and sending a chat message (2026-10-06,
    external security review). Google accounts never see this: Google's own OIDC claim already
    verifies the email at account creation (GoogleSignInUseCase), and every account that existed
    before this gate shipped was grandfathered verified by the introducing migration.
    """

    def __init__(self) -> None:
        super().__init__("Verify your email to use this feature.")


class InvalidVerificationTokenError(AuthDomainError):
    """Raised for a missing, unknown, expired, or already-used email verification token
    (2026-10-06) - the same non-distinguishing style InvalidResetTokenError already uses.
    """

    def __init__(self) -> None:
        super().__init__("This verification link is invalid or has expired.")


class GoogleAccountAlreadyLinkedError(AuthDomainError):
    """Raised by ConnectGoogleAccountUseCase (2026-10-06, Settings -> Security -> Connected
    accounts) when the Google identity being connected is already linked to a *different*
    ScholarOS account - each Google identity can only ever be linked to one account.
    """

    def __init__(self) -> None:
        super().__init__("This Google account is already connected to a different ScholarOS account.")


class EmailAlreadyInUseError(AuthDomainError):
    """Raised when registering, or when updating an account's email (Settings), with an email
    already registered to a different account - the `users.email` UNIQUE constraint's
    domain-level translation.
    """

    def __init__(self) -> None:
        super().__init__("That email is already associated with another account.")
