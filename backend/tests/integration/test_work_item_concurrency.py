"""Real-Postgres Work Item queue concurrency coverage (2026-09-30, concurrent-load planning).
Same POSTGRES_TEST_URL-gated pattern as test_row_level_security.py - `SELECT ... FOR UPDATE
SKIP LOCKED` cannot be exercised against SQLite at all (no such feature there), so a real local
Postgres is required to prove `claim_next_queued` is actually safe under concurrent callers.

Run against a real local Postgres:
    POSTGRES_TEST_URL="postgresql://user:pass@localhost:5432/scholaros_test" pytest tests/integration/test_work_item_concurrency.py -v

This is the regression test this codebase didn't have: `test_row_level_security.py` already
proves RLS's own mechanism works, but nothing proved the Work Item queue's claiming logic is
safe under real concurrent access - the exact kind of Postgres-only behavior that has no
SQLite-based substitute. This file proves two things directly: (1) N threads claiming from a
shared queue at the same real moment never claim the same row twice, and (2) running several
`WorkItemExecutorLoop` worker threads genuinely processes items faster in wall-clock time than
one, not just "should in theory."
"""

import os
import threading
import time

import pytest
from sqlalchemy import text

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.document.application.use_cases import UploadResearchDocumentUseCase
from app.modules.document.domain.enums import DocumentProcessingStatus
from app.modules.document.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.storage.filesystem import FilesystemStorage
from app.workers.enums import WorkItemKind, WorkItemState
from app.workers.executor import WorkItemExecutorLoop
from app.workers.models import WorkItem as WorkItemModel
from app.workers.repository import WorkItemRepository

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL not set - skipping real-Postgres Work Item concurrency tests",
)


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class SlowTextGenerationProvider:
    """Simulates a real AI call's latency without a real one - a fixed, short, deterministic
    sleep is enough to prove wall-clock throughput scales with worker_count; the exact duration
    doesn't matter, only that it's the same for every item so a 1-worker vs N-worker comparison
    is apples to apples.
    """

    def __init__(self, delay_seconds: float = 0.2) -> None:
        self._delay_seconds = delay_seconds

    def generate(self, prompt: str) -> str:
        time.sleep(self._delay_seconds)
        return '[{"element_type": "concept", "label": "Concurrent", "description": "d"}]'


@pytest.fixture()
def pg_engine():
    """A real engine against the local Postgres test database, schema created fresh and torn
    down after - no roles/RLS policies needed here (unlike test_row_level_security.py), since
    this file tests the Work Item queue's own concurrency safety, not RLS.
    """
    eng = build_engine(POSTGRES_TEST_URL)
    with eng.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def storage(tmp_path):
    return FilesystemStorage(tmp_path / "object-store")


def _upload_documents(engine, storage, count: int) -> None:
    """Enqueues `count` real process_document Work Items against a real Postgres session -
    reuses the actual application use case (UploadResearchDocumentUseCase), not a hand-rolled
    INSERT, so this exercises the same enqueue path production does.
    """
    session = build_sessionmaker(engine)()
    try:
        user = User(username=f"concurrency-test-{id(session)}")
        session.add(user)
        session.flush()

        agents = SqlAlchemyAgentRepository(session)
        projects = SqlAlchemyProjectRepository(session)
        uow = SqlAlchemyUnitOfWork(session)
        workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
            user_id=user.user_id, project_title="Thesis", project_topic="Topic"
        )

        documents = SqlAlchemyDocumentRepository(session)
        from app.ai.usage_guard import AiUsageGuard
        from app.auth.email_verification_guard import EmailVerificationGuard
        from app.auth.infrastructure import SqlAlchemyUserCredentialLookup
        from app.workers.repository import WorkItemRepository as WIR

        upload = UploadResearchDocumentUseCase(
            documents,
            projects,
            agents,
            storage,
            uow,
            WIR(session),
            AiUsageGuard(None, None, daily_token_cap=None),
            EmailVerificationGuard(SqlAlchemyUserCredentialLookup(session)),
        )
        for i in range(count):
            upload.execute(
                project_id=workspace.project.project_id,
                user_id=user.user_id,
                title=f"Doc {i}",
                format="txt",
                content=b"Some content.",
            )
        session.commit()
    finally:
        session.close()


def _enqueue_fake_work_items(engine, count: int) -> None:
    """Plain Work Item rows with no underlying document/conversation - enough for a
    claim_next_queued concurrency test, which only ever touches the work_items table itself and
    never processes the item, unlike test_more_workers_drain_the_queue_faster below. Avoids
    UploadResearchDocumentUseCase's own MAX_RESEARCH_DOCUMENTS_PER_PROJECT business limit (20),
    which is irrelevant to what this test is actually proving.
    """
    session = build_sessionmaker(engine)()
    try:
        work_items = WorkItemRepository(session)
        for i in range(count):
            work_items.enqueue(
                kind=WorkItemKind.PIPELINE_STAGE,
                payload_reference=f"process_document:{i}",
                idempotency_key=f"concurrency-test:{id(session)}:{i}",
            )
        session.commit()
    finally:
        session.close()


def test_concurrent_claimers_never_claim_the_same_work_item_twice(pg_engine, storage):
    """The actual point of SKIP LOCKED: real threads, real separate sessions, all claiming from
    the same table at genuinely the same moment - not simulated, not sequential.
    """
    item_count = 30
    thread_count = 6
    _enqueue_fake_work_items(pg_engine, item_count)

    claimed_ids: list[int] = []
    lock = threading.Lock()
    start_barrier = threading.Barrier(thread_count)

    def _claim_until_empty() -> None:
        session = build_sessionmaker(pg_engine)()
        try:
            start_barrier.wait()  # maximize actual concurrent contention on the first claim
            while True:
                with session.begin():
                    item = WorkItemRepository(session).claim_next_queued()
                if item is None:
                    return
                with lock:
                    claimed_ids.append(item.work_item_id)
        finally:
            session.close()

    threads = [threading.Thread(target=_claim_until_empty) for _ in range(thread_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(claimed_ids) == item_count
    assert len(set(claimed_ids)) == item_count  # no duplicate claims


def test_more_workers_drain_the_queue_faster(pg_engine, storage):
    """The throughput half of the proof: `WorkItemExecutorLoop` with more worker threads
    genuinely finishes the same amount of work sooner, not just "should in theory" - this would
    fail to show any improvement if the old asyncio-task design (or an unsafe claim path
    serializing everything anyway) were still in place.
    """
    item_count = 10
    delay_seconds = 0.2

    def _drain(worker_count: int) -> float:
        _upload_documents(pg_engine, storage, item_count)
        loop = WorkItemExecutorLoop(
            lambda: build_sessionmaker(pg_engine)(),
            SlowTextGenerationProvider(delay_seconds),
            FakeEmbeddingProvider(),
            "test-embedding-model",
            storage,
            poll_interval=0.02,
            worker_count=worker_count,
        )
        start = time.monotonic()
        loop.start()
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                session = build_sessionmaker(pg_engine)()
                try:
                    remaining = (
                        session.query(WorkItemModel)
                        .filter(WorkItemModel.state.in_([WorkItemState.QUEUED, WorkItemState.RUNNING]))
                        .count()
                    )
                finally:
                    session.close()
                if remaining == 0:
                    break
                time.sleep(0.02)
            else:
                pytest.fail("queue never drained within the timeout")
        finally:
            import asyncio

            asyncio.run(loop.stop())
        return time.monotonic() - start

    one_worker_elapsed = _drain(worker_count=1)
    many_worker_elapsed = _drain(worker_count=5)

    # Generous slack (not asserting a precise Nx multiplier) - just proving a real, substantial
    # improvement exists, immune to machine-speed variance between CI/local runs.
    assert many_worker_elapsed < one_worker_elapsed * 0.6

    session = build_sessionmaker(pg_engine)()
    try:
        succeeded = session.query(WorkItemModel).filter(WorkItemModel.state == WorkItemState.SUCCEEDED).count()
        not_succeeded = session.query(WorkItemModel).filter(WorkItemModel.state != WorkItemState.SUCCEEDED).count()
    finally:
        session.close()
    assert succeeded == item_count * 2  # both _drain() calls' items, each processed exactly once
    assert not_succeeded == 0
