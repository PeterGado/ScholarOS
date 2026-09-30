import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LandingPage } from "./LandingPage";
import { AuthProvider } from "@/lib/AuthContext";
import { ThemeProvider } from "@/lib/ThemeContext";
import { setToken } from "@/lib/authToken";
import { apiClient } from "@/lib/apiClient";

vi.mock("@/lib/apiClient", () => ({
  apiClient: { get: vi.fn() },
}));

function renderLandingPage() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <ThemeProvider>
        <AuthProvider>
          <LandingPage />
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

describe("LandingPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setToken(null);
    vi.clearAllMocks();
  });

  it("shows sign in / get started for a logged-out visitor and never navigates away", () => {
    renderLandingPage();

    expect(screen.getAllByRole("link", { name: "Sign in" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Get started" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: /workspace/i })).not.toBeInTheDocument();
  });

  it("still renders the landing page for an authenticated visitor, with a way into the workspace instead of sign in / get started", async () => {
    setToken("a-valid-token");
    vi.mocked(apiClient.get).mockResolvedValue({ status: 204, data: undefined });

    renderLandingPage();

    // Hero content is still there - 2026-09-30: this used to auto-redirect away entirely.
    expect(screen.getByText(/research operating system/i)).toBeInTheDocument();

    await waitFor(() => expect(screen.getAllByRole("link", { name: /go to your workspace/i }).length).toBeGreaterThan(0));
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Get started" })).not.toBeInTheDocument();
  });
});
