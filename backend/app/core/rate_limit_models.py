from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RateLimitCounter(Base):
    """Backing store for the rate limiter (2026-09-21, second infra/scaling security pass).

    Read and written exclusively by `app.core.rate_limit_storage.PostgresRateLimitStorage`
    (a `limits.storage.Storage` implementation), never through this ORM model directly -
    replaces slowapi's default in-memory storage, which resets on every redeploy and cannot be
    shared if this app is ever run on more than one machine (ADR-006 pins it to one today).
    Chosen over adding Redis so rate-limit state survives a redeploy without a new service or
    credential to manage.

    `expires_at` is a Unix epoch float (`time.time()`), matching `limits.storage.memory.
    MemoryStorage`'s own semantics exactly - avoids any conversion between what
    PostgresRateLimitStorage computes and what's stored.
    """

    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    counter: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
