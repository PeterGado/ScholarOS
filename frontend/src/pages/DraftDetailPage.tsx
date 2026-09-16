import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getDraft, listDraftVersions, requestDraftGeneration, submitDraftReview } from "@/api/writing";
import type { ReviewOutcome } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const GENERATION_POLL_TIMEOUT_MS = 120_000;
const GENERATION_POLL_INTERVAL_MS = 2000;

export function DraftDetailPage() {
  const { draftId: draftIdParam } = useParams<{ draftId: string }>();
  const draftId = Number(draftIdParam);
  const queryClient = useQueryClient();
  const [instructions, setInstructions] = useState("");
  const [isWaitingForVersion, setIsWaitingForVersion] = useState(false);

  const draftQuery = useQuery({ queryKey: ["draft", draftId], queryFn: () => getDraft(draftId) });
  const versionsQuery = useQuery({
    queryKey: ["draft-versions", draftId],
    queryFn: () => listDraftVersions(draftId),
    // No Work Item status endpoint exists (see docs/Frontend_Implementation_Plan.md Sec3) - the
    // only observable signal that generation finished is a new version appearing here.
    refetchInterval: isWaitingForVersion ? GENERATION_POLL_INTERVAL_MS : false,
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      const versionCountBefore = versionsQuery.data?.length ?? 0;
      await requestDraftGeneration(draftId, instructions);
      return versionCountBefore;
    },
    onSuccess: (versionCountBefore) => {
      setInstructions("");
      setIsWaitingForVersion(true);
      const startedAt = Date.now();
      const interval = setInterval(async () => {
        const versions = await queryClient.fetchQuery({
          queryKey: ["draft-versions", draftId],
          queryFn: () => listDraftVersions(draftId),
        });
        if (versions.length > versionCountBefore || Date.now() - startedAt > GENERATION_POLL_TIMEOUT_MS) {
          setIsWaitingForVersion(false);
          clearInterval(interval);
        }
      }, GENERATION_POLL_INTERVAL_MS);
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ versionId, outcome }: { versionId: number; outcome: ReviewOutcome }) =>
      submitDraftReview(draftId, versionId, outcome),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["draft", draftId] }),
  });

  function handleGenerate(event: FormEvent) {
    event.preventDefault();
    generateMutation.mutate();
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold">{draftQuery.data?.title ?? "Draft"}</h1>
        {draftQuery.data && <Badge variant="secondary">{draftQuery.data.status}</Badge>}
      </div>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">Generate a New Version</h2>
        <form onSubmit={handleGenerate} className="space-y-3">
          <Textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="Instructions for this generation (e.g. 'Write the introduction section')"
            rows={3}
            required
          />
          <Button type="submit" disabled={generateMutation.isPending || isWaitingForVersion}>
            {isWaitingForVersion ? "Generating..." : generateMutation.isPending ? "Requesting..." : "Generate"}
          </Button>
        </form>
        {generateMutation.isError && (
          <p className="text-sm text-destructive">
            {generateMutation.error instanceof ApiError
              ? generateMutation.error.message
              : "Could not request generation."}
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold">Versions</h2>
        {versionsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading versions...</p>}
        {versionsQuery.data && versionsQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No versions yet - generate one above.</p>
        )}
        <div className="space-y-4">
          {versionsQuery.data
            ?.slice()
            .reverse()
            .map((version) => (
              <Card key={version.version_id}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span>
                      Version {version.version_number} ({version.created_by})
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="whitespace-pre-wrap text-sm">{version.content}</p>
                  {version.evidence.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground">Evidence</p>
                      <ul className="text-xs text-muted-foreground">
                        {version.evidence.map((link, index) => (
                          <li key={index}>
                            {link.target_type}: {link.chunk_id ?? link.document_id}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={reviewMutation.isPending}
                      onClick={() => reviewMutation.mutate({ versionId: version.version_id, outcome: "approved" })}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reviewMutation.isPending}
                      onClick={() =>
                        reviewMutation.mutate({ versionId: version.version_id, outcome: "revisions_requested" })
                      }
                    >
                      Request revisions
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={reviewMutation.isPending}
                      onClick={() => reviewMutation.mutate({ versionId: version.version_id, outcome: "rejected" })}
                    >
                      Reject
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
        </div>
      </section>
    </div>
  );
}
