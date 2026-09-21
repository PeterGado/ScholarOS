from dataclasses import dataclass

from app.ai.providers.base import TextGenerationProvider
from app.ai.token_estimate import estimate_tokens
from app.ai.usage_guard import AiUsageGuard
from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.ports import ContentStore
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.repositories import ProjectRepository
from app.modules.writing.application.style_ingestion import DEFAULT_WRITING_PROFILE_NAME
from app.modules.writing.domain.entities import ProfileCharacteristic, ProfileCharacteristicSource, WritingProfile
from app.modules.writing.domain.exceptions import (
    InvalidStyleSampleReferenceError,
    MissingStoredStyleSampleError,
    NoUsableWritingStyleSamplesError,
    UnusableWritingStyleSampleError,
    WritingProfileAlreadyExtractedError,
)
from app.modules.writing.domain.repositories import (
    ProfileCharacteristicRepository,
    ProfileCharacteristicSourceRepository,
    WritingProfileRepository,
)
from app.modules.writing.domain.style_extraction import decode_sample_text, extract_style_characteristics


@dataclass
class ExtractedProfileCharacteristic:
    """A persisted characteristic together with the sample document_ids that support it -
    every characteristic returned by this use case has provenance by construction (Stage 4
    prompt §9); there is no code path that produces a "floating" characteristic.
    """

    characteristic: ProfileCharacteristic
    source_document_ids: list[int]


@dataclass
class WritingStyleProfileExtraction:
    profile: WritingProfile
    characteristics: list[ExtractedProfileCharacteristic]


class ExtractWritingStyleProfileUseCase:
    """Stage 4 of Project Writing: derive real `Profile Characteristic` rows (via the existing
    `TextGenerationProvider` - no new AI abstraction) from writing-style samples Stage 3
    already persisted, with mandatory provenance to those samples.

    **Which samples to analyze.** The caller supplies the exact `document_ids` to analyze,
    rather than this use case silently scanning the whole Project (which would risk pulling
    ordinary research material into style analysis, corrupting the profile). This matches the
    Stage 4 prompt's own §10 guidance precisely: "the application associates the characteristic
    with the samples used for extraction" - the *set* of samples used is therefore an explicit
    input, not something silently inferred. It also matches WR-010's framing ("the system shall
    allow the user to provide... samples for... analysis") - sample selection is a user-driven
    action. (`DocumentPurpose.WRITING_STYLE_SAMPLE` - added after Stage 3/4 first shipped -
    now also lets the frontend list a user's own already-uploaded samples across sessions
    without depending on this explicit-id-list requirement for that; extraction itself still
    requires an explicit list, unchanged.)

    **Provenance, exactly.** The AI provider returns semantic characteristics only - never a
    source/document reference (Stage 4 prompt §7/§10: the model must not be trusted to choose
    persistence identifiers). Because every characteristic in one extraction run is derived
    from the *same* pooled sample set, each persisted `ProfileCharacteristic` is linked, via a
    `ProfileCharacteristicSource` row, to every document_id actually supplied to that run -
    deterministic, not model-chosen, and exactly what "the samples used for extraction" means
    here.

    **Regeneration - a genuine, reported ambiguity, deliberately left unresolved.** The frozen
    model gives `Profile Characteristic` no status/supersession column and explicitly forbids
    tombstoning it (05_Constraints_and_Integrity.md: "never tombstoned... superseded or
    retained, never deleted") - yet provides no field to represent "superseded" for this
    entity the way Knowledge Element/Memory Record do. Accumulating characteristics forever
    across repeated runs, or silently deleting old ones, would each be a real correctness
    problem this use case has no frozen authority to decide between. Per the Stage 4 prompt's
    own instruction ("If the frozen architecture does not specify the update semantics, stop
    and report the ambiguity... rather than silently choosing a persistence strategy"), running
    extraction a second time against a profile that already has characteristics is refused
    outright (`WritingProfileAlreadyExtractedError`) rather than guessed at - see the Stage 4
    completion report's Deviations/Open Items.

    **Atomicity.** The AI call and its validation both happen before persistence begins (mirrors
    `ExtractDocumentKnowledgeUseCase`'s own "gather everything, then persist everything"
    pattern) - any malformed provider response raises before a single row is written; any
    persistence-layer failure rolls back the whole batch via `UnitOfWork`.
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        project_repository: ProjectRepository,
        document_repository: DocumentRepository,
        content_store: ContentStore,
        writing_profile_repository: WritingProfileRepository,
        profile_characteristic_repository: ProfileCharacteristicRepository,
        profile_characteristic_source_repository: ProfileCharacteristicSourceRepository,
        text_provider: TextGenerationProvider,
        unit_of_work: UnitOfWork,
        ai_usage_guard: AiUsageGuard,
    ) -> None:
        self._agents = agent_repository
        self._projects = project_repository
        self._documents = document_repository
        self._content_store = content_store
        self._writing_profiles = writing_profile_repository
        self._characteristics = profile_characteristic_repository
        self._sources = profile_characteristic_source_repository
        self._text_provider = text_provider
        self._uow = unit_of_work
        self._ai_usage_guard = ai_usage_guard

    def execute(self, *, user_id: int, document_ids: list[int]) -> WritingStyleProfileExtraction:
        agent = self._agents.get_by_user_id(user_id)
        if agent is None:
            raise AgentNotFoundForUserError(user_id=user_id)

        project = self._projects.get_by_agent_id(agent.agent_id)
        assert project is not None, f"Agent {agent.agent_id} has no Project (invariant 15 violated)"

        if not document_ids:
            raise NoUsableWritingStyleSamplesError()

        documents = self._resolve_documents(document_ids, project_id=project.project_id)
        samples = self._load_sample_texts(documents)

        profile = self._writing_profiles.get_active_by_agent_id(agent.agent_id)
        if profile is not None and self._characteristics.list_by_profile_id(profile.profile_id):
            raise WritingProfileAlreadyExtractedError(profile_id=profile.profile_id)

        # AI usage cap (2026-09-21 security pass): estimated from the pooled sample text that
        # extract_style_characteristics will actually send to the provider.
        self._ai_usage_guard.check_and_record(
            user_id=user_id, estimated_tokens=estimate_tokens("\n\n".join(samples))
        )
        extracted = extract_style_characteristics(samples, self._text_provider)

        try:
            if profile is None:
                profile = self._writing_profiles.add(
                    WritingProfile(agent_id=agent.agent_id, user_id=user_id, name=DEFAULT_WRITING_PROFILE_NAME)
                )

            persisted: list[ExtractedProfileCharacteristic] = []
            for item in extracted:
                characteristic = self._characteristics.add(
                    ProfileCharacteristic(
                        profile_id=profile.profile_id,
                        characteristic_type=item.characteristic_type,
                        signal=item.signal,
                        confidence=item.confidence,
                    )
                )
                for document in documents:
                    self._sources.add(
                        ProfileCharacteristicSource(
                            characteristic_id=characteristic.characteristic_id, document_id=document.document_id
                        )
                    )
                persisted.append(
                    ExtractedProfileCharacteristic(
                        characteristic=characteristic, source_document_ids=[d.document_id for d in documents]
                    )
                )

            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        return WritingStyleProfileExtraction(profile=profile, characteristics=persisted)

    def _resolve_documents(self, document_ids: list[int], *, project_id: int) -> list[ResearchDocument]:
        documents = []
        for document_id in document_ids:
            document = self._documents.get_by_id(document_id)
            if document is None or document.project_id != project_id:
                # Deliberately indistinguishable from "does not exist" - mirrors
                # ProjectNotFoundError's established non-enumeration precedent (Stage 6).
                raise InvalidStyleSampleReferenceError(document_id=document_id)
            documents.append(document)
        return documents

    def _load_sample_texts(self, documents: list[ResearchDocument]) -> list[str]:
        samples: list[str] = []
        for document in documents:
            if not self._content_store.exists(document.content_reference):
                raise MissingStoredStyleSampleError(document_id=document.document_id)
            raw_bytes = self._content_store.read(document.content_reference)
            text = decode_sample_text(raw_bytes, document_id=document.document_id)
            if not text.strip():
                raise UnusableWritingStyleSampleError(document_id=document.document_id)
            samples.append(text)
        return samples
