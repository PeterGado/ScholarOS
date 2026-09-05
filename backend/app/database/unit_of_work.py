from sqlalchemy.orm import Session


class SqlAlchemyUnitOfWork:
    """Concrete UnitOfWork (app.core.unit_of_work) backed by a SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
