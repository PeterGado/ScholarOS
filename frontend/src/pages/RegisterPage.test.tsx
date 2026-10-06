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
// RegisterPage's own onCredential/onUnavailable handling can be tested in isolation.
vi.mock("@/components/GoogleSignInButton", () => ({
  GoogleSignInButton: ({
    onCredential,
    onUnavailable,
  }: {
    onCredential: (idToken: string) => void;
    onUnavailable?: () => void;
  }) => (
    <div>
      <button onClick={() => onCredential("fake-google-id-token")}>Sign in with Google</button>
      <button onClick={() => onUnavailable?.()}>Simulate Google unavailable</button>
    </div>
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

  it("has a way back to the landing page", () => {
    renderRegisterPage();

    expect(screen.getByRole("link", { name: /back to home/i })).toHaveAttribute("href", "/");
  });

  it("signs up via Google with no invite code - registration is fully open", async () => {
    vi.mocked(authApi.loginWithGoogle).mockResolvedValue({ access_token: "token-456", token_type: "bearer" });
    const user = userEvent.setup();
    renderRegisterPage();

    await user.click(screen.getByRole("button", { name: "Sign in with Google" }));

    await waitFor(() => expect(authApi.loginWithGoogle).toHaveBeenCalledWith("fake-google-id-token"));
  });

  it("shows an error message when Google sign-in fails", async () => {
    vi.mocked(authApi.loginWithGoogle).mockRejectedValue(new Error("Something went wrong."));
    const user = userEvent.setup();
    renderRegisterPage();

    await user.click(screen.getByRole("button", { name: "Sign in with Google" }));

    expect(await screen.findByText(/google sign-in failed/i)).toBeInTheDocument();
  });

  it("shows a fallback message and the password form still works when Google is unavailable", async () => {
    vi.mocked(authApi.register).mockResolvedValue({ access_token: "token-123", token_type: "bearer" });
    const user = userEvent.setup();
    renderRegisterPage();

    await user.click(screen.getByRole("button", { name: "Simulate Google unavailable" }));
    expect(await screen.findByText(/google sign-in isn't loading/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Email"), "new-researcher@example.com");
    await user.type(screen.getByLabelText("Password"), "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(authApi.register).toHaveBeenCalledWith("new-researcher@example.com", "a-real-password"),
    );
  });

  it("submits the entered email and password to the register API", async () => {
    vi.mocked(authApi.register).mockResolvedValue({ access_token: "token-123", token_type: "bearer" });
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Email"), "new-researcher@example.com");
    await user.type(screen.getByLabelText("Password"), "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(authApi.register).toHaveBeenCalledWith("new-researcher@example.com", "a-real-password"),
    );
  });

  it("shows an error message when registration fails", async () => {
    vi.mocked(authApi.register).mockRejectedValue(new Error("That email is already associated with another account."));
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Email"), "taken@example.com");
    await user.type(screen.getByLabelText("Password"), "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    // The mocked rejection is a plain Error, not an ApiError instance, so the component falls
    // back to its generic message - mirrors LoginPage.test.tsx's own equivalent assertion.
    expect(await screen.findByText(/registration failed/i)).toBeInTheDocument();
  });

  it("has a link to sign in for an existing account", () => {
    renderRegisterPage();

    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/login");
  });
});
