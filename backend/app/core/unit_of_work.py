from typing import Protocol


class UnitOfWork(Protocol):
    """Transaction boundary abstraction. Application use cases depend on this, never on a
    concrete session type, so domain/application code stays framework-agnostic.
    """

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
