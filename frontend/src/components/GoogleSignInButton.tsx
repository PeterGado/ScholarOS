import { useEffect, useRef } from "react";

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

// The first dynamic third-party script loader in this codebase (confirmed via exploration - no
// prior pattern to match). Guarded by checking window.google first so re-mounting this
// component (e.g. navigating between LoginPage/RegisterPage) never injects the script twice.
function loadGoogleIdentityScript(): Promise<void> {
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
  if (existing) {
    return new Promise((resolve) => existing.addEventListener("load", () => resolve()));
  }
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => resolve());
    document.head.appendChild(script);
  });
}

interface GoogleSignInButtonProps {
  /** Called with the raw Google ID token once the user completes the Google flow - this
   * component is presentation-only; the caller owns calling the backend and setToken. */
  onCredential: (idToken: string) => void;
}

export function GoogleSignInButton({ onCredential }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    loadGoogleIdentityScript().then(() => {
      if (cancelled || !containerRef.current || !window.google) return;
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
    });

    return () => {
      cancelled = true;
    };
  }, [onCredential]);

  if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
    return null;
  }

  return <div ref={containerRef} />;
}
