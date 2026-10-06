import { useEffect, useState } from "react";

// Three stage thresholds, not real backend progress - the Work Item's own status has no
// sub-stage (queued/running/succeeded/failed only), so this is honest elapsed-time framing,
// not a claim of exact sync with the draft -> critique -> revise pipeline (2026-10-06) that
// made replies take noticeably longer. Thresholds are generous: multi-pass generation is three
// sequential AI calls, each itself taking a few seconds, so the early "Thinking" label alone
// would otherwise sit on screen for most of a reply's duration.
const STAGES = [
  { afterMs: 0, label: "Thinking" },
  { afterMs: 6_000, label: "Drafting a response" },
  { afterMs: 16_000, label: "Reviewing and refining the draft" },
  { afterMs: 30_000, label: "Polishing the final version" },
] as const;

function stageForElapsed(elapsedMs: number): string {
  let label: string = STAGES[0].label;
  for (const stage of STAGES) {
    if (elapsedMs >= stage.afterMs) label = stage.label;
  }
  return label;
}

// Replaces a static "Thinking..." line with a typing-style pulse and a label that advances
// through a few honest, generic stages as the wait grows - multi-pass generation (2026-10-06)
// made a reply take roughly 3x as long, and a wait with no visible progress reads as stuck.
export function ThinkingIndicator({ startedAt }: { startedAt: number }) {
  const [elapsedMs, setElapsedMs] = useState(() => Date.now() - startedAt);

  useEffect(() => {
    const interval = window.setInterval(() => setElapsedMs(Date.now() - startedAt), 1000);
    return () => window.clearInterval(interval);
  }, [startedAt]);

  const label = stageForElapsed(elapsedMs);

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1" aria-hidden="true">
        <span className="size-1.5 rounded-full bg-muted-foreground/60 motion-safe:animate-pulse [animation-delay:0ms]" />
        <span className="size-1.5 rounded-full bg-muted-foreground/60 motion-safe:animate-pulse [animation-delay:150ms]" />
        <span className="size-1.5 rounded-full bg-muted-foreground/60 motion-safe:animate-pulse [animation-delay:300ms]" />
      </div>
      <p key={label} className="text-sm text-muted-foreground motion-safe:animate-in motion-safe:fade-in motion-safe:duration-300">
        {label}
        <span className="sr-only"> - working on your reply</span>
      </p>
    </div>
  );
}
