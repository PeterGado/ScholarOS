import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.ai.crossref import CrossrefWork, fetch_crossref_work
from app.ai.openalex import (
    OpenAlexWork,
    SourceSearchUnavailableError,
    get_openalex_work_by_id,
    search_openalex_works,
)
from app.ai.tavily import WebSearchResult, WebSearchUnavailableError, search_web
from app.ai.usage_guard import AiUsageGuard
from app.ai.web_fetch import WebSource, fetch_web_source
from app.auth.email_verification_guard import EmailVerificationGuard
from app.core.pagination import DEFAULT_LIST_LIMIT
from app.core.unit_of_work import UnitOfWork
from app.modules.agent.domain.repositories import AgentRepository
from app.modules.document.domain.entities import ResearchDocument
from app.modules.document.domain.enums import (
    DocumentProcessingStatus,
    DocumentPurpose,
    DoiVerificationStatus,
)
from app.modules.document.domain.exceptions import (
    DocumentCannotBeDeletedError,
    DocumentCannotBeRetriedError,
    EmptyDocumentContentError,
    ExternalSourceHasNoContentError,
    ExternalSourceNotFoundError,
    ResearchDocumentNotFoundError,
    SourceSearchFailedError,
    SourceSearchNotConfiguredError,
    TooManyResearchDocumentsError,
    WebPageFetchFailedError,
)
from app.modules.document.domain.ports import ContentStore
from app.modules.document.domain.repositories import DocumentRepository
from app.modules.project.domain.exceptions import ProjectNotFoundError
from app.modules.project.domain.repositories import ProjectRepository
from app.workers.enums import WorkItemKind
from app.workers.payloads import (
    build_process_document_idempotency_key,
    build_process_document_payload_reference,
)
from app.workers.ports import WorkItemEnqueuer, WorkItemOutcomeLookup

_DELETABLE_STATUSES = {DocumentProcessingStatus.PENDING, DocumentProcessingStatus.FAILED}
"""A document may only be deleted before it has contributed anything to the knowledge base:
`pending` (never attempted, or a Work Item never got created for it) and `failed` (permanently
failed extraction, e.g. an unsupported format). `processing` is excluded to avoid racing the
worker; `processed` is excluded by product decision (see DocumentCannotBeDeletedError)."""

MAX_RESEARCH_DOCUMENTS_PER_PROJECT = 20
"""A deliberate cap, not an incidental limitation - each document costs real AI provider calls
to process (classification + embedding), and an unbounded project could exhaust a free-tier
daily quota (or run up a paid one) on its own. See TooManyResearchDocumentsError."""


def _create_and_enqueue_document(
    *,
    documents: DocumentRepository,
    work_items: WorkItemEnqueuer,
    uow: UnitOfWork,
    project_id: int,
    title: str,
    format: str,
    content_reference: str,
    author: str | None,
    source: str | None,
    publication_year: int | None,
    doi: str | None,
    purpose: DocumentPurpose,
) -> ResearchDocument:
    """Shared tail of UploadResearchDocumentUseCase and ImportExternalSourceUseCase (2026-10-17)
    - both are on-ramps into the same Research Document pipeline, differing only in where
    `content_reference` came from (a client upload vs. a server-side OpenAlex fetch), so the
    actual creation, Work Item enqueue, and commit/rollback semantics live here once.
    """
    try:
        document = ResearchDocument.create(
            project_id=project_id,
            title=title,
            format=format,
            content_reference=content_reference,
            author=author,
            source=source,
            publication_year=publication_year,
            doi=doi,
            purpose=purpose,
        )
        document = documents.add(document)
        work_items.enqueue(
            kind=WorkItemKind.PIPELINE_STAGE,
            payload_reference=build_process_document_payload_reference(document.document_id),
            idempotency_key=build_process_document_idempotency_key(document.document_id),
        )
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    return document


class UploadResearchDocumentUseCase:
    """Realizes 05_Backend_Architecture.md §10.1: accept and register a Research Document
    within its owning Project (§10.2 - depends on the project service for project
    association). Content is written to the object store first, then the metadata row is
    persisted referencing it - an orphaned file from a failed commit is harmless
    (content-addressed, ADR-004 §5), but a DB row pointing at a missing file is not.

    Enforces ownership (§15.1 API-036/API-037; Constraints invariant 15) transitively:
    Project has no user_id of its own, so ownership is proven via the Project's owning Agent.
    A mismatch is reported as the same ProjectNotFoundError as a genuinely missing project -
    deliberately indistinguishable, the same principle Stage 5's login already applies to
    unknown-username vs wrong-password, so a caller cannot use this endpoint to probe which
    project IDs exist.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
        work_item_enqueuer: WorkItemEnqueuer,
        ai_usage_guard: AiUsageGuard,
        email_verification_guard: EmailVerificationGuard,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._content_store = content_store
        self._uow = unit_of_work
        self._work_items = work_item_enqueuer
        self._ai_usage_guard = ai_usage_guard
        self._email_verification_guard = email_verification_guard

    def execute(
        self,
        *,
        project_id: int,
        user_id: int,
        title: str,
        format: str,
        content: bytes,
        author: str | None = None,
        source: str | None = None,
        publication_year: int | None = None,
        doi: str | None = None,
        extension: str = "",
    ) -> ResearchDocument:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        # Email verification gate (2026-10-06, external security review) - right after
        # ownership is confirmed, before any content-store write or AI usage is recorded.
        self._email_verification_guard.require_verified(user_id)

        existing_count = len(self._documents.list_by_project_id(project_id, purpose=DocumentPurpose.RESEARCH))
        if existing_count >= MAX_RESEARCH_DOCUMENTS_PER_PROJECT:
            raise TooManyResearchDocumentsError(project_id=project_id, limit=MAX_RESEARCH_DOCUMENTS_PER_PROJECT)

        if not content:
            raise EmptyDocumentContentError()

        # AI usage cap (2026-09-21 security pass): estimated directly from the raw uploaded
        # bytes (classification + embedding cost, later, in the Work Item executor, scales with
        # document size) - a byte-length calc, not app.ai.token_estimate.estimate_tokens(str),
        # since content is bytes, not decoded text (and decoding untrusted upload bytes just to
        # estimate a count isn't worth the cost/risk).
        self._ai_usage_guard.check_and_record(user_id=user_id, estimated_tokens=max(1, len(content) // 4))

        content_reference = self._content_store.save(content, extension=extension)

        return _create_and_enqueue_document(
            documents=self._documents,
            work_items=self._work_items,
            uow=self._uow,
            project_id=project_id,
            title=title,
            format=format,
            content_reference=content_reference,
            author=author,
            source=source,
            publication_year=publication_year,
            doi=doi,
            purpose=DocumentPurpose.RESEARCH,
        )


@dataclass(frozen=True)
class ResearchDocumentWithError:
    """A Research Document bundled with the reason its processing failed, if any - so the
    interface layer never has to make a second per-document Work Item lookup itself (mirrors
    `MemoryRecordWithProvenance`'s own shape). `error_message` is always None for a document
    that isn't currently `failed`.
    """

    document: ResearchDocument
    error_message: str | None


class ListProjectDocumentsUseCase:
    """Lists a Project's Research Documents, most recently used to observe `processing_status`
    transitioning from `pending` -> `processing` -> `processed`/`failed`. Added resolving a
    Frontend milestone Stage 1 finding: `POST /projects/{id}/documents` never had a matching
    read endpoint, even though `DocumentRepository.list_by_project_id` already existed -
    exposing it required no new persistence, only the same ownership-checked read pattern
    `UploadResearchDocumentUseCase` already applies.

    Also surfaces *why* a `failed` document failed (the underlying Work Item's `last_error`) -
    a real gap found via manual use: a document could sit there marked "failed" with the user
    given no way to tell an unsupported-format problem from a transient AI-provider outage.

    Scoped to `DocumentPurpose.RESEARCH` only - a writing-style sample is never submitted to
    the knowledge pipeline (see `UploadWritingStyleDocumentUseCase`), so it would otherwise sit
    here forever at `pending` with no explanation, a real bug found via manual use once
    `DocumentPurpose` existed to actually name the distinction.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        work_items: WorkItemOutcomeLookup,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._work_items = work_items

    def execute(
        self, *, project_id: int, user_id: int, limit: int = DEFAULT_LIST_LIMIT, offset: int = 0
    ) -> tuple[list[ResearchDocumentWithError], bool]:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        documents = self._documents.list_by_project_id(
            project_id, purpose=DocumentPurpose.RESEARCH, limit=limit, offset=offset
        )
        # The repository returns up to limit + 1 rows (2026-09-23, pagination) - the extra row,
        # if present, means more exist beyond this page; trimmed before building the response.
        # (In practice MAX_RESEARCH_DOCUMENTS_PER_PROJECT already caps this well under any
        # reasonable limit - added for API consistency with the other 4 paginated endpoints and
        # as a defensive bound if that cap ever changes.)
        has_more = len(documents) > limit
        documents = documents[:limit]
        return [
            ResearchDocumentWithError(document=document, error_message=self._error_message_for(document))
            for document in documents
        ], has_more

    def _error_message_for(self, document: ResearchDocument) -> str | None:
        if document.processing_status != DocumentProcessingStatus.FAILED:
            return None
        work_item = self._work_items.get_by_payload_reference(
            build_process_document_payload_reference(document.document_id)
        )
        return work_item.last_error if work_item is not None else None


class DeleteResearchDocumentUseCase:
    """Deletes a Research Document that was never successfully processed - found necessary
    once real uploads (real .docx files, before .docx extraction was supported) got
    permanently stuck with no way to clear them. Restricted to `pending`/`failed` documents
    only (see `_DELETABLE_STATUSES`): a `processed` document has already contributed real
    Knowledge Elements/Chunks/Embeddings to the Agent's knowledge base, and by product decision
    is no longer shown or manageable through this interface at all - refused here too, not
    only hidden in the UI, so the rule holds even against a direct API call.

    Soft-deletes only (`ResearchDocument.deleted_at`) - the underlying stored content is left
    in place. Deleting it would risk breaking a *different* document that happens to share the
    same content-addressed reference (ADR-004 §5: identical content is stored once); an
    unreferenced file left behind is the same harmless-orphan case this codebase already
    accepts for a failed upload commit.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        work_items: WorkItemOutcomeLookup,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._work_items = work_items
        self._uow = unit_of_work

    def execute(self, *, project_id: int, user_id: int, document_id: int) -> None:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        document = self._documents.get_by_id(document_id)
        if document is None or document.project_id != project_id or document.deleted_at is not None:
            raise ResearchDocumentNotFoundError(document_id=document_id)

        if document.processing_status not in _DELETABLE_STATUSES:
            raise DocumentCannotBeDeletedError(
                document_id=document_id, processing_status=document.processing_status.value
            )

        try:
            # A `pending` document can still have a queued (not yet claimed) processing Work
            # Item - cancel it first so the executor never claims one whose document has been
            # deleted out from under it (see `cancel_queued_by_payload_reference`'s docstring
            # for the outage this caused before this call existed).
            self._work_items.cancel_queued_by_payload_reference(
                build_process_document_payload_reference(document_id)
            )
            self._documents.mark_deleted(document_id, deleted_at=datetime.now(UTC))
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise


class RetryDocumentProcessingUseCase:
    """Re-enqueues processing for a document whose previous attempt terminally `failed` -
    found necessary the same way `DeleteResearchDocumentUseCase` was: without it, a document
    that failed for a transient reason (e.g. the AI provider's quota was briefly exhausted) had
    no path back to `processed` except deleting it and uploading the exact same file again.

    Resets the existing Work Item back to `queued` (`WorkItemOutcomeLookup.
    requeue_failed_by_payload_reference`) rather than enqueuing a new one - the same
    idempotency_key is already taken by the original attempt. Only `failed` documents are
    retriable; `pending`/`processing` already have a live attempt in flight, and `processed`
    has already contributed real knowledge (mirrors `DeleteResearchDocumentUseCase`'s own
    status-gating).
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        work_items: WorkItemOutcomeLookup,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._work_items = work_items
        self._uow = unit_of_work

    def execute(self, *, project_id: int, user_id: int, document_id: int) -> ResearchDocument:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        document = self._documents.get_by_id(document_id)
        if document is None or document.project_id != project_id or document.deleted_at is not None:
            raise ResearchDocumentNotFoundError(document_id=document_id)

        if document.processing_status != DocumentProcessingStatus.FAILED:
            raise DocumentCannotBeRetriedError(
                document_id=document_id, processing_status=document.processing_status.value
            )

        try:
            self._work_items.requeue_failed_by_payload_reference(
                build_process_document_payload_reference(document_id)
            )
            self._documents.update_processing_status(document_id, DocumentProcessingStatus.PENDING)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        document.processing_status = DocumentProcessingStatus.PENDING
        return document


_DOI_NAME_TOKEN = re.compile(r"[A-Za-z]+")


class VerifyDocumentDoiUseCase:
    """Checks a user-supplied DOI against Crossref (2026-10-06, citation grounding) - run as a
    non-critical enrichment step after knowledge extraction succeeds (see
    `process_one_work_item`'s document branch), never blocking document processing itself: a
    Crossref outage must not turn a successfully-processed document into a failed one.

    A no-op when the document has no `doi` set - every caller can call this unconditionally
    rather than pre-checking, the same pattern `fetch_wikipedia_background` uses for an empty
    topic.

    When the DOI resolves and the user left `author`/`publication_year` blank, both are filled
    from the verified Crossref record - the most accurate metadata available, for the least
    user effort. When the user *did* supply them, they are compared (loosely - whole-word
    token overlap on the author, exact match on the year) against the real record rather than
    overwritten; a mismatch is surfaced via `DoiVerificationStatus.MISMATCH`, not silently
    corrected, since the user's own text might be right and Crossref's record wrong.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        unit_of_work: UnitOfWork,
        *,
        doi_lookup_provider: Callable[[str], CrossrefWork | None] = fetch_crossref_work,
    ) -> None:
        self._documents = document_repository
        self._uow = unit_of_work
        self._lookup = doi_lookup_provider

    def execute(self, *, document_id: int) -> None:
        document = self._documents.get_by_id(document_id)
        if document is None or not document.doi:
            return

        work = self._lookup(document.doi)
        if work is None:
            status = DoiVerificationStatus.NOT_FOUND
            author, publication_year = document.author, document.publication_year
        elif self._matches(document, work):
            status = DoiVerificationStatus.VERIFIED
            author = document.author or (", ".join(work.authors) if work.authors else document.author)
            publication_year = document.publication_year or work.year
        else:
            status = DoiVerificationStatus.MISMATCH
            author, publication_year = document.author, document.publication_year

        try:
            self._documents.update_doi_verification(
                document_id, status=status, author=author, publication_year=publication_year
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

    @staticmethod
    def _matches(document: ResearchDocument, work: CrossrefWork) -> bool:
        year_ok = document.publication_year is None or document.publication_year == work.year
        if not document.author:
            author_ok = True
        else:
            entered_tokens = {token.lower() for token in _DOI_NAME_TOKEN.findall(document.author)}
            real_tokens = {
                token.lower() for name in work.authors for token in _DOI_NAME_TOKEN.findall(name)
            }
            author_ok = bool(entered_tokens & real_tokens)
        return year_ok and author_ok


class SearchExternalSourcesUseCase:
    """Search-and-import source discovery (2026-10-17) - the search half. NotebookLM-style: the
    system finds and presents specific, named candidate sources for the user to explicitly
    choose from, never an unrestricted crawl of the open web. Searches OpenAlex's scholarly
    index; the user picks which result(s), if any, to actually bring into their project via
    ImportExternalSourceUseCase.

    No ownership check here, unlike every other use case in this module - this searches a
    public, external index, not anything project- or user-scoped. project_id only becomes
    relevant at import time, when a real ResearchDocument gets created.
    """

    def __init__(
        self,
        *,
        openalex_api_key: str | None,
        search_provider: Callable[..., list[OpenAlexWork]] = search_openalex_works,
    ) -> None:
        self._api_key = openalex_api_key
        self._search = search_provider

    def execute(self, *, query: str, limit: int = 10) -> list[OpenAlexWork]:
        if not self._api_key:
            raise SourceSearchNotConfiguredError()
        try:
            return self._search(query, api_key=self._api_key, limit=limit)
        except SourceSearchUnavailableError as exc:
            raise SourceSearchFailedError() from exc


class ImportExternalSourceUseCase:
    """Search-and-import source discovery (2026-10-17) - the import half. Re-resolves the work
    server-side by ID (never trusts client-supplied title/author/year/DOI for document creation
    - see app.ai.openalex.get_openalex_work_by_id's own docstring), then tries, in order: the
    work's fetchable_url (a real open-access full text) via app.ai.web_fetch.fetch_web_source
    with a far larger content cap than chat grounding needs; falling back to the reconstructed
    abstract alone when no fetchable URL exists or the fetch fails; raising
    ExternalSourceHasNoContentError only when neither is available - a metadata-only stub with
    no abstract and no full text would leave nothing for the knowledge pipeline to work with.

    Shares UploadResearchDocumentUseCase's ownership/cap/email-verification checks exactly -
    this is a second on-ramp into the same Research Document pipeline (_create_and_enqueue_
    document), not a separate one.
    """

    _IMPORT_CONTENT_LENGTH = 50_000
    """Far larger than web-source chat grounding's 3,000-char cap (app.ai.web_fetch) - an
    imported document goes through the same chunking/embedding pipeline any uploaded document
    does, not stuffed whole into one prompt, so it can comfortably hold most full papers."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
        work_item_enqueuer: WorkItemEnqueuer,
        ai_usage_guard: AiUsageGuard,
        email_verification_guard: EmailVerificationGuard,
        *,
        openalex_api_key: str | None,
        work_lookup_provider: Callable[..., OpenAlexWork | None] = get_openalex_work_by_id,
        content_fetch_provider: Callable[..., WebSource | None] = fetch_web_source,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._content_store = content_store
        self._uow = unit_of_work
        self._work_items = work_item_enqueuer
        self._ai_usage_guard = ai_usage_guard
        self._email_verification_guard = email_verification_guard
        self._api_key = openalex_api_key
        self._lookup_work = work_lookup_provider
        self._fetch_content = content_fetch_provider

    def execute(self, *, project_id: int, user_id: int, openalex_id: str) -> ResearchDocument:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        # Email verification gate (2026-10-06 precedent) - right after ownership is confirmed,
        # before any external fetch, content-store write, or AI usage is recorded.
        self._email_verification_guard.require_verified(user_id)

        existing_count = len(self._documents.list_by_project_id(project_id, purpose=DocumentPurpose.RESEARCH))
        if existing_count >= MAX_RESEARCH_DOCUMENTS_PER_PROJECT:
            raise TooManyResearchDocumentsError(project_id=project_id, limit=MAX_RESEARCH_DOCUMENTS_PER_PROJECT)

        if not self._api_key:
            raise SourceSearchNotConfiguredError()

        try:
            work = self._lookup_work(openalex_id, api_key=self._api_key)
        except SourceSearchUnavailableError as exc:
            raise SourceSearchFailedError() from exc
        if work is None:
            raise ExternalSourceNotFoundError(openalex_id=openalex_id)

        content_text: str | None = None
        if work.fetchable_url:
            fetched = self._fetch_content(work.fetchable_url, max_content_length=self._IMPORT_CONTENT_LENGTH)
            if fetched is not None:
                content_text = fetched.content
        if not content_text:
            content_text = work.abstract
        if not content_text:
            raise ExternalSourceHasNoContentError()

        content_bytes = content_text.encode("utf-8")

        # Same AI usage cap reasoning as UploadResearchDocumentUseCase - a byte-length estimate,
        # charged against the user importing the source.
        self._ai_usage_guard.check_and_record(user_id=user_id, estimated_tokens=max(1, len(content_bytes) // 4))

        content_reference = self._content_store.save(content_bytes, extension="txt")

        return _create_and_enqueue_document(
            documents=self._documents,
            work_items=self._work_items,
            uow=self._uow,
            project_id=project_id,
            title=work.title,
            format="txt",
            content_reference=content_reference,
            author=", ".join(work.authors) if work.authors else None,
            source=work.source_name,
            publication_year=work.publication_year,
            doi=work.doi,
            purpose=DocumentPurpose.RESEARCH,
        )


class SearchWebUseCase:
    """General web search discovery (2026-10-17) - the same NotebookLM-style "Discover sources"
    pattern as SearchExternalSourcesUseCase, applied to the open web via Tavily instead of
    OpenAlex's curated scholarly index. Still never project-scoped: this searches a public
    external index, not anything project- or user-scoped.
    """

    def __init__(
        self,
        *,
        tavily_api_key: str | None,
        search_provider: Callable[..., list[WebSearchResult]] = search_web,
    ) -> None:
        self._api_key = tavily_api_key
        self._search = search_provider

    def execute(self, *, query: str, limit: int = 10) -> list[WebSearchResult]:
        if not self._api_key:
            raise SourceSearchNotConfiguredError()
        try:
            return self._search(query, api_key=self._api_key, limit=limit)
        except WebSearchUnavailableError as exc:
            raise SourceSearchFailedError() from exc


class ImportWebSearchResultUseCase:
    """General web search discovery (2026-10-17) - the import half. Unlike
    ImportExternalSourceUseCase, there is no authoritative registry to re-resolve a work by ID:
    a random web page has no such identity. `url` and `title` travel back from the search result
    the client saw exactly as shown - the same trust boundary the existing chat-paste-URL feature
    already accepts for any URL a user provides (see app.ai.tavily.WebSearchResult's own
    docstring). The real security boundary is fetch-time SSRF checking
    (app.ai.web_fetch.fetch_web_source), which runs on this url exactly like it does on every
    other url this app fetches - not a server-side re-lookup.

    Shares UploadResearchDocumentUseCase's ownership/cap/email-verification checks exactly -
    this is a third on-ramp into the same Research Document pipeline
    (_create_and_enqueue_document).
    """

    _IMPORT_CONTENT_LENGTH = 50_000
    """Same cap as ImportExternalSourceUseCase - an imported document goes through the same
    chunking/embedding pipeline any uploaded document does, not stuffed whole into one prompt."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        project_repository: ProjectRepository,
        agent_repository: AgentRepository,
        content_store: ContentStore,
        unit_of_work: UnitOfWork,
        work_item_enqueuer: WorkItemEnqueuer,
        ai_usage_guard: AiUsageGuard,
        email_verification_guard: EmailVerificationGuard,
        *,
        content_fetch_provider: Callable[..., WebSource | None] = fetch_web_source,
    ) -> None:
        self._documents = document_repository
        self._projects = project_repository
        self._agents = agent_repository
        self._content_store = content_store
        self._uow = unit_of_work
        self._work_items = work_item_enqueuer
        self._ai_usage_guard = ai_usage_guard
        self._email_verification_guard = email_verification_guard
        self._fetch_content = content_fetch_provider

    def execute(self, *, project_id: int, user_id: int, url: str, title: str) -> ResearchDocument:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id=project_id)

        owning_agent = self._agents.get_by_id(project.agent_id)
        if owning_agent is None or owning_agent.user_id != user_id:
            raise ProjectNotFoundError(project_id=project_id)

        # Email verification gate (2026-10-06 precedent) - right after ownership is confirmed,
        # before any external fetch, content-store write, or AI usage is recorded.
        self._email_verification_guard.require_verified(user_id)

        existing_count = len(self._documents.list_by_project_id(project_id, purpose=DocumentPurpose.RESEARCH))
        if existing_count >= MAX_RESEARCH_DOCUMENTS_PER_PROJECT:
            raise TooManyResearchDocumentsError(project_id=project_id, limit=MAX_RESEARCH_DOCUMENTS_PER_PROJECT)

        fetched = self._fetch_content(url, max_content_length=self._IMPORT_CONTENT_LENGTH)
        if fetched is None or not fetched.content:
            raise WebPageFetchFailedError()

        content_bytes = fetched.content.encode("utf-8")

        # Same AI usage cap reasoning as UploadResearchDocumentUseCase - a byte-length estimate,
        # charged against the user importing the source.
        self._ai_usage_guard.check_and_record(user_id=user_id, estimated_tokens=max(1, len(content_bytes) // 4))

        content_reference = self._content_store.save(content_bytes, extension="txt")

        return _create_and_enqueue_document(
            documents=self._documents,
            work_items=self._work_items,
            uow=self._uow,
            project_id=project_id,
            title=title,
            format="txt",
            content_reference=content_reference,
            author=None,
            source=url,
            publication_year=None,
            doi=None,
            purpose=DocumentPurpose.RESEARCH,
        )
