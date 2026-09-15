from app.ai.providers.base import TextGenerationProvider
from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.writing.domain.context_assembly import ContextAssemblyInput, assemble_context
from app.modules.writing.domain.entities import Draft, DraftEvidenceLink, DraftVersion
from app.modules.writing.domain.enums import CreatedBy
from app.modules.writing.domain.exceptions import (
    DraftNotFoundError,
    EmptyGeneratedDraftContentError,
    InsufficientDraftEvidenceError,
)
from app.modules.writing.domain.repositories import DraftRepository, DraftVersionRepository
from app.modules.writing.domain.repositories import DraftEvidenceLinkRepository
from app.workers.enums import WorkItemKind
from app.workers.payloads import build_generate_draft_version_payload_reference
from app.workers.ports import WorkItemEnqueuer


class CreateDraftUseCase:
    """Stage 2's minimal persistence-oriented entry point (Project_Writing_Implementation_
    Plan.md §18 Stage 2; Stage 2 prompt §21) - creates the stable writing-workspace object.
    Deliberately does not touch AI providers, retrieval, or Work Items: no generation happens
    here or anywhere in Stage 2.
    """

    def __init__(self, draft_repository: DraftRepository, unit_of_work: UnitOfWork) -> None:
        self._drafts = draft_repository
        self._uow = unit_of_work

    def execute(self, *, agent_id: int, title: str, target: str | None = None) -> Draft:
        draft = Draft.create(agent_id=agent_id, title=title, target=target)
        try:
            persisted = self._drafts.add(draft)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return persisted


class CreateDraftVersionUseCase:
    """Assigns the next `version_number` for a Draft and persists the new, immutable
    Draft Version (04_Logical_Data_Model.md §3.16: "versions are strictly ordered per draft";
    §6: the current version is the latest version_number, never a stored attribute - so this
    use case computes it from existing versions rather than reading/writing a pointer field).

    Does not perform generation: `content` is supplied by the caller (a human-authored draft,
    or - in a later stage - the Generation Gateway's output). No LLM call, no context
    assembly, and no provider dependency exists in this module (Stage 2 prompt §21/§22).
    """

    def __init__(self, draft_version_repository: DraftVersionRepository, unit_of_work: UnitOfWork) -> None:
        self._versions = draft_version_repository
        self._uow = unit_of_work

    def execute(self, *, draft_id: int, content: str, created_by: CreatedBy = CreatedBy.USER) -> DraftVersion:
        latest = self._versions.get_latest_by_draft_id(draft_id)
        next_version_number = latest.version_number + 1 if latest is not None else 1
        version = DraftVersion(
            draft_id=draft_id, version_number=next_version_number, content=content, created_by=created_by
        )
        try:
            persisted = self._versions.add(version)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return persisted


class GenerateDraftVersionUseCase:
    """Synchronously generate and persist one evidence-linked Draft Version.

    Context resolution remains outside this Stage 5 use case: callers provide the already
    resolved ContextAssemblyInput, keeping retrieval and profile loading behind their existing
    application boundaries. Work Items and HTTP orchestration are deliberately deferred to
    later stages.
    """

    def __init__(
        self,
        draft_repository: DraftRepository,
        draft_version_repository: DraftVersionRepository,
        evidence_link_repository: DraftEvidenceLinkRepository,
        text_provider: TextGenerationProvider,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._drafts = draft_repository
        self._versions = draft_version_repository
        self._evidence_links = evidence_link_repository
        self._text_provider = text_provider
        self._uow = unit_of_work

    def execute(self, *, draft_id: int, context: ContextAssemblyInput) -> DraftVersion:
        draft = self._drafts.get_by_id(draft_id)
        if draft is None:
            raise DraftNotFoundError(draft_id=draft_id)

        assembled = assemble_context(context)
        if not assembled.evidence:
            raise InsufficientDraftEvidenceError(draft_id=draft_id)

        generated_content = self._text_provider.generate(assembled.prompt)
        if not generated_content or not generated_content.strip():
            raise EmptyGeneratedDraftContentError()

        latest = self._versions.get_latest_by_draft_id(draft_id)
        version = DraftVersion(
            draft_id=draft_id,
            version_number=latest.version_number + 1 if latest is not None else 1,
            content=generated_content.strip(),
            created_by=CreatedBy.SYSTEM,
        )

        try:
            persisted_version = self._versions.add(version)
            for evidence in assembled.evidence:
                self._evidence_links.add(
                    DraftEvidenceLink.for_knowledge_chunk(
                        draft_version_id=persisted_version.version_id,
                        chunk_id=evidence.chunk_id,
                    )
                )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return persisted_version


class EnqueueDraftGenerationUseCase:
    """Creates one server-owned Work Item for a resolved Stage 5 generation request."""

    def __init__(
        self,
        draft_repository: DraftRepository,
        agent_repository: AgentRepository,
        work_item_enqueuer: WorkItemEnqueuer,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._drafts = draft_repository
        self._agents = agent_repository
        self._work_items = work_item_enqueuer
        self._uow = unit_of_work

    def execute(self, *, user_id: int, draft_id: int, context: ContextAssemblyInput):
        draft = self._drafts.get_by_id(draft_id)
        agent = self._agents.get_by_id(
            draft.agent_id) if draft is not None else None
        if draft is None or agent is None or agent.user_id != user_id:
            raise DraftNotFoundError(draft_id=draft_id)
        payload_reference, idempotency_key = build_generate_draft_version_payload_reference(
            draft_id, context)
        try:
            work_item = self._work_items.enqueue(
                kind=WorkItemKind.PIPELINE_STAGE,
                payload_reference=payload_reference,
                idempotency_key=idempotency_key,
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return work_item
