from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared instance (2026-09-19 production security pass): a single Limiter, imported by both
# app.main (to install the middleware/state) and each rate-limited route module (to decorate
# its endpoints) - slowapi's own required pattern, since @limiter.limit(...) needs the exact
# instance registered on app.state.limiter. Keyed by IP (get_remote_address); Fly.io sits
# behind a proxy, so this only reads the real client IP once uvicorn is run with
# --proxy-headers (see Dockerfile).
limiter = Limiter(key_func=get_remote_address)
