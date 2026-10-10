import { useRef, type FormEvent } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileTextIcon, PencilLineIcon } from "@phosphor-icons/react";
import {
  extractWritingStyleProfile,
  getWritingProfile,
  listWritingStyleDocuments,
  uploadWritingStyleDocument,
} from "@/api/writing";
import { deleteResearchDocument } from "@/api/documents";
import { ApiError } from "@/lib/apiClient";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useWorkspaceContext } from "@/components/WorkspaceGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

// Mirrors the backend's own MAX_WRITING_STYLE_SAMPLES (app/modules/writing/application/
// style_ingestion.py, itself equal to style_extraction's MAX_SAMPLES_PER_EXTRACTION) - the
// backend is the real enforcement point, this is only so the UI can proactively disable
// uploads instead of waiting for a failed round trip.
const WRITING_STYLE_SAMPLE_LIMIT = 5;

export function StyleProfilePage() {
  useDocumentTitle("Writing Style");
  const workspace = useWorkspaceContext();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const documentsQuery = useInfiniteQuery({
    queryKey: ["writing-style-documents"],
    queryFn: ({ pageParam }) => listWritingStyleDocuments({ offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.hasMore ? allPages.reduce((total, page) => total + page.items.length, 0) : undefined,
  });
  const documents = documentsQuery.data?.pages.flatMap((page) => page.items) ?? [];

  const profileQuery = useQuery({
    queryKey: ["writing-profile"],
    queryFn: getWritingProfile,
    retry: false,
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const file = fileInputRef.current?.files?.[0];
      if (!file) throw new Error("Choose a file first.");
      const extension = file.name.split(".").pop() ?? "txt";
      return uploadWritingStyleDocument({ file, title: file.name, format: extension });
    },
    onSuccess: () => {
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["writing-style-documents"] });
    },
  });

  const extractMutation = useMutation({
    mutationFn: () => extractWritingStyleProfile(documents.map((d) => d.document_id)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["writing-profile"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (documentId: number) => deleteResearchDocument(workspace.project.project_id, documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["writing-style-documents"] }),
  });

  function handleUpload(event: FormEvent) {
    event.preventDefault();
    uploadMutation.mutate();
  }

  const hasExtractedProfile = (profileQuery.data?.characteristics.length ?? 0) > 0;
  const uploadedCount = documents.length;
  const atLimit = uploadedCount >= WRITING_STYLE_SAMPLE_LIMIT;

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight leading-snug">Writing Style</h1>
        <p className="text-sm text-muted-foreground">
          Upload samples of your own writing so the AI can match your voice. Uploaded samples stay
          here across visits - they're never shown on the Research Documents page since they're
          never processed as research material. Up to {WRITING_STYLE_SAMPLE_LIMIT} samples
          ({uploadedCount}/{WRITING_STYLE_SAMPLE_LIMIT} used).
        </p>
        <form onSubmit={handleUpload} className="flex items-end gap-3">
          <Input ref={fileInputRef} type="file" className="max-w-xs" required disabled={atLimit} />
          <Button type="submit" disabled={uploadMutation.isPending || atLimit}>
            {uploadMutation.isPending ? "Uploading..." : "Upload sample"}
          </Button>
        </form>
        {atLimit && (
          <p className="text-sm text-muted-foreground">
            You've reached the {WRITING_STYLE_SAMPLE_LIMIT}-sample limit. Delete one below to make
            room for another.
          </p>
        )}
        {uploadMutation.isError && (
          <p role="alert" className="text-sm text-destructive">
            {uploadMutation.error instanceof ApiError ? uploadMutation.error.message : "Upload failed."}
          </p>
        )}

        {documentsQuery.isLoading && (
          <div className="space-y-2" aria-label="Loading samples">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        )}
        {documentsQuery.data && documents.length === 0 && (
          <EmptyState
            icon={FileTextIcon}
            title="No writing samples yet"
            description="Upload something you've written above so ScholarOS can learn to match your voice."
          />
        )}
        {documentsQuery.data && documents.length > 0 && (
          <ul className="divide-y divide-border">
            {documents.map((doc) => (
              <li key={doc.document_id} className="flex items-center justify-between py-3">
                <span className="text-sm font-medium">{doc.title}</span>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(doc.document_id)}
                >
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        )}
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
        {deleteMutation.isError && (
          <p role="alert" className="text-sm text-destructive">
            {deleteMutation.error instanceof ApiError ? deleteMutation.error.message : "Could not delete sample."}
          </p>
        )}

        <Button
          variant="secondary"
          disabled={uploadedCount === 0 || hasExtractedProfile || extractMutation.isPending}
          onClick={() => extractMutation.mutate()}
        >
          {extractMutation.isPending
            ? "Extracting..."
            : `Extract style profile from ${uploadedCount} uploaded sample(s)`}
        </Button>
        {hasExtractedProfile && (
          <p className="text-sm text-muted-foreground">
            A style profile has already been extracted (see below) - re-extraction isn't supported yet.
          </p>
        )}
        {extractMutation.isError && (
          <p role="alert" className="text-sm text-destructive">
            {extractMutation.error instanceof ApiError
              ? extractMutation.error.message
              : "Extraction failed."}
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold tracking-tight leading-snug">Current Profile</h2>
        {profileQuery.isLoading && (
          <div className="space-y-2" aria-label="Loading profile">
            <Skeleton className="h-16" />
          </div>
        )}
        {profileQuery.isError && (
          <EmptyState
            icon={PencilLineIcon}
            title="No writing profile yet"
            description="Upload and extract samples above to generate one."
          />
        )}
        {profileQuery.data && (
          <div className="space-y-2">
            <p className="text-sm font-medium">{profileQuery.data.profile_name}</p>
            {profileQuery.data.characteristics.map((c) => (
              <Card key={c.characteristic_id}>
                <CardHeader>
                  <CardTitle className="text-sm">{c.characteristic_type}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">{c.signal}</CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
