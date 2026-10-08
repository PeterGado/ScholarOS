"""add index on work items state

Revision ID: b017cd8cd1c0
Revises: c65baaf64ccf
Create Date: 2026-09-30 02:08:42.342294

Concurrent-load planning (2026-09-30): `claim_next_queued` (app/workers/repository.py) has
always been a full sequential scan of `work_items` - there is no index on `state` today, in any
prior migration. Moving to `SELECT ... FOR UPDATE SKIP LOCKED` for concurrent claimers (multiple
executor worker threads) doesn't remove that scan; it just means every concurrent claimer also
has to skip past every other claimer's already-locked row while scanning. Free and low-risk to
add now, and `work_items` only grows over time - nothing archives or prunes terminal
(`succeeded`/`failed`) rows.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b017cd8cd1c0'
down_revision: str | Sequence[str] | None = 'c65baaf64ccf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_work_items_state_work_item_id', 'work_items', ['state', 'work_item_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_work_items_state_work_item_id', table_name='work_items')
