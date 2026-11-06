import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";

const FIXTURES = [
  { label: "Thinking", at: 0 },
  { label: "Drafting a response", at: 6_000 },
  { label: "Reviewing and refining the draft", at: 16_000 },
  { label: "Polishing the final version", at: 30_000 },
  { label: "Polishing the final version", at: 60_000 },
];

for (const { label, at } of FIXTURES) {
  it(`displays "${label}" after ${at}ms`, async () => {
    vi.useFakeTimers();
    const startedAt = Date.now();
    render(<ThinkingIndicator startedAt={startedAt} />);
    await vi.advanceTimersByTimeAsync(at);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(/working on your reply/i)).toBeInTheDocument();
    vi.useRealTimers();
  });
}
