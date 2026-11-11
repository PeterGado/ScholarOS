from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.rate_limit_storage import (
    PostgresRateLimitStorage,  # noqa: F401 - registers "scholaros-sql"
)
from app.database.rls_context import current_user_id


def rate_limit_key(request: Request) -> str:
    """Per-user when the caller is authenticated, per-IP when they are not (2026-10-23).

    Why not IP alone: this app is used by people sharing one network - a campus, an office, a
    household - where every user behind the same NAT would otherwise share a single budget (the
    first person to upload 20 documents locks everyone else out for the rest of the minute).
    The inverse failure is just as real: one user can reset an IP-keyed budget by changing
    network. Keying on the authenticated identity fixes both, and it is the only key that
    matches what the limits actually mean ("20 AI searches per user per minute").

    Identity comes from `current_user_id` - the exact ContextVar app.database.rls_context
    already uses for Row-Level Security, set by get_current_user_id. FastAPI resolves every
    dependency before it invokes the endpoint function, and slowapi's decorator checks the
    limit at the top of that function, so by the time this runs the value is set with no extra
    database round trip and no second token verification. A request that is not authenticated
    (login, registration, password reset, email verification) has no user yet and correctly
    stays on its IP - those limits exist to slow down credential-stuffing from one source, which
    is an IP-shaped problem.

    Degrades safely: if the value is ever absent (an authenticated route whose identity
    dependency ran in a context this does not see), the request simply falls back to the IP
    bucket rather than escaping rate limiting entirely.
    """
    user_id = current_user_id.get()
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


# Shared instance (2026-09-19 production security pass): a single Limiter, imported by both
# app.main (to install the middleware/state) and each rate-limited route module (to decorate
# its endpoints) - slowapi's own required pattern, since @limiter.limit(...) needs the exact
# instance registered on app.state.limiter.
#
# key_func (2026-10-23) is rate_limit_key above, not slowapi's get_remote_address directly - see
# its docstring for why authenticated traffic is keyed by user. Fly.io still sits behind a proxy,
# so the IP fallback reads the real client IP only once uvicorn is run with --proxy-headers (see
# Dockerfile).
#
# storage_uri (2026-09-21, second infra/scaling pass): backed by this app's own database
# (app.core.rate_limit_storage.PostgresRateLimitStorage) rather than slowapi's default
# in-memory store, so counters survive a redeploy and would work correctly across more than
# one machine - the PostgresRateLimitStorage import above must run first so this scheme is
# registered before Limiter resolves it.
limiter = Limiter(key_func=rate_limit_key, storage_uri="scholaros-sql://")
