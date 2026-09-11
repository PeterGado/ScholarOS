from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.modules.knowledge.domain.enums import CreatedBy, KnowledgeElementStatus, KnowledgeElementType


@dataclass
class KnowledgeElement:
    """An individual unit of interpreted understanding (04_Logical_Data_Model.md §3.5).
    Stage 5's persisted output - genuinely classified, never a placeholder (see
    TextChunkCandidate's docstring for why Stage 4 could not create these).
    """

    agent_id: int
    element_type: KnowledgeElementType
    label: str
    element_id: int | None = None
    description: str | None = None
    status: KnowledgeElementStatus = KnowledgeElementStatus.CURRENT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: CreatedBy = CreatedBy.SYSTEM
    superseded_element_id: int | None = None
    superseded_at: datetime | None = None


@dataclass
class KnowledgeChunk:
    """A discrete retrievable unit of interpreted knowledge (04_Logical_Data_Model.md §3.7),
    derived from a KnowledgeElement - not a raw text fragment.
    """

    agent_id: int
    element_id: int
    content: str
    chunk_id: int | None = None
    summary: str | None = None
    status: KnowledgeElementStatus = KnowledgeElementStatus.CURRENT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None


@dataclass
class ChunkEvidenceLink:
    """First-class evidence association between a Knowledge Chunk and the Research Document
    it draws from (04_Logical_Data_Model.md §4.1). Immutable once created.
    """

    chunk_id: int
    document_id: int
    link_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: CreatedBy = CreatedBy.SYSTEM


@dataclass
class ChunkEmbedding:
    """A Knowledge Chunk's retrieval vector (04_Logical_Data_Model.md §3.7 note; ADR-004
    Decision 3; ADR-005 Decision 5) - derived data, never a source of truth, rebuildable from
    the structured core (06_Physical_Design_Strategy.md §7).
    """

    chunk_id: int
    embedding_vector: list[float]
    embedding_model_version: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class TextChunkCandidate:
    """A mechanically-produced, transient text segment - deliberately NOT the persisted
    `KnowledgeChunk` entity (04_Logical_Data_Model.md §3.7).

    `KnowledgeChunk.element_id` is a not-null foreign key to `Knowledge Element`, and every
    Knowledge Element type (concept/theme/method/claim/relationship) means genuine semantic
    interpretation everywhere it is defined (02_Domain_Model.md §4; 02_System_Components.md
    §3.3; 04_AI_Architecture.md §7). Stage 4 performs no semantic interpretation - it only
    extracts, normalizes, and mechanically segments text - so it must not create Knowledge
    Element or Knowledge Chunk rows. `TextChunkCandidate` is this stage's actual output: an
    in-memory value object that a later, AI-assisted stage consumes to produce real Knowledge
    Elements and Knowledge Chunks. No fake/placeholder Knowledge Element is created to work
    around this - see Stage 4's completion report, "Deviations".
    """

    document_id: int
    sequence_number: int
    text: str
    start_offset: int
    end_offset: int
