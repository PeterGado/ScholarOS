from datetime import UTC, datetime, timedelta

from app.auth.repository import UserAccountRepository, UserCredential
from app.core.unit_of_work import UnitOfWork


def reclaim_if_abandoned(
    existing: UserCredential,
    *,
    accounts: UserAccountRepository,
    unit_of_work: UnitOfWork,
    reap_after: timedelta,
) -> bool:
    """Email-squatting / account-takeover fix (2026-10-10, production-readiness pass): before
    this, claiming someone else's email was permanent - register (or attempt Google Sign-In)
    with a victim's email, and the real owner could never register with their own email again
    (`EmailAlreadyInUseError`) or link their verified Google identity to it
    (`GoogleAccountEmailConflictError`), with no recovery path, since the squatting account's
    email is never required to actually be verified to keep the claim.

    Called by `RegisterUserUseCase`/`GoogleSignInUseCase` right before they would otherwise
    raise one of those two errors. If the row already holding `email` is still unverified after
    `reap_after` has elapsed since it was created, its claim on that email is abandoned: the
    email is cleared from the old row (never deleted - the old account, its username, and
    anything else it owns are untouched, and it remains login-able by username+password if the
    squatter ever verifies a *different* email later), freeing the email for the real request
    that triggered this check to proceed normally.

    Safe to clear rather than needing to cascade-delete anything: an unverified account cannot
    upload documents or use chat at all (`EmailVerificationGuard`), so there is provably nothing
    of value tied to that email claim if it was never verified in time.

    A still-verified row, or one not yet past the TTL, is left untouched - returns False, and
    the caller raises its own conflict error exactly as before.
    """
    if existing.email_verified:
        return False

    created_at = existing.created_at
    if created_at.tzinfo is None:
        # SQLite (local dev/test) returns a naive datetime even though every value written
        # here is already UTC (User.created_at's own default) - Postgres returns it tz-aware
        # already, so this is a no-op there. Same cross-dialect gotcha as
        # app.workers.health.check_queue_health.
        created_at = created_at.replace(tzinfo=UTC)

    if datetime.now(UTC) - created_at < reap_after:
        return False

    accounts.update_email(existing.user_id, None)
    unit_of_work.commit()
    return True
