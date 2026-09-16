import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { AuthProvider } from "@/lib/AuthContext";
import { setToken } from "@/lib/authToken";
import * as authApi from "@/api/auth";

vi.mock("@/api/auth");

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
});
