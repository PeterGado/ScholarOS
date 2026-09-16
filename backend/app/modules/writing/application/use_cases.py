from dataclasses import dataclass

from app.ai.providers.base import TextGenerationProvider
from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.ports import ContentStore
from app.modules.writing.domain.context_assembly import ContextAssemblyInput, assemble_context
from app.modules.writing.domain.entities import Draft, DraftEvidenceLink, DraftVersion
from app.modules.writing.domain.enums import CreatedBy
from app.modules.writing.domain.exceptions import (
    DraftNotFoundError,
    EmptyGeneratedDraftContentError,
)
from app.modules.writing.domain.repositories import (
    DraftEvidenceLinkRepository,
    DraftRepository,
    DraftVersionRepository,
)
from app.workers.enums import WorkItemKind
from app.workers.payloads import build_generate_draft_version_payload_reference
from app.workers.ports import WorkItemEnqueuer


class CreateDraftUseCase:
    """Stage 2's minimal persistence-oriented entry point (Project_Writing_Implementation_
    Plan.md §18 Stage 2; Stage 2 prompt §21) - creates the stable writing-workspace object.
    Deliberately does not touch AI providers, retrieval, or Work Items: no generation happens
    here or anywhere in Stage 2.

    Resolves `agent_id` from the authenticated `user_id` (added Stage 7, this use case's
    first real caller beyond tests) - mirrors every other ownership-resolving use case in this
    module (`EnqueueDraftGenerationUseCase`, `UploadWritingStyleDocumentUseCase`). The client
    never supplies agent_id.
    """

    def __init__(
        self, draft_repository: DraftRepository, agent_repository: AgentRepository, unit_of_work: UnitOfWork
    ) -> None:
        self._drafts = draft_repository
        self._agents = agent_repository
        self._uow = unit_of_work

    def execute(self, *, user_id: int, title: str, target: str | None = None) -> Draft:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        draft = Draft.create(agent_id=agent.agent_id, title=title, target=target)
        try:
            persisted = self._drafts.add(draft)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return persisted


class ListDraftsUseCase:
    """Agent-scoped by construction - mirrors `SearchKnowledgeUseCase`'s own precedent: an
    Agent that exists but owns no Drafts yet returns an empty list (200); a user with no
    Agent at all raises `AgentNotFoundForUserError` (404), a different condition.
    """

    def __init__(self, draft_repository: DraftRepository, agent_repository: AgentRepository) -> None:
        self._drafts = draft_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int) -> list[Draft]:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)
        return self._drafts.list_by_agent_id(agent.agent_id)


class GetDraftUseCase:
    """Fetches one Draft, enforcing ownership. A Draft that exists but belongs to a different
    Agent is reported identically to a genuinely missing Draft (non-enumeration), the same
    principle `UploadResearchDocumentUseCase` already established for Project ownership.
    """

    def __init__(self, draft_repository: DraftRepository, agent_repository: AgentRepository) -> None:
        self._drafts = draft_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int, draft_id: int) -> Draft:
        draft = self._drafts.get_by_id(draft_id)
        agent = self._agents.get_by_id(draft.agent_id) if draft is not None else None
        if draft is None or agent is None or agent.user_id != user_id:
            raise DraftNotFoundError(draft_id=draft_id)
        return draft


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


@dataclass
class DraftVersionWithEvidence:
    """A Draft Version bundled with the Draft Evidence Links that support it - the shape
    `ListDraftVersionsUseCase` returns, so the interface layer never has to make a second
    per-version repository call itself (Stage 7 prompt §4: routes only invoke a use case).
    """

    version: DraftVersion
    evidence: list[DraftEvidenceLink]


class ListDraftVersionsUseCase:
    """Lists a Draft's immutable Draft Versions (oldest first - `DraftVersionRepository.
    list_by_draft_id`'s own documented ordering) together with each version's evidence links.
    Enforces the same ownership check as `GetDraftUseCase`; an empty list is a valid result
    for a Draft that has never been generated (05_Constraints_and_Integrity.md: Draft
    Version's own existence is optional, never implied by Draft's existence).
    """

    def __init__(
        self,
        draft_repository: DraftRepository,
        draft_version_repository: DraftVersionRepository,
        evidence_link_repository: DraftEvidenceLinkRepository,
        agent_repository: AgentRepository,
    ) -> None:
        self._drafts = draft_repository
        self._versions = draft_version_repository
        self._evidence_links = evidence_link_repository
        self._agents = agent_repository

    def execute(self, *, user_id: int, draft_id: int) -> list[DraftVersionWithEvidence]:
        draft = self._drafts.get_by_id(draft_id)
        agent = self._agents.get_by_id(draft.agent_id) if draft is not None else None
        if draft is None or agent is None or agent.user_id != user_id:
            raise DraftNotFoundError(draft_id=draft_id)

        versions = self._versions.list_by_draft_id(draft_id)
        return [
            DraftVersionWithEvidence(
                version=version,
                evidence=self._evidence_links.list_by_draft_version_id(version.version_id),
            )
            for version in versions
        ]


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
    """Creates one server-owned Work Item for a resolved Stage 5 generation request.

    The context is written to `content_store` (not inlined into `payload_reference` - see
    app.workers.payloads' module docstring) so a request with real, evidence-sized context
    can actually be enqueued.
    """

    def __init__(
        self,
        draft_repository: DraftRepository,
        agent_repository: AgentRepository,
        work_item_enqueuer: WorkItemEnqueuer,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._drafts = draft_repository
        self._agents = agent_repository
        self._work_items = work_item_enqueuer
        self._content_store = content_store
        self._uow = unit_of_work

    def execute(self, *, user_id: int, draft_id: int, context: ContextAssemblyInput, message_id: int | None = None):
        draft = self._drafts.get_by_id(draft_id)
        agent = self._agents.get_by_id(draft.agent_id) if draft is not None else None
        if draft is None or agent is None or agent.user_id != user_id:
            raise DraftNotFoundError(draft_id=draft_id)
        payload_reference, idempotency_key = build_generate_draft_version_payload_reference(
            draft_id, context, self._content_store, message_id=message_id
        )
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
