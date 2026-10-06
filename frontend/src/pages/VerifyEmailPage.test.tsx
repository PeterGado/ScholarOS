import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { VerifyEmailPage } from "./VerifyEmailPage";
import * as authApi from "@/api/auth";

vi.mock("@/api/auth");

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <VerifyEmailPage />
    </MemoryRouter>,
  );
}

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("confirms the token from the link and reports success", async () => {
    vi.mocked(authApi.confirmEmailVerification).mockResolvedValue(undefined);

    renderAt("/verify-email?token=abc123");

    await waitFor(() => expect(authApi.confirmEmailVerification).toHaveBeenCalledWith("abc123"));
    expect(await screen.findByText(/your email is verified/i)).toBeInTheDocument();
  });

  it("shows a link-needed message when no token is present", () => {
    renderAt("/verify-email");

    expect(screen.getByText(/needs a verification link/i)).toBeInTheDocument();
    expect(authApi.confirmEmailVerification).not.toHaveBeenCalled();
  });

  it("shows the failure message when the token is rejected", async () => {
    vi.mocked(authApi.confirmEmailVerification).mockRejectedValue(new Error("Could not verify your email."));

    renderAt("/verify-email?token=stale");

    expect(await screen.findByText(/could not verify your email/i)).toBeInTheDocument();
  });
});
