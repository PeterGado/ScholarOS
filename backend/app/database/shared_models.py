import enum
from datetime import datetime, timezone

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class User(Base):
    """Minimal persistence entity required by the Agent FK graph (04_Logical_Data_Model.md §3.1).

    Realizes the Authentication Boundary's credential store as of ADR-010 (05_Backend_Architecture.md
    §15/§15.4) - `password_hash` is the only addition that ADR authorized.
    """

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # NOT NULL per 04_Logical_Data_Model.md §3.1 (ADR-010). Defaults to "" only so tests that
    # construct a User directly without a credential (e.g. to seed a workspace) don't need to
    # supply one; Stage 4's provisioning sync always sets a real bcrypt hash for the one
    # configured account, and login always goes through it. An empty-string value is never a
    # valid bcrypt hash and will never verify successfully.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=16), nullable=False, default=UserStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
