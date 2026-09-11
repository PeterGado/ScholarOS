import json

from sqlalchemy.orm import Session

from app.modules.knowledge.domain.entities import ChunkEmbedding, ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement
from app.modules.knowledge.domain.enums import KnowledgeElementStatus
from app.modules.knowledge.domain.repositories import (
    ChunkEvidenceLinkRepository,
    KnowledgeChunkEmbeddingRepository,
    KnowledgeChunkRepository,
    KnowledgeElementRepository,
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
