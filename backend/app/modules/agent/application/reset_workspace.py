from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository

# Leaf-to-root deletion order across every table that (directly or transitively) hangs off one
# Agent. SQLite foreign keys are enforced in this codebase (app/database/base.py: `PRAGMA
# foreign_keys=ON`), so children must always be removed before their parents or the delete is
# rejected. Each statement is scoped to exactly one agent_id via a subquery chain - never a
# bare `DELETE FROM <table>` - so a bug here fails loudly (an unrelated agent's rows are simply
# never matched) rather than silently wiping every user's data.
_DELETE_STATEMENTS = [
    """DELETE FROM message_context_links WHERE message_id IN (
        SELECT message_id FROM messages WHERE conversation_id IN (
            SELECT conversation_id FROM conversations WHERE agent_id = :agent_id
        )
    )""",
    "DELETE FROM messages WHERE conversation_id IN (SELECT conversation_id FROM conversations WHERE agent_id = :agent_id)",
    "DELETE FROM memory_provenance_links WHERE record_id IN (SELECT record_id FROM memory_records WHERE agent_id = :agent_id)",
    # memory_records.superseded_record_id is self-referential - null it out before deleting.
    "UPDATE memory_records SET superseded_record_id = NULL WHERE agent_id = :agent_id",
    "DELETE FROM memory_records WHERE agent_id = :agent_id",
    """DELETE FROM profile_characteristic_sources WHERE characteristic_id IN (
        SELECT characteristic_id FROM profile_characteristics WHERE profile_id IN (
            SELECT profile_id FROM writing_profiles WHERE agent_id = :agent_id
        )
    )""",
    """DELETE FROM profile_characteristics WHERE profile_id IN (
        SELECT profile_id FROM writing_profiles WHERE agent_id = :agent_id
    )""",
    "DELETE FROM writing_profiles WHERE agent_id = :agent_id",
    "DELETE FROM chunk_evidence_links WHERE chunk_id IN (SELECT chunk_id FROM knowledge_chunks WHERE agent_id = :agent_id)",
    "DELETE FROM knowledge_chunk_embeddings WHERE chunk_id IN (SELECT chunk_id FROM knowledge_chunks WHERE agent_id = :agent_id)",
    "DELETE FROM knowledge_chunks WHERE agent_id = :agent_id",
    "DELETE FROM knowledge_elements WHERE agent_id = :agent_id",
    "DELETE FROM conversations WHERE agent_id = :agent_id",
    "DELETE FROM research_documents WHERE project_id IN (SELECT project_id FROM projects WHERE agent_id = :agent_id)",
    "DELETE FROM projects WHERE agent_id = :agent_id",
    "DELETE FROM agents WHERE agent_id = :agent_id",
]
"""Not cleaned up here: Work Items referencing this agent's now-deleted documents by a string
`payload_reference` (no FK, so nothing blocks their deletion either way). Left in place
deliberately - almost always already `succeeded` by the time a reset happens, and a stale
`failed`/`queued` Work Item referencing a gone row is inert (never re-read by anything else,
simply fails harmlessly with a not-found error if the executor ever claims it). Not worth the
fragility of string-matching payload_reference values to clean up proactively.
"""


class ResetAgentWorkspaceUseCase:
    """Permanently and irreversibly deletes everything in the authenticated user's Agent
    Workspace - Project, research documents, extracted knowledge, writing profile and
    characteristics, memory records and provenance, conversations and messages - and the
    Agent row itself, so the user can go through onboarding again from a clean slate
    (`AgentRepository.get_by_user_id` returns `None` afterward, exactly the "no workspace yet"
    state `POST /agents` already requires).

    A deliberate, narrow exception to this codebase's per-module repository pattern: wiping an
    entire tenant's data is a genuinely cross-cutting infrastructure operation (nearly every
    module has agent-scoped tables), not a normal per-aggregate write - the same shape a real
    "delete my data" tool takes in any real system. This is the only use case in the codebase
    that takes a raw `Session`; nothing else should reach across modules like this.

    Hard delete, not soft delete - there is no undo. The route calling this is responsible for
    requiring explicit confirmation before ever invoking it; this use case itself only checks
    ownership (the user has an Agent to reset) and does not ask twice.
    """

    def __init__(self, agent_repository: AgentRepository, session: Session, unit_of_work: UnitOfWork) -> None:
        self._agents = agent_repository
        self._session = session
        self._uow = unit_of_work

    def execute(self, *, user_id: int) -> None:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        try:
            for statement in _DELETE_STATEMENTS:
                self._session.execute(text(statement), {"agent_id": agent.agent_id})
            # ADR-005's SQLite lexical index (knowledge_chunk_fts) is a derived shadow table
            # with no foreign key to knowledge_chunks - deleting the real rows above leaves it
            # with orphaned entries. Found via this exact reset-then-reuse flow: SQLite reuses
            # a deleted rowid the moment the table becomes empty (no AUTOINCREMENT on
            # KnowledgeChunkModel), so the very next chunk created after a reset could collide
            # with a still-present orphaned FTS5 row's rowid, failing the insert outright.
            # Postgres needs no equivalent - its lexical index is a generated column on
            # knowledge_chunks itself, deleted automatically with the row.
            if self._session.get_bind().dialect.name == "sqlite":
                self._session.execute(text("DELETE FROM knowledge_chunk_fts WHERE agent_id = :agent_id"), {"agent_id": agent.agent_id})
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
