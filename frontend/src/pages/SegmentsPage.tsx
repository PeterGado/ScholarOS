import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createWritingSegment, deleteWritingSegment, listWritingSegments, updateWritingSegment } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WritingSegmentResponse } from "@/api/schemas";

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

  const segmentsQuery = useQuery({ queryKey: WRITING_SEGMENTS_QUERY_KEY, queryFn: listWritingSegments });
  const segments = segmentsQuery.data ?? [];

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
        <h1 className="text-lg font-semibold">Project Segments</h1>
        <p className="text-sm text-muted-foreground">
          Save extra writing instructions for different parts of your project (e.g. "Background of
          the Study", "Statement of the Problem"). Pick a segment before sending a chat message to
          apply its instructions to that specific reply.
        </p>
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
        <h2 className="text-base font-semibold">Your Segments</h2>
        {segmentsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {segmentsQuery.data && segments.length === 0 && (
          <p className="text-sm text-muted-foreground">No segments yet - add one above.</p>
        )}
        <ul className="space-y-2">
          {segments.map((segment) => (
            <li key={segment.segment_id}>
              <Card>
                {editingId === segment.segment_id ? (
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
                ) : (
                  <>
                    <CardHeader className="flex-row items-center justify-between space-y-0">
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
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">{segment.instructions}</CardContent>
                  </>
                )}
              </Card>
            </li>
          ))}
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
