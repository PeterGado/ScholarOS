"""Real-Postgres Row-Level Security coverage (2026-09-21, second infra/scaling security pass).
Same POSTGRES_TEST_URL-gated pattern as test_postgres_dialect_compatibility.py - RLS cannot be
tested against SQLite at all (SQLite has no RLS), so a real local Postgres is required.

Run against a real local Postgres:
    POSTGRES_TEST_URL="postgresql://user:pass@localhost:5432/scholaros_test" pytest tests/integration/test_row_level_security.py -v

This file proves the actual point of the feature: a hand-crafted query that OMITS its WHERE
clause entirely (the exact class of bug RLS exists to catch, since the app's own query-level
filtering already has real test coverage elsewhere) still returns only the current user's rows
once run as the restricted, non-owner role - not as a fake/mock, as a real second Postgres
login. It also proves the fail-closed default (no user context set -> zero rows, not an error
and not everything) and that the empty-string-after-LOCAL-reset Postgres behavior documented in
the "add row level security policies" migration's app_current_user_id() function is handled
correctly (this was a real bug, caught by testing this exact scenario by hand before writing
this file - see that migration's docstring).

The test role created here (TEST_ROLE) is granted the same privilege set the real production
`scholaros_app` role will get - this file is what actually proves that grant set is sufficient,
not just that RLS syntax works in principle.
"""

import os

import pytest
from sqlalchemy import text

from app.database.rls_context import current_user_id
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL not set - skipping real-Postgres RLS tests",
)

TEST_ROLE = "scholaros_app_test"
TEST_ROLE_PASSWORD = "test-only-not-a-real-secret"

# Mirrors RLS_TABLES in alembic/versions/cff25673e0e3_add_row_level_security_policies.py
# exactly - duplicated rather than imported, since alembic/versions/ has no __init__.py and
# isn't a real package (and "alembic" itself is also the name of the installed migration
# library, so importing from a local "alembic.versions...." path risks resolving to the wrong
# module entirely depending on sys.path order). A narrower subset is enough to exercise the
# representative hop-depths this file's tests actually check: direct-owner (agents), one-hop
# (projects), and the real-repository end-to-end case (agents again, via get_by_id).
RLS_TABLES: list[tuple[str, str]] = [
    ("agents", "user_id = app_current_user_id()"),
    (
        "projects",
        """EXISTS (
            SELECT 1 FROM agents a
            WHERE a.agent_id = projects.agent_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
]


def _restricted_role_url(owner_url: str) -> str:
    """Same host/db as `owner_url`, different role - a real second login, not `SET ROLE` on the
    owner connection, since `SET ROLE` on a superuser-ish connection can behave differently than
    an actual role login for RLS bypass semantics; a real login is the strongest proof.
    """
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(owner_url)
    netloc = f"{TEST_ROLE}:{TEST_ROLE_PASSWORD}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@pytest.fixture()
def owner_engine():
    """Schema + RLS policies via a real migration-equivalent bootstrap (init_db creates tables;
    RLS itself is created by the actual "add row level security policies" migration, run here
    directly via op-equivalent SQL so this test exercises the exact same policies production
    will run, not a hand-rolled approximation).
    """
    eng = build_engine(POSTGRES_TEST_URL)
    init_db(eng)

    with eng.connect() as connection:
        connection.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION app_current_user_id() RETURNS integer
                LANGUAGE sql STABLE AS $$
                    SELECT NULLIF(current_setting('app.current_user_id', true), '')::int
                $$;
                """
            )
        )
        for table_name, condition_sql in RLS_TABLES:
            connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;"))
            # Idempotent: drop-then-create rather than relying solely on teardown having fully
            # completed (schema/role drop and a fresh init_db() genuinely race on a local
            # Postgres server under repeated back-to-back test runs) - self-healing setup is
            # more robust than a perfectly-timed teardown.
            connection.execute(text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name};"))
            connection.execute(
                text(
                    f"CREATE POLICY tenant_isolation ON {table_name} "
                    f"USING ({condition_sql}) WITH CHECK ({condition_sql});"
                )
            )
        # A role can't be dropped while it still holds any GRANTed privileges (not just owned
        # objects) - `DROP OWNED BY` revokes those first. Wrapped in an existence check since
        # `DROP OWNED BY`/`DROP ROLE` both error on a role that doesn't exist, unlike the `IF
        # EXISTS` forms used elsewhere in this fixture.
        connection.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{TEST_ROLE}') THEN
                        EXECUTE 'DROP OWNED BY {TEST_ROLE}';
                        EXECUTE 'DROP ROLE {TEST_ROLE}';
                    END IF;
                END
                $$;
                """
            )
        )
        connection.execute(
            text(
                f"CREATE ROLE {TEST_ROLE} LOGIN PASSWORD '{TEST_ROLE_PASSWORD}' "
                f"NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;"
            )
        )
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {TEST_ROLE};"))
        connection.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {TEST_ROLE};"))
        connection.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {TEST_ROLE};"))
        connection.commit()

    yield eng

    with eng.connect() as connection:
        # Drop the schema (and everything in it - tables, sequences, and the privilege grants
        # tied to them) BEFORE the role itself, so DROP ROLE never fights over still-live
        # grants the way DROP ROLE would if attempted first (a real ordering bug found by
        # running this fixture, not a hypothetical).
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{TEST_ROLE}') THEN
                        EXECUTE 'DROP OWNED BY {TEST_ROLE}';
                        EXECUTE 'DROP ROLE {TEST_ROLE}';
                    END IF;
                END
                $$;
                """
            )
        )
        connection.commit()
    eng.dispose()


@pytest.fixture()
def owner_session(owner_engine):
    factory = build_sessionmaker(owner_engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def restricted_engine(owner_engine):
    """A real, separate connection logged in as the restricted role - not the owner connection
    with SET ROLE. Depends on owner_engine so the role/grants/policies already exist.
    """
    eng = build_engine(_restricted_role_url(POSTGRES_TEST_URL))
    yield eng
    eng.dispose()


def _create_agent(owner_session, *, username: str) -> tuple[int, int]:
    """Provisions a real user + agent + project (the shortest real ownership chain), as the
    owner role - test setup only, never what's under test.
    """
    user = User(username=username)
    owner_session.add(user)
    owner_session.flush()

    agents = SqlAlchemyAgentRepository(owner_session)
    projects = SqlAlchemyProjectRepository(owner_session)
    uow = SqlAlchemyUnitOfWork(owner_session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic="Topic"
    )
    owner_session.commit()
    return workspace.agent.agent_id, user.user_id


def test_an_unfiltered_query_as_the_restricted_role_only_returns_the_current_users_rows(owner_session, restricted_engine):
    """The actual point of RLS: a hand-crafted query with NO WHERE clause at all - the exact
    class of bug this feature exists to catch as a second layer under the app's own real
    query-level filtering.
    """
    agent_a, user_a = _create_agent(owner_session, username="user-a")
    agent_b, user_b = _create_agent(owner_session, username="user-b")

    token = current_user_id.set(user_a)
    try:
        with restricted_engine.begin() as conn:
            rows = conn.execute(text("SELECT agent_id FROM agents")).all()
    finally:
        current_user_id.reset(token)

    agent_ids = {row[0] for row in rows}
    assert agent_ids == {agent_a}
    assert agent_b not in agent_ids


def test_an_unfiltered_query_on_a_two_hop_table_only_returns_the_current_users_rows(owner_session, restricted_engine):
    _, user_a = _create_agent(owner_session, username="user-a2")
    _, user_b = _create_agent(owner_session, username="user-b2")

    projects_a = owner_session.execute(text("SELECT project_id FROM projects WHERE agent_id IN "
                                              "(SELECT agent_id FROM agents WHERE user_id = :uid)"), {"uid": user_a}).all()
    projects_b = owner_session.execute(text("SELECT project_id FROM projects WHERE agent_id IN "
                                              "(SELECT agent_id FROM agents WHERE user_id = :uid)"), {"uid": user_b}).all()
    project_id_a = {row[0] for row in projects_a}
    project_id_b = {row[0] for row in projects_b}

    token = current_user_id.set(user_a)
    try:
        with restricted_engine.begin() as conn:
            rows = conn.execute(text("SELECT project_id FROM projects")).all()
    finally:
        current_user_id.reset(token)

    seen = {row[0] for row in rows}
    assert seen == project_id_a
    assert not (seen & project_id_b)


def test_no_user_context_set_denies_every_row_rather_than_erroring_or_allowing_everything(owner_session, restricted_engine):
    _create_agent(owner_session, username="user-fail-closed")

    with restricted_engine.begin() as conn:
        rows = conn.execute(text("SELECT agent_id FROM agents")).all()

    assert rows == []


def test_fail_closed_holds_even_after_a_prior_transaction_set_a_real_user(owner_session, restricted_engine):
    """Reproduces the exact bug found and fixed while building this feature: Postgres reverts a
    `set_config(..., true)` value to an empty string (not NULL) once its transaction ends, on a
    connection that previously had it set - naive `current_setting(...)::int` would raise a cast
    error here instead of failing closed. app_current_user_id()'s NULLIF fix is what this test
    actually exercises.
    """
    agent_a, user_a = _create_agent(owner_session, username="user-reuse-a")

    token = current_user_id.set(user_a)
    try:
        with restricted_engine.begin() as conn:
            first = conn.execute(text("SELECT agent_id FROM agents")).all()
    finally:
        current_user_id.reset(token)
    assert {row[0] for row in first} == {agent_a}

    # No user set this time, same engine/pool - must not raise, must deny all rows.
    with restricted_engine.begin() as conn:
        second = conn.execute(text("SELECT agent_id FROM agents")).all()
    assert second == []


def test_a_real_repository_get_by_id_is_blocked_by_rls_even_though_it_does_not_filter_by_owner(owner_session, restricted_engine):
    """SqlAlchemyAgentRepository.get_by_id(agent_id) is a pure primary-key lookup - it does not
    filter by owner itself (ownership is enforced at a higher use-case/authorization layer, not
    this repository method). This is exactly the scenario RLS exists to backstop: prove that
    even this real application code path can't read another user's row once RLS is live,
    independent of whether some future caller forgets to check ownership above it.
    """
    agent_a, user_a = _create_agent(owner_session, username="user-repo-a")
    agent_b, _ = _create_agent(owner_session, username="user-repo-b")

    restricted_factory = build_sessionmaker(restricted_engine)
    restricted_session = restricted_factory()
    token = current_user_id.set(user_a)
    try:
        repo = SqlAlchemyAgentRepository(restricted_session)
        own_agent = repo.get_by_id(agent_a)
        other_agent = repo.get_by_id(agent_b)
        restricted_session.commit()
    finally:
        current_user_id.reset(token)
        restricted_session.close()

    assert own_agent is not None
    assert own_agent.agent_id == agent_a
    assert other_agent is None
