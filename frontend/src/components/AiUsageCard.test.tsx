import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AiUsageCard } from "./AiUsageCard";
import { getAiUsage } from "@/api/usage";
import { ApiError } from "@/lib/apiClient";

// The query key is imported from the same module as the fetch function, so the mock has to
// provide both - a module-level mock replaces the whole module, not just getAiUsage.
vi.mock("@/api/usage", () => ({ getAiUsage: vi.fn(), AI_USAGE_QUERY_KEY: ["ai-usage"] }));

const mockedGetAiUsage = vi.mocked(getAiUsage);

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AiUsageCard />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("AiUsageCard", () => {
  it("shows used, remaining and a progress bar for a capped account", async () => {
    mockedGetAiUsage.mockResolvedValue({
      used_tokens: 25_000,
      daily_token_cap: 100_000,
      remaining_tokens: 75_000,
      window_hours: 24,
    });

    renderCard();

    const bar = await screen.findByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "25000");
    expect(bar).toHaveAttribute("aria-valuemax", "100000");
    expect(bar).toHaveAttribute("aria-valuetext", "25000 of 100000 tokens used, 75000 left");
    expect(screen.getByText(/25%/)).toBeInTheDocument();
    expect(screen.getByText(/left/)).toBeInTheDocument();
  });

  it("renders an unlimited account as unlimited rather than as an empty budget", async () => {
    // remaining_tokens is null when no cap is configured - rendering that as "0 left" would
    // tell the user the exact opposite of the truth.
    mockedGetAiUsage.mockResolvedValue({
      used_tokens: 1_200,
      daily_token_cap: null,
      remaining_tokens: null,
      window_hours: 24,
    });

    renderCard();

    expect(await screen.findByText(/Unlimited/)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("never renders a bar wider than 100% when usage has overshot the cap", async () => {
    mockedGetAiUsage.mockResolvedValue({
      used_tokens: 120_000,
      daily_token_cap: 100_000,
      remaining_tokens: 0,
      window_hours: 24,
    });

    renderCard();

    const bar = await screen.findByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "120000");
    expect(bar.firstElementChild).toHaveStyle({ width: "100%" });
  });

  it("surfaces the backend's error message and offers a retry", async () => {
    mockedGetAiUsage.mockRejectedValueOnce(new ApiError(503, { error_type: "Unavailable", detail: "Try again later." }));

    renderCard();

    expect(await screen.findByRole("alert")).toHaveTextContent("Try again later.");

    mockedGetAiUsage.mockResolvedValueOnce({
      used_tokens: 10,
      daily_token_cap: 1_000,
      remaining_tokens: 990,
      window_hours: 24,
    });
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("progressbar")).toBeInTheDocument();
  });
});
