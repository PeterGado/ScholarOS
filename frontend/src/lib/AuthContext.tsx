import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getToken, setToken, subscribeToToken } from "./authToken";
import { apiClient } from "./apiClient";

/** "loading" covers the brief window while a stored token is being confirmed against the
 * server - neither "authenticated" nor "unauthenticated" yet. Routes that care about auth
 * state (ProtectedRoute, LandingPage) must treat "loading" as "don't decide yet", not as
 * either final state - see this file's own AuthProvider docstring for why. */
type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  token: string | null;
  authStatus: AuthStatus;
  isAuthenticated: boolean;
  setToken: (token: string | null) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [authStatus, setAuthStatus] = useState<AuthStatus>(() => (getToken() === null ? "unauthenticated" : "loading"));

  useEffect(() => subscribeToToken(setTokenState), []);

  // 2026-09-30: a stored token used to be treated as proof of a valid session by itself - it
  // never expires client-side and was never actually checked against the server (authToken.ts's
  // own comment: "the backend never expires a token on its own"). A stale/already-ended session
  // (e.g. from a prior logout in another tab, or a token from before a backend redeploy) still
  // satisfied `token !== null`, so the landing page silently redirected straight past itself to
  // /chat, which then failed its own authenticated requests and bounced to /login - "can't reach
  // the landing page, straight to login" was a real reported symptom of exactly this. GET
  // /auth/me actually confirms the session is still real; apiClient's existing response
  // interceptor already clears the token on a 401, so a confirmed-invalid token naturally flows
  // back into `token` here via subscribeToToken.
  useEffect(() => {
    if (token === null) {
      setAuthStatus("unauthenticated");
      return;
    }
    let cancelled = false;
    setAuthStatus("loading");
    apiClient
      .get("/auth/me")
      .then(() => {
        if (!cancelled) setAuthStatus("authenticated");
      })
      .catch(() => {
        // A non-401 failure (e.g. the backend being unreachable) also can't be trusted as
        // "authenticated" - fail closed rather than assuming the stored token is good.
        if (!cancelled) setAuthStatus("unauthenticated");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const value: AuthContextValue = {
    token,
    authStatus,
    isAuthenticated: authStatus === "authenticated",
    setToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
