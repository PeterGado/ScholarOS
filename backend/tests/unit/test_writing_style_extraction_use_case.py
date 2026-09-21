import pytest

from app.ai.exceptions import ProviderRequestError
from app.ai.usage_guard import AiUsageGuard
from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.entities import Project
from app.modules.project.domain.repositories import ProjectRepository
from app.modules.writing.application.style_extraction import ExtractWritingStyleProfileUseCase
from app.modules.writing.domain.entities import ProfileCharacteristic, ProfileCharacteristicSource, WritingProfile
from app.modules.writing.domain.enums import ProfileCharacteristicType
from app.modules.writing.domain.exceptions import (
    InvalidStyleSampleReferenceError,
    MissingStoredStyleSampleError,
    NoUsableWritingStyleSamplesError,
    StyleExtractionError,
    UnusableWritingStyleSampleError,
    WritingProfileAlreadyExtractedError,
)
from app.modules.writing.domain.repositories import (
    ProfileCharacteristicRepository,
    ProfileCharacteristicSourceRepository,
    WritingProfileRepository,
)

USER_ID = 1
AGENT_ID = 1
PROJECT_ID = 1

VALID_RESPONSE = """{"characteristics": [
  {"characteristic_type": "structure", "signal": "Short declarative sentences.", "confidence": 0.8},
  {"characteristic_type": "vocabulary", "signal": "Frequent technical terminology."}
]}"""


class FakeAgentRepository(AgentRepository):
    def __init__(self, agents: dict[int, Agent] | None = None):
        self._agents = agents if agents is not None else {AGENT_ID: Agent(user_id=USER_ID, agent_id=AGENT_ID)}

    def get_by_user_id(self, user_id):
        return next((a for a in self._agents.values() if a.user_id == user_id), None)

    def get_by_id(self, agent_id):
        return self._agents.get(agent_id)

    def add(self, agent):
        raise NotImplementedError


class FakeProjectRepository(ProjectRepository):
    def __init__(self):
        self.project = Project(project_id=PROJECT_ID, agent_id=AGENT_ID, title="Thesis", topic="Topic")

    def get_by_agent_id(self, agent_id):
        return self.project if agent_id == AGENT_ID else None

    def get_by_id(self, project_id):
        raise NotImplementedError

    def add(self, project):
        raise NotImplementedError


class FakeDocumentRepository(DocumentRepository):
    def __init__(self, documents: dict[int, ResearchDocument] | None = None):
        self._by_id = documents or {}

    def get_by_id(self, document_id):
        return self._by_id.get(document_id)

    def list_by_project_id(self, project_id):
        return [d for d in self._by_id.values() if d.project_id == project_id]

    def add(self, document):
        raise NotImplementedError

    def update_processing_status(self, document_id, status, *, processed_at=None):
        raise NotImplementedError

    def mark_deleted(self, document_id, *, deleted_at):
        raise NotImplementedError


class FakeContentStore:
    def __init__(self, content_by_reference: dict[str, bytes] | None = None):
        self._content = content_by_reference or {}

    def exists(self, reference: str) -> bool:
        return reference in self._content

    def read(self, reference: str) -> bytes:
        return self._content[reference]

    def save(self, content: bytes, *, extension: str = "") -> str:
        raise NotImplementedError


class FakeWritingProfileRepository(WritingProfileRepository):
    def __init__(self, existing: WritingProfile | None = None):
        self._next_id = 1
        self._by_id: dict[int, WritingProfile] = {}
        if existing is not None:
            existing.profile_id = self._next_id
            self._by_id[self._next_id] = existing
            self._next_id += 1

    def add(self, profile: WritingProfile) -> WritingProfile:
        profile.profile_id = self._next_id
        self._by_id[self._next_id] = profile
        self._next_id += 1
        return profile

    def get_by_id(self, profile_id):
        return self._by_id.get(profile_id)

    def get_active_by_agent_id(self, agent_id):
        return next((p for p in self._by_id.values() if p.agent_id == agent_id and p.status.value == "active"), None)


class FakeProfileCharacteristicRepository(ProfileCharacteristicRepository):
    def __init__(self, fail_on_add: bool = False):
        self._next_id = 1
        self.saved: list[ProfileCharacteristic] = []
        self._fail_on_add = fail_on_add

    def add(self, characteristic: ProfileCharacteristic) -> ProfileCharacteristic:
        if self._fail_on_add and len(self.saved) >= 1:
            raise RuntimeError("simulated persistence failure")
        characteristic.characteristic_id = self._next_id
        self._next_id += 1
        self.saved.append(characteristic)
        return characteristic

    def list_by_profile_id(self, profile_id):
        return [c for c in self.saved if c.profile_id == profile_id]


class FakeProfileCharacteristicSourceRepository(ProfileCharacteristicSourceRepository):
    def __init__(self):
        self._next_id = 1
        self.saved: list[ProfileCharacteristicSource] = []

    def add(self, source: ProfileCharacteristicSource) -> ProfileCharacteristicSource:
        source.link_id = self._next_id
        self._next_id += 1
        self.saved.append(source)
        return source

    def list_by_characteristic_id(self, characteristic_id):
        return [s for s in self.saved if s.characteristic_id == characteristic_id]


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeProvider:
    def __init__(self, response: str | None = None, exception: Exception | None = None):
        self.response = response
        self.exception = exception
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.exception is not None:
            raise self.exception
        return self.response


def _make_document(document_id: int, *, project_id: int = PROJECT_ID, content_reference: str = "ref") -> ResearchDocument:
    return ResearchDocument(
        document_id=document_id, project_id=project_id, title=f"Doc {document_id}", format="txt", content_reference=content_reference
    )


def _build(
    *,
    agents=None,
    documents=None,
    content=None,
    existing_profile=None,
    provider_response=VALID_RESPONSE,
    provider_exception=None,
    fail_characteristic_add=False,
):
    agent_repository = FakeAgentRepository(agents)
    project_repository = FakeProjectRepository()
    document_repository = FakeDocumentRepository(documents)
    content_store = FakeContentStore(content)
    profiles = FakeWritingProfileRepository(existing=existing_profile)
    characteristics = FakeProfileCharacteristicRepository(fail_on_add=fail_characteristic_add)
    sources = FakeProfileCharacteristicSourceRepository()
    provider = FakeProvider(response=provider_response, exception=provider_exception)
    uow = FakeUnitOfWork()

    use_case = ExtractWritingStyleProfileUseCase(
        agent_repository, project_repository, document_repository, content_store, profiles, characteristics, sources, provider, uow,
        AiUsageGuard(None, None, daily_token_cap=None),
    )
    return use_case, profiles, characteristics, sources, uow, provider


# --- happy path -------------------------------------------------------------------


def test_extraction_creates_profile_and_characteristics_with_provenance():
    doc1 = _make_document(1, content_reference="ref-1")
    doc2 = _make_document(2, content_reference="ref-2")
    use_case, profiles, characteristics, sources, uow, provider = _build(
        documents={1: doc1, 2: doc2}, content={"ref-1": b"Sample one.", "ref-2": b"Sample two."}
    )

    result = use_case.execute(user_id=USER_ID, document_ids=[1, 2])

    assert result.profile.profile_id is not None
    assert len(result.characteristics) == 2
    assert uow.committed is True
    for item in result.characteristics:
        assert set(item.source_document_ids) == {1, 2}
    # Every persisted characteristic has at least one ProfileCharacteristicSource row.
    for characteristic in characteristics.saved:
        assert sources.list_by_characteristic_id(characteristic.characteristic_id)


def test_extraction_reuses_the_existing_active_writing_profile():
    existing = WritingProfile(agent_id=AGENT_ID, user_id=USER_ID, name="Existing Profile")
    doc = _make_document(1)
    use_case, profiles, characteristics, sources, uow, provider = _build(
        documents={1: doc}, content={"ref": b"Sample."}, existing_profile=existing
    )

    result = use_case.execute(user_id=USER_ID, document_ids=[1])

    assert result.profile.profile_id == existing.profile_id


def test_prompt_receives_all_supplied_sample_texts_in_order():
    doc1 = _make_document(1, content_reference="ref-1")
    doc2 = _make_document(2, content_reference="ref-2")
    use_case, *_rest, provider = _build(
        documents={1: doc1, 2: doc2}, content={"ref-1": b"First sample.", "ref-2": b"Second sample."}
    )

    use_case.execute(user_id=USER_ID, document_ids=[1, 2])

    prompt = provider.prompts[0]
    assert prompt.index("First sample.") < prompt.index("Second sample.")


# --- ownership -------------------------------------------------------------------


def test_user_with_no_agent_is_rejected():
    use_case, profiles, characteristics, sources, uow, provider = _build(agents={})

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=USER_ID, document_ids=[1])

    assert uow.committed is False


def test_document_not_belonging_to_the_callers_project_is_rejected():
    foreign_doc = _make_document(1, project_id=999)
    use_case, profiles, characteristics, sources, uow, provider = _build(documents={1: foreign_doc})

    with pytest.raises(InvalidStyleSampleReferenceError):
        use_case.execute(user_id=USER_ID, document_ids=[1])

    assert uow.committed is False
    assert characteristics.saved == []


def test_nonexistent_document_id_is_rejected():
    use_case, profiles, characteristics, sources, uow, provider = _build(documents={})

    with pytest.raises(InvalidStyleSampleReferenceError):
        use_case.execute(user_id=USER_ID, document_ids=[999])


def test_ai_response_cannot_control_which_agent_or_profile_is_used():
    """The AI response has no field for agent_id/profile_id/user_id at all - ownership is
    established entirely before the provider is ever called.
    """
    doc = _make_document(1)
    malicious_response = '{"characteristics": [{"characteristic_type": "structure", "signal": "x", "agent_id": 999, "profile_id": 999, "user_id": 999}]}'
    use_case, profiles, characteristics, sources, uow, provider = _build(
        documents={1: doc}, content={"ref": b"Sample."}, provider_response=malicious_response
    )

    result = use_case.execute(user_id=USER_ID, document_ids=[1])

    assert result.profile.agent_id == AGENT_ID
    assert characteristics.saved[0].profile_id == result.profile.profile_id


# --- empty / missing samples -------------------------------------------------------------------


def test_no_document_ids_is_rejected():
    use_case, profiles, characteristics, sources, uow, provider = _build()

    with pytest.raises(NoUsableWritingStyleSamplesError):
        use_case.execute(user_id=USER_ID, document_ids=[])

    assert uow.committed is False


def test_missing_stored_content_is_rejected():
    doc = _make_document(1, content_reference="ref-missing")
    use_case, profiles, characteristics, sources, uow, provider = _build(documents={1: doc}, content={})

    with pytest.raises(MissingStoredStyleSampleError):
        use_case.execute(user_id=USER_ID, document_ids=[1])

    assert uow.committed is False


def test_empty_sample_content_is_rejected():
    doc = _make_document(1, content_reference="ref-empty")
    use_case, profiles, characteristics, sources, uow, provider = _build(documents={1: doc}, content={"ref-empty": b"   "})

    with pytest.raises(UnusableWritingStyleSampleError):
        use_case.execute(user_id=USER_ID, document_ids=[1])


# --- provider failure -------------------------------------------------------------------


def test_provider_failure_propagates_and_writes_nothing():
    doc = _make_document(1)
    use_case, profiles, characteristics, sources, uow, provider = _build(
        documents={1: doc}, content={"ref": b"Sample."}, provider_exception=ProviderRequestError("boom")
    )

    with pytest.raises(ProviderRequestError):
        use_case.execute(user_id=USER_ID, document_ids=[1])

    assert uow.committed is False
    assert characteristics.saved == []


# --- mandatory failure-atomicity test (Stage 4 prompt §29) -------------------------------------------------------------------


def test_malformed_ai_output_leaves_no_partial_profile():
    """One valid characteristic followed by one invalid characteristic in the same response
    must result in zero persisted WritingProfile/ProfileCharacteristic/ProfileCharacteristicSource
    rows - the parse fails before persistence ever begins.
    """
    doc = _make_document(1)
    mixed_response = '{"characteristics": [{"characteristic_type": "structure", "signal": "Valid."}, {"characteristic_type": "not-a-type", "signal": "Invalid."}]}'
    use_case, profiles, characteristics, sources, uow, provider = _build(
        documents={1: doc}, content={"ref": b"Sample."}, provider_response=mixed_response
    )

    with pytest.raises(StyleExtractionError):
        use_case.execute(user_id=USER_ID, document_ids=[1])

    assert uow.committed is False
    assert characteristics.saved == []
    assert sources.saved == []
    assert profiles.get_active_by_agent_id(AGENT_ID) is None


def test_persistence_failure_rolls_back_the_whole_batch():
    """A database/repository failure partway through persisting characteristics must roll
    back everything already written in this call, not leave a partial profile.
    """
    doc = _make_document(1)
    two_characteristic_response = '{"characteristics": [{"characteristic_type": "structure", "signal": "A"}, {"characteristic_type": "vocabulary", "signal": "B"}]}'
    use_case, profiles, characteristics, sources, uow, provider = _build(
        documents={1: doc}, content={"ref": b"Sample."}, provider_response=two_characteristic_response, fail_characteristic_add=True
    )

    with pytest.raises(RuntimeError):
        use_case.execute(user_id=USER_ID, document_ids=[1])

    assert uow.rolled_back is True
    assert uow.committed is False


# --- regeneration ambiguity (Stage 4 prompt §12/§13) -------------------------------------------------------------------


def test_re_extraction_against_an_already_extracted_profile_is_refused():
    existing = WritingProfile(agent_id=AGENT_ID, user_id=USER_ID, name="Existing Profile")
    doc = _make_document(1)
    use_case, profiles, characteristics, sources, uow, provider = _build(
        documents={1: doc}, content={"ref": b"Sample."}, existing_profile=existing
    )
    characteristics.add(
        ProfileCharacteristic(profile_id=existing.profile_id, characteristic_type=ProfileCharacteristicType.STRUCTURE, signal="Prior.")
    )

    with pytest.raises(WritingProfileAlreadyExtractedError):
        use_case.execute(user_id=USER_ID, document_ids=[1])

    assert len(provider.prompts) == 0, "the AI provider must not be called when extraction is refused up front"
