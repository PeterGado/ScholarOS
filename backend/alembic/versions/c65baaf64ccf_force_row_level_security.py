"""force row level security

Revision ID: c65baaf64ccf
Revises: 2e1d18abf226
Create Date: 2026-09-21 21:56:47.647652

Row-Level Security (2026-09-21, second infra/scaling security pass), step 5 (final) of the
5-step rollout: `FORCE ROW LEVEL SECURITY` on all 16 policy-protected tables.

Not load-bearing for current production behavior - the app already connects as the restricted
`scholaros_app` role (step 4, cut over and live-verified via a real write+read against
production), which has no table ownership and no `BYPASSRLS` attribute, so RLS policies were
already being enforced before this migration. `FORCE` only matters for the table *owner* role
(`neondb_owner`, confirmed via a live `pg_roles` query to have `rolbypassrls = true`, which
FORCE cannot override anyway) or any future role with elevated privileges - this closes that
door specifically against future role/ownership drift (e.g. a later change that accidentally
points the app back at an owner-equivalent role), not against anything active today.

Table names mirror RLS_TABLES in the "add row level security policies" migration
(cff25673e0e3) exactly - duplicated as a plain list rather than imported, since alembic/versions
has no __init__.py and isn't a real importable package (see that same reasoning in
tests/integration/test_row_level_security.py).

Gated to no-op on SQLite, matching every other Postgres-only migration in this project.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c65baaf64ccf'
down_revision: Union[str, Sequence[str], None] = '2e1d18abf226'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLE_NAMES: list[str] = [
    "agents",
    "writing_profiles",
    "ai_usage_records",
    "projects",
    "knowledge_elements",
    "knowledge_chunks",
    "memory_records",
    "conversations",
    "research_documents",
    "profile_characteristics",
    "knowledge_chunk_embeddings",
    "chunk_evidence_links",
    "memory_provenance_links",
    "messages",
    "profile_characteristic_sources",
    "message_context_links",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in RLS_TABLE_NAMES:
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in RLS_TABLE_NAMES:
        op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY;")
