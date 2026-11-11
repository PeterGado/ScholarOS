"""add google sign-in fields

Revision ID: e0429480c207
Revises: 2dc6158c48d9
Create Date: 2026-09-20 23:00:27.506912

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.database.migration_helpers import (
    existing_columns,
    existing_unique_constraint_names,
)

# revision identifiers, used by Alembic.
revision: str = 'e0429480c207'
down_revision: str | Sequence[str] | None = '2dc6158c48d9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add email/google_subject to users (Google Sign-In, 2026-09-20).

    Hand-written, not the raw autogenerate output: autogenerate also proposed dropping the
    knowledge_chunk_fts* SQLite FTS5 shadow tables, which are created by raw SQL at runtime
    (app.modules.knowledge.infrastructure), not tracked in SQLAlchemy metadata at all - a false
    positive, not a real schema difference, stripped out here.

    Uses batch mode because SQLite (local dev/tests) has no `ALTER TABLE ADD CONSTRAINT`; batch
    mode recreates the table there while emitting plain ALTER statements on Postgres (production)
    - the same portable approach either dialect needs, not SQLite-specific special-casing.

    Idempotent (2026-11-06): a `users` table bootstrapped by `create_all()` before this
    revision exists but has neither column, so each addition and constraint is guarded. Nothing
    is skipped on a database that reached this revision through the normal migration path.
    """
    already_present = existing_columns('users')
    already_constrained = existing_unique_constraint_names('users')
    with op.batch_alter_table('users') as batch_op:
        if 'email' not in already_present:
            batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
        if 'google_subject' not in already_present:
            batch_op.add_column(sa.Column('google_subject', sa.String(length=255), nullable=True))
        if 'uq_users_email' not in already_constrained:
            batch_op.create_unique_constraint('uq_users_email', ['email'])
        if 'uq_users_google_subject' not in already_constrained:
            batch_op.create_unique_constraint('uq_users_google_subject', ['google_subject'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('uq_users_google_subject', type_='unique')
        batch_op.drop_constraint('uq_users_email', type_='unique')
        batch_op.drop_column('google_subject')
        batch_op.drop_column('email')
