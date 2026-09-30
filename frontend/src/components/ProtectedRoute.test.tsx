import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { AuthProvider } from "@/lib/AuthContext";
import { setToken } from "@/lib/authToken";
import { apiClient } from "@/lib/apiClient";

vi.mock("@/lib/apiClient", () => ({
  apiClient: { get: vi.fn() },
}));

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={["/chat"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>Login page</p>} />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <p>Protected content</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setToken(null);
    vi.clearAllMocks();
  });

  it("redirects to /login immediately when there is no stored token at all", () => {
    renderProtected();

    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("shows a loading state instead of redirecting while a stored token is still being verified", () => {
    setToken("a-token");
    vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {})); // never resolves during this test

    renderProtected();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.queryByText("Login page")).not.toBeInTheDocument();
  });

  it("renders the protected content once a stored token is confirmed valid", async () => {
    setToken("a-valid-token");
    vi.mocked(apiClient.get).mockResolvedValue({ status: 204, data: undefined });

    renderProtected();

    await waitFor(() => expect(screen.getByText("Protected content")).toBeInTheDocument());
  });

  it("redirects to /login once a stored token is confirmed invalid, not before", async () => {
    setToken("a-stale-token");
    vi.mocked(apiClient.get).mockRejectedValue(new Error("simulated 401"));

    renderProtected();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Login page")).toBeInTheDocument());
  });
});
