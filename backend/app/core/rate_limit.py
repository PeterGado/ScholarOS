from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.rate_limit_storage import PostgresRateLimitStorage  # noqa: F401 - registers "scholaros-sql"

# Shared instance (2026-09-19 production security pass): a single Limiter, imported by both
# app.main (to install the middleware/state) and each rate-limited route module (to decorate
# its endpoints) - slowapi's own required pattern, since @limiter.limit(...) needs the exact
# instance registered on app.state.limiter. Keyed by IP (get_remote_address); Fly.io sits
# behind a proxy, so this only reads the real client IP once uvicorn is run with
# --proxy-headers (see Dockerfile).
#
# storage_uri (2026-09-21, second infra/scaling pass): backed by this app's own database
# (app.core.rate_limit_storage.PostgresRateLimitStorage) rather than slowapi's default
# in-memory store, so counters survive a redeploy and would work correctly across more than
# one machine - the PostgresRateLimitStorage import above must run first so this scheme is
# registered before Limiter resolves it.
limiter = Limiter(key_func=get_remote_address, storage_uri="scholaros-sql://")
