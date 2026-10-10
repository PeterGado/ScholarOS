import { useEffect, useRef, useState, type FormEvent } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { TrayIcon } from "@phosphor-icons/react";
import {
  deleteResearchDocument,
  listProjectDocuments,
  retryResearchDocument,
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

  function handleUpload(event: FormEvent) {
    event.preventDefault();
    uploadMutation.mutate();
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    setSearchSubmitted(query);
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
