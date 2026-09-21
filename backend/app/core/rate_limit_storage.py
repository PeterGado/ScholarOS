import time

from limits.storage.base import Storage
from sqlalchemy import text

import app.database.session as db_session


class PostgresRateLimitStorage(Storage):
    """A `limits.storage.Storage` backend using this app's own database (Postgres in
    production, SQLite in tests) instead of slowapi's default in-memory store - chosen over
    adding Redis so rate-limit state survives a redeploy and would work correctly if this app
    is ever run on more than one machine (ADR-006 pins it to one today), without a new service
    or credential to manage.

    Registers itself as the "scholaros-sql" storage scheme the moment this module is imported
    (`limits.storage.base.StorageRegistry`'s metaclass hook on `STORAGE_SCHEME`) -
    `Limiter(storage_uri="scholaros-sql://")` (app.core.rate_limit) then resolves to this class
    via `limits.storage.storage_from_string`. The scheme string carries no real connection
    info; every method reads `db_session.engine` fresh on each call rather than binding it at
    import time, so it follows the same test database as `get_db()`/`init_db()` when a test
    monkeypatches `app.database.session.engine` (see tests/e2e/conftest.py's `db_engine`
    fixture) instead of holding a stale reference to whatever engine existed at import time.

    Implements the fixed-window counter semantics `limits.strategies.FixedWindowRateLimiter`
    expects: a key's counter resets (not accumulates) once its window has expired, mirroring
    `limits.storage.memory.MemoryStorage.incr` exactly - `incr`'s single
    `INSERT ... ON CONFLICT DO UPDATE` statement is the atomic equivalent of MemoryStorage's
    per-key lock, so two concurrent requests incrementing the same key can never lose a count
    or read a stale expiry. `key` is always a bound parameter, never interpolated into SQL.
    """

    STORAGE_SCHEME = ["scholaros-sql"]

    @property
    def base_exceptions(self) -> type[Exception] | tuple[type[Exception], ...]:
        return Exception

    def incr(self, key: str, expiry: int, amount: int = 1) -> int:
        now = time.time()
        new_expiry = now + expiry
        with db_session.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO rate_limit_counters (key, counter, expires_at)
                    VALUES (:key, :amount, :new_expiry)
                    ON CONFLICT (key) DO UPDATE SET
                        counter = CASE
                            WHEN rate_limit_counters.expires_at <= :now THEN :amount
                            ELSE rate_limit_counters.counter + :amount
                        END,
                        expires_at = CASE
                            WHEN rate_limit_counters.expires_at <= :now THEN :new_expiry
                            ELSE rate_limit_counters.expires_at
                        END
                    RETURNING counter
                    """
                ),
                {"key": key, "amount": amount, "new_expiry": new_expiry, "now": now},
            ).first()
        return row[0]

    def get(self, key: str) -> int:
        with db_session.engine.connect() as conn:
            row = conn.execute(
                text("SELECT counter, expires_at FROM rate_limit_counters WHERE key = :key"),
                {"key": key},
            ).first()
        if row is None or row[1] <= time.time():
            return 0
        return row[0]

    def get_expiry(self, key: str) -> float:
        with db_session.engine.connect() as conn:
            row = conn.execute(
                text("SELECT expires_at FROM rate_limit_counters WHERE key = :key"),
                {"key": key},
            ).first()
        return row[0] if row is not None else time.time()

    def check(self) -> bool:
        try:
            with db_session.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def reset(self) -> int | None:
        with db_session.engine.begin() as conn:
            result = conn.execute(text("DELETE FROM rate_limit_counters"))
            return result.rowcount

    def clear(self, key: str) -> None:
        with db_session.engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_counters WHERE key = :key"), {"key": key})
