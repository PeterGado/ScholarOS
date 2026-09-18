from dataclasses import dataclass

from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import DocumentPurpose
from app.modules.document.domain.exceptions import EmptyDocumentContentError
from app.modules.document.domain.ports import ContentStore
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.repositories import ProjectRepository
from app.modules.writing.domain.entities import WritingProfile
from app.modules.writing.domain.exceptions import TooManyWritingStyleSamplesError
from app.modules.writing.domain.repositories import WritingProfileRepository
from app.modules.writing.domain.style_extraction import MAX_SAMPLES_PER_EXTRACTION

DEFAULT_WRITING_PROFILE_NAME = "Primary Writing Profile"

MAX_WRITING_STYLE_SAMPLES = MAX_SAMPLES_PER_EXTRACTION
"""Reuses style_extraction's own ceiling rather than a separate magic number: extraction never
looks at more than MAX_SAMPLES_PER_EXTRACTION samples per run regardless, so allowing more
uploads than that would only let samples pile up that can never actually be used."""


@dataclass
class WritingStyleDocumentUpload:
    """The result of accepting one writing-style source document: the stored, persisted
    Research Document and the Writing Profile it is now associated with (created on first
    upload if the Agent had none yet - see UploadWritingStyleDocumentUseCase's docstring).
    """

    document: ResearchDocument
    profile: WritingProfile


class UploadWritingStyleDocumentUseCase:
    """Stage 3 of Project Writing (Writing-Style Document Ingestion): accept a user-supplied
    authored-work sample (WR-010) and persist it as material for a *later* style-extraction
    stage - no semantic analysis happens here (Stage 3 prompt §1 "Critical scope boundary").

    **Entity reuse, not invention.** The frozen Logical Data Model has no "StyleDocument" or
    equivalent entity - a writing-style sample is stored as an ordinary `ResearchDocument`
    (04_Logical_Data_Model.md §3.4), the same entity and the same table Slice 2 already uses
    for research material, reusing the same `ContentStore` abstraction and the same
    content-addressed-storage-then-persist-metadata ordering as
    `UploadResearchDocumentUseCase` (orphaned content on a failed commit is accepted as
    harmless, per that use case's own documented convention - content-addressed storage never
    duplicates or corrupts, ADR-004 §5). Tagged `DocumentPurpose.WRITING_STYLE_SAMPLE` (see
    that enum's own docstring for why this was added after Stage 3/4 first shipped without it)
    so it never bleeds into the Research Documents listing, which is scoped to
    `DocumentPurpose.RESEARCH` only.

    **Critical difference from `UploadResearchDocumentUseCase`: no Work Item is enqueued.**
    Enqueuing the existing knowledge-processing Work Item would run this document through the
    Knowledge Processing Pipeline (semantic classification -> Knowledge Element/Chunk), which
    would incorrectly treat a writing-style sample as research knowledge - the two pipelines
    are architecturally separate and must never overlap
    (docs/Backend_Slice2_AI_Readiness_Review.md §8). This document's `processing_status`
    therefore remains `pending` indefinitely with respect to the *knowledge* pipeline, which
    is accurate: it is genuinely never submitted to that pipeline, not stuck mid-processing.

    **The "relationship... with the Writing Profile" (Stage 3 prompt requirement 3) is the
    existing Agent-scoping chain, not a new junction row.** `Profile Characteristic Source`
    (04_Logical_Data_Model.md §4.5) traces a *characteristic* to the sample that informed it -
    it requires a `Profile Characteristic` to already exist, which requires semantic
    extraction, which this stage must not perform. Creating one now would mean inventing a
    Profile Characteristic to hang it off, which is explicitly forbidden. Instead, this use
    case relies on the same "indirect association via shared Agent scope" the frozen model
    itself already uses for a structurally identical case - "Writing Profile - Draft (N:M):
    Realized indirectly - a draft's project associates it with the project's active profile"
    (04_Logical_Data_Model.md §5) - here, the uploaded Research Document's Project resolves to
    the same Agent that owns the Writing Profile. `Profile Characteristic Source` rows are
    created later, by the extraction stage, once real Profile Characteristics exist to link.

    **Profile creation policy - decided, not silently assumed:** if the Agent has no active
    Writing Profile yet, one is created automatically, atomically with the document upload
    (mirrors `CreateAgentWorkspaceUseCase`'s Agent+Project atomicity pattern). This keeps
    first-use friction-free while the invariant "at most one active Writing Profile per Agent"
    (05_Constraints_and_Integrity.md invariant 8) remains enforced by the database constraint
    already added in Stage 2 - a concurrent double-creation would surface as an IntegrityError,
    not a silently duplicated profile.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        writing_profile_repository: WritingProfileRepository,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._writing_profiles = writing_profile_repository
        self._content_store = content_store
        self._uow = unit_of_work

    def execute(
        self,
        *,
        user_id: int,
        title: str,
        format: str,
        content: bytes,
        author: str | None = None,
        source: str | None = None,
        extension: str = "",
    ) -> WritingStyleDocumentUpload:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        # Defensive, not expected to fail: an Agent always owns exactly one permanent Project
        # (05_Constraints_and_Integrity.md invariant 15). No ProjectNotFoundError is raised
        # here deliberately - a missing Project for an existing Agent is an invariant
        # violation, not a client-facing 404 condition.
        project = self._projects.get_by_agent_id(agent.agent_id)
        assert project is not None, f"Agent {agent.agent_id} has no Project (invariant 15 violated)"

        existing_count = len(
            self._documents.list_by_project_id(project.project_id, purpose=DocumentPurpose.WRITING_STYLE_SAMPLE)
        )
        if existing_count >= MAX_WRITING_STYLE_SAMPLES:
            raise TooManyWritingStyleSamplesError(limit=MAX_WRITING_STYLE_SAMPLES)

        if not content:
            raise EmptyDocumentContentError()

        content_reference = self._content_store.save(content, extension=extension)

        try:
            profile = self._writing_profiles.get_active_by_agent_id(agent.agent_id)
            if profile is None:
                profile = self._writing_profiles.add(
                    WritingProfile(agent_id=agent.agent_id, user_id=user_id, name=DEFAULT_WRITING_PROFILE_NAME)
                )

            document = ResearchDocument.create(
                project_id=project.project_id,
                title=title,
                format=format,
                content_reference=content_reference,
                author=author,
                source=source,
                purpose=DocumentPurpose.WRITING_STYLE_SAMPLE,
            )
            document = self._documents.add(document)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return WritingStyleDocumentUpload(document=document, profile=profile)


class ListWritingStyleDocumentsUseCase:
    """Lists the authenticated user's own already-uploaded writing-style samples (`Document
    Purpose.WRITING_STYLE_SAMPLE`) - added resolving a real gap found via manual use: the
    frontend previously tracked "documents uploaded this session" as pure local component
    state, so navigating away or refreshing lost track of everything already uploaded, even
    though it was safely persisted server-side. Mirrors `ListProjectDocumentsUseCase`'s own
    ownership-checked read pattern.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int) -> list[ResearchDocument]:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        project = self._projects.get_by_agent_id(agent.agent_id)
        assert project is not None, f"Agent {agent.agent_id} has no Project (invariant 15 violated)"

        return self._documents.list_by_project_id(project.project_id, purpose=DocumentPurpose.WRITING_STYLE_SAMPLE)
