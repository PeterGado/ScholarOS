import { useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Brain } from "lucide-react";
import { listMemory, supersedeMemoryRecord } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

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
  const memoryQuery = useInfiniteQuery({
    queryKey: ["memory"],
    queryFn: ({ pageParam }) => listMemory({ offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.hasMore ? allPages.reduce((total, page) => total + page.items.length, 0) : undefined,
  });
  const records = memoryQuery.data?.pages.flatMap((page) => page.items) ?? [];
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
      {memoryQuery.data && records.length === 0 && (
        <EmptyState
          icon={Brain}
          title="Nothing remembered yet"
          description="Memory builds automatically as you chat - decisions, terminology, and direction get captured here so you never have to re-explain your own research."
        />
      )}
      <div className="space-y-3">
        {records.map((record) => (
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
      {memoryQuery.hasNextPage && (
        <Button
          variant="outline"
          size="sm"
          disabled={memoryQuery.isFetchingNextPage}
          onClick={() => memoryQuery.fetchNextPage()}
        >
          {memoryQuery.isFetchingNextPage ? "Loading..." : "Load more"}
        </Button>
      )}
    </div>
  );
}
