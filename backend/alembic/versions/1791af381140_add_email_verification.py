"""add email verification

Revision ID: 1791af381140
Revises: e0316c6e0352
Create Date: 2026-10-06 19:01:33.323454

Email verification (2026-10-06, external security review): gates document upload and chat on
a confirmed email for password accounts. `email_verified` defaults true at the DDL level so
every row that exists before this migration runs is grandfathered verified with zero
disruption - only a password account created after this ships (via RegisterUserUseCase, which
explicitly passes False) ever starts out unverified. email_verification_tokens mirrors
password_reset_tokens exactly, including its exclusion from Row-Level Security (same bootstrap
reasoning: looked up by hash, e0316c6e0352's own docstring).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1791af381140'
down_revision: str | Sequence[str] | None = 'e0316c6e0352'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        'email_verification_tokens',
        sa.Column('token_id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('email_verification_tokens')
    op.drop_column('users', 'email_verified')
