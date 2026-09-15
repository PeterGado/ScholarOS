import pytest

from app.modules.writing.application.use_cases import (
    CreateDraftUseCase,
    CreateDraftVersionUseCase,
    GenerateDraftVersionUseCase,
)
from app.modules.writing.domain.context_assembly import ContextAssemblyInput, ContextEvidence
from app.modules.writing.domain.entities import Draft, DraftVersion
from app.modules.writing.domain.enums import CreatedBy, DraftEvidenceTargetType
from app.modules.writing.domain.exceptions import (
    DraftNotFoundError,
    EmptyGeneratedDraftContentError,
    InsufficientDraftEvidenceError,
)
from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.writing.application.use_cases import EnqueueDraftGenerationUseCase


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeDraftRepository:
    def __init__(self) -> None:
        self._next_id = 1
        self.saved: list[Draft] = []

    def add(self, draft: Draft) -> Draft:
        draft.draft_id = self._next_id
        self._next_id += 1
        self.saved.append(draft)
        return draft

    def get_by_id(self, draft_id):
        return next((d for d in self.saved if d.draft_id == draft_id), None)

    def list_by_agent_id(self, agent_id):
        return [d for d in self.saved if d.agent_id == agent_id]


class FakeDraftVersionRepository:
    def __init__(self) -> None:
        self._next_id = 1
        self.saved: list[DraftVersion] = []

    def add(self, version: DraftVersion) -> DraftVersion:
        version.version_id = self._next_id
        self._next_id += 1
        self.saved.append(version)
        return version

    def get_by_id(self, version_id):
        return next((v for v in self.saved if v.version_id == version_id), None)

    def list_by_draft_id(self, draft_id):
        return sorted((v for v in self.saved if v.draft_id == draft_id), key=lambda v: v.version_number)

    def get_latest_by_draft_id(self, draft_id):
        versions = self.list_by_draft_id(draft_id)
        return versions[-1] if versions else None


class FakeDraftEvidenceLinkRepository:
    def __init__(self, fail_on_add: bool = False) -> None:
        self.saved = []
        self.fail_on_add = fail_on_add

    def add(self, link):
        if self.fail_on_add:
            raise RuntimeError("simulated evidence persistence failure")
        link.link_id = len(self.saved) + 1
        self.saved.append(link)
        return link

    def list_by_draft_version_id(self, draft_version_id):
        return [link for link in self.saved if link.draft_version_id == draft_version_id]


class FakeTextProvider:
    def __init__(self, response: str = "Generated draft.", exception: Exception | None = None) -> None:
        self.response = response
        self.exception = exception
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.exception is not None:
            raise self.exception
        return self.response


class FakeAgentRepository:
    def __init__(self, agent: Agent | None = None) -> None:
        self.agent = agent

    def get_by_id(self, agent_id):
        return self.agent if self.agent is not None and self.agent.agent_id == agent_id else None

    def get_by_user_id(self, user_id):
        return self.agent if self.agent is not None and self.agent.user_id == user_id else None

    def add(self, agent):
        raise NotImplementedError


class FakeWorkItemEnqueuer:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, **kwargs):
        self.enqueued.append(kwargs)
        return kwargs


class FakeContentStore:
    """In-memory ContentStore fake - matches tests/unit/test_workers_payloads.py's own."""

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


def _generation_context(*chunk_ids: int) -> ContextAssemblyInput:
    return ContextAssemblyInput(
        topic="Research topic",
        instructions="Write a grounded paragraph.",
        evidence=tuple(
            ContextEvidence(
                chunk_id=chunk_id, content=f"Evidence {chunk_id}.", summary=None, score=1.0)
            for chunk_id in chunk_ids
        ),
    )


def _generation_use_case(*, provider=None, evidence_links=None, versions=None, uow=None):
    drafts = FakeDraftRepository()
    draft = drafts.add(Draft.create(agent_id=1, title="Draft"))
    return (
        GenerateDraftVersionUseCase(
            drafts,
            versions or FakeDraftVersionRepository(),
            evidence_links or FakeDraftEvidenceLinkRepository(),
            provider or FakeTextProvider(),
            uow or FakeUnitOfWork(),
        ),
        draft,
    )


def test_create_draft_use_case_persists_and_commits():
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftUseCase(drafts, FakeAgentRepository(Agent(agent_id=1, user_id=9)), uow)

    draft = use_case.execute(user_id=9, title="Chapter 1 Draft")

    assert draft.draft_id == 1
    assert draft.agent_id == 1
    assert uow.committed is True
    assert uow.rolled_back is False


def test_create_draft_use_case_requires_an_existing_agent():
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftUseCase(drafts, FakeAgentRepository(None), uow)

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=9, title="Chapter 1 Draft")

    assert drafts.saved == []
    assert uow.committed is False


def test_create_draft_version_use_case_assigns_version_number_one_for_first_version():
    versions = FakeDraftVersionRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftVersionUseCase(versions, uow)

    version = use_case.execute(draft_id=1, content="Introduction paragraph.")

    assert version.version_number == 1
    assert version.created_by == CreatedBy.USER


def test_create_draft_version_use_case_increments_from_existing_latest():
    versions = FakeDraftVersionRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftVersionUseCase(versions, uow)

    use_case.execute(draft_id=1, content="First version.")
    second = use_case.execute(draft_id=1, content="Revised version.")

    assert second.version_number == 2


def test_create_draft_version_use_case_numbers_independently_per_draft():
    versions = FakeDraftVersionRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftVersionUseCase(versions, uow)

    use_case.execute(draft_id=1, content="Draft 1 version.")
    other_draft_version = use_case.execute(
        draft_id=2, content="Draft 2 version.")

    assert other_draft_version.version_number == 1


def test_generate_draft_version_persists_content_and_one_link_per_selected_chunk():
    evidence_links = FakeDraftEvidenceLinkRepository()
    provider = FakeTextProvider()
    uow = FakeUnitOfWork()
    use_case, draft = _generation_use_case(
        provider=provider, evidence_links=evidence_links, uow=uow)

    version = use_case.execute(
        draft_id=draft.draft_id, context=_generation_context(4, 7))

    assert version.content == "Generated draft."
    assert version.version_number == 1
    assert version.created_by == CreatedBy.SYSTEM
    assert [(link.target_type, link.chunk_id) for link in evidence_links.saved] == [
        (DraftEvidenceTargetType.KNOWLEDGE_CHUNK, 4),
        (DraftEvidenceTargetType.KNOWLEDGE_CHUNK, 7),
    ]
    assert uow.committed is True
    assert provider.prompts[0].startswith("## PROJECT TOPIC")


def test_generate_draft_version_increments_existing_versions():
    versions = FakeDraftVersionRepository()
    uow = FakeUnitOfWork()
    use_case, draft = _generation_use_case(versions=versions, uow=uow)
    versions.add(DraftVersion(draft_id=draft.draft_id,
                 version_number=1, content="Existing"))

    version = use_case.execute(
        draft_id=draft.draft_id, context=_generation_context(1))

    assert version.version_number == 2


@pytest.mark.parametrize("provider_response", ["", "   "])
def test_empty_provider_result_is_rejected_without_persistence(provider_response):
    versions = FakeDraftVersionRepository()
    evidence_links = FakeDraftEvidenceLinkRepository()
    use_case, draft = _generation_use_case(
        provider=FakeTextProvider(response=provider_response), versions=versions, evidence_links=evidence_links
    )

    with pytest.raises(EmptyGeneratedDraftContentError):
        use_case.execute(draft_id=draft.draft_id,
                         context=_generation_context(1))

    assert versions.saved == []
    assert evidence_links.saved == []


def test_generation_requires_supporting_evidence():
    versions = FakeDraftVersionRepository()
    provider = FakeTextProvider()
    use_case, draft = _generation_use_case(
        provider=provider, versions=versions)

    with pytest.raises(InsufficientDraftEvidenceError):
        use_case.execute(draft_id=draft.draft_id,
                         context=_generation_context())

    assert provider.prompts == []
    assert versions.saved == []


def test_evidence_persistence_failure_rolls_back():
    uow = FakeUnitOfWork()
    versions = FakeDraftVersionRepository()
    evidence_links = FakeDraftEvidenceLinkRepository(fail_on_add=True)
    use_case, draft = _generation_use_case(
        versions=versions, evidence_links=evidence_links, uow=uow
    )

    with pytest.raises(RuntimeError, match="evidence persistence failure"):
        use_case.execute(draft_id=draft.draft_id,
                         context=_generation_context(1))

    assert uow.committed is False
    assert uow.rolled_back is True


def test_enqueue_generation_requires_authenticated_draft_owner():
    drafts = FakeDraftRepository()
    draft = drafts.add(Draft.create(agent_id=4, title="Owned Draft"))
    enqueuer = FakeWorkItemEnqueuer()
    uow = FakeUnitOfWork()
    use_case = EnqueueDraftGenerationUseCase(
        drafts, FakeAgentRepository(Agent(agent_id=4, user_id=9)), enqueuer, FakeContentStore(), uow
    )

    work_item = use_case.execute(
        user_id=9, draft_id=draft.draft_id, context=_generation_context(1))

    assert work_item["kind"].value == "pipeline_stage"
    assert work_item["idempotency_key"].startswith("generate_draft_version:")
    assert uow.committed is True

    with pytest.raises(DraftNotFoundError):
        use_case.execute(user_id=10, draft_id=draft.draft_id,
                         context=_generation_context(1))


def test_enqueue_generation_accepts_a_realistic_evidence_sized_context():
    """Regression test for the fixed defect: enqueuing used to inline the full serialized
    context into payload_reference and reject anything over 512 characters, which any context
    with real evidence content would exceed. The context now goes through content_store.
    """
    drafts = FakeDraftRepository()
    draft = drafts.add(Draft.create(agent_id=4, title="Owned Draft"))
    enqueuer = FakeWorkItemEnqueuer()
    uow = FakeUnitOfWork()
    use_case = EnqueueDraftGenerationUseCase(
        drafts, FakeAgentRepository(Agent(agent_id=4, user_id=9)), enqueuer, FakeContentStore(), uow
    )
    realistic_context = ContextAssemblyInput(
        topic="Research topic",
        instructions="Write a grounded paragraph.",
        evidence=tuple(
            ContextEvidence(chunk_id=index, content="Evidence paragraph. " * 100, summary=None, score=1.0)
            for index in range(10)
        ),
    )

    work_item = use_case.execute(user_id=9, draft_id=draft.draft_id, context=realistic_context)

    assert len(work_item["payload_reference"]) < 200
    assert uow.committed is True
