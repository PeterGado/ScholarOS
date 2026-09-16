import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createDraft, listDrafts } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function DraftsPage() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");

  const draftsQuery = useQuery({ queryKey: ["drafts"], queryFn: listDrafts });

  const createMutation = useMutation({
    mutationFn: () => createDraft(title),
    onSuccess: () => {
      setTitle("");
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">Drafts</h1>
      <form onSubmit={handleSubmit} className="flex gap-3">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New draft title" required />
        <Button type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Creating..." : "Create draft"}
        </Button>
      </form>
      {createMutation.isError && (
        <p className="text-sm text-destructive">
          {createMutation.error instanceof ApiError ? createMutation.error.message : "Could not create draft."}
        </p>
      )}

      {draftsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading drafts...</p>}
      {draftsQuery.data && draftsQuery.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No drafts yet - create one above.</p>
      )}
      <ul className="space-y-2">
        {draftsQuery.data?.map((draft) => (
          <li key={draft.draft_id}>
            <Link to={`/drafts/${draft.draft_id}`}>
              <Card>
                <CardContent className="flex items-center justify-between py-3">
                  <span className="text-sm font-medium">{draft.title}</span>
                  <Badge variant="secondary">{draft.status}</Badge>
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
