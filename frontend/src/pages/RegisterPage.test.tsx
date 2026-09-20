import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { RegisterPage } from "./RegisterPage";
import { AuthProvider } from "@/lib/AuthContext";
import { setToken } from "@/lib/authToken";
import * as authApi from "@/api/auth";

vi.mock("@/api/auth");
// GoogleSignInButton's real behavior is covered by its own test file - stubbed here so
// RegisterPage's own onCredential handling (passing along the typed invite code) can be tested
// in isolation.
vi.mock("@/components/GoogleSignInButton", () => ({
  GoogleSignInButton: ({ onCredential }: { onCredential: (idToken: string) => void }) => (
    <button onClick={() => onCredential("fake-google-id-token")}>Sign in with Google</button>
  ),
}));

function renderRegisterPage() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("RegisterPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setToken(null);
    vi.clearAllMocks();
  });

  it("submits the entered username, password, and invite code to the register API", async () => {
    vi.mocked(authApi.register).mockResolvedValue({ access_token: "token-123", token_type: "bearer" });
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Username"), "new-researcher");
    await user.type(screen.getByLabelText("Password"), "a-real-password");
    await user.type(screen.getByLabelText(/invite code/i), "friends-2026");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(authApi.register).toHaveBeenCalledWith("new-researcher", "a-real-password", "friends-2026"),
    );
  });

  it("submits successfully with no invite code entered", async () => {
    vi.mocked(authApi.register).mockResolvedValue({ access_token: "token-123", token_type: "bearer" });
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Username"), "new-researcher");
    await user.type(screen.getByLabelText("Password"), "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(authApi.register).toHaveBeenCalledWith("new-researcher", "a-real-password", ""));
  });

  it("shows an error message when registration fails", async () => {
    vi.mocked(authApi.register).mockRejectedValue(new Error("That username is already taken."));
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Username"), "taken-name");
    await user.type(screen.getByLabelText("Password"), "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    // The mocked rejection is a plain Error, not an ApiError instance, so the component falls
    // back to its generic message - mirrors LoginPage.test.tsx's own equivalent assertion.
    expect(await screen.findByText(/registration failed/i)).toBeInTheDocument();
  });

  it("signs in via Google, passing along the typed invite code", async () => {
    vi.mocked(authApi.loginWithGoogle).mockResolvedValue({ access_token: "token-456", token_type: "bearer" });
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText(/invite code/i), "friends-2026");
    await user.click(screen.getByRole("button", { name: "Sign in with Google" }));

    await waitFor(() =>
      expect(authApi.loginWithGoogle).toHaveBeenCalledWith("fake-google-id-token", "friends-2026"),
    );
  });

  it("shows an error message when Google sign-in fails", async () => {
    // A plain Error, not an ApiError instance - falls back to the generic message, mirroring
    // the equivalent password-registration test above.
    vi.mocked(authApi.loginWithGoogle).mockRejectedValue(new Error("Invalid invite code."));
    const user = userEvent.setup();
    renderRegisterPage();

    await user.click(screen.getByRole("button", { name: "Sign in with Google" }));

    expect(await screen.findByText(/google sign-in failed/i)).toBeInTheDocument();
  });
});
