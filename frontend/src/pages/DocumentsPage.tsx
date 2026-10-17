import { useEffect, useRef, useState, type FormEvent } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MagnifyingGlassIcon, TrayIcon } from "@phosphor-icons/react";
import {
  deleteResearchDocument,
  importExternalSource,
  listProjectDocuments,
  retryResearchDocument,
  searchExternalSources,
  uploadResearchDocument,
  uploadResearchDocuments,
} from "@/api/documents";
import { searchKnowledge } from "@/api/knowledge";
import { ApiError } from "@/lib/apiClient";
import { useToast } from "@/lib/ToastContext";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { EmailVerificationNotice } from "@/components/EmailVerificationNotice";
import { useWorkspaceContext } from "@/components/WorkspaceGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

const DELETABLE_STATUSES = new Set(["pending", "failed"]);
// Mirrors the backend's own MAX_RESEARCH_DOCUMENTS_PER_PROJECT (app/modules/document/
// application/use_cases.py) - the backend is the real enforcement point, this is only so the
// UI can proactively disable uploads instead of waiting for a failed round trip.
const RESEARCH_DOCUMENT_LIMIT = 20;

export function DocumentsPage() {
  useDocumentTitle("Research Documents");
  const workspace = useWorkspaceContext();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [year, setYear] = useState("");
  const [doi, setDoi] = useState("");
  const [selectedFileCount, setSelectedFileCount] = useState(0);
  const [query, setQuery] = useState("");
  const [searchSubmitted, setSearchSubmitted] = useState("");
  const [acquisitionTab, setAcquisitionTab] = useState<"upload" | "search-sources">("upload");
  const [sourceQuery, setSourceQuery] = useState("");
  const [sourceQuerySubmitted, setSourceQuerySubmitted] = useState("");
  const [importingId, setImportingId] = useState<string | null>(null);
  const previousStatusesRef = useRef<Record<number, string>>({});

  const documentsQuery = useInfiniteQuery({
    queryKey: ["documents", workspace.project.project_id],
    queryFn: ({ pageParam }) => listProjectDocuments(workspace.project.project_id, { offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.hasMore ? allPages.reduce((total, page) => total + page.items.length, 0) : undefined,
    // Documents transition pending -> processing -> processed/failed in the background
    // (the app's own Work Item executor) - poll while any document hasn't reached a terminal
    // state yet, since there is no push channel or dedicated status endpoint.
    refetchInterval: (query) => {
      const documents = query.state.data?.pages.flatMap((page) => page.items) ?? [];
      const stillProcessing = documents.some(
        (doc) => doc.processing_status === "pending" || doc.processing_status === "processing",
      );
      return stillProcessing ? 2000 : false;
    },
  });

  const allDocuments = documentsQuery.data?.pages.flatMap((page) => page.items) ?? [];

  // A processed document intentionally disappears from the list below (see the comment on
  // inProgressDocuments) with nothing else marking success - confusing enough that a user
  // reported it as "vanished, did it work?". Fires a toast on the actual pending/processing ->
  // processed transition observed during this page visit, never on first load (a document
  // already processed before the user opened the page isn't a new event worth announcing).
  useEffect(() => {
    if (!documentsQuery.data) return;
    for (const doc of allDocuments) {
      const previousStatus = previousStatusesRef.current[doc.document_id];
      if (previousStatus && previousStatus !== "processed" && doc.processing_status === "processed") {
        showToast(`"${doc.title}" finished processing.`);
      }
      previousStatusesRef.current[doc.document_id] = doc.processing_status;
    }
  }, [documentsQuery.data, showToast]);

  // Once a document is fully processed, its knowledge has already been absorbed into the
  // Agent's knowledge base - it's no longer a "file" to manage here, only searchable below.
  // This list is an upload/status queue, not a permanent archive.
  const inProgressDocuments = allDocuments.filter((doc) => doc.processing_status !== "processed");
  // Shown separately below (read-only - already part of the knowledge base, can't be deleted
  // from here) so finishing processing doesn't make the page look empty with no confirmation
  // anything ever succeeded - a real point of confusion reported by a user.
  const processedDocuments = allDocuments.filter((doc) => doc.processing_status === "processed");

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const files = Array.from(fileInputRef.current?.files ?? []);
      if (files.length === 0) throw new Error("Choose at least one file first.");
      if (files.length > RESEARCH_DOCUMENT_LIMIT - documentCount) {
        throw new Error(`You can upload ${RESEARCH_DOCUMENT_LIMIT - documentCount} more document(s) in this project.`);
      }
      // A custom title (and author/year/DOI) only makes sense for a single file. Multi-file
      // uploads preserve each filename so their source remains identifiable in the knowledge
      // base, with no per-file metadata UI.
      if (files.length === 1 && (title.trim() || author.trim() || year.trim() || doi.trim())) {
        const file = files[0];
        const extension = file.name.split(".").pop() ?? "txt";
        const parsedYear = year.trim() ? Number(year.trim()) : undefined;
        return [await uploadResearchDocument({
          projectId: workspace.project.project_id,
          file,
          title: title.trim() || file.name,
          format: extension,
          author: author.trim() || undefined,
          publicationYear: parsedYear,
          doi: doi.trim() || undefined,
        })];
      }
      return uploadResearchDocuments(workspace.project.project_id, files);
    },
    onSuccess: (documents) => {
      setTitle("");
      setAuthor("");
      setYear("");
      setDoi("");
      setSelectedFileCount(0);
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["documents", workspace.project.project_id] });
      showToast(`${documents.length} document${documents.length === 1 ? "" : "s"} uploaded. Processing is queued.`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (documentId: number) => deleteResearchDocument(workspace.project.project_id, documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", workspace.project.project_id] }),
  });

  const retryMutation = useMutation({
    mutationFn: (documentId: number) => retryResearchDocument(workspace.project.project_id, documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", workspace.project.project_id] }),
  });

  const searchQuery = useQuery({
    queryKey: ["knowledge-search", searchSubmitted],
    queryFn: () => searchKnowledge(searchSubmitted),
    enabled: searchSubmitted.length > 0,
  });

  // Search-and-import source discovery (2026-10-17): searches OpenAlex's scholarly index for
  // specific, named candidate sources - NotebookLM-style, the user explicitly picks which one(s)
  // to import, never an unrestricted crawl of the open web.
  const sourceSearchQuery = useQuery({
    queryKey: ["external-source-search", sourceQuerySubmitted],
    queryFn: () => searchExternalSources(sourceQuerySubmitted),
    enabled: sourceQuerySubmitted.length > 0,
  });

  const importMutation = useMutation({
    mutationFn: (openalexId: string) => importExternalSource(workspace.project.project_id, openalexId),
    onMutate: (openalexId: string) => setImportingId(openalexId),
    onSuccess: (document) => {
      queryClient.invalidateQueries({ queryKey: ["documents", workspace.project.project_id] });
      showToast(`"${document.title}" imported. Processing is queued.`);
    },
    onSettled: () => setImportingId(null),
  });

  function handleUpload(event: FormEvent) {
    event.preventDefault();
    uploadMutation.mutate();
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    setSearchSubmitted(query);
  }

  function handleSourceSearch(event: FormEvent) {
    event.preventDefault();
    setSourceQuerySubmitted(sourceQuery);
  }

  const documentCount = allDocuments.length;
  const atLimit = documentCount >= RESEARCH_DOCUMENT_LIMIT;

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight leading-snug">Research Documents</h1>
          <p className="text-sm text-muted-foreground">
            Upload source material for your AI to draw on. Supports plain text, Word (.docx), and
            PDF files. Once a document finishes processing, it moves out of the pending list
            below into "Processed documents" and your searchable knowledge base. Up to
            {" "}{RESEARCH_DOCUMENT_LIMIT} documents per project (
            <span className="tabular-nums">
              {documentCount}/{RESEARCH_DOCUMENT_LIMIT}
            </span>{" "}
            used).
          </p>
        </div>

        {/* Acquisition tabs (2026-10-17, search-and-import source discovery): "Upload" (a
            client file) and "Search sources" (an OpenAlex result the server fetches) are both
            ways to bring a Research Document into this project - kept on one page since that's
            where a user already looks for either. */}
        <div role="tablist" aria-label="Add a research document" className="flex gap-1 border-b border-border">
          <button
            type="button"
            role="tab"
            id="acquisition-tab-upload"
            aria-selected={acquisitionTab === "upload"}
            aria-controls="acquisition-panel-upload"
            onClick={() => setAcquisitionTab("upload")}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              acquisitionTab === "upload"
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Upload
          </button>
          <button
            type="button"
            role="tab"
            id="acquisition-tab-search-sources"
            aria-selected={acquisitionTab === "search-sources"}
            aria-controls="acquisition-panel-search-sources"
            onClick={() => setAcquisitionTab("search-sources")}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              acquisitionTab === "search-sources"
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Search sources
          </button>
        </div>

        {acquisitionTab === "upload" && (
        <div role="tabpanel" id="acquisition-panel-upload" aria-labelledby="acquisition-tab-upload" className="space-y-4">
        <form onSubmit={handleUpload} className="flex flex-wrap items-end gap-3">
          {/* Accessibility (found during an audit, 2026-10-09): these labels had no htmlFor/id
              pairing to their inputs, so a screen reader wouldn't announce the field name. */}
          <div className="space-y-1">
            <label htmlFor="document-title" className="text-sm font-medium">
              Title (optional)
            </label>
            <Input
              id="document-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={selectedFileCount > 1 ? "Each file keeps its filename" : "Document title"}
              disabled={atLimit || selectedFileCount > 1}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="document-author" className="text-sm font-medium">
              Author (optional)
            </label>
            <Input
              id="document-author"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="e.g. Uadiale, O."
              className="max-w-40"
              disabled={atLimit || selectedFileCount > 1}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="document-year" className="text-sm font-medium">
              Year (optional)
            </label>
            <Input
              id="document-year"
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              placeholder="e.g. 2012"
              className="max-w-24"
              disabled={atLimit || selectedFileCount > 1}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="document-doi" className="text-sm font-medium">
              DOI (optional)
            </label>
            <Input
              id="document-doi"
              value={doi}
              onChange={(e) => setDoi(e.target.value)}
              placeholder="e.g. 10.1038/nphys1170"
              className="max-w-48"
              disabled={atLimit || selectedFileCount > 1}
            />
          </div>
          <Input
            ref={fileInputRef}
            type="file"
            multiple
            className="max-w-xs"
            required
            disabled={atLimit}
            onChange={(event) => setSelectedFileCount(event.target.files?.length ?? 0)}
          />
          <Button type="submit" disabled={uploadMutation.isPending || atLimit}>
            {uploadMutation.isPending ? "Uploading..." : selectedFileCount > 1 ? `Upload ${selectedFileCount} documents` : "Upload"}
          </Button>
        </form>
        {selectedFileCount > 1 && (
          <p className="text-sm text-muted-foreground">
            The files will upload one at a time from this single action. Each file keeps its own name in your knowledge base.
          </p>
        )}
        {selectedFileCount <= 1 && (
          <p className="text-sm text-muted-foreground">
            Add an author and year so your AI can cite this source accurately - without them, it
            can only refer to this document by title. Adding a DOI checks the author/year against
            the real published record and fills them in automatically if left blank.
          </p>
        )}
        {atLimit && (
          <p className="text-sm text-muted-foreground">
            You've reached the {RESEARCH_DOCUMENT_LIMIT}-document limit for this project. A pending
            or failed document below can be deleted to make room - an already-processed one can't be
            removed, since its knowledge is already part of your Agent's knowledge base.
          </p>
        )}
        {uploadMutation.isError &&
          (uploadMutation.error instanceof ApiError && uploadMutation.error.errorType === "EmailNotVerifiedError" ? (
            <EmailVerificationNotice />
          ) : (
            <p role="alert" className="text-sm text-destructive">
              {uploadMutation.error instanceof ApiError ? uploadMutation.error.message : "Upload failed."}
            </p>
          ))}

        {documentsQuery.isLoading && (
          <div className="space-y-2" aria-label="Loading documents">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        )}
        {documentsQuery.data && allDocuments.length === 0 && (
          <EmptyState
            icon={TrayIcon}
            title="No documents yet"
            description="Upload source material above so your AI can draw on it when writing for you."
          />
        )}
        {documentsQuery.data && allDocuments.length > 0 && inProgressDocuments.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nothing pending - uploaded documents will appear here while processing.
          </p>
        )}
        <ul className="divide-y divide-border">
          {inProgressDocuments.map((doc) => (
            <li key={doc.document_id} className="space-y-2 py-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{doc.title}</span>
                <div className="flex items-center gap-2">
                  <Badge variant={doc.processing_status === "failed" ? "destructive" : "secondary"}>
                    {doc.processing_status}
                  </Badge>
                  {doc.processing_status === "failed" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={retryMutation.isPending}
                      onClick={() => retryMutation.mutate(doc.document_id)}
                    >
                      Retry
                    </Button>
                  )}
                  {DELETABLE_STATUSES.has(doc.processing_status) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(doc.document_id)}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </div>
              {doc.error_message && <p role="alert" className="text-sm text-destructive">{doc.error_message}</p>}
            </li>
          ))}
        </ul>
        {documentsQuery.hasNextPage && (
          <Button
            variant="outline"
            size="sm"
            disabled={documentsQuery.isFetchingNextPage}
            onClick={() => documentsQuery.fetchNextPage()}
          >
            {documentsQuery.isFetchingNextPage ? "Loading..." : "Load more"}
          </Button>
        )}
        {retryMutation.isError && (
          <p role="alert" className="text-sm text-destructive">
            {retryMutation.error instanceof ApiError ? retryMutation.error.message : "Could not retry document."}
          </p>
        )}
        {deleteMutation.isError && (
          <p role="alert" className="text-sm text-destructive">
            {deleteMutation.error instanceof ApiError ? deleteMutation.error.message : "Could not delete document."}
          </p>
        )}
        </div>
        )}

        {acquisitionTab === "search-sources" && (
        <div
          role="tabpanel"
          id="acquisition-panel-search-sources"
          aria-labelledby="acquisition-tab-search-sources"
          className="space-y-4"
        >
          <p className="text-sm text-muted-foreground">
            Search OpenAlex's open scholarly index and import a specific result into this project.
            Only sources you explicitly choose are ever added - nothing is fetched automatically.
          </p>
          <form onSubmit={handleSourceSearch} className="flex gap-3">
            <Input
              value={sourceQuery}
              onChange={(e) => setSourceQuery(e.target.value)}
              placeholder="Search by topic, title, or author..."
              aria-label="Search external sources"
            />
            <Button type="submit" disabled={atLimit}>Search</Button>
          </form>
          {atLimit && (
            <p className="text-sm text-muted-foreground">
              You've reached the {RESEARCH_DOCUMENT_LIMIT}-document limit for this project - delete
              a pending or failed document above to make room before importing another.
            </p>
          )}
          {sourceSearchQuery.isFetching && (
            <div className="space-y-2" aria-label="Searching external sources">
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          )}
          {sourceSearchQuery.isError && (
            <p role="alert" className="text-sm text-destructive">
              {sourceSearchQuery.error instanceof ApiError
                ? sourceSearchQuery.error.errorType === "SourceSearchNotConfiguredError"
                  ? "Source search isn't set up yet."
                  : sourceSearchQuery.error.message
                : "Search failed. Try again."}
            </p>
          )}
          {sourceSearchQuery.data && sourceSearchQuery.data.length === 0 && (
            <EmptyState
              icon={MagnifyingGlassIcon}
              title="No results"
              description="Try a different search term."
            />
          )}
          {importMutation.isError && (
            <p role="alert" className="text-sm text-destructive">
              {importMutation.error instanceof ApiError
                ? importMutation.error.errorType === "ExternalSourceHasNoContentError"
                  ? "This source has no open-access full text or abstract available to import."
                  : importMutation.error.message
                : "Import failed. Try again."}
            </p>
          )}
          <ul className="divide-y divide-border">
            {sourceSearchQuery.data?.map((result) => (
              <li key={result.openalex_id} className="space-y-2 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{result.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {result.authors.length > 0 ? result.authors.join(", ") : "Author not listed"}
                      {result.publication_year ? ` (${result.publication_year})` : ""}
                      {result.source_name ? ` - ${result.source_name}` : ""}
                    </p>
                    {result.abstract && (
                      <p className="text-xs text-muted-foreground line-clamp-2">{result.abstract}</p>
                    )}
                    <div className="flex items-center gap-2">
                      {result.has_fetchable_full_text ? (
                        <Badge variant="success">Full text available</Badge>
                      ) : result.abstract ? (
                        <Badge variant="secondary">Abstract only</Badge>
                      ) : (
                        <Badge variant="destructive">Nothing to import</Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    disabled={
                      atLimit ||
                      (!result.has_fetchable_full_text && !result.abstract) ||
                      importMutation.isPending
                    }
                    onClick={() => importMutation.mutate(result.openalex_id)}
                  >
                    {importMutation.isPending && importingId === result.openalex_id ? "Importing..." : "Import"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        )}
      </section>

      {processedDocuments.length > 0 && (
        <section className="space-y-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight leading-snug">Processed documents</h2>
            <p className="text-sm text-muted-foreground">
              Already absorbed into your Agent's knowledge base - searchable below, not editable
              as files here.
            </p>
          </div>
          <ul className="divide-y divide-border">
            {processedDocuments.map((doc) => (
              <li key={doc.document_id} className="flex items-center justify-between py-3">
                <div>
                  <span className="text-sm font-medium">{doc.title}</span>
                  <p className="text-xs text-muted-foreground">
                    {doc.author && doc.publication_year
                      ? `${doc.author} (${doc.publication_year})`
                      : doc.author
                        ? `${doc.author} - year not set`
                        : doc.publication_year
                          ? `${doc.publication_year} - author not set`
                          : "No author/year set - can only be cited by title"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {doc.doi_verification_status === "verified" && (
                    <Badge variant="success">DOI verified</Badge>
                  )}
                  {doc.doi_verification_status === "mismatch" && (
                    <Badge variant="warning">DOI mismatch - check this</Badge>
                  )}
                  {doc.doi_verification_status === "not_found" && (
                    <Badge variant="destructive">DOI not found</Badge>
                  )}
                  <Badge variant="success">processed</Badge>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-4">
        <h2 className="text-base font-semibold tracking-tight leading-snug">Search Processed Knowledge</h2>
        <form onSubmit={handleSearch} className="flex gap-3">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search your knowledge..." />
          <Button type="submit">Search</Button>
        </form>
        {searchQuery.isFetching && (
          <div className="space-y-2" aria-label="Searching">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        )}
        {searchQuery.data && searchQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No matching knowledge yet.</p>
        )}
        <ul className="divide-y divide-border">
          {searchQuery.data?.map((result) => (
            <li key={result.chunk_id} className="space-y-1 py-3">
              <p className="text-sm font-medium tabular-nums">Score: {result.score.toFixed(3)}</p>
              <p className="text-sm text-muted-foreground">{result.content}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
