from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Each module's infrastructure layer defines its own ORM models against this base (04_Logical_Data_Model.md; modular monolith, ADR-003)."""
