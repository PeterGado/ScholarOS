import pytest

from app.auth.hashing import hash_password
from app.auth.infrastructure import SqlAlchemyUserCredentialLookup
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "auth_credential_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_the_provisioned_user_can_be_found_by_username(db_session):
    user = User(username="researcher", password_hash=hash_password("s3cret"))
    db_session.add(user)
    db_session.commit()

    lookup = SqlAlchemyUserCredentialLookup(db_session)
    found = lookup.get_by_username("researcher")

    assert found is not None
    assert found.user_id == user.user_id
    assert found.username == "researcher"


def test_the_password_hash_is_retrievable_through_the_credential_abstraction(db_session):
    expected_hash = hash_password("s3cret")
    db_session.add(User(username="researcher", password_hash=expected_hash))
    db_session.commit()

    lookup = SqlAlchemyUserCredentialLookup(db_session)
    found = lookup.get_by_username("researcher")

    assert found.password_hash == expected_hash


def test_an_unknown_username_returns_none_not_a_distinguishable_error(db_session):
    lookup = SqlAlchemyUserCredentialLookup(db_session)
    assert lookup.get_by_username("nobody") is None
