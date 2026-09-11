from app.ai.providers.base import EmbeddingProvider, TextGenerationProvider
from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.exceptions import ResearchDocumentNotFoundError
from app.modules.document.domain.ports import ContentStore
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.knowledge.domain.chunking import chunk_text
from app.modules.knowledge.domain.entities import (
    ChunkEmbedding,
    ChunkEvidenceLink,
    KnowledgeChunk,
    KnowledgeElement,
    TextChunkCandidate,
)
from app.modules.knowledge.domain.exceptions import AgentResolutionError, MissingStoredContentError
from app.modules.knowledge.domain.repositories import (
    ChunkEvidenceLinkRepository,
    KnowledgeChunkEmbeddingRepository,
    KnowledgeChunkRepository,
    KnowledgeElementRepository,
)
from app.modules.knowledge.domain.semantic_classification import classify_chunk
from app.modules.knowledge.domain.text_extraction import DocumentTextExtractor
from app.modules.knowledge.domain.text_normalization import normalize_text
from app.modules.project.domain.repositories import ProjectRepository


class ProcessDocumentUseCase:
    """Stage 4 of the Knowledge Processing Pipeline (04_AI_Architecture.md §7): mechanical
    extraction, normalization, and chunking only - no semantic interpretation.

    Deliberately makes no AI provider call and writes nothing to the database. Its output,
    `list[TextChunkCandidate]`, is a transient value a later, AI-assisted stage consumes to
    produce real Knowledge Elements and Knowledge Chunks (see
    app.modules.knowledge.domain.entities.TextChunkCandidate's docstring for why). Because
    this use case has no persistence side effect, it is idempotent by construction: calling
    it twice for the same document produces the same result twice, never a duplicate row,
    because no row is ever written.

    Does not touch `ResearchDocument.processing_status` and does not interact with the Work
    Item outbox - both are the responsibility of the stage that actually persists knowledge
    (the mechanical result alone does not make a document "processed" into knowledge).
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        content_store: ContentStore,
        extractor: DocumentTextExtractor,
    ) -> None:
        self._documents = document_repository
        self._content_store = content_store
        self._extractor = extractor

    def execute(self, *, document_id: int) -> list[TextChunkCandidate]:
        document = self._documents.get_by_id(document_id)
        if document is None:
            raise ResearchDocumentNotFoundError(document_id=document_id)

        if not self._content_store.exists(document.content_reference):
            raise MissingStoredContentError(document_id=document_id, content_reference=document.content_reference)

        content = self._content_store.read(document.content_reference)
        raw_text = self._extractor.extract(content, document_id=document_id)
        normalized = normalize_text(raw_text)
        return chunk_text(normalized, document_id=document_id)


class ExtractDocumentKnowledgeUseCase:
    """Stage 5 of the Knowledge Processing Pipeline (04_AI_Architecture.md §7 stages 2 and
    6): conceptual extraction and evidence linkage. Consumes Stage 4's `TextChunkCandidate`
    output (via `ProcessDocumentUseCase`, composed not duplicated) and, through the Provider
    Abstraction gateway, produces genuinely-classified, persisted `KnowledgeElement` +
    `KnowledgeChunk` + `ChunkEvidenceLink` rows.

    Idempotent by detection, not by construction (Backend_Slice2_Stage5_Implementation_Plan.md
    §5): if the document already has evidence links, it has already been semantically
    processed, and the existing chunks are returned rather than reprocessed - the AI provider
    is not deterministic the way Stage 4's mechanical pipeline is, so idempotency must be
    enforced structurally here.

    Atomic per document: every chunk's classification and embedding is obtained *before* any
    persistence begins: if any classification or embedding call fails, nothing is written for
    that document. All persistence for a document commits together via UnitOfWork, or rolls
    back together.

    Stage 7 (Embedding & Vector Index) extended this use case to also embed each chunk,
    rather than introducing a second pass that would need to re-fetch and re-derive the same
    candidates - one atomic "gather everything from the provider, then persist everything"
    phase covers both conceptual extraction and embedding.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        process_document_use_case: ProcessDocumentUseCase,
        text_provider: TextGenerationProvider,
        embedding_provider: EmbeddingProvider,
        embedding_model_version: str,
        knowledge_element_repository: KnowledgeElementRepository,
        knowledge_chunk_repository: KnowledgeChunkRepository,
        chunk_evidence_link_repository: ChunkEvidenceLinkRepository,
        knowledge_chunk_embedding_repository: KnowledgeChunkEmbeddingRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._process_document = process_document_use_case
        self._text_provider = text_provider
        self._embedding_provider = embedding_provider
        self._embedding_model_version = embedding_model_version
        self._elements = knowledge_element_repository
        self._chunks = knowledge_chunk_repository
        self._evidence_links = chunk_evidence_link_repository
        self._embeddings = knowledge_chunk_embedding_repository
        self._uow = unit_of_work

    def execute(self, *, document_id: int) -> list[KnowledgeChunk]:
        if self._evidence_links.exists_for_document(document_id):
            return self._existing_chunks_for(document_id)

        document = self._documents.get_by_id(document_id)
        if document is None:
            raise ResearchDocumentNotFoundError(document_id=document_id)

        agent_id = self._resolve_agent_id(document.project_id, document_id=document_id)
        candidates = self._process_document.execute(document_id=document_id)

        classifications = [classify_chunk(candidate.text, self._text_provider) for candidate in candidates]
        embedding_vectors = [self._embedding_provider.embed(candidate.text) for candidate in candidates]

        try:
            persisted_chunks = self._persist(document_id, agent_id, candidates, classifications, embedding_vectors)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return persisted_chunks

    def _existing_chunks_for(self, document_id: int) -> list[KnowledgeChunk]:
        links = self._evidence_links.list_by_document_id(document_id)
        chunks = [self._chunks.get_by_id(link.chunk_id) for link in links]
        return [chunk for chunk in chunks if chunk is not None]

    def _resolve_agent_id(self, project_id: int, *, document_id: int) -> int:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise AgentResolutionError(document_id=document_id)
        agent = self._agents.get_by_id(project.agent_id)
        if agent is None:
            raise AgentResolutionError(document_id=document_id)
        return agent.agent_id

    def _persist(
        self,
        document_id: int,
        agent_id: int,
        candidates: list[TextChunkCandidate],
        classifications: list,
        embedding_vectors: list[list[float]],
    ) -> list[KnowledgeChunk]:
        persisted_chunks: list[KnowledgeChunk] = []
        for candidate, classification, embedding_vector in zip(candidates, classifications, embedding_vectors, strict=True):
            element = self._elements.add(
                KnowledgeElement(
                    agent_id=agent_id,
                    element_type=classification.element_type,
                    label=classification.label,
                    description=classification.description,
                )
            )
            chunk = self._chunks.add(KnowledgeChunk(agent_id=agent_id, element_id=element.element_id, content=candidate.text))
            self._evidence_links.add(ChunkEvidenceLink(chunk_id=chunk.chunk_id, document_id=document_id))
            self._embeddings.add(
                ChunkEmbedding(
                    chunk_id=chunk.chunk_id,
                    embedding_vector=embedding_vector,
                    embedding_model_version=self._embedding_model_version,
                )
            )
            persisted_chunks.append(chunk)
        return persisted_chunks
