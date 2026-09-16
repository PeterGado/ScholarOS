import { useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { extractWritingStyleProfile, getWritingProfile, uploadWritingStyleDocument } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function StyleProfilePage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadedDocumentIds, setUploadedDocumentIds] = useState<number[]>([]);

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
    onSuccess: (upload) => {
      setUploadedDocumentIds((ids) => [...ids, upload.document_id]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const extractMutation = useMutation({
    mutationFn: () => extractWritingStyleProfile(uploadedDocumentIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["writing-profile"] }),
  });

  function handleUpload(event: FormEvent) {
    event.preventDefault();
    uploadMutation.mutate();
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-lg font-semibold">Writing Style</h1>
        <form onSubmit={handleUpload} className="flex items-end gap-3">
          <Input ref={fileInputRef} type="file" className="max-w-xs" required />
          <Button type="submit" disabled={uploadMutation.isPending}>
            {uploadMutation.isPending ? "Uploading..." : "Upload sample"}
          </Button>
        </form>
        {uploadedDocumentIds.length > 0 && (
          <p className="text-sm text-muted-foreground">
            Uploaded {uploadedDocumentIds.length} sample(s) this session: {uploadedDocumentIds.join(", ")}
          </p>
        )}
        <Button
          variant="secondary"
          disabled={uploadedDocumentIds.length === 0 || extractMutation.isPending}
          onClick={() => extractMutation.mutate()}
        >
          {extractMutation.isPending ? "Extracting..." : "Extract style profile from uploaded samples"}
        </Button>
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
