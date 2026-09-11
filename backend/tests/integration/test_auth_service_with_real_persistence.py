import pytest

from app.auth.exceptions import InvalidCredentialsError, InvalidSessionError
from app.auth.hashing import hash_password
from app.auth.infrastructure import SqlAlchemyAuthSessionRepository, SqlAlchemyUserCredentialLookup
from app.auth.service import AuthService
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "auth_service_real_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def service(db_session):
    return AuthService(
        SqlAlchemyAuthSessionRepository(db_session),
        SqlAlchemyUserCredentialLookup(db_session),
        SqlAlchemyUnitOfWork(db_session),
    )


def _provision_user(db_session, username="researcher", password="s3cret"):
    user = User(username=username, password_hash=hash_password(password))
    db_session.add(user)
    db_session.commit()
    return user


def test_login_against_real_persistence_creates_a_session_row(db_session, service):
    _provision_user(db_session)

    token = service.login(username="researcher", password="s3cret")

    identity = service.verify_token(token)
    assert identity.user_id is not None


def test_login_with_wrong_password_against_real_persistence_raises_invalid_credentials(db_session, service):
    _provision_user(db_session)
    with pytest.raises(InvalidCredentialsError):
        service.login(username="researcher", password="wrong")


def test_logout_against_real_persistence_ends_the_session(db_session, service):
    _provision_user(db_session)
    token = service.login(username="researcher", password="s3cret")

    service.logout(token)

    with pytest.raises(InvalidSessionError):
        service.verify_token(token)


def test_a_session_created_via_one_connection_is_visible_from_a_completely_separate_one(tmp_path):
    """The actual regression this stage found: repositories only flush; without AuthService
    committing via its UnitOfWork, a session created here would be invisible (rolled back on
    close) to a completely separate engine/connection pointed at the same file - exactly what
    happens between two real HTTP requests, each with its own Session from get_db().
    """
    db_path = tmp_path / "auth_service_separate_connections_test.db"

    write_engine = build_engine(f"sqlite:///{db_path}")
    init_db(write_engine)
    write_session = build_sessionmaker(write_engine)()
    _provision_user(write_session)
    write_service = AuthService(
        SqlAlchemyAuthSessionRepository(write_session),
        SqlAlchemyUserCredentialLookup(write_session),
        SqlAlchemyUnitOfWork(write_session),
    )
    token = write_service.login(username="researcher", password="s3cret")
    write_session.close()
    write_engine.dispose()

    read_engine = build_engine(f"sqlite:///{db_path}")
    read_session = build_sessionmaker(read_engine)()
    try:
        read_service = AuthService(
            SqlAlchemyAuthSessionRepository(read_session),
            SqlAlchemyUserCredentialLookup(read_session),
            SqlAlchemyUnitOfWork(read_session),
        )
        identity = read_service.verify_token(token)
        assert identity.user_id is not None
    finally:
        read_session.close()
        read_engine.dispose()
