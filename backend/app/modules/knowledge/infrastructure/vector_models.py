from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

__all__ = ["KnowledgeChunkEmbedding"]


class KnowledgeChunkEmbedding(Base):
    """Vector-index realization for the MVP (ADR-004 Decision 3; ADR-005 Decision 5).

    Embeddings are derived data, kept out of the Knowledge Chunk entity itself
    (04_Logical_Data_Model.md §3.7 note) and never treated as a source of truth - rebuildable
    from the structured core (06_Physical_Design_Strategy.md §7). `embedding_vector` is a
    JSON-encoded list of floats: simplest, dependency-free realization for the MVP corpus
    size (Backend_Slice2_Implementation_Plan.md §6/§19 item 3) - a storage-format detail, not
    a retrieval-contract change, if it is ever replaced.
    """

    __tablename__ = "knowledge_chunk_embeddings"

    chunk_id: Mapped[int] = mapped_column(ForeignKey("knowledge_chunks.chunk_id"), primary_key=True)
    embedding_vector: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)
