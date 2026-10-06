import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applySegmentTemplate,
  createWritingSegment,
  deleteWritingSegment,
  listSegmentTemplates,
  listWritingSegments,
  updateWritingSegment,
} from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StackIcon } from "@phosphor-icons/react";
import type { ApplySegmentTemplateResponse, WritingSegmentResponse } from "@/api/schemas";

// Mirrors the backend's own MAX_WRITING_SEGMENTS_PER_AGENT (app/modules/writing/application/
// segments.py) - the backend is the real enforcement point, this only lets the UI show a
// sensible message instead of waiting for a failed round trip.
const WRITING_SEGMENT_LIMIT = 50;

export const WRITING_SEGMENTS_QUERY_KEY = ["writing-segments"];

export function SegmentsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editInstructions, setEditInstructions] = useState("");
  const [lastApplyResult, setLastApplyResult] = useState<ApplySegmentTemplateResponse | null>(null);

  const segmentsQuery = useQuery({ queryKey: WRITING_SEGMENTS_QUERY_KEY, queryFn: listWritingSegments });
  const segments = segmentsQuery.data ?? [];

  const templatesQuery = useQuery({ queryKey: ["segment-templates"], queryFn: listSegmentTemplates });
  const templates = templatesQuery.data ?? [];

  const applyTemplateMutation = useMutation({
    mutationFn: (templateId: string) => applySegmentTemplate(templateId),
    onSuccess: (result) => {
      setLastApplyResult(result);
      queryClient.invalidateQueries({ queryKey: WRITING_SEGMENTS_QUERY_KEY });
    },
  });

  const createMutation = useMutation({
    mutationFn: () => createWritingSegment(name.trim(), instructions.trim()),
    onSuccess: () => {
      setName("");
      setInstructions("");
      queryClient.invalidateQueries({ queryKey: WRITING_SEGMENTS_QUERY_KEY });
    },
  });

  const updateMutation = useMutation({
    mutationFn: (segmentId: number) => updateWritingSegment(segmentId, editName.trim(), editInstructions.trim()),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: WRITING_SEGMENTS_QUERY_KEY });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (segmentId: number) => deleteWritingSegment(segmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: WRITING_SEGMENTS_QUERY_KEY }),
  });

  function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !instructions.trim()) return;
    createMutation.mutate();
  }

  function startEditing(segment: WritingSegmentResponse) {
    setEditingId(segment.segment_id);
    setEditName(segment.name);
    setEditInstructions(segment.instructions);
  }

  const atLimit = segments.length >= WRITING_SEGMENT_LIMIT;

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight leading-snug">Project Segments</h1>
        <p className="text-sm text-muted-foreground">
          Save extra writing instructions for different parts of your project (e.g. "Background of
          the Study", "Statement of the Problem"). Pick a segment before sending a chat message to
          apply its instructions to that specific reply.
        </p>
      </section>

      {templates.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold tracking-tight leading-snug">Templates</h2>
          <p className="text-sm text-muted-foreground">
            Built-in segment sets you can apply in one click. Applying is safe to repeat - anything
            that already exists by name is left untouched, not duplicated.
          </p>
          <ul className="divide-y divide-border">
            {templates.map((template) => (
              <li key={template.template_id} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <p className="text-sm font-medium">{template.name}</p>
                  <p className="text-sm text-muted-foreground">{template.description}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{template.segment_count} segments</p>
                </div>
                <Button
                  size="sm"
                  disabled={applyTemplateMutation.isPending}
                  onClick={() => applyTemplateMutation.mutate(template.template_id)}
                >
                  {applyTemplateMutation.isPending ? "Applying..." : "Apply"}
                </Button>
              </li>
            ))}
          </ul>
          {applyTemplateMutation.isError && (
            <p className="text-sm text-destructive">
              {applyTemplateMutation.error instanceof ApiError
                ? applyTemplateMutation.error.message
                : "Could not apply template."}
            </p>
          )}
          {lastApplyResult && (
            <p className="text-sm text-muted-foreground">
              Added {lastApplyResult.created.length} new segment(s)
              {lastApplyResult.skipped_existing.length > 0
                ? `, ${lastApplyResult.skipped_existing.length} already existed and were left unchanged.`
                : "."}
              {lastApplyResult.limit_reached &&
                " Stopped early - you've reached the segment limit; delete some to add the rest."}
            </p>
          )}
        </section>
      )}

      <section className="space-y-4">
        <h2 className="text-base font-semibold tracking-tight leading-snug">Add a Segment</h2>
        <form onSubmit={handleCreate} className="space-y-3">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Segment name (e.g. Background of the Study)"
            disabled={atLimit}
            required
          />
          <Textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="Instructions to apply whenever this segment is selected..."
            rows={3}
            disabled={atLimit}
            required
          />
          <Button type="submit" disabled={createMutation.isPending || atLimit || !name.trim() || !instructions.trim()}>
            {createMutation.isPending ? "Adding..." : "Add segment"}
          </Button>
        </form>
        {atLimit && (
          <p className="text-sm text-muted-foreground">
            You've reached the {WRITING_SEGMENT_LIMIT}-segment limit. Delete one below to make room
            for another.
          </p>
        )}
        {createMutation.isError && (
          <p className="text-sm text-destructive">
            {createMutation.error instanceof ApiError ? createMutation.error.message : "Could not add segment."}
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold tracking-tight leading-snug">Your Segments</h2>
        {segmentsQuery.isLoading && (
          <div className="space-y-2" aria-label="Loading segments">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        )}
        {segmentsQuery.data && segments.length === 0 && (
          <EmptyState
            icon={StackIcon}
            title="No segments yet"
            description="Add a segment above to save extra writing instructions for a specific part of your project."
          />
        )}
        <ul className="divide-y divide-border">
          {segments.map((segment) =>
            editingId === segment.segment_id ? (
              <li key={segment.segment_id} className="py-2">
                <Card>
                  <CardContent className="space-y-3 py-4">
                    <Input value={editName} onChange={(e) => setEditName(e.target.value)} required />
                    <Textarea
                      value={editInstructions}
                      onChange={(e) => setEditInstructions(e.target.value)}
                      rows={3}
                      required
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={updateMutation.isPending || !editName.trim() || !editInstructions.trim()}
                        onClick={() => updateMutation.mutate(segment.segment_id)}
                      >
                        {updateMutation.isPending ? "Saving..." : "Save"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                        Cancel
                      </Button>
                    </div>
                    {updateMutation.isError && (
                      <p className="text-sm text-destructive">
                        {updateMutation.error instanceof ApiError ? updateMutation.error.message : "Could not save."}
                      </p>
                    )}
                  </CardContent>
                </Card>
              </li>
            ) : (
              <li key={segment.segment_id} className="py-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">{segment.name}</CardTitle>
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" onClick={() => startEditing(segment)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(segment.segment_id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{segment.instructions}</p>
              </li>
            ),
          )}
        </ul>
        {deleteMutation.isError && (
          <p className="text-sm text-destructive">
            {deleteMutation.error instanceof ApiError ? deleteMutation.error.message : "Could not delete segment."}
          </p>
        )}
      </section>
    </div>
  );
}
