from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuthSession:
    """The Authentication Boundary's session record (04_Logical_Data_Model.md §3.2 `Session`;
    named `AuthSession` in code per ADR-010 Decision item 6 to avoid colliding with
    `sqlalchemy.orm.Session`, already imported throughout the codebase).

    `is_active` reflects only the explicit `open -> ended` transition
    (05_Constraints_and_Integrity.md §5). There is no time-based validity check here by
    design - ADR-010 Decision item 2 is definitive: no automatic session expiry exists in
    this milestone. `last_active_at` is activity metadata only and must never be read to
    determine validity.
    """

    user_id: int
    token_hash: str
    started_at: datetime
    session_id: int | None = None
    last_active_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.ended_at is None
