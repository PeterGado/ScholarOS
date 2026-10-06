import { useEffect, useRef } from "react";

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";
// Generous but bounded - a slow network shouldn't false-positive into "unavailable" too
// eagerly, but a genuinely blocked script (corporate/school network, ad-blocker) shouldn't
// leave the caller waiting indefinitely either, especially now that RegisterPage has no
// other way in at all (2026-10-06).
const LOAD_TIMEOUT_MS = 6000;

// The first dynamic third-party script loader in this codebase (confirmed via exploration - no
// prior pattern to match). Guarded by checking window.google first so re-mounting this
// component (e.g. navigating between LoginPage/RegisterPage) never injects the script twice.
function loadGoogleIdentityScript(): Promise<void> {
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("Failed to load Google Identity script.")));
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("Failed to load Google Identity script.")));
    document.head.appendChild(script);
  });
}

interface GoogleSignInButtonProps {
  /** Called with the raw Google ID token once the user completes the Google flow - this
   * component is presentation-only; the caller owns calling the backend and setToken. */
  onCredential: (idToken: string) => void;
  /** Called when Google Sign-In doesn't become usable within a few seconds - no client ID
   * configured, the identity script failed to load (a corporate/school network or an
   * ad-blocker can do this), or it simply never finished in time. Lets the caller show a
   * fallback instead of silently rendering nothing. */
  onUnavailable?: () => void;
}

export function GoogleSignInButton({ onCredential, onUnavailable }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
      onUnavailable?.();
      return;
    }

    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (!settled) {
        settled = true;
        onUnavailable?.();
      }
    }, LOAD_TIMEOUT_MS);

    loadGoogleIdentityScript()
      .then(() => {
        if (settled || !containerRef.current || !window.google) return;
        settled = true;
        window.clearTimeout(timeoutId);
        window.google.accounts.id.initialize({
          client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
          callback: (response) => onCredential(response.credential),
        });
        // width is a pixel value per Google's own API (a string number, not a percentage) - 300
        // comfortably fits this app's existing max-w-sm (384px) auth form.
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: "outline",
          size: "large",
          width: "300",
        });
      })
      .catch(() => {
        if (!settled) {
          settled = true;
          window.clearTimeout(timeoutId);
          onUnavailable?.();
        }
      });

    return () => {
      settled = true;
      window.clearTimeout(timeoutId);
    };
    // onUnavailable deliberately excluded - this effect should only re-run when the credential
    // handler changes, not on every render a parent passes a fresh inline callback.
  }, [onCredential]);

  if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
    return null;
  }

  return <div ref={containerRef} />;
}
