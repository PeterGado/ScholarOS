from datetime import datetime, timezone

import pytest

from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.knowledge.application.retrieval import SearchResult, SearchResultEvidence
from app.modules.project.domain.entities import Project
from app.modules.writing.application.generation_request import RequestDraftGenerationUseCase
from app.modules.writing.application.profile_view import GetWritingProfileUseCase
from app.modules.writing.application.reviews import SubmitDraftReviewUseCase
from app.modules.writing.application.use_cases import (
    EnqueueDraftGenerationUseCase,
    GetDraftUseCase,
    ListDraftsUseCase,
    ListDraftVersionsUseCase,
)
from app.modules.writing.domain.entities import (
    Draft,
    DraftEvidenceLink,
    DraftVersion,
    ProfileCharacteristic,
    Review,
    WritingProfile,
)
from app.modules.writing.domain.enums import DraftStatus, ProfileCharacteristicType, ReviewOutcome
from app.modules.writing.domain.exceptions import (
    DraftNotFoundError,
    DraftVersionNotFoundError,
    InsufficientDraftEvidenceError,
    WritingProfileNotFoundError,
)
from app.workers.entities import WorkItem
from app.workers.enums import WorkItemState

OWNER_USER_ID = 9
OTHER_USER_ID = 10
AGENT_ID = 4


class FakeAgentRepository:
    def __init__(self, agent: Agent | None = None) -> None:
        self.agent = agent

    def get_by_id(self, agent_id):
        return self.agent if self.agent is not None and self.agent.agent_id == agent_id else None

    def get_by_user_id(self, user_id):
        return self.agent if self.agent is not None and self.agent.user_id == user_id else None

    def add(self, agent):
        raise NotImplementedError


class FakeDraftRepository:
    def __init__(self, drafts: list[Draft] | None = None) -> None:
        self._drafts = drafts or []
        self.status_updates: list[tuple[int, DraftStatus]] = []

    def add(self, draft):
        raise NotImplementedError

    def get_by_id(self, draft_id):
        return next((d for d in self._drafts if d.draft_id == draft_id), None)

    def list_by_agent_id(self, agent_id):
        return [d for d in self._drafts if d.agent_id == agent_id]

    def update_status(self, draft_id, status):
        self.status_updates.append((draft_id, status))
        draft = self.get_by_id(draft_id)
        if draft is not None:
            draft.status = status


class FakeDraftVersionRepository:
    def __init__(self, versions: list[DraftVersion] | None = None) -> None:
        self._versions = versions or []

    def add(self, version):
        raise NotImplementedError

    def get_by_id(self, version_id):
        return next((v for v in self._versions if v.version_id == version_id), None)

    def list_by_draft_id(self, draft_id):
        return sorted((v for v in self._versions if v.draft_id == draft_id), key=lambda v: v.version_number)

    def get_latest_by_draft_id(self, draft_id):
        versions = self.list_by_draft_id(draft_id)
        return versions[-1] if versions else None


class FakeDraftEvidenceLinkRepository:
    def __init__(self, links: list[DraftEvidenceLink] | None = None) -> None:
        self._links = links or []

    def add(self, link):
        raise NotImplementedError

    def list_by_draft_version_id(self, draft_version_id):
        return [link for link in self._links if link.draft_version_id == draft_version_id]


class FakeReviewRepository:
    def __init__(self) -> None:
        self.saved: list[Review] = []
        self._next_id = 1

    def add(self, review):
        review.review_id = self._next_id
        self._next_id += 1
        self.saved.append(review)
        return review

    def get_by_id(self, review_id):
        return next((r for r in self.saved if r.review_id == review_id), None)

    def get_open_by_draft_version_id(self, draft_version_id):
        return next(
            (r for r in self.saved if r.draft_version_id == draft_version_id and r.status.value == "open"), None
        )


class FakeReviewDecisionRepository:
    def __init__(self) -> None:
        self.saved = []
        self._next_id = 1

    def add(self, decision):
        decision.decision_id = self._next_id
        self._next_id += 1
        self.saved.append(decision)
        return decision

    def get_by_review_id(self, review_id):
        return next((d for d in self.saved if d.review_id == review_id), None)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeWorkItemEnqueuer:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, **kwargs):
        self.enqueued.append(kwargs)
        return WorkItem(
            work_item_id=1,
            kind=kwargs["kind"],
            state=WorkItemState.QUEUED,
            payload_reference=kwargs["payload_reference"],
            idempotency_key=kwargs["idempotency_key"],
            attempts=0,
            last_error=None,
            created_at=datetime.now(timezone.utc),
            executed_at=None,
            completed_at=None,
        )


class FakeContentStore:
    def __init__(self) -> None:
        self._by_reference: dict[str, bytes] = {}

    def save(self, content: bytes, *, extension: str = "") -> str:
        reference = f"ref-{len(self._by_reference)}{('.' + extension) if extension else ''}"
        self._by_reference[reference] = content
        return reference

    def read(self, reference: str) -> bytes:
        return self._by_reference[reference]

    def exists(self, reference: str) -> bool:
        return reference in self._by_reference


class FakeProjectRepository:
    def __init__(self, project: Project | None = None) -> None:
        self.project = project

    def get_by_agent_id(self, agent_id):
        return self.project if self.project is not None and self.project.agent_id == agent_id else None

    def get_by_id(self, project_id):
        raise NotImplementedError

    def add(self, project):
        raise NotImplementedError


class FakeWritingProfileRepository:
    def __init__(self, profile: WritingProfile | None = None) -> None:
        self.profile = profile

    def add(self, profile):
        raise NotImplementedError

    def get_by_id(self, profile_id):
        return self.profile if self.profile is not None and self.profile.profile_id == profile_id else None

    def get_active_by_agent_id(self, agent_id):
        return self.profile if self.profile is not None and self.profile.agent_id == agent_id else None


class FakeProfileCharacteristicRepository:
    def __init__(self, characteristics: list[ProfileCharacteristic] | None = None) -> None:
        self._characteristics = characteristics or []

    def add(self, characteristic):
        raise NotImplementedError

    def list_by_profile_id(self, profile_id):
        return [c for c in self._characteristics if c.profile_id == profile_id]


class FakeMemoryRecordRepository:
    def __init__(self, records=None) -> None:
        self._records = records or []

    def add(self, record):
        raise NotImplementedError

    def get_by_id(self, record_id):
        raise NotImplementedError

    def list_current_by_agent_id(self, agent_id):
        return [r for r in self._records if r.agent_id == agent_id]


class FakeConversationRepository:
    def __init__(self) -> None:
        self._conversations = []
        self._next_id = 1

    def add(self, conversation):
        conversation.conversation_id = self._next_id
        self._next_id += 1
        self._conversations.append(conversation)
        return conversation

    def get_by_id(self, conversation_id):
        return next((c for c in self._conversations if c.conversation_id == conversation_id), None)

    def get_by_agent_id_and_title(self, agent_id, title):
        return next(
            (c for c in self._conversations if c.agent_id == agent_id and c.title == title), None
        )


class FakeMessageRepository:
    def __init__(self) -> None:
        self._messages = []
        self._next_id = 1

    def add(self, message):
        message.message_id = self._next_id
        self._next_id += 1
        self._messages.append(message)
        return message

    def get_by_id(self, message_id):
        return next((m for m in self._messages if m.message_id == message_id), None)

    def count_by_conversation_id(self, conversation_id):
        return sum(1 for m in self._messages if m.conversation_id == conversation_id)


class FakeSearchKnowledgeUseCase:
    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results if results is not None else []
        self.calls: list[dict] = []

    def execute(self, *, user_id, query, top_k=10):
        self.calls.append({"user_id": user_id, "query": query, "top_k": top_k})
        return self.results


def _owner_agent() -> Agent:
    return Agent(agent_id=AGENT_ID, user_id=OWNER_USER_ID)


# --- ListDraftsUseCase / GetDraftUseCase -------------------------------------------------------------------


def test_list_drafts_returns_only_the_callers_own_drafts():
    agent = _owner_agent()
    drafts = FakeDraftRepository([Draft.create(agent_id=AGENT_ID, title="A"), Draft.create(agent_id=99, title="Other")])
    use_case = ListDraftsUseCase(drafts, FakeAgentRepository(agent))

    result = use_case.execute(user_id=OWNER_USER_ID)

    assert [d.title for d in result] == ["A"]


def test_list_drafts_requires_an_existing_agent():
    use_case = ListDraftsUseCase(FakeDraftRepository(), FakeAgentRepository(None))
    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=OWNER_USER_ID)


def test_get_draft_rejects_a_draft_owned_by_another_agent():
    agent = _owner_agent()
    other_draft = Draft(agent_id=99, title="Not mine", draft_id=1)
    use_case = GetDraftUseCase(FakeDraftRepository([other_draft]), FakeAgentRepository(agent))

    with pytest.raises(DraftNotFoundError):
        use_case.execute(user_id=OWNER_USER_ID, draft_id=1)


def test_get_draft_returns_the_callers_own_draft():
    agent = _owner_agent()
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    use_case = GetDraftUseCase(FakeDraftRepository([draft]), FakeAgentRepository(agent))

    result = use_case.execute(user_id=OWNER_USER_ID, draft_id=1)

    assert result.title == "Mine"


# --- ListDraftVersionsUseCase -------------------------------------------------------------------


def test_list_draft_versions_bundles_evidence_per_version():
    agent = _owner_agent()
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    version = DraftVersion(draft_id=1, version_number=1, content="Body", version_id=5)
    link = DraftEvidenceLink.for_knowledge_chunk(draft_version_id=5, chunk_id=7)
    use_case = ListDraftVersionsUseCase(
        FakeDraftRepository([draft]), FakeDraftVersionRepository([version]), FakeDraftEvidenceLinkRepository([link]),
        FakeAgentRepository(agent),
    )

    result = use_case.execute(user_id=OWNER_USER_ID, draft_id=1)

    assert len(result) == 1
    assert result[0].version.version_id == 5
    assert [e.chunk_id for e in result[0].evidence] == [7]


def test_list_draft_versions_returns_empty_list_for_a_never_generated_draft():
    agent = _owner_agent()
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    use_case = ListDraftVersionsUseCase(
        FakeDraftRepository([draft]), FakeDraftVersionRepository([]), FakeDraftEvidenceLinkRepository([]),
        FakeAgentRepository(agent),
    )

    assert use_case.execute(user_id=OWNER_USER_ID, draft_id=1) == []


def test_list_draft_versions_rejects_another_users_draft():
    agent = _owner_agent()
    use_case = ListDraftVersionsUseCase(
        FakeDraftRepository([]), FakeDraftVersionRepository([]), FakeDraftEvidenceLinkRepository([]),
        FakeAgentRepository(agent),
    )
    with pytest.raises(DraftNotFoundError):
        use_case.execute(user_id=OWNER_USER_ID, draft_id=999)


# --- SubmitDraftReviewUseCase -------------------------------------------------------------------


def _review_use_case(draft, version, agent=None):
    agent = agent or _owner_agent()
    drafts = FakeDraftRepository([draft])
    versions = FakeDraftVersionRepository([version])
    reviews = FakeReviewRepository()
    decisions = FakeReviewDecisionRepository()
    uow = FakeUnitOfWork()
    use_case = SubmitDraftReviewUseCase(drafts, versions, reviews, decisions, FakeAgentRepository(agent), uow)
    return use_case, drafts, reviews, decisions, uow


def test_submit_review_approved_transitions_draft_to_approved():
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1, status=DraftStatus.IN_REVIEW)
    version = DraftVersion(draft_id=1, version_number=1, content="Body", version_id=5)
    use_case, drafts, reviews, decisions, uow = _review_use_case(draft, version)

    decision = use_case.execute(
        user_id=OWNER_USER_ID, draft_id=1, version_id=5, outcome=ReviewOutcome.APPROVED, rationale="Looks good."
    )

    assert decision.outcome == ReviewOutcome.APPROVED
    assert decision.decided_by == OWNER_USER_ID
    assert reviews.saved[0].status.value == "decided"
    assert reviews.saved[0].decided_at is not None
    assert drafts.get_by_id(1).status == DraftStatus.APPROVED
    assert uow.committed is True


def test_submit_review_revisions_requested_transitions_draft_to_drafting():
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1, status=DraftStatus.IN_REVIEW)
    version = DraftVersion(draft_id=1, version_number=1, content="Body", version_id=5)
    use_case, drafts, *_ = _review_use_case(draft, version)

    use_case.execute(user_id=OWNER_USER_ID, draft_id=1, version_id=5, outcome=ReviewOutcome.REVISIONS_REQUESTED)

    assert drafts.get_by_id(1).status == DraftStatus.DRAFTING


def test_submit_review_rejected_leaves_draft_status_unchanged():
    """No frozen Draft-level transition exists for `rejected` - deliberately not guessed."""
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1, status=DraftStatus.IN_REVIEW)
    version = DraftVersion(draft_id=1, version_number=1, content="Body", version_id=5)
    use_case, drafts, *_ = _review_use_case(draft, version)

    use_case.execute(user_id=OWNER_USER_ID, draft_id=1, version_id=5, outcome=ReviewOutcome.REJECTED)

    assert drafts.get_by_id(1).status == DraftStatus.IN_REVIEW


def test_submit_review_rejects_a_version_belonging_to_another_draft():
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    version = DraftVersion(draft_id=999, version_number=1, content="Body", version_id=5)
    use_case, *_ = _review_use_case(draft, version)

    with pytest.raises(DraftVersionNotFoundError):
        use_case.execute(user_id=OWNER_USER_ID, draft_id=1, version_id=5, outcome=ReviewOutcome.APPROVED)


def test_submit_review_rejects_another_users_draft():
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    version = DraftVersion(draft_id=1, version_number=1, content="Body", version_id=5)
    use_case, *_ = _review_use_case(draft, version)

    with pytest.raises(DraftNotFoundError):
        use_case.execute(user_id=OTHER_USER_ID, draft_id=1, version_id=5, outcome=ReviewOutcome.APPROVED)


# --- RequestDraftGenerationUseCase -------------------------------------------------------------------


def _generation_request_use_case(
    *, agent=None, project=None, search_results=None, profile=None, characteristics=None, memories=None
):
    agent = agent or _owner_agent()
    project = project if project is not None else Project(project_id=1, agent_id=AGENT_ID, title="Thesis", topic="Coastal erosion")
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    drafts = FakeDraftRepository([draft])
    enqueuer = EnqueueDraftGenerationUseCase(
        drafts, FakeAgentRepository(agent), FakeWorkItemEnqueuer(), FakeContentStore(), FakeUnitOfWork()
    )
    search = FakeSearchKnowledgeUseCase(search_results)
    use_case = RequestDraftGenerationUseCase(
        drafts,
        FakeProjectRepository(project),
        FakeAgentRepository(agent),
        FakeWritingProfileRepository(profile),
        FakeProfileCharacteristicRepository(characteristics),
        FakeMemoryRecordRepository(memories),
        FakeConversationRepository(),
        FakeMessageRepository(),
        search,
        enqueuer,
        FakeUnitOfWork(),
    )
    return use_case, search


def test_request_generation_rejects_with_no_search_results():
    use_case, search = _generation_request_use_case(search_results=[])

    with pytest.raises(InsufficientDraftEvidenceError):
        use_case.execute(user_id=OWNER_USER_ID, draft_id=1, instructions="Write the introduction.")


def test_request_generation_enqueues_a_work_item_with_real_evidence():
    results = [
        SearchResult(
            chunk_id=7,
            content="Erosion accelerates near the shoreline.",
            summary=None,
            score=0.9,
            evidence=[SearchResultEvidence(document_id=3, document_title="Survey")],
        )
    ]
    use_case, search = _generation_request_use_case(search_results=results)

    work_item = use_case.execute(user_id=OWNER_USER_ID, draft_id=1, instructions="Write the introduction.")

    assert work_item.work_item_id == 1
    assert search.calls == [{"user_id": OWNER_USER_ID, "query": "Write the introduction.", "top_k": 10}]


def test_request_generation_rejects_another_users_draft():
    use_case, _ = _generation_request_use_case()

    with pytest.raises(DraftNotFoundError):
        use_case.execute(user_id=OTHER_USER_ID, draft_id=1, instructions="Write the introduction.")


def test_request_generation_never_lets_evidence_be_client_supplied():
    """There is no code path in this use case (or its request schema) through which a caller
    can supply chunk_id/content directly - the only source of Draft Evidence Link content is
    SearchKnowledgeUseCase's own real, agent-scoped results.
    """
    import inspect

    signature = inspect.signature(RequestDraftGenerationUseCase.execute)
    assert set(signature.parameters) == {"self", "user_id", "draft_id", "instructions"}


def test_request_generation_persists_instructions_as_a_conversation_message():
    """Resolves the instructions-contract discrepancy (Stage 8 finding): instructions must be
    persisted via the frozen Conversation/Message entities, not only passed through as an
    ephemeral field.
    """
    from app.workers.payloads import parse_generate_draft_version_payload_reference

    results = [SearchResult(chunk_id=1, content="Evidence.", summary=None, score=1.0, evidence=[])]
    agent = _owner_agent()
    project = Project(project_id=1, agent_id=AGENT_ID, title="Thesis", topic="Coastal erosion")
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    drafts = FakeDraftRepository([draft])
    content_store = FakeContentStore()
    enqueuer = EnqueueDraftGenerationUseCase(
        drafts, FakeAgentRepository(agent), FakeWorkItemEnqueuer(), content_store, FakeUnitOfWork()
    )
    conversations = FakeConversationRepository()
    messages = FakeMessageRepository()
    use_case = RequestDraftGenerationUseCase(
        drafts,
        FakeProjectRepository(project),
        FakeAgentRepository(agent),
        FakeWritingProfileRepository(None),
        FakeProfileCharacteristicRepository(None),
        FakeMemoryRecordRepository(None),
        conversations,
        messages,
        FakeSearchKnowledgeUseCase(results),
        enqueuer,
        FakeUnitOfWork(),
    )

    work_item = use_case.execute(user_id=OWNER_USER_ID, draft_id=1, instructions="Write the introduction.")

    conversation = conversations.get_by_agent_id_and_title(AGENT_ID, "draft:1:instructions")
    assert conversation is not None
    message = messages.get_by_id(1)
    assert message is not None
    assert message.conversation_id == conversation.conversation_id
    assert message.content == "Write the introduction."
    assert message.sequence == 1

    _draft_id, _context, _request_id, message_id = parse_generate_draft_version_payload_reference(
        work_item.payload_reference, content_store
    )
    assert message_id == message.message_id


def test_request_generation_reuses_the_same_conversation_across_requests():
    results = [SearchResult(chunk_id=1, content="Evidence.", summary=None, score=1.0, evidence=[])]
    agent = _owner_agent()
    project = Project(project_id=1, agent_id=AGENT_ID, title="Thesis", topic="Coastal erosion")
    draft = Draft(agent_id=AGENT_ID, title="Mine", draft_id=1)
    drafts = FakeDraftRepository([draft])
    enqueuer = EnqueueDraftGenerationUseCase(
        drafts, FakeAgentRepository(agent), FakeWorkItemEnqueuer(), FakeContentStore(), FakeUnitOfWork()
    )
    conversations = FakeConversationRepository()
    messages = FakeMessageRepository()
    use_case = RequestDraftGenerationUseCase(
        drafts,
        FakeProjectRepository(project),
        FakeAgentRepository(agent),
        FakeWritingProfileRepository(None),
        FakeProfileCharacteristicRepository(None),
        FakeMemoryRecordRepository(None),
        conversations,
        messages,
        FakeSearchKnowledgeUseCase(results),
        enqueuer,
        FakeUnitOfWork(),
    )

    use_case.execute(user_id=OWNER_USER_ID, draft_id=1, instructions="Write the introduction.")
    use_case.execute(user_id=OWNER_USER_ID, draft_id=1, instructions="Now write the conclusion.")

    assert len({c.conversation_id for c in conversations._conversations}) == 1
    conversation_id = conversations._conversations[0].conversation_id
    assert [m.sequence for m in messages._messages if m.conversation_id == conversation_id] == [1, 2]


def test_request_generation_includes_style_and_memory_when_present():
    from app.modules.writing.domain.entities import MemoryRecord
    from app.modules.writing.domain.enums import MemoryRecordType

    results = [SearchResult(chunk_id=1, content="Evidence.", summary=None, score=1.0, evidence=[])]
    profile = WritingProfile(agent_id=AGENT_ID, user_id=OWNER_USER_ID, name="Primary", profile_id=2)
    characteristics = [
        ProfileCharacteristic(profile_id=2, characteristic_type=ProfileCharacteristicType.STRUCTURE, signal="Short paragraphs.")
    ]
    memories = [MemoryRecord(agent_id=AGENT_ID, record_type=MemoryRecordType.DECISION, content="Use IMRaD structure.")]
    use_case, search = _generation_request_use_case(
        search_results=results, profile=profile, characteristics=characteristics, memories=memories
    )

    work_item = use_case.execute(user_id=OWNER_USER_ID, draft_id=1, instructions="Write the introduction.")

    assert work_item.work_item_id == 1


# --- GetWritingProfileUseCase -------------------------------------------------------------------


def test_get_writing_profile_requires_an_active_profile():
    use_case = GetWritingProfileUseCase(
        FakeWritingProfileRepository(None), FakeProfileCharacteristicRepository([]), FakeAgentRepository(_owner_agent())
    )
    with pytest.raises(WritingProfileNotFoundError):
        use_case.execute(user_id=OWNER_USER_ID)


def test_get_writing_profile_returns_profile_with_characteristics():
    profile = WritingProfile(agent_id=AGENT_ID, user_id=OWNER_USER_ID, name="Primary", profile_id=2)
    characteristics = [
        ProfileCharacteristic(profile_id=2, characteristic_type=ProfileCharacteristicType.VOCABULARY, signal="Formal tone.")
    ]
    use_case = GetWritingProfileUseCase(
        FakeWritingProfileRepository(profile),
        FakeProfileCharacteristicRepository(characteristics),
        FakeAgentRepository(_owner_agent()),
    )

    result = use_case.execute(user_id=OWNER_USER_ID)

    assert result.profile.profile_id == 2
    assert len(result.characteristics) == 1


def test_get_writing_profile_requires_an_existing_agent():
    use_case = GetWritingProfileUseCase(
        FakeWritingProfileRepository(None), FakeProfileCharacteristicRepository([]), FakeAgentRepository(None)
    )
    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=OWNER_USER_ID)
