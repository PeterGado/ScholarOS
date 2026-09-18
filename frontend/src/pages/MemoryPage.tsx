import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listMemory, supersedeMemoryRecord } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const PROVENANCE_LABELS: Record<string, string> = {
  user_input: "from your own correction",
  conversation: "from a conversation",
  knowledge_element: "from research knowledge",
  document: "from a document",
};

// Persistent Brain v2: "let the user see what the brain remembers... show provenance...
// allow correction". Read-only listing plus a per-record "Correct this" action that supersedes
// a record rather than editing it in place - the old content is preserved, not rewritten.
export function MemoryPage() {
  const queryClient = useQueryClient();
  const memoryQuery = useQuery({ queryKey: ["memory"], queryFn: listMemory });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draftContent, setDraftContent] = useState("");

  const supersedeMutation = useMutation({
    mutationFn: ({ recordId, content }: { recordId: number; content: string }) =>
      supersedeMemoryRecord(recordId, content),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["memory"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Memory</h1>
        <p className="text-sm text-muted-foreground">
          What your Agent Workspace remembers, and where each memory came from. The AI never
          silently redefines this - every entry here came from your own conversation or your
          own correction.
        </p>
      </div>

      {memoryQuery.isLoading && <p className="text-sm text-muted-foreground">Loading memory...</p>}
      {memoryQuery.data && memoryQuery.data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No memory yet - it accumulates automatically as you chat.
        </p>
      )}
      <div className="space-y-3">
        {memoryQuery.data?.map((record) => (
          <Card key={record.record_id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-sm">
                <Badge variant="secondary">{record.record_type}</Badge>
                <span className="text-xs font-normal text-muted-foreground">
                  {record.provenance
                    .map((p) => PROVENANCE_LABELS[p.source_type] ?? p.source_type)
                    .join(", ") || "no provenance recorded"}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {editingId === record.record_id ? (
                <div className="space-y-2">
                  <Textarea value={draftContent} onChange={(e) => setDraftContent(e.target.value)} rows={2} />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      disabled={supersedeMutation.isPending || !draftContent.trim()}
                      onClick={() => supersedeMutation.mutate({ recordId: record.record_id, content: draftContent })}
                    >
                      Save correction
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-sm whitespace-pre-wrap">{record.content}</p>
                  {record.rationale && (
                    <p className="text-xs text-muted-foreground">Why: {record.rationale}</p>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setEditingId(record.record_id);
                      setDraftContent(record.content);
                    }}
                  >
                    Correct this
                  </Button>
                </>
              )}
              {supersedeMutation.isError && editingId === null && (
                <p className="text-sm text-destructive">
                  {supersedeMutation.error instanceof ApiError
                    ? supersedeMutation.error.message
                    : "Could not save correction."}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
