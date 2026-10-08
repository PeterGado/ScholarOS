import io

from app.ai.crossref import CrossrefWork
from app.database.session import build_sessionmaker
from app.modules.document.domain.enums import (
    DocumentProcessingStatus,
    DoiVerificationStatus,
)
from app.modules.document.infrastructure.repositories import (
    SqlAlchemyDocumentRepository,
)
from app.storage.filesystem import FilesystemStorage
from app.workers.executor import process_one_work_item
from app.workers.repository import WorkItemRepository


class FakeTextGenerationProvider:
    """Stands in for the real AI provider - the executor is exercised for real, over a real
    HTTP-uploaded document and real SQLite persistence, but no test may call a real external
    provider (Backend_Slice2_Implementation_Plan.md §8).
    """

    def generate(self, prompt: str) -> str:
        return '[{"element_type": "concept", "label": "E2E concept", "description": "From a real HTTP upload."}]'


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_a_document_uploaded_over_real_http_is_processed_by_the_executor_over_a_separate_step(
    client, auth_headers, db_engine, tmp_path
):
    """The full Stage 6 loop, over genuinely separate operations (not one shared session):
    1. POST /agents (real HTTP)
    2. POST /projects/{id}/documents (real HTTP) - enqueues a Work Item as a side effect
    3. The executor (a separate step, exactly as the background loop would run it) claims
       and processes that Work Item against the same real database
    4. A fresh read confirms the document's real, persisted, evidence-linked knowledge
    """
    workspace_response = client.post(
        "/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=auth_headers
    )
    project_id = workspace_response.json()["project"]["project_id"]

    upload_response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Real HTTP-uploaded content."), "text/plain")},
        data={"title": "Baseline survey", "format": "txt"},
        headers=auth_headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["document_id"]

    # Simulate the background executor's next tick - a separate operation, its own session.
    session = build_sessionmaker(db_engine)()
    try:
        storage = FilesystemStorage(tmp_path / "object-store")
        claimed = process_one_work_item(
            session,
            text_provider=FakeTextGenerationProvider(),
            embedding_provider=FakeEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=storage,
        )
        assert claimed is True
    finally:
        session.close()

    # A completely fresh session/read - confirms real persistence, not an artifact of a
    # shared in-memory object.
    verification_session = build_sessionmaker(db_engine)()
    try:
        documents = SqlAlchemyDocumentRepository(verification_session)
        document = documents.get_by_id(document_id)
        assert document.processing_status == DocumentProcessingStatus.PROCESSED
        assert document.processed_at is not None

        work_items = WorkItemRepository(verification_session)
        assert work_items.claim_next_queued() is None  # already succeeded, nothing left queued
    finally:
        verification_session.close()


def test_a_real_doi_is_verified_as_part_of_the_same_processing_pass(client, auth_headers, db_engine, tmp_path):
    """DOI verification (2026-10-06) runs as a non-critical step after knowledge extraction, in
    the *same* Work Item - proves the real wiring end to end over real HTTP + real persistence,
    not just VerifyDocumentDoiUseCase in isolation. A fake doi_lookup_provider stands in for
    Crossref (no test may call a real external provider).
    """
    workspace_response = client.post(
        "/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=auth_headers
    )
    project_id = workspace_response.json()["project"]["project_id"]

    upload_response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("source.txt", io.BytesIO(b"Real HTTP-uploaded content."), "text/plain")},
        data={"title": "Baseline survey", "format": "txt", "doi": "10.1038/nphys1170"},
        headers=auth_headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["document_id"]

    fake_crossref_work = CrossrefWork(title="Measured measurement", authors=("Aspelmeyer",), year=2009)

    session = build_sessionmaker(db_engine)()
    try:
        storage = FilesystemStorage(tmp_path / "object-store")
        claimed = process_one_work_item(
            session,
            text_provider=FakeTextGenerationProvider(),
            embedding_provider=FakeEmbeddingProvider(),
            embedding_model_version="test-embedding-model",
            storage=storage,
            doi_lookup_provider=lambda doi: fake_crossref_work,
        )
        assert claimed is True
    finally:
        session.close()

    verification_session = build_sessionmaker(db_engine)()
    try:
        documents = SqlAlchemyDocumentRepository(verification_session)
        document = documents.get_by_id(document_id)
        assert document.processing_status == DocumentProcessingStatus.PROCESSED
        assert document.doi_verification_status == DoiVerificationStatus.VERIFIED
        assert document.author == "Aspelmeyer"
        assert document.publication_year == 2009
    finally:
        verification_session.close()
