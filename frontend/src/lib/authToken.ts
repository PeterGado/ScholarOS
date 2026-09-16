// Single-user, no-automatic-expiry session token (ADR-010). Held in memory during the app's
// lifetime and mirrored to localStorage so a reload doesn't force a fresh login - there is
// nothing to silently invalidate on reload, since the backend never expires a token on its own
// (see docs/Frontend_Implementation_Plan.md, "Auth/session storage").
const STORAGE_KEY = "scholaros.token";

let currentToken: string | null = null;
const listeners = new Set<(token: string | null) => void>();

export function getToken(): string | null {
  if (currentToken === null) {
    currentToken = window.localStorage.getItem(STORAGE_KEY);
  }
  return currentToken;
}

export function setToken(token: string | null): void {
  currentToken = token;
  if (token === null) {
    window.localStorage.removeItem(STORAGE_KEY);
  } else {
    window.localStorage.setItem(STORAGE_KEY, token);
  }
  for (const listener of listeners) listener(token);
}

export function subscribeToToken(listener: (token: string | null) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
