import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { AuthProvider } from "@/lib/AuthContext";
import { setToken } from "@/lib/authToken";
import * as authApi from "@/api/auth";

vi.mock("@/api/auth");
// GoogleSignInButton's real behavior (script loading, Google's own button) is covered by its
// own test file - stubbed here to a plain button so LoginPage's own onCredential handling can
// be tested in isolation, the same boundary the codebase exploration already identified.
vi.mock("@/components/GoogleSignInButton", () => ({
  GoogleSignInButton: ({ onCredential }: { onCredential: (idToken: string) => void }) => (
    <button onClick={() => onCredential("fake-google-id-token")}>Sign in with Google</button>
  ),
}));

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setToken(null);
    vi.clearAllMocks();
  });

  it("submits the entered credentials to the login API", async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access_token: "token-123", token_type: "bearer" });
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Username"), "researcher");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(authApi.login).toHaveBeenCalledWith("researcher", "secret"));
  });

  it("shows an error message when login fails", async () => {
    vi.mocked(authApi.login).mockRejectedValue(new Error("Invalid username or password."));
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Username"), "researcher");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(/login failed/i)).toBeInTheDocument();
  });

  it("signs in via Google without an invite code", async () => {
    vi.mocked(authApi.loginWithGoogle).mockResolvedValue({ access_token: "token-456", token_type: "bearer" });
    const user = userEvent.setup();
    renderLoginPage();

    await user.click(screen.getByRole("button", { name: "Sign in with Google" }));

    await waitFor(() => expect(authApi.loginWithGoogle).toHaveBeenCalledWith("fake-google-id-token"));
  });

  it("shows an error message when Google sign-in fails", async () => {
    // A plain Error, not an ApiError instance - falls back to the generic message, mirroring
    // the equivalent password-login test above.
    vi.mocked(authApi.loginWithGoogle).mockRejectedValue(new Error("Invalid Google sign-in token."));
    const user = userEvent.setup();
    renderLoginPage();

    await user.click(screen.getByRole("button", { name: "Sign in with Google" }));

    expect(await screen.findByText(/google sign-in failed/i)).toBeInTheDocument();
  });
});
