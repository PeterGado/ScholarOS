import { useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listProjectDocuments, uploadResearchDocument } from "@/api/documents";
import { searchKnowledge } from "@/api/knowledge";
import { ApiError } from "@/lib/apiClient";
import { useWorkspaceContext } from "@/components/WorkspaceGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function DocumentsPage() {
  const workspace = useWorkspaceContext();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [query, setQuery] = useState("");
  const [searchSubmitted, setSearchSubmitted] = useState("");

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

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-lg font-semibold">Research Documents</h1>
        <form onSubmit={handleUpload} className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-sm font-medium">Title (optional)</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Document title" />
          </div>
          <Input ref={fileInputRef} type="file" className="max-w-xs" required />
          <Button type="submit" disabled={uploadMutation.isPending}>
            {uploadMutation.isPending ? "Uploading..." : "Upload"}
          </Button>
        </form>
        {uploadMutation.isError && (
          <p className="text-sm text-destructive">
            {uploadMutation.error instanceof ApiError ? uploadMutation.error.message : "Upload failed."}
          </p>
        )}

        {documentsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading documents...</p>}
        {documentsQuery.data && documentsQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
        )}
        <ul className="space-y-2">
          {documentsQuery.data?.map((doc) => (
            <li key={doc.document_id}>
              <Card>
                <CardContent className="flex items-center justify-between py-3">
                  <span className="text-sm font-medium">{doc.title}</span>
                  <Badge variant={doc.processing_status === "processed" ? "default" : "secondary"}>
                    {doc.processing_status}
                  </Badge>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
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
