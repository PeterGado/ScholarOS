"""add google sign-in fields

Revision ID: e0429480c207
Revises: 2dc6158c48d9
Create Date: 2026-09-20 23:00:27.506912

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0429480c207'
down_revision: Union[str, Sequence[str], None] = '2dc6158c48d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add email/google_subject to users (Google Sign-In, 2026-09-20).

    Hand-written, not the raw autogenerate output: autogenerate also proposed dropping the
    knowledge_chunk_fts* SQLite FTS5 shadow tables, which are created by raw SQL at runtime
    (app.modules.knowledge.infrastructure), not tracked in SQLAlchemy metadata at all - a false
    positive, not a real schema difference, stripped out here.

    Uses batch mode because SQLite (local dev/tests) has no `ALTER TABLE ADD CONSTRAINT`; batch
    mode recreates the table there while emitting plain ALTER statements on Postgres (production)
    - the same portable approach either dialect needs, not SQLite-specific special-casing.
    """
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('google_subject', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_users_email', ['email'])
        batch_op.create_unique_constraint('uq_users_google_subject', ['google_subject'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('uq_users_google_subject', type_='unique')
        batch_op.drop_constraint('uq_users_email', type_='unique')
        batch_op.drop_column('google_subject')
        batch_op.drop_column('email')
