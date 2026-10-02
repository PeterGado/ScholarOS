"""add writing segments table

Revision ID: 988ef4146382
Revises: b017cd8cd1c0
Create Date: 2026-10-02 00:00:00.000000

Writing Segments (2026-10-02): a named part of the project (e.g. "Background of the Study",
"Statement of the Problem") with its own saved writing instructions, requested directly by the
project owner ("extra instructions for different segments of the project"). Agent-scoped, like
writing_profiles and memory_records.

This is a brand-new table with no existing production data, so all three Row-Level Security
steps (ENABLE, CREATE POLICY, FORCE) are done together here in one migration rather than the
staged 3-of-5 rollout the original tables went through (cff25673e0e3/c65baaf64ccf) - that
staging existed specifically to give an already-live, owner-role-connected app a zero-risk path
to RLS; a table that doesn't exist yet in production carries none of that risk. The policy
condition mirrors memory_records' own one-hop-via-agents shape exactly (confirmed against that
table's real policy in cff25673e0e3), and reuses the existing `app_current_user_id()` function
rather than redefining it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '988ef4146382'
down_revision: Union[str, Sequence[str], None] = 'b017cd8cd1c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'writing_segments',
        sa.Column('segment_id', sa.Integer(), primary_key=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.agent_id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('agent_id', 'name', name='uq_writing_segment_agent_name'),
    )
    op.create_index('ix_writing_segments_agent_id', 'writing_segments', ['agent_id'], unique=False)

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE writing_segments ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY tenant_isolation ON writing_segments "
        "USING (EXISTS ("
        "    SELECT 1 FROM agents a"
        "    WHERE a.agent_id = writing_segments.agent_id"
        "      AND a.user_id = app_current_user_id()"
        ")) "
        "WITH CHECK (EXISTS ("
        "    SELECT 1 FROM agents a"
        "    WHERE a.agent_id = writing_segments.agent_id"
        "      AND a.user_id = app_current_user_id()"
        "));"
    )
    op.execute("ALTER TABLE writing_segments FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON writing_segments;")
        op.execute("ALTER TABLE writing_segments NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE writing_segments DISABLE ROW LEVEL SECURITY;")

    op.drop_index('ix_writing_segments_agent_id', table_name='writing_segments')
    op.drop_table('writing_segments')
