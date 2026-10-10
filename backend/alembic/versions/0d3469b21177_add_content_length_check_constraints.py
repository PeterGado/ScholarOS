"""add content length check constraints

Revision ID: 0d3469b21177
Revises: 1791af381140
Create Date: 2026-10-10 00:00:00.000000

Defense-in-depth only (2026-10-10, production-readiness pass): `messages.content` and
`knowledge_chunks.content` were plain `Text` with no DB-level bound. The user's own outgoing
chat message is already capped at 8000 chars at the API boundary, but an AI reply writes into
the same `messages.content` column through the background Work Item executor, never through
that schema - so the column itself was genuinely unbounded for that path. Knowledge chunks are
never meant to exceed the ~1000-char chunking target by much.

On Postgres, both constraints are added `NOT VALID` via raw SQL rather than through
`op.create_check_constraint` (which validates every existing row and would fail the whole
migration if any row already exceeds the new bound - unknown without querying production,
which this pass could not do). `NOT VALID` enforces the constraint on every new INSERT/UPDATE
from this point forward without retroactively checking (and risking a hard failure on) rows
that already exist. Existing oversized rows, if any, are grandfathered in rather than migration-
blocking; this is an accepted tradeoff, not an oversight. On SQLite (dev/test), a batch rebuild
is required anyway for any ALTER, and a fresh `create_all()` already applies the constraint
plainly via the model's own `__table_args__`, so no NOT VALID equivalent exists or is needed.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d3469b21177"
down_revision: str | Sequence[str] | None = "1791af381140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE messages ADD CONSTRAINT ck_messages_content_length "
            "CHECK (length(content) <= 40000) NOT VALID"
        )
        op.execute(
            "ALTER TABLE knowledge_chunks ADD CONSTRAINT ck_knowledge_chunks_content_length "
            "CHECK (length(content) <= 10000) NOT VALID"
        )
    else:
        with op.batch_alter_table("messages") as batch_op:
            batch_op.create_check_constraint("ck_messages_content_length", "length(content) <= 40000")
        with op.batch_alter_table("knowledge_chunks") as batch_op:
            batch_op.create_check_constraint(
                "ck_knowledge_chunks_content_length", "length(content) <= 10000"
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE messages DROP CONSTRAINT ck_messages_content_length")
        op.execute("ALTER TABLE knowledge_chunks DROP CONSTRAINT ck_knowledge_chunks_content_length")
    else:
        with op.batch_alter_table("messages") as batch_op:
            batch_op.drop_constraint("ck_messages_content_length", type_="check")
        with op.batch_alter_table("knowledge_chunks") as batch_op:
            batch_op.drop_constraint("ck_knowledge_chunks_content_length", type_="check")
