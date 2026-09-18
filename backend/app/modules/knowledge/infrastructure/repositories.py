import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.knowledge.domain.entities import ChunkEmbedding, ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.knowledge.domain.enums import KnowledgeElementStatus
from app.modules.knowledge.domain.lexical_query import build_fts_match_query, build_postgres_tsquery
from app.modules.knowledge.domain.repositories import (
    ChunkEvidenceLinkRepository,
    KnowledgeChunkEmbeddingRepository,
    KnowledgeChunkRepository,
    KnowledgeElementRepository,
    LexicalSearchRepository,
)
from app.modules.knowledge.infrastructure.models import ChunkEvidenceLink as ChunkEvidenceLinkModel
from app.modules.knowledge.infrastructure.models import KnowledgeChunk as KnowledgeChunkModel
from app.modules.knowledge.infrastructure.models import KnowledgeElement as KnowledgeElementModel
from app.modules.knowledge.infrastructure.vector_models import KnowledgeChunkEmbedding as KnowledgeChunkEmbeddingModel


class SqlAlchemyKnowledgeElementRepository(KnowledgeElementRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, element: KnowledgeElement) -> KnowledgeElement:
        row = KnowledgeElementModel(
            agent_id=element.agent_id,
            element_type=element.element_type,
            label=element.label,
            description=element.description,
            status=element.status,
            created_by=element.created_by,
        )
        self._session.add(row)
        self._session.flush()
        element.element_id = row.element_id
        element.created_at = row.created_at
        return element


class SqlAlchemyKnowledgeChunkRepository(KnowledgeChunkRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, chunk: KnowledgeChunk) -> KnowledgeChunk:
        row = KnowledgeChunkModel(
            agent_id=chunk.agent_id,
            element_id=chunk.element_id,
            content=chunk.content,
            summary=chunk.summary,
            status=chunk.status,
        )
        self._session.add(row)
        self._session.flush()
        chunk.chunk_id = row.chunk_id
        chunk.created_at = row.created_at

        # Keeps the ADR-005 lexical index (knowledge_chunk_fts) in sync with the real Knowledge
        # Chunk row on write - there is no delete/update path for chunks anywhere in this
        # codebase (append-only, like the structured core generally), so an insert-only sync is
        # complete, not a partial implementation. `rowid` is set explicitly to `chunk_id` (see
        # init_db's own comment) so a lexical hit maps straight back with no join.
        if self._session.get_bind().dialect.name == "sqlite":
            self._session.execute(
                text("INSERT INTO knowledge_chunk_fts(rowid, content, agent_id) VALUES (:rowid, :content, :agent_id)"),
                {"rowid": row.chunk_id, "content": row.content, "agent_id": row.agent_id},
            )
        return chunk

    def get_by_id(self, chunk_id: int) -> KnowledgeChunk | None:
        row = self._session.get(KnowledgeChunkModel, chunk_id)
        return self._to_domain(row) if row is not None else None

    @staticmethod
    def _to_domain(row: KnowledgeChunkModel) -> KnowledgeChunk:
        return KnowledgeChunk(
            chunk_id=row.chunk_id,
            agent_id=row.agent_id,
            element_id=row.element_id,
            content=row.content,
            summary=row.summary,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SqlAlchemyChunkEvidenceLinkRepository(ChunkEvidenceLinkRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, link: ChunkEvidenceLink) -> ChunkEvidenceLink:
        row = ChunkEvidenceLinkModel(chunk_id=link.chunk_id, document_id=link.document_id, created_by=link.created_by)
        self._session.add(row)
        self._session.flush()
        link.link_id = row.link_id
        link.created_at = row.created_at
        return link

    def exists_for_document(self, document_id: int) -> bool:
        return (
            self._session.query(ChunkEvidenceLinkModel).filter_by(document_id=document_id).first() is not None
        )

    def list_by_document_id(self, document_id: int) -> list[ChunkEvidenceLink]:
        rows = self._session.query(ChunkEvidenceLinkModel).filter_by(document_id=document_id).all()
        return [self._to_domain(row) for row in rows]

    def list_by_chunk_id(self, chunk_id: int) -> list[ChunkEvidenceLink]:
        rows = self._session.query(ChunkEvidenceLinkModel).filter_by(chunk_id=chunk_id).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: ChunkEvidenceLinkModel) -> ChunkEvidenceLink:
        return ChunkEvidenceLink(
            link_id=row.link_id,
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            created_at=row.created_at,
            created_by=row.created_by,
        )


class SqlAlchemyKnowledgeChunkEmbeddingRepository(KnowledgeChunkEmbeddingRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, embedding: ChunkEmbedding) -> ChunkEmbedding:
        row = KnowledgeChunkEmbeddingModel(
            chunk_id=embedding.chunk_id,
            embedding_vector=json.dumps(embedding.embedding_vector),
            embedding_model_version=embedding.embedding_model_version,
        )
        self._session.add(row)
        self._session.flush()
        embedding.created_at = row.created_at
        return embedding

    def list_by_agent_id(self, agent_id: int) -> list[ChunkEmbedding]:
        """Only `current` chunks are candidates for retrieval - `superseded` chunks are
        history-bearing, not deleted (04_Logical_Data_Model.md §9/§12), but must not surface
        in normal search results (Stage 8; no reprocessing path creates `superseded` chunks
        yet, but this is the correct behavior regardless of when one first does).
        """
        rows = (
            self._session.query(KnowledgeChunkEmbeddingModel)
            .join(KnowledgeChunkModel, KnowledgeChunkEmbeddingModel.chunk_id == KnowledgeChunkModel.chunk_id)
            .filter(KnowledgeChunkModel.agent_id == agent_id, KnowledgeChunkModel.status == KnowledgeElementStatus.CURRENT)
            .all()
        )
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: KnowledgeChunkEmbeddingModel) -> ChunkEmbedding:
        return ChunkEmbedding(
            chunk_id=row.chunk_id,
            embedding_vector=json.loads(row.embedding_vector),
            embedding_model_version=row.embedding_model_version,
            created_at=row.created_at,
        )


class SqlAlchemyLexicalSearchRepository(LexicalSearchRepository):
    """ADR-005 Decision 1's lexical branch. Dialect-aware: SQLite FTS5 (`knowledge_chunk_fts`,
    kept in sync by `SqlAlchemyKnowledgeChunkRepository.add`) or Postgres `tsvector`/GIN (the
    `knowledge_chunks.search_vector` generated column, maintained by Postgres itself on every
    write - no application-side sync needed on that dialect, unlike SQLite's shadow table).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, *, agent_id: int, query: str, limit: int) -> list[int]:
        if self._session.get_bind().dialect.name == "postgresql":
            return self._search_postgres(agent_id=agent_id, query=query, limit=limit)
        return self._search_sqlite(agent_id=agent_id, query=query, limit=limit)

    def _search_sqlite(self, *, agent_id: int, query: str, limit: int) -> list[int]:
        match_query = build_fts_match_query(query)
        if not match_query:
            return []

        # Joined against the real knowledge_chunks table (not just the FTS5 index's own
        # agent_id column) to apply the same `status = current` filter the semantic branch
        # already applies (KnowledgeChunkEmbeddingRepository.list_by_agent_id) - without this,
        # lexical search could surface a superseded chunk the semantic branch would never
        # return, a real inconsistency between the two branches of one "hybrid" result set.
        # `KnowledgeElementStatus.CURRENT.name` (not `.value`) matches this column's actual
        # stored representation - SQLAlchemy's default Enum column stores the member name, a
        # pre-existing, flagged deviation in this module (see KnowledgeChunkModel's own status
        # column), not something this query should silently get wrong by assuming `.value`.
        # The FTS5 MATCH is isolated in its own subquery, then joined against the real table -
        # bm25()/MATCH resolved against an aliased FTS5 table in the same top-level FROM/JOIN as
        # another table raises "no such column" on SQLite's query planner; this form sidesteps
        # that entirely rather than depending on alias-resolution quirks.
        rows = self._session.execute(
            text(
                "SELECT c.chunk_id AS chunk_id FROM ("
                "  SELECT rowid, bm25(knowledge_chunk_fts) AS score FROM knowledge_chunk_fts "
                "  WHERE knowledge_chunk_fts MATCH :match_query AND agent_id = :agent_id"
                ") AS m "
                "JOIN knowledge_chunks AS c ON c.chunk_id = m.rowid "
                "WHERE c.status = :status "
                "ORDER BY m.score "  # bm25(): lower is a better match
                "LIMIT :limit"
            ),
            {
                "match_query": match_query,
                "agent_id": agent_id,
                "status": KnowledgeElementStatus.CURRENT.name,
                "limit": limit,
            },
        )
        return [row.chunk_id for row in rows]

    def _search_postgres(self, *, agent_id: int, query: str, limit: int) -> list[int]:
        tsquery = build_postgres_tsquery(query)
        if not tsquery:
            return []

        rows = self._session.execute(
            text(
                "SELECT chunk_id FROM knowledge_chunks "
                "WHERE agent_id = :agent_id AND status = :status "
                "AND search_vector @@ to_tsquery('english', :tsquery) "
                "ORDER BY ts_rank(search_vector, to_tsquery('english', :tsquery)) DESC "  # higher is better
                "LIMIT :limit"
            ),
            {
                "tsquery": tsquery,
                "agent_id": agent_id,
                "status": KnowledgeElementStatus.CURRENT.name,
                "limit": limit,
            },
        )
        return [row.chunk_id for row in rows]
