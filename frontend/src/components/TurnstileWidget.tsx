import { useEffect, useRef } from "react";

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

// Same dynamic-script-loading shape as GoogleSignInButton (the first precedent in this
// codebase) - guards against double-injection if this component remounts (e.g. navigating away
// from and back to RegisterPage).
function loadTurnstileScript(): Promise<void> {
  if (window.turnstile) {
    return Promise.resolve();
  }
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("Failed to load Turnstile script.")));
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("Failed to load Turnstile script.")));
    document.head.appendChild(script);
  });
}

interface TurnstileWidgetProps {
  /** Called with the verification token once the challenge is solved, and again with null if
   * it expires or errors - the caller should treat a null token as "not yet verified" rather
   * than submit a stale one. */
  onToken: (token: string | null) => void;
}

// Renders nothing, and never loads Cloudflare's script, when VITE_TURNSTILE_SITE_KEY isn't
// configured (2026-10-11, bot protection on registration) - mirrors GoogleSignInButton's own
// "missing config disables the feature" shape, so registration keeps working exactly as before
// until the project owner actually sets up a Cloudflare account and site key.
export function TurnstileWidget({ onToken }: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    const siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY;
    if (!siteKey) {
      return;
    }

    let cancelled = false;

    loadTurnstileScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return;
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          callback: (token) => onToken(token),
          "expired-callback": () => onToken(null),
          "error-callback": () => onToken(null),
        });
      })
      .catch(() => {
        // Script failed to load (network block, ad-blocker) - onToken is simply never called,
        // leaving the caller's token state at its initial null, same as "not yet verified".
      });

    return () => {
      cancelled = true;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
      }
    };
    // onToken deliberately excluded - same reasoning as GoogleSignInButton's onCredential.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!import.meta.env.VITE_TURNSTILE_SITE_KEY) {
    return null;
  }

  return <div ref={containerRef} />;
}
