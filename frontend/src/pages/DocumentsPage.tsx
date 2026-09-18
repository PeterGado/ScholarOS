import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteResearchDocument, listProjectDocuments, retryResearchDocument, uploadResearchDocument } from "@/api/documents";
import { searchKnowledge } from "@/api/knowledge";
import { ApiError } from "@/lib/apiClient";
import { useToast } from "@/lib/ToastContext";
import { useWorkspaceContext } from "@/components/WorkspaceGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const DELETABLE_STATUSES = new Set(["pending", "failed"]);
// Mirrors the backend's own MAX_RESEARCH_DOCUMENTS_PER_PROJECT (app/modules/document/
// application/use_cases.py) - the backend is the real enforcement point, this is only so the
// UI can proactively disable uploads instead of waiting for a failed round trip.
const RESEARCH_DOCUMENT_LIMIT = 20;

export function DocumentsPage() {
  const workspace = useWorkspaceContext();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [query, setQuery] = useState("");
  const [searchSubmitted, setSearchSubmitted] = useState("");
  const previousStatusesRef = useRef<Record<number, string>>({});

  const documentsQuery = useQuery({
    queryKey: ["documents", workspace.project.project_id],
    queryFn: () => listProjectDocuments(workspace.project.project_id),
    // Documents transition pending -> processing -> processed/failed in the background
    // (the app's own Work Item executor) - poll while any document hasn't reached a terminal
    // state yet, since there is no push channel or dedicated status endpoint.
    refetchInterval: (query) => {
      const documents = query.state.data ?? [];
      const stillProcessing = documents.some(
        (doc) => doc.processing_status === "pending" || doc.processing_status === "processing",
      );
      return stillProcessing ? 2000 : false;
    },
  });

  // A processed document intentionally disappears from the list below (see the comment on
  // inProgressDocuments) with nothing else marking success - confusing enough that a user
  // reported it as "vanished, did it work?". Fires a toast on the actual pending/processing ->
  // processed transition observed during this page visit, never on first load (a document
  // already processed before the user opened the page isn't a new event worth announcing).
  useEffect(() => {
    if (!documentsQuery.data) return;
    for (const doc of documentsQuery.data) {
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
  const inProgressDocuments = documentsQuery.data?.filter((doc) => doc.processing_status !== "processed") ?? [];

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const file = fileInputRef.current?.files?.[0];
      if (!file) throw new Error("Choose a file first.");
      const extension = file.name.split(".").pop() ?? "txt";
      return uploadResearchDocument({
        projectId: workspace.project.project_id,
        file,
        title: title || file.name,
        format: extension,
      });
    },
    onSuccess: () => {
      setTitle("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["documents", workspace.project.project_id] });
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

  const documentCount = documentsQuery.data?.length ?? 0;
  const atLimit = documentCount >= RESEARCH_DOCUMENT_LIMIT;

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Research Documents</h1>
          <p className="text-sm text-muted-foreground">
            Upload source material for your AI to draw on. Supports plain text, Word (.docx), and
            PDF files. Once a document finishes processing, it moves into your searchable
            knowledge base below and no longer appears in this list. Up to {RESEARCH_DOCUMENT_LIMIT}
            {" "}documents per project ({documentCount}/{RESEARCH_DOCUMENT_LIMIT} used).
          </p>
        </div>
        <form onSubmit={handleUpload} className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-sm font-medium">Title (optional)</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Document title" disabled={atLimit} />
          </div>
          <Input ref={fileInputRef} type="file" className="max-w-xs" required disabled={atLimit} />
          <Button type="submit" disabled={uploadMutation.isPending || atLimit}>
            {uploadMutation.isPending ? "Uploading..." : "Upload"}
          </Button>
        </form>
        {atLimit && (
          <p className="text-sm text-muted-foreground">
            You've reached the {RESEARCH_DOCUMENT_LIMIT}-document limit for this project. A pending
            or failed document below can be deleted to make room - an already-processed one can't be
            removed, since its knowledge is already part of your Agent's knowledge base.
          </p>
        )}
        {uploadMutation.isError && (
          <p className="text-sm text-destructive">
            {uploadMutation.error instanceof ApiError ? uploadMutation.error.message : "Upload failed."}
          </p>
        )}

        {documentsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading documents...</p>}
        {documentsQuery.data && inProgressDocuments.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nothing pending - uploaded documents will appear here while processing.
          </p>
        )}
        <ul className="space-y-2">
          {inProgressDocuments.map((doc) => (
            <li key={doc.document_id}>
              <Card>
                <CardContent className="space-y-2 py-3">
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
                  {doc.error_message && <p className="text-sm text-destructive">{doc.error_message}</p>}
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
        {retryMutation.isError && (
          <p className="text-sm text-destructive">
            {retryMutation.error instanceof ApiError ? retryMutation.error.message : "Could not retry document."}
          </p>
        )}
        {deleteMutation.isError && (
          <p className="text-sm text-destructive">
            {deleteMutation.error instanceof ApiError ? deleteMutation.error.message : "Could not delete document."}
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold">Search Processed Knowledge</h2>
        <form onSubmit={handleSearch} className="flex gap-3">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search your knowledge..." />
          <Button type="submit">Search</Button>
        </form>
        {searchQuery.isFetching && <p className="text-sm text-muted-foreground">Searching...</p>}
        {searchQuery.data && searchQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No matching knowledge yet.</p>
        )}
        <ul className="space-y-2">
          {searchQuery.data?.map((result) => (
            <li key={result.chunk_id}>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Score: {result.score.toFixed(3)}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">{result.content}</CardContent>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
