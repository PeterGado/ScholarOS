import { useRef, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  extractWritingStyleProfile,
  getWritingProfile,
  listWritingStyleDocuments,
  uploadWritingStyleDocument,
} from "@/api/writing";
import { deleteResearchDocument } from "@/api/documents";
import { ApiError } from "@/lib/apiClient";
import { useWorkspaceContext } from "@/components/WorkspaceGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Mirrors the backend's own MAX_WRITING_STYLE_SAMPLES (app/modules/writing/application/
// style_ingestion.py, itself equal to style_extraction's MAX_SAMPLES_PER_EXTRACTION) - the
// backend is the real enforcement point, this is only so the UI can proactively disable
// uploads instead of waiting for a failed round trip.
const WRITING_STYLE_SAMPLE_LIMIT = 5;

export function StyleProfilePage() {
  const workspace = useWorkspaceContext();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const documentsQuery = useQuery({
    queryKey: ["writing-style-documents"],
    queryFn: listWritingStyleDocuments,
  });

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
    mutationFn: () => extractWritingStyleProfile((documentsQuery.data ?? []).map((d) => d.document_id)),
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
  const uploadedCount = documentsQuery.data?.length ?? 0;
  const atLimit = uploadedCount >= WRITING_STYLE_SAMPLE_LIMIT;

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-lg font-semibold">Writing Style</h1>
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
          <p className="text-sm text-destructive">
            {uploadMutation.error instanceof ApiError ? uploadMutation.error.message : "Upload failed."}
          </p>
        )}

        {documentsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading samples...</p>}
        {documentsQuery.data && documentsQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No samples uploaded yet.</p>
        )}
        {documentsQuery.data && documentsQuery.data.length > 0 && (
          <ul className="space-y-2">
            {documentsQuery.data.map((doc) => (
              <li key={doc.document_id}>
                <Card>
                  <CardContent className="flex items-center justify-between py-3">
                    <span className="text-sm font-medium">{doc.title}</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(doc.document_id)}
                    >
                      Delete
                    </Button>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        )}
        {deleteMutation.isError && (
          <p className="text-sm text-destructive">
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
          <p className="text-sm text-destructive">
            {extractMutation.error instanceof ApiError
              ? extractMutation.error.message
              : "Extraction failed."}
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold">Current Profile</h2>
        {profileQuery.isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {profileQuery.isError && (
          <p className="text-sm text-muted-foreground">No writing profile yet - upload and extract samples above.</p>
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
