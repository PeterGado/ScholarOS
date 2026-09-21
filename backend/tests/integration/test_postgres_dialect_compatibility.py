"""Real-Postgres compatibility coverage for the Postgres migration (ADR-004's named eventual
path). Every test here is skipped unless POSTGRES_TEST_URL is set to a real, reachable Postgres
connection string - Postgres is local infrastructure the developer must have running (unlike
this project's paid/external AI providers, which real tests never call per
Backend_Slice2_Implementation_Plan.md §8 - a genuinely different concern from "is a local
database reachable").

Run against a real local Postgres:
    POSTGRES_TEST_URL="postgresql://user:pass@localhost:5432/scholaros_test" pytest tests/integration/test_postgres_dialect_compatibility.py -v
"""

import os

import pytest
from sqlalchemy import text

from app.ai.usage_guard import AiUsageGuard
from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge.application.retrieval import SearchKnowledgeUseCase
from app.modules.knowledge.application.use_cases import ExtractDocumentKnowledgeUseCase, ProcessDocumentUseCase
from app.modules.knowledge.domain.text_extraction import PlainTextExtractor
from app.modules.knowledge.infrastructure.repositories import (
    SqlAlchemyChunkEvidenceLinkRepository,
    SqlAlchemyKnowledgeChunkEmbeddingRepository,
    SqlAlchemyKnowledgeChunkRepository,
    SqlAlchemyKnowledgeElementRepository,
    SqlAlchemyLexicalSearchRepository,
)
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.repository import WorkItemRepository

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL not set - skipping real-Postgres compatibility tests",
)


class FakeTextGenerationProvider:
    def generate(self, prompt: str) -> str:
        return '[{"element_type": "concept", "label": "L", "description": "d"}]'


class FakeEmbeddingProvider:
    def __init__(self, vectors_by_text: dict[str, list[float]]):
        self._vectors_by_text = vectors_by_text

    def embed(self, text: str) -> list[float]:
        return self._vectors_by_text.get(text, [0.0, 0.0])

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


@pytest.fixture()
def engine():
    """A real Postgres engine, schema created via init_db() (create_all + the dialect-aware
    lexical index setup) - proves the same bootstrap path the app's own test fixtures already
    use for SQLite also works, unmodified, against a real Postgres instance. Every table is
    dropped at teardown so repeated runs start clean.
    """
    eng = build_engine(POSTGRES_TEST_URL)
    init_db(eng)
    yield eng
    with eng.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()
    eng.dispose()


@pytest.fixture()
def session(engine):
    factory = build_sessionmaker(engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def storage(tmp_path):
    return FilesystemStorage(tmp_path / "object-store")


def test_init_db_creates_the_search_vector_column_and_gin_index(engine):
    with engine.connect() as connection:
        column = connection.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'knowledge_chunks' AND column_name = 'search_vector'"
            )
        ).first()
        assert column is not None
        assert column[0] == "tsvector"

        index = connection.execute(
            text("SELECT indexname FROM pg_indexes WHERE indexname = 'knowledge_chunks_search_vector_idx'")
        ).first()
        assert index is not None


def _provision_agent_with_knowledge(session, storage, *, username: str, content: bytes, embedding_provider) -> tuple:
    user = User(username=username)
    session.add(user)
    session.flush()

    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic="Topic"
    )

    documents = SqlAlchemyDocumentRepository(session)
    document = UploadResearchDocumentUseCase(
        documents, projects, agents, storage, uow, WorkItemRepository(session), AiUsageGuard(None, None, daily_token_cap=None)
    ).execute(project_id=workspace.project.project_id, user_id=user.user_id, title="Doc", format="txt", content=content)

    process_document = ProcessDocumentUseCase(documents, storage, PlainTextExtractor())
    ExtractDocumentKnowledgeUseCase(
        documents,
        projects,
        agents,
        process_document,
        FakeTextGenerationProvider(),
        embedding_provider,
        "test-embedding-model",
        SqlAlchemyKnowledgeElementRepository(session),
        SqlAlchemyKnowledgeChunkRepository(session),
        SqlAlchemyChunkEvidenceLinkRepository(session),
        SqlAlchemyKnowledgeChunkEmbeddingRepository(session),
        uow,
    ).execute(document_id=document.document_id)

    return workspace.agent.agent_id, user.user_id


def _search_use_case(session, embedding_provider) -> SearchKnowledgeUseCase:
    return SearchKnowledgeUseCase(
        SqlAlchemyAgentRepository(session),
        embedding_provider,
        SqlAlchemyKnowledgeChunkEmbeddingRepository(session),
        SqlAlchemyKnowledgeChunkRepository(session),
        SqlAlchemyChunkEvidenceLinkRepository(session),
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyLexicalSearchRepository(session),
        AiUsageGuard(None, None, daily_token_cap=None),
    )


def test_hybrid_search_works_end_to_end_on_real_postgres(session, storage):
    """The same real pipeline test_search_knowledge_integration.py runs against SQLite, run
    here against real Postgres - proves the tsvector/GIN lexical branch and the semantic branch
    both work and fuse correctly on this dialect, not just SQLite's FTS5 path.
    """
    embedding_provider = FakeEmbeddingProvider(
        {"About coastal erosion research.": [1.0, 0.0], "search query about coastal erosion": [1.0, 0.0]}
    )
    _, user_id = _provision_agent_with_knowledge(
        session, storage, username="researcher", content=b"About coastal erosion research.", embedding_provider=embedding_provider
    )

    results = _search_use_case(session, embedding_provider).execute(
        user_id=user_id, query="search query about coastal erosion"
    )

    assert len(results) == 1
    assert results[0].content == "About coastal erosion research."


def test_an_exact_term_the_embedding_would_miss_is_still_found_on_real_postgres(session, storage):
    """ADR-005's own stated rationale, proven on Postgres specifically - the same case
    `test_knowledge_search_api.py` proves over real HTTP on SQLite.
    """
    embedding_provider = FakeEmbeddingProvider({})  # every text embeds to [0.0, 0.0] - no signal
    _, user_id = _provision_agent_with_knowledge(
        session,
        storage,
        username="researcher2",
        content=b"See Rimamshung et al., 2023 for the full methodology.",
        embedding_provider=embedding_provider,
    )

    results = _search_use_case(session, embedding_provider).execute(user_id=user_id, query="Rimamshung")

    assert len(results) == 1
    assert "Rimamshung" in results[0].content


def test_at_most_one_active_writing_profile_per_agent_is_enforced_but_a_second_after_deactivation_is_allowed(session):
    """Directly proves the postgresql_where fix (app/modules/writing/infrastructure/models.py)
    - without it, this partial unique index silently became a *full* unique index on Postgres,
    which would make the second insert below fail even though the first profile is inactive.
    """
    from app.modules.writing.domain.entities import WritingProfile
    from app.modules.writing.domain.enums import WritingProfileStatus
    from app.modules.writing.infrastructure.repositories import SqlAlchemyWritingProfileRepository

    user = User(username="profile-owner")
    session.add(user)
    session.flush()
    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic="Topic"
    )
    agent_id = workspace.agent.agent_id

    profiles = SqlAlchemyWritingProfileRepository(session)
    first = profiles.add(
        WritingProfile(agent_id=agent_id, user_id=user.user_id, name="Primary Writing Profile", status=WritingProfileStatus.ACTIVE)
    )
    session.commit()

    # A second *active* profile for the same Agent must still be rejected (the real invariant).
    with pytest.raises(Exception):  # noqa: B017 - a real IntegrityError from the DB, not a domain exception
        profiles.add(
            WritingProfile(
                agent_id=agent_id, user_id=user.user_id, name="Second Active", status=WritingProfileStatus.ACTIVE
            )
        )
        session.commit()
    session.rollback()

    # Deactivating the first, then creating a second, must succeed - this is exactly what a
    # full (non-partial) unique index would have wrongly forbidden.
    session.execute(
        text("UPDATE writing_profiles SET status = 'inactive' WHERE profile_id = :id"), {"id": first.profile_id}
    )
    profiles.add(
        WritingProfile(
            agent_id=agent_id, user_id=user.user_id, name="Second, After Deactivation", status=WritingProfileStatus.ACTIVE
        )
    )
    session.commit()  # must not raise
