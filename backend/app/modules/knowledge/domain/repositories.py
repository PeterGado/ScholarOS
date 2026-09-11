from abc import ABC, abstractmethod

from app.modules.knowledge.domain.entities import ChunkEmbedding, ChunkEvidenceLink, KnowledgeChunk, KnowledgeElement


class KnowledgeElementRepository(ABC):
    @abstractmethod
    def add(self, element: KnowledgeElement) -> KnowledgeElement: ...


class KnowledgeChunkRepository(ABC):
    @abstractmethod
    def add(self, chunk: KnowledgeChunk) -> KnowledgeChunk: ...

    @abstractmethod
    def get_by_id(self, chunk_id: int) -> KnowledgeChunk | None: ...


class ChunkEvidenceLinkRepository(ABC):
    @abstractmethod
    def add(self, link: ChunkEvidenceLink) -> ChunkEvidenceLink: ...

    @abstractmethod
    def exists_for_document(self, document_id: int) -> bool: ...

    @abstractmethod
    def list_by_document_id(self, document_id: int) -> list[ChunkEvidenceLink]: ...

    @abstractmethod
    def list_by_chunk_id(self, chunk_id: int) -> list[ChunkEvidenceLink]:
        """Added Stage 8: retrieval needs to answer "which document(s) produced this chunk"
        for provenance, the reverse direction of `list_by_document_id`.
        """
        ...


class KnowledgeChunkEmbeddingRepository(ABC):
    @abstractmethod
    def add(self, embedding: ChunkEmbedding) -> ChunkEmbedding: ...

    @abstractmethod
    def list_by_agent_id(self, agent_id: int) -> list[ChunkEmbedding]:
        """Scoped by Agent via a join through Knowledge Chunk - the embeddings table itself
        carries no agent_id (it is keyed only by chunk_id, 04_Logical_Data_Model.md §3.7 note).
        """
        ...
