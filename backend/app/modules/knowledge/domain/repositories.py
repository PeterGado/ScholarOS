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


class LexicalSearchRepository(ABC):
    """ADR-005 Decision 1's lexical branch - BM25-style keyword search over the FTS5 index
    (`knowledge_chunk_fts`, kept in sync by `KnowledgeChunkRepository.add`). Separate from
    `KnowledgeChunkRepository` itself: this is a read-only, index-backed capability with a
    fundamentally different query shape (a MATCH expression, not a primary-key lookup), the
    same separation-of-concerns `KnowledgeChunkEmbeddingRepository` already established for the
    semantic branch.
    """

    @abstractmethod
    def search(self, *, agent_id: int, query: str, limit: int) -> list[int]:
        """Returns matching chunk_ids, best match first, scoped to the caller's own Agent.
        Never raises on a query with no lexical matches or no word characters at all - both
        return an empty list, letting the semantic branch carry the result on its own."""
        ...
