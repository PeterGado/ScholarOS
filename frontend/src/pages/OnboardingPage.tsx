import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createAgentWorkspace } from "@/api/agents";
import { uploadResearchDocuments } from "@/api/documents";
import { extractWritingStyleProfile, startConversation, uploadWritingStyleDocument } from "@/api/writing";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AgentWorkspaceResponse } from "@/api/schemas";

type Step = "project" | "documents" | "generating";

const STEPS: { key: Step; label: string }[] = [
  { key: "project", label: "Project" },
  { key: "documents", label: "Documents" },
];

/** First-run guided setup: Project -> Documents (research + writing style together, both
 * optional) -> Generate, landing directly in a live conversation. Both document kinds are
 * genuinely optional (Persistent Brain Decision 6) - "Generate" always advances, whether or
 * not anything was uploaded, and the system falls back to its built-in style/reasoning when
 * nothing was. */
export function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("project");
  const [workspace, setWorkspace] = useState<AgentWorkspaceResponse | null>(null);

  return (
    <div className="mx-auto max-w-lg space-y-6 py-10">
      <ol className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
        {STEPS.map((s, index) => (
          <li key={s.key} className="flex items-center gap-2">
            <span
              className={
                "flex size-5 items-center justify-center rounded-full border text-[0.7rem] " +
                (s.key === step || STEPS.findIndex((x) => x.key === step) > index
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border")
              }
            >
              {index + 1}
            </span>
            <span className={s.key === step ? "font-medium text-foreground" : ""}>{s.label}</span>
            {index < STEPS.length - 1 && <span className="mx-1 text-border">&rarr;</span>}
          </li>
        ))}
      </ol>

      {step === "project" && (
        <ProjectStep
          onCreated={(ws) => {
            setWorkspace(ws);
            setStep("documents");
          }}
        />
      )}
      {step === "documents" && workspace && (
        <DocumentsStep
          projectId={workspace.project.project_id}
          onGenerate={async () => {
            setStep("generating");
            const conversation = await startConversation();
            navigate(`/chat/${conversation.conversation_id}`);
          }}
        />
      )}
      {step === "generating" && <p className="text-center text-sm text-muted-foreground">Setting up your chat...</p>}
    </div>
  );
}

function ProjectStep({ onCreated }: { onCreated: (workspace: AgentWorkspaceResponse) => void }) {
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [description, setDescription] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      createAgentWorkspace({
        project_title: title,
        project_topic: topic,
        project_description: description || null,
      }),
    onSuccess: (workspace) => {
      // WorkspaceGate reads this same query key. After a workspace reset, that cache entry can
      // still hold a stale 404 (from the reset's own invalidation racing a still-mounted
      // WorkspaceGate) - seed it with the real, just-created workspace so the next WorkspaceGate
      // mount (right after "Skip and generate" navigates to /chat/:id) sees truth immediately
      // instead of momentarily re-reading that stale error and bouncing back to onboarding.
      queryClient.setQueryData(["agent-workspace"], workspace);
      onCreated(workspace);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Set up your workspace</h1>
        <p className="text-sm text-muted-foreground">
          ScholarOS gives you one Agent workspace with one Project. Tell it what you're working on.
        </p>
      </div>
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
            placeholder="Project type, expected length, audience, methodology, tone - anything useful for the AI to know every time it writes for you."
          />
        </div>
        {mutation.isError && (
          <p className="text-sm text-destructive">
            {mutation.error instanceof ApiError ? mutation.error.message : "Could not create the workspace."}
          </p>
        )}
        <Button type="submit" disabled={mutation.isPending} className="w-full">
          {mutation.isPending ? "Creating..." : "Next"}
        </Button>
      </form>
    </div>
  );
}

function DocumentsStep({ projectId, onGenerate }: { projectId: number; onGenerate: () => void }) {
  const researchFileInputRef = useRef<HTMLInputElement>(null);
  const styleFileInputRef = useRef<HTMLInputElement>(null);
  const [researchUploaded, setResearchUploaded] = useState<string[]>([]);
  const [styleDocumentIds, setStyleDocumentIds] = useState<number[]>([]);
  const [isFinishing, setIsFinishing] = useState(false);

  const researchUploadMutation = useMutation({
    mutationFn: async () => {
      const files = Array.from(researchFileInputRef.current?.files ?? []);
      if (files.length === 0) throw new Error("Choose at least one file first.");
      return uploadResearchDocuments(projectId, files);
    },
    onSuccess: (documents) => {
      setResearchUploaded((titles) => [...titles, ...documents.map((document) => document.title)]);
      if (researchFileInputRef.current) researchFileInputRef.current.value = "";
    },
  });

  const styleUploadMutation = useMutation({
    mutationFn: async () => {
      const file = styleFileInputRef.current?.files?.[0];
      if (!file) throw new Error("Choose a file first.");
      const extension = file.name.split(".").pop() ?? "txt";
      return uploadWritingStyleDocument({ file, title: file.name, format: extension });
    },
    onSuccess: (upload) => {
      setStyleDocumentIds((ids) => [...ids, upload.document_id]);
      if (styleFileInputRef.current) styleFileInputRef.current.value = "";
    },
  });

  const extractStyleMutation = useMutation({
    mutationFn: () => extractWritingStyleProfile(styleDocumentIds),
  });

  async function handleGenerate() {
    setIsFinishing(true);
    try {
      if (styleDocumentIds.length > 0) {
        await extractStyleMutation.mutateAsync();
      }
      onGenerate();
    } finally {
      setIsFinishing(false);
    }
  }

  const hasUploadedAnything = researchUploaded.length > 0 || styleDocumentIds.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Add your documents (optional)</h1>
        <p className="text-sm text-muted-foreground">
          Both are optional and can be skipped entirely - generation works fine without either,
          using the AI's built-in reasoning and a solid default writing style. Add them now, or
          later from the sidebar.
        </p>
      </div>

      <div className="space-y-2 rounded-lg border border-border p-4">
        <h2 className="text-sm font-semibold">Research documents</h2>
        <p className="text-xs text-muted-foreground">
          Source material for your AI to cite and draw on. Supports plain text and Word (.docx).
        </p>
        <div className="flex items-end gap-3">
          <Input ref={researchFileInputRef} type="file" multiple className="max-w-xs" />
          <Button
            type="button"
            variant="secondary"
            disabled={researchUploadMutation.isPending}
            onClick={() => researchUploadMutation.mutate()}
          >
            {researchUploadMutation.isPending ? "Uploading..." : "Upload"}
          </Button>
        </div>
        {researchUploadMutation.isError && (
          <p className="text-sm text-destructive">
            {researchUploadMutation.error instanceof ApiError
              ? researchUploadMutation.error.message
              : "Upload failed."}
          </p>
        )}
        {researchUploaded.length > 0 && (
          <ul className="space-y-1 text-sm text-muted-foreground">
            {researchUploaded.map((title, index) => (
              <li key={index}>&#10003; {title}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2 rounded-lg border border-border p-4">
        <h2 className="text-sm font-semibold">Writing style samples</h2>
        <p className="text-xs text-muted-foreground">
          Something you've written, so the AI can match your voice. Without one, a solid
          built-in style is used as a baseline.
        </p>
        <div className="flex items-end gap-3">
          <Input ref={styleFileInputRef} type="file" className="max-w-xs" />
          <Button
            type="button"
            variant="secondary"
            disabled={styleUploadMutation.isPending}
            onClick={() => styleUploadMutation.mutate()}
          >
            {styleUploadMutation.isPending ? "Uploading..." : "Upload"}
          </Button>
        </div>
        {styleUploadMutation.isError && (
          <p className="text-sm text-destructive">
            {styleUploadMutation.error instanceof ApiError ? styleUploadMutation.error.message : "Upload failed."}
          </p>
        )}
        {styleDocumentIds.length > 0 && (
          <p className="text-sm text-muted-foreground">Uploaded {styleDocumentIds.length} sample(s).</p>
        )}
        {extractStyleMutation.isError && (
          <p className="text-sm text-destructive">
            {extractStyleMutation.error instanceof ApiError
              ? extractStyleMutation.error.message
              : "Style extraction failed."}
          </p>
        )}
      </div>

      <Button type="button" onClick={handleGenerate} disabled={isFinishing} className="w-full">
        {isFinishing ? "Generating..." : hasUploadedAnything ? "Generate" : "Skip and generate"}
      </Button>
    </div>
  );
}
