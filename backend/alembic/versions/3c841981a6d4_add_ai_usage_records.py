"""add ai usage records

Revision ID: 3c841981a6d4
Revises: e0429480c207
Create Date: 2026-09-21 10:01:35.991273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c841981a6d4'
down_revision: Union[str, Sequence[str], None] = 'e0429480c207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ai_usage_records (AI usage cap, 2026-09-21 security pass).

    Hand-written, not the raw autogenerate output: autogenerate also proposed dropping the
    knowledge_chunk_fts* SQLite FTS5 shadow tables, the same known false positive already
    stripped out of e0429480c207 (they're created by raw SQL at runtime, never tracked in
    SQLAlchemy metadata).
    """
    op.create_table(
        'ai_usage_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tokens', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_usage_records_user_id_recorded_at', 'ai_usage_records', ['user_id', 'recorded_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ai_usage_records_user_id_recorded_at', table_name='ai_usage_records')
    op.drop_table('ai_usage_records')
