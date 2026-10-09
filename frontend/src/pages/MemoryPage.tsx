import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BrainIcon } from "@phosphor-icons/react";
import { listMemory, supersedeMemoryRecord } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { useToast } from "@/lib/ToastContext";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

function humanizeRecordType(recordType: string): string {
  return recordType.charAt(0).toUpperCase() + recordType.slice(1).replaceAll("_", " ");
}

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
  const { showToast } = useToast();
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
  const correctTriggerRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  const previousEditingIdRef = useRef<number | null>(null);

  // Accessibility: focusing synchronously inside Cancel's onClick doesn't work - at that
  // point React hasn't re-rendered yet, so the ref still holds null from when the trigger
  // button was unmounted (see AppShell.tsx's own version of this fix for the full explanation,
  // found there first via an actual browser check).
  useEffect(() => {
    if (editingId === null && previousEditingIdRef.current !== null) {
      correctTriggerRefs.current[previousEditingIdRef.current]?.focus();
    }
    previousEditingIdRef.current = editingId;
  }, [editingId]);

  const supersedeMutation = useMutation({
    mutationFn: ({ recordId, content }: { recordId: number; content: string }) =>
      supersedeMemoryRecord(recordId, content),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["memory"] });
      showToast("Memory record updated.");
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight leading-snug">Memory</h1>
        <p className="text-sm text-muted-foreground">
          What your Agent Workspace remembers, and where each memory came from. The AI never
          silently redefines this - every entry here came from your own conversation or your
          own correction.
        </p>
      </div>

      {memoryQuery.isLoading && (
        <div className="space-y-2" aria-label="Loading memory">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      )}
      {memoryQuery.data && records.length === 0 && (
        <EmptyState
          icon={BrainIcon}
          title="Nothing remembered yet"
          description="Memory builds automatically as you chat - decisions, terminology, and direction get captured here so you never have to re-explain your own research."
        />
      )}
      <ul className="divide-y divide-border">
        {records.map((record) =>
          editingId === record.record_id ? (
            <li key={record.record_id} className="py-2">
              <Card>
                <CardHeader>
                  <CardTitle>{humanizeRecordType(record.record_type)}</CardTitle>
                  <CardAction>
                    <span className="text-xs font-normal text-muted-foreground">
                      {record.provenance
                        .map((p) => PROVENANCE_LABELS[p.source_type] ?? p.source_type)
                        .join(", ") || "no provenance recorded"}
                    </span>
                  </CardAction>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Textarea value={draftContent} onChange={(e) => setDraftContent(e.target.value)} rows={2} />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      disabled={supersedeMutation.isPending || !draftContent.trim()}
                      onClick={() => supersedeMutation.mutate({ recordId: record.record_id, content: draftContent })}
                    >
                      Save correction
                    </Button>
                    <Button
                      // Accessibility (found during an audit, 2026-10-09): swapping to this
                      // edit card used to drop keyboard focus to <body> with no follow-up.
                      autoFocus
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingId(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                  {supersedeMutation.isError && (
                    <p className="text-sm text-destructive">
                      {supersedeMutation.error instanceof ApiError
                        ? supersedeMutation.error.message
                        : "Could not save correction."}
                    </p>
                  )}
                </CardContent>
              </Card>
            </li>
          ) : (
            <li key={record.record_id} className="space-y-2 py-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{humanizeRecordType(record.record_type)}</p>
                <span className="text-xs text-muted-foreground">
                  {record.provenance
                    .map((p) => PROVENANCE_LABELS[p.source_type] ?? p.source_type)
                    .join(", ") || "no provenance recorded"}
                </span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{record.content}</p>
              {record.rationale && <p className="text-xs text-muted-foreground">Why: {record.rationale}</p>}
              <Button
                ref={(el) => {
                  correctTriggerRefs.current[record.record_id] = el;
                }}
                size="sm"
                variant="outline"
                onClick={() => {
                  setEditingId(record.record_id);
                  setDraftContent(record.content);
                }}
              >
                Correct this
              </Button>
            </li>
          ),
        )}
      </ul>
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
