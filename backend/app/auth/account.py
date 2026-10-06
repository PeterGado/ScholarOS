from sqlalchemy.exc import IntegrityError

from app.auth.exceptions import EmailAlreadyInUseError
from app.auth.repository import UserAccountRepository, UserCredentialLookup
from app.core.unit_of_work import UnitOfWork


class UpdateEmailUseCase:
    """Lets an already-authenticated user add or change the email on their own account
    (2026-10-06, Settings) - the only way a username/password account ever gets an email on
    file, since registration itself never collects one. Primarily what makes password reset
    reachable for that account; not required to use the product otherwise.
    """

    def __init__(
        self,
        user_lookup: UserCredentialLookup,
        user_account: UserAccountRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._users = user_lookup
        self._user_account = user_account
        self._uow = unit_of_work

    def execute(self, *, user_id: int, email: str) -> None:
        existing = self._users.get_by_email(email)
        if existing is not None and existing.user_id != user_id:
            raise EmailAlreadyInUseError()

        try:
            self._user_account.update_email(user_id, email)
            self._uow.commit()
        except IntegrityError:
            # A real race, not just a defensive precaution - mirrors RegisterUserUseCase's own
            # identical reasoning for username uniqueness: the check above and this write are
            # two separate statements, so a second update to the same email arriving in that
            # narrow window hits the `users.email` UNIQUE constraint instead of the check above.
            self._uow.rollback()
            raise EmailAlreadyInUseError() from None
        except Exception:
            self._uow.rollback()
            raise
