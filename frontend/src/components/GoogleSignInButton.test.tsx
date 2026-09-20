import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { GoogleSignInButton } from "./GoogleSignInButton";

describe("GoogleSignInButton", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com");
    document.head.innerHTML = "";
    delete (window as { google?: unknown }).google;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders nothing when no client ID is configured", () => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    const { container } = render(<GoogleSignInButton onCredential={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("initializes and renders the real Google button once the script loads", async () => {
    const initialize = vi.fn();
    const renderButton = vi.fn();
    // Simulates the real accounts.google.com/gsi/client script: it defines window.google as
    // soon as it "loads" - the component waits on the script's load event, so setting this up
    // before the script tag's load event fires (triggered manually below) matches real timing.
    const installGoogleGlobal = () => {
      window.google = { accounts: { id: { initialize, renderButton } } };
    };

    render(<GoogleSignInButton onCredential={vi.fn()} />);

    const script = document.head.querySelector<HTMLScriptElement>('script[src="https://accounts.google.com/gsi/client"]');
    expect(script).not.toBeNull();
    installGoogleGlobal();
    script?.dispatchEvent(new Event("load"));

    await waitFor(() => expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({ client_id: "test-client-id.apps.googleusercontent.com" }),
    ));
    expect(renderButton).toHaveBeenCalled();
  });

  it("calls onCredential with the raw ID token from Google's callback", async () => {
    const onCredential = vi.fn();
    let capturedCallback: ((response: { credential: string }) => void) | undefined;
    const initialize = vi.fn((config: { callback: (response: { credential: string }) => void }) => {
      capturedCallback = config.callback;
    });
    window.google = { accounts: { id: { initialize, renderButton: vi.fn() } } };

    render(<GoogleSignInButton onCredential={onCredential} />);

    await waitFor(() => expect(initialize).toHaveBeenCalled());
    capturedCallback?.({ credential: "raw-google-id-token" });

    expect(onCredential).toHaveBeenCalledWith("raw-google-id-token");
  });

  it("does not inject a second script tag when window.google is already present", () => {
    window.google = { accounts: { id: { initialize: vi.fn(), renderButton: vi.fn() } } };

    render(<GoogleSignInButton onCredential={vi.fn()} />);

    const scripts = document.head.querySelectorAll('script[src="https://accounts.google.com/gsi/client"]');
    expect(scripts.length).toBe(0);
  });
});
