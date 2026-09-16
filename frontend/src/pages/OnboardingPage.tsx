import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { createAgentWorkspace } from "@/api/agents";
import { ApiError } from "@/lib/apiClient";

/** First-run flow: a user has exactly one Agent, which owns exactly one Project (ADR-009) -
 * there is no "create another project" flow because none exists in the backend. */
export function OnboardingPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createAgentWorkspace({
        project_title: title,
        project_topic: topic,
        project_description: description || null,
      }),
    onSuccess: () => navigate("/drafts"),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-lg font-semibold">Set up your workspace</h1>
      <p className="text-sm text-muted-foreground">
        ScholarOS gives you one Agent workspace with one Project. Tell it what you're working on.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="title" className="text-sm font-medium">
            Project title
          </label>
          <input
            id="title"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="topic" className="text-sm font-medium">
            Topic
          </label>
          <input
            id="topic"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="description" className="text-sm font-medium">
            Description (optional)
          </label>
          <textarea
            id="description"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
        </div>
        {mutation.isError && (
          <p className="text-sm text-destructive">
            {mutation.error instanceof ApiError ? mutation.error.message : "Could not create the workspace."}
          </p>
        )}
        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {mutation.isPending ? "Creating..." : "Create workspace"}
        </button>
      </form>
    </div>
  );
}
