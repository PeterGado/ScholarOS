"""add doi and doi_verification_status to research_documents

Revision ID: e151d6a4fdf6
Revises: c7afc0adbc04
Create Date: 2026-10-06 01:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e151d6a4fdf6'
down_revision: str | Sequence[str] | None = 'c7afc0adbc04'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add research_documents.doi and .doi_verification_status (2026-10-06, citation
    grounding): a user-supplied DOI is checked against Crossref rather than trusted at face
    value - see VerifyDocumentDoiUseCase and DoiVerificationStatus's own docstrings.

    Batch mode for SQLite portability (local dev/tests), matching this codebase's existing
    column-add migrations - plain ALTER on Postgres (production).
    """
    with op.batch_alter_table('research_documents') as batch_op:
        batch_op.add_column(sa.Column('doi', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('doi_verification_status', sa.String(length=16), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('research_documents') as batch_op:
        batch_op.drop_column('doi_verification_status')
        batch_op.drop_column('doi')
