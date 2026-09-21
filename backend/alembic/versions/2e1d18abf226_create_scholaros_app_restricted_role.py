"""create scholaros app restricted role

Revision ID: 2e1d18abf226
Revises: cff25673e0e3
Create Date: 2026-09-21 20:50:19.841039

Row-Level Security (2026-09-21, second infra/scaling security pass), step 2 of the 5-step
rollout: creates the restricted, non-owner Postgres role the running app will eventually
connect as (`scholaros_app`), so the RLS policies from the previous migration stop being
bypassed by the table-owner role currently in use. Deliberately its own migration/deploy,
separate from actually switching the app to use this role (see app.core.config's
`app_database_url` and app.database.session - unused until that later, explicit cutover step).

No password is set here - `LOGIN` with no `PASSWORD` clause creates a role that cannot actually
authenticate until `ALTER ROLE scholaros_app WITH PASSWORD '...'` is run separately, out-of-
band, directly against the real database - never as a literal in a committed migration.

`NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`: no privilege beyond ordinary CRUD on
application tables - specifically no DDL rights, so this role structurally cannot run a
migration even if `APP_DATABASE_URL` were ever pointed at `alembic` by mistake (migrations
always run as the owner role, via `DATABASE_URL`, unchanged).

`ALTER DEFAULT PRIVILEGES` (run as the owner role, since Alembic always connects as owner) so a
FUTURE migration's new table automatically grants to `scholaros_app` too, without this
migration needing to be revisited every time a table is added - it only affects objects created
by the same role that runs it (the owner), matching how every migration already runs.

Grants are database-wide (every application table, not just the 16 RLS-protected ones) since
the app also needs ordinary CRUD on tables RLS deliberately doesn't cover (`users`, `sessions`,
`work_items`, `rate_limit_counters` - see the previous migration's docstring for why those are
excluded from RLS specifically, not from the app's normal access).

Gated to no-op on SQLite, matching every other Postgres-only migration in this project.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2e1d18abf226'
down_revision: Union[str, Sequence[str], None] = 'cff25673e0e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_NAME = "scholaros_app"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE_NAME}') THEN
                CREATE ROLE {ROLE_NAME} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_NAME};")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE_NAME};")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE_NAME};")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ROLE_NAME};"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {ROLE_NAME};"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {ROLE_NAME};")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {ROLE_NAME};")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE_NAME}') THEN
                EXECUTE 'DROP OWNED BY {ROLE_NAME}';
                EXECUTE 'DROP ROLE {ROLE_NAME}';
            END IF;
        END
        $$;
        """
    )
