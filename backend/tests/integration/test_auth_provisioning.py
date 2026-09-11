import pytest

from app.auth.exceptions import InvalidAuthConfigurationError, InvalidCredentialsError
from app.auth.hashing import hash_password
from app.auth.infrastructure import SqlAlchemyAuthSessionRepository, SqlAlchemyUserCredentialLookup
from app.auth.provisioning import sync_configured_user
from app.auth.service import AuthService
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "provisioning_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


VALID_HASH = hash_password("s3cret")


# --- Configuration validation -------------------------------------------------------------------


def test_both_unset_is_a_noop_and_creates_no_user(db_session):
    sync_configured_user(db_session, username=None, password_hash=None)
    assert db_session.query(User).count() == 0


def test_blank_username_is_rejected(db_session):
    with pytest.raises(InvalidAuthConfigurationError):
        sync_configured_user(db_session, username="   ", password_hash=VALID_HASH)


def test_blank_password_hash_is_rejected(db_session):
    with pytest.raises(InvalidAuthConfigurationError):
        sync_configured_user(db_session, username="researcher", password_hash="   ")


def test_malformed_bcrypt_hash_is_rejected(db_session):
    with pytest.raises(InvalidAuthConfigurationError):
        sync_configured_user(db_session, username="researcher", password_hash="not-a-bcrypt-hash")


def test_username_only_partial_configuration_is_rejected(db_session):
    with pytest.raises(InvalidAuthConfigurationError):
        sync_configured_user(db_session, username="researcher", password_hash=None)


def test_password_hash_only_partial_configuration_is_rejected(db_session):
    with pytest.raises(InvalidAuthConfigurationError):
        sync_configured_user(db_session, username=None, password_hash=VALID_HASH)


def test_rejection_does_not_leak_the_invalid_hash_value(db_session):
    secret_looking_garbage = "definitely-not-a-hash-abc123"
    with pytest.raises(InvalidAuthConfigurationError) as exc_info:
        sync_configured_user(db_session, username="researcher", password_hash=secret_looking_garbage)
    assert secret_looking_garbage not in str(exc_info.value)


def test_none_of_the_rejected_cases_leave_a_user_behind(db_session):
    for username, password_hash in [("   ", VALID_HASH), ("researcher", "   "), ("researcher", "garbage")]:
        try:
            sync_configured_user(db_session, username=username, password_hash=password_hash)
        except InvalidAuthConfigurationError:
            pass
    assert db_session.query(User).count() == 0


# --- Fresh provisioning -------------------------------------------------------------------


def test_fresh_database_provisions_exactly_one_user(db_session):
    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)
    assert db_session.query(User).count() == 1


def test_provisioned_username_matches_configuration(db_session):
    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)
    user = db_session.query(User).one()
    assert user.username == "researcher"


def test_provisioned_password_hash_matches_configuration_and_is_never_plaintext(db_session):
    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)
    user = db_session.query(User).one()
    assert user.password_hash == VALID_HASH
    assert user.password_hash != "s3cret"


def test_provisioned_user_is_usable_by_the_credential_lookup(db_session):
    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)

    lookup = SqlAlchemyUserCredentialLookup(db_session)
    found = lookup.get_by_username("researcher")

    assert found is not None
    assert found.password_hash == VALID_HASH


# --- Existing user -------------------------------------------------------------------


def test_case_a_matching_existing_user_is_left_valid_and_not_duplicated(db_session):
    db_session.add(User(username="researcher", password_hash=VALID_HASH))
    db_session.commit()

    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)

    assert db_session.query(User).count() == 1
    assert db_session.query(User).one().password_hash == VALID_HASH


def test_case_b_stale_hash_is_synchronized_to_the_configured_hash(db_session):
    stale_hash = hash_password("old-password")
    db_session.add(User(username="researcher", password_hash=stale_hash))
    db_session.commit()

    new_hash = hash_password("new-password")
    sync_configured_user(db_session, username="researcher", password_hash=new_hash)

    user = db_session.query(User).one()
    assert user.password_hash == new_hash
    assert user.password_hash != stale_hash


def test_case_c_existing_user_with_a_different_username_is_renamed_to_match_configuration(db_session):
    """The database row is a *cache* of configuration (ADR-010 Decision item 1) - a username
    change updates that same cached identity rather than creating a second row.
    """
    db_session.add(User(username="old-name", password_hash=VALID_HASH))
    db_session.commit()

    sync_configured_user(db_session, username="new-name", password_hash=VALID_HASH)

    assert db_session.query(User).count() == 1
    assert db_session.query(User).one().username == "new-name"


def test_multiple_existing_users_raises_rather_than_guessing(db_session):
    """A genuine ambiguity ADR-010 does not resolve - reported, not silently decided."""
    db_session.add(User(username="a", password_hash=VALID_HASH))
    db_session.add(User(username="b", password_hash=VALID_HASH))
    db_session.commit()

    with pytest.raises(InvalidAuthConfigurationError):
        sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)


# --- Idempotency -------------------------------------------------------------------


def test_running_provisioning_four_times_still_produces_exactly_one_user(db_session):
    for _ in range(4):
        sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)

    assert db_session.query(User).count() == 1


# --- Authentication integration (no HTTP route exists yet - Stage 5) -------------------------------------------------------------------


def test_the_provisioned_credentials_authenticate_successfully_via_auth_service(db_session):
    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)
    service = AuthService(
        SqlAlchemyAuthSessionRepository(db_session),
        SqlAlchemyUserCredentialLookup(db_session),
        SqlAlchemyUnitOfWork(db_session),
    )

    token = service.login(username="researcher", password="s3cret")

    identity = service.verify_token(token)
    assert identity.user_id == db_session.query(User).one().user_id


def test_the_wrong_password_against_the_provisioned_user_fails(db_session):
    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)
    service = AuthService(
        SqlAlchemyAuthSessionRepository(db_session),
        SqlAlchemyUserCredentialLookup(db_session),
        SqlAlchemyUnitOfWork(db_session),
    )

    with pytest.raises(InvalidCredentialsError):
        service.login(username="researcher", password="wrong-password")


def test_an_unknown_username_fails_the_same_way_as_a_wrong_password(db_session):
    sync_configured_user(db_session, username="researcher", password_hash=VALID_HASH)
    service = AuthService(
        SqlAlchemyAuthSessionRepository(db_session),
        SqlAlchemyUserCredentialLookup(db_session),
        SqlAlchemyUnitOfWork(db_session),
    )

    with pytest.raises(InvalidCredentialsError) as unknown_user:
        service.login(username="nobody", password="whatever")
    with pytest.raises(InvalidCredentialsError) as wrong_password:
        service.login(username="researcher", password="wrong-password")

    assert str(unknown_user.value) == str(wrong_password.value)
