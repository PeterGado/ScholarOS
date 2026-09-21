"""add row level security policies

Revision ID: cff25673e0e3
Revises: 4d323d592976
Create Date: 2026-09-21 20:01:23.140213

Row-Level Security (2026-09-21, second infra/scaling security pass): a second, defense-in-
depth layer of tenant isolation underneath the app's own real, tested query-level filtering
(app.database.rls_context / the Postgres-only "begin" listener in app.database.session sets
the `app.current_user_id` session variable every transaction reads). If a future query ever
forgets a WHERE clause, Postgres itself denies the cross-tenant rows instead of leaking them.

Step 1 of a 5-step rollout (see the approved plan) - this migration only ENABLES RLS and
creates policies; it does NOT force them. The running app still connects as the Postgres
table-owner role (which bypasses RLS by default regardless of policies), so this migration is
a pure no-op for production until a later, separate step switches the app to a restricted,
non-owner role. Deliberately split this way so enabling RLS itself carries zero deploy risk.

Every table's policy condition walks its real foreign-key chain back to `agents.user_id` (the
ownership root next to `users` itself), confirmed against the live model files, not guessed:
  - Direct owner column: agents, writing_profiles, ai_usage_records.
  - One hop via agents: projects, knowledge_elements, knowledge_chunks, memory_records,
    conversations.
  - Two-plus hops: research_documents (via projects), profile_characteristics (via
    writing_profiles), knowledge_chunk_embeddings (via knowledge_chunks), memory_provenance_links
    (via memory_records), messages (via conversations), profile_characteristic_sources (via
    profile_characteristics), message_context_links (via messages, its only always-non-null FK
    on an exclusive-arc table).
  - chunk_evidence_links has two independent FK chains (chunk_id and document_id) - its policy
    requires BOTH to resolve to the current user, defensively, not just for convenience.

Deliberately excluded, each for a stated reason (not silent gaps):
  - users - the ownership root itself, not owned by anyone.
  - sessions (app/auth/models.py) - this is what ESTABLISHES identity in the first place;
    AuthService.verify_token looks a session up by token hash before any user_id is known, so
    RLS'ing this table would create a chicken-and-egg problem on the very first query of every
    request. Already protected by a cryptographically random token-hash lookup - a different,
    adequate protection model for a table looked up by secret, not by owner.
  - work_items (app/workers/models.py) - confirmed no FK to anything at all, a free-text
    payload_reference outbox. No ownership chain exists to express as RLS.
  - rate_limit_counters (app/core/rate_limit_models.py) - not user content.

`app_current_user_id()` centralizes `current_setting('app.current_user_id', true)` so it isn't
repeated (and isn't at risk of a typo) 16 times; `true` (missing_ok) makes it return NULL when
the session variable was never referenced at all on this connection. But a *pooled* connection
that previously had it set via `set_config(..., true)` (transaction-local) reverts to an empty
string, not NULL, once that transaction ends and a later transaction never re-sets it - a real,
live-tested Postgres behavior (confirmed by hand against a real local instance before writing
this), not a hypothetical. `''::int` raises a hard cast error rather than evaluating to NULL,
so a naive `current_setting(...)::int` would make every RLS-protected query on an
already-used-then-anonymous pooled connection fail with a 500 instead of failing closed.
`NULLIF(..., '')` folds that empty-string case back to NULL before the cast, so both "never
touched this connection" and "reverted after a prior transaction" behave identically: NULL,
`column = NULL` is always false in SQL, every policy fails closed with no special-casing.

Gated to no-op on SQLite (`bind.dialect.name != "postgresql"`), matching the existing
`is_sqlite` gating idiom already used elsewhere in this codebase (see build_engine) - RLS is a
Postgres-only concept, irrelevant to local dev/test.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'cff25673e0e3'
down_revision: Union[str, Sequence[str], None] = '4d323d592976'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RLS_TABLES: list[tuple[str, str]] = [
    ("agents", "user_id = app_current_user_id()"),
    ("writing_profiles", "user_id = app_current_user_id()"),
    ("ai_usage_records", "user_id = app_current_user_id()"),
    (
        "projects",
        """EXISTS (
            SELECT 1 FROM agents a
            WHERE a.agent_id = projects.agent_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "knowledge_elements",
        """EXISTS (
            SELECT 1 FROM agents a
            WHERE a.agent_id = knowledge_elements.agent_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "knowledge_chunks",
        """EXISTS (
            SELECT 1 FROM agents a
            WHERE a.agent_id = knowledge_chunks.agent_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "memory_records",
        """EXISTS (
            SELECT 1 FROM agents a
            WHERE a.agent_id = memory_records.agent_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "conversations",
        """EXISTS (
            SELECT 1 FROM agents a
            WHERE a.agent_id = conversations.agent_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "research_documents",
        """EXISTS (
            SELECT 1 FROM projects p
            JOIN agents a ON a.agent_id = p.agent_id
            WHERE p.project_id = research_documents.project_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "profile_characteristics",
        """EXISTS (
            SELECT 1 FROM writing_profiles wp
            WHERE wp.profile_id = profile_characteristics.profile_id
              AND wp.user_id = app_current_user_id()
        )""",
    ),
    (
        "knowledge_chunk_embeddings",
        """EXISTS (
            SELECT 1 FROM knowledge_chunks kc
            JOIN agents a ON a.agent_id = kc.agent_id
            WHERE kc.chunk_id = knowledge_chunk_embeddings.chunk_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "chunk_evidence_links",
        """EXISTS (
            SELECT 1 FROM knowledge_chunks kc
            JOIN agents a ON a.agent_id = kc.agent_id
            WHERE kc.chunk_id = chunk_evidence_links.chunk_id
              AND a.user_id = app_current_user_id()
        ) AND EXISTS (
            SELECT 1 FROM research_documents rd
            JOIN projects p ON p.project_id = rd.project_id
            JOIN agents a2 ON a2.agent_id = p.agent_id
            WHERE rd.document_id = chunk_evidence_links.document_id
              AND a2.user_id = app_current_user_id()
        )""",
    ),
    (
        "memory_provenance_links",
        """EXISTS (
            SELECT 1 FROM memory_records mr
            JOIN agents a ON a.agent_id = mr.agent_id
            WHERE mr.record_id = memory_provenance_links.record_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "messages",
        """EXISTS (
            SELECT 1 FROM conversations c
            JOIN agents a ON a.agent_id = c.agent_id
            WHERE c.conversation_id = messages.conversation_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
    (
        "profile_characteristic_sources",
        """EXISTS (
            SELECT 1 FROM profile_characteristics pc
            JOIN writing_profiles wp ON wp.profile_id = pc.profile_id
            WHERE pc.characteristic_id = profile_characteristic_sources.characteristic_id
              AND wp.user_id = app_current_user_id()
        )""",
    ),
    (
        "message_context_links",
        """EXISTS (
            SELECT 1 FROM messages m
            JOIN conversations c ON c.conversation_id = m.conversation_id
            JOIN agents a ON a.agent_id = c.agent_id
            WHERE m.message_id = message_context_links.message_id
              AND a.user_id = app_current_user_id()
        )""",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_user_id() RETURNS integer
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.current_user_id', true), '')::int
        $$;
        """
    )
    for table_name, condition_sql in RLS_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            f"USING ({condition_sql}) WITH CHECK ({condition_sql});"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name, _ in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name};")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP FUNCTION IF EXISTS app_current_user_id();")
