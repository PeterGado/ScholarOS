from sqlalchemy.exc import IntegrityError

from app.auth.exceptions import InvalidInviteCodeError, UsernameAlreadyTakenError, WeakPasswordError
from app.auth.hashing import hash_password
from app.auth.repository import UserCredentialLookup, UserRegistrationRepository
from app.auth.service import AuthService
from app.core.unit_of_work import UnitOfWork

MINIMUM_PASSWORD_LENGTH = 8
"""ADR-011's own minimum, deliberately low - this is friend-testing, not a public launch with
real attacker exposure yet; revisit if/when the invite-code gate is ever lifted.
"""


class RegisterUserUseCase:
    """Self-service registration (ADR-011), additive alongside the existing pre-provisioned
    account (`sync_configured_user`, ADR-010 Decision item 1) - registration never touches or
    replaces that mechanism, it only creates additional `User` rows the same shape produces.

    Deliberately does not create an Agent Workspace - that remains the existing, separate
    onboarding flow (`POST /agents`). Registration's only job is the `User` row and a session
    token, mirroring exactly what a subsequent `POST /auth/login` would return.
    """

    def __init__(
        self,
        user_lookup: UserCredentialLookup,
        user_registration: UserRegistrationRepository,
        auth_service: AuthService,
        unit_of_work: UnitOfWork,
        *,
        required_invite_code: str | None,
    ) -> None:
        self._users = user_lookup
        self._registration = user_registration
        self._auth_service = auth_service
        self._uow = unit_of_work
        self._required_invite_code = required_invite_code

    def execute(self, *, username: str, password: str, invite_code: str | None) -> str:
        """Returns a raw session token, exactly like `AuthService.login` - the caller is
        registered and logged in in one step, per ADR-011 Decision item 1.
        """
        if self._required_invite_code and invite_code != self._required_invite_code:
            raise InvalidInviteCodeError()

        if len(password) < MINIMUM_PASSWORD_LENGTH:
            raise WeakPasswordError(minimum_length=MINIMUM_PASSWORD_LENGTH)

        if self._users.get_by_username(username) is not None:
            raise UsernameAlreadyTakenError()

        try:
            self._registration.create(username=username, password_hash=hash_password(password))
            self._uow.commit()
        except IntegrityError:
            # A real race, not just a defensive precaution: the get_by_username check above and
            # this insert are two separate statements, so a second registration for the same
            # username arriving in that narrow window hits the `users.username` UNIQUE
            # constraint instead of the check above. Translated to the same domain exception
            # the check would have raised, rather than leaking a raw 500.
            self._uow.rollback()
            raise UsernameAlreadyTakenError() from None
        except Exception:
            self._uow.rollback()
            raise

        # Reuses AuthService.login's own public behavior wholesale (re-verifying the
        # just-set password) rather than duplicating session-token creation here - the same
        # "one real mechanism, no parallel path" discipline ADR-010 already established.
        return self._auth_service.login(username=username, password=password)
