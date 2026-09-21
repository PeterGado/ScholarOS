import pytest

from app.ai.exceptions import ProviderRequestError
from app.ai.usage_guard import AiUsageGuard
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.domain.exceptions import AgentNotFoundForUserError
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.application.style_extraction import ExtractWritingStyleProfileUseCase
from app.modules.writing.application.style_ingestion import UploadWritingStyleDocumentUseCase
from app.modules.writing.domain.exceptions import (
    InvalidStyleSampleReferenceError,
    StyleExtractionError,
    WritingProfileAlreadyExtractedError,
)
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyProfileCharacteristicSourceRepository,
    SqlAlchemyWritingProfileRepository,
)
from app.storage.filesystem import FilesystemStorage

VALID_RESPONSE = """{"characteristics": [
  {"characteristic_type": "structure", "signal": "Short declarative sentences.", "confidence": 0.8},
  {"characteristic_type": "vocabulary", "signal": "Frequent technical terminology."}
]}"""


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


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "writing_style_extraction_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


@pytest.fixture()
def storage(tmp_path):
    return FilesystemStorage(tmp_path / "object-store")


def _make_workspace(session, username="researcher"):
    user = User(username=username)
    session.add(user)
    session.flush()

    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    create_project = CreateProjectUseCase(projects)
    workspace_use_case = CreateAgentWorkspaceUseCase(agents, create_project, uow)
    return workspace_use_case.execute(user_id=user.user_id, project_title="Thesis", project_topic="Topic")


def _upload_style_documents(session, storage, user_id: int, contents: list[bytes]) -> list[int]:
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    agents = SqlAlchemyAgentRepository(session)
    profiles = SqlAlchemyWritingProfileRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    use_case = UploadWritingStyleDocumentUseCase(documents, projects, agents, profiles, storage, uow)

    document_ids = []
    for i, content in enumerate(contents):
        result = use_case.execute(user_id=user_id, title=f"Sample {i}", format="txt", content=content)
        document_ids.append(result.document.document_id)
    return document_ids


def _build_extraction_use_case(session, storage, provider):
    documents = SqlAlchemyDocumentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    agents = SqlAlchemyAgentRepository(session)
    profiles = SqlAlchemyWritingProfileRepository(session)
    characteristics = SqlAlchemyProfileCharacteristicRepository(session)
    sources = SqlAlchemyProfileCharacteristicSourceRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    use_case = ExtractWritingStyleProfileUseCase(
        agents, projects, documents, storage, profiles, characteristics, sources, provider, uow,
        AiUsageGuard(None, None, daily_token_cap=None),
    )
    return use_case, profiles, characteristics, sources


def test_extraction_persists_profile_characteristics_and_provenance(session, storage):
    workspace = _make_workspace(session)
    document_ids = _upload_style_documents(session, storage, workspace.agent.user_id, [b"Sample A content.", b"Sample B content."])
    provider = FakeProvider(response=VALID_RESPONSE)
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)

    result = use_case.execute(user_id=workspace.agent.user_id, document_ids=document_ids)

    session.expire_all()
    stored_profile = profiles.get_active_by_agent_id(workspace.agent.agent_id)
    assert stored_profile is not None
    assert stored_profile.profile_id == result.profile.profile_id

    stored_characteristics = characteristics.list_by_profile_id(stored_profile.profile_id)
    assert len(stored_characteristics) == 2


def test_provenance_mandatory_test_every_characteristic_traces_to_the_actual_samples(session, storage):
    """Stage 4 prompt §30: given samples A, B, C and characteristics X, Y, verify persisted
    characteristics have valid ProfileCharacteristicSource relationships pointing only to the
    actual supplied samples - never an arbitrary integer from the model output.
    """
    workspace = _make_workspace(session)
    document_ids = _upload_style_documents(
        session, storage, workspace.agent.user_id, [b"Sample A.", b"Sample B.", b"Sample C."]
    )
    malicious_response = (
        '{"characteristics": ['
        '{"characteristic_type": "structure", "signal": "X", "source_id": 999999}, '
        '{"characteristic_type": "vocabulary", "signal": "Y", "document_id": 888888}'
        "]}"
    )
    provider = FakeProvider(response=malicious_response)
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)

    result = use_case.execute(user_id=workspace.agent.user_id, document_ids=document_ids)

    for characteristic in characteristics.list_by_profile_id(result.profile.profile_id):
        linked_sources = sources.list_by_characteristic_id(characteristic.characteristic_id)
        assert linked_sources, "every characteristic must have provenance"
        linked_document_ids = {s.document_id for s in linked_sources}
        assert linked_document_ids == set(document_ids), "provenance must point only to the actual supplied samples"
        assert 999999 not in linked_document_ids
        assert 888888 not in linked_document_ids


def test_no_duplicate_profile_and_no_orphan_characteristics_after_successful_extraction(session, storage):
    workspace = _make_workspace(session)
    document_ids = _upload_style_documents(session, storage, workspace.agent.user_id, [b"Sample content."])
    provider = FakeProvider(response=VALID_RESPONSE)
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)

    use_case.execute(user_id=workspace.agent.user_id, document_ids=document_ids)

    from app.modules.writing.infrastructure.models import WritingProfile as WritingProfileModel

    all_profiles = session.query(WritingProfileModel).filter_by(agent_id=workspace.agent.agent_id).all()
    assert len(all_profiles) == 1

    for characteristic in characteristics.list_by_profile_id(all_profiles[0].profile_id):
        assert sources.list_by_characteristic_id(characteristic.characteristic_id)


def test_malformed_ai_output_rolls_back_and_leaves_no_partial_state(session, storage):
    workspace = _make_workspace(session)
    document_ids = _upload_style_documents(session, storage, workspace.agent.user_id, [b"Sample content."])
    mixed_response = '{"characteristics": [{"characteristic_type": "structure", "signal": "Valid."}, {"characteristic_type": "bogus", "signal": "Invalid."}]}'
    provider = FakeProvider(response=mixed_response)
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)

    with pytest.raises(StyleExtractionError):
        use_case.execute(user_id=workspace.agent.user_id, document_ids=document_ids)

    session.expire_all()
    stored_profile = profiles.get_active_by_agent_id(workspace.agent.agent_id)
    # Stage 3's upload use case already created the profile (before extraction ever ran) -
    # confirm extraction added zero characteristics to it.
    assert stored_profile is not None
    assert characteristics.list_by_profile_id(stored_profile.profile_id) == []


def test_provider_failure_leaves_no_partial_state(session, storage):
    workspace = _make_workspace(session)
    document_ids = _upload_style_documents(session, storage, workspace.agent.user_id, [b"Sample content."])
    provider = FakeProvider(exception=ProviderRequestError("simulated provider outage"))
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)

    with pytest.raises(ProviderRequestError):
        use_case.execute(user_id=workspace.agent.user_id, document_ids=document_ids)

    session.expire_all()
    stored_profile = profiles.get_active_by_agent_id(workspace.agent.agent_id)
    assert characteristics.list_by_profile_id(stored_profile.profile_id) == []


def test_document_from_a_different_agent_cannot_be_used_as_a_sample(session, storage):
    workspace_a = _make_workspace(session, username="user-a")
    workspace_b = _make_workspace(session, username="user-b")
    document_ids_b = _upload_style_documents(session, storage, workspace_b.agent.user_id, [b"B's sample."])

    provider = FakeProvider(response=VALID_RESPONSE)
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)

    with pytest.raises(InvalidStyleSampleReferenceError):
        use_case.execute(user_id=workspace_a.agent.user_id, document_ids=document_ids_b)

    assert profiles.get_active_by_agent_id(workspace_a.agent.agent_id) is None


def test_user_with_no_agent_cannot_trigger_extraction(session, storage):
    other_user = User(username="no-agent-yet")
    session.add(other_user)
    session.commit()
    provider = FakeProvider(response=VALID_RESPONSE)
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)

    with pytest.raises(AgentNotFoundForUserError):
        use_case.execute(user_id=other_user.user_id, document_ids=[1])


def test_second_extraction_against_the_same_profile_is_refused(session, storage):
    workspace = _make_workspace(session)
    document_ids = _upload_style_documents(session, storage, workspace.agent.user_id, [b"Sample content."])
    provider = FakeProvider(response=VALID_RESPONSE)
    use_case, profiles, characteristics, sources = _build_extraction_use_case(session, storage, provider)
    use_case.execute(user_id=workspace.agent.user_id, document_ids=document_ids)

    second_provider = FakeProvider(response=VALID_RESPONSE)
    second_use_case, *_ = _build_extraction_use_case(session, storage, second_provider)

    with pytest.raises(WritingProfileAlreadyExtractedError):
        second_use_case.execute(user_id=workspace.agent.user_id, document_ids=document_ids)

    assert len(second_provider.prompts) == 0
