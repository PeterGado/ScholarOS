"""add password_reset_tokens table

Revision ID: e0316c6e0352
Revises: e151d6a4fdf6
Create Date: 2026-10-06 02:00:00.000000

Password reset (2026-10-06): a single-use, time-limited token looked up by hash before any
identity is known - the same bootstrap reasoning `sessions` is excluded from Row-Level Security
for (cff25673e0e3's own docstring: "this is what ESTABLISHES identity in the first place")
applies identically here, so this table is deliberately excluded from RLS too, not a gap.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0316c6e0352'
down_revision: Union[str, Sequence[str], None] = 'e151d6a4fdf6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'password_reset_tokens',
        sa.Column('token_id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('password_reset_tokens')
