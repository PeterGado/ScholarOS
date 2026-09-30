import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthContext";
import { setToken } from "./authToken";
import { apiClient } from "./apiClient";

vi.mock("./apiClient", () => ({
  apiClient: { get: vi.fn() },
}));

function Probe() {
  const { authStatus, isAuthenticated } = useAuth();
  return <p>{`status:${authStatus} authenticated:${isAuthenticated}`}</p>;
}

function renderWithProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setToken(null);
    vi.clearAllMocks();
  });

  it("is immediately unauthenticated with no stored token, and never calls /auth/me", async () => {
    renderWithProvider();

    expect(screen.getByText("status:unauthenticated authenticated:false")).toBeInTheDocument();
    // Give any stray async work a tick to run, then confirm it still never called the API.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("starts loading then becomes authenticated once a stored token is confirmed valid", async () => {
    setToken("a-valid-token");
    vi.mocked(apiClient.get).mockResolvedValue({ status: 204, data: undefined });

    renderWithProvider();

    expect(screen.getByText("status:loading authenticated:false")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/auth/me");

    await waitFor(() =>
      expect(screen.getByText("status:authenticated authenticated:true")).toBeInTheDocument(),
    );
  });

  it("becomes unauthenticated when a stored token turns out to be invalid", async () => {
    setToken("a-stale-token");
    vi.mocked(apiClient.get).mockRejectedValue(new Error("simulated 401"));

    renderWithProvider();

    expect(screen.getByText("status:loading authenticated:false")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText("status:unauthenticated authenticated:false")).toBeInTheDocument(),
    );
  });
});
