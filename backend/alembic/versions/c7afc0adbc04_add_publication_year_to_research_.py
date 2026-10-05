"""add publication_year to research_documents

Revision ID: c7afc0adbc04
Revises: 988ef4146382
Create Date: 2026-10-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7afc0adbc04'
down_revision: Union[str, Sequence[str], None] = '988ef4146382'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add research_documents.publication_year - a user-supplied, optional field alongside the
    existing `author` (2026-10-06, citation grounding): the AI can only cite a real "(Author,
    Year)" from a user's own uploaded source if both pieces of metadata actually exist on it.

    Batch mode for SQLite portability (local dev/tests), matching this codebase's existing
    column-add migrations (e.g. e0429480c207) - plain ALTER on Postgres (production).
    """
    with op.batch_alter_table('research_documents') as batch_op:
        batch_op.add_column(sa.Column('publication_year', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('research_documents') as batch_op:
        batch_op.drop_column('publication_year')
