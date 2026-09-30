import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { authStatus } = useAuth();
  // Wait for a stored token to actually be confirmed before deciding - redirecting to /login
  // during this brief window would bounce a genuinely logged-in user on every page load/reload.
  if (authStatus === "loading") {
    return <p className="p-6 text-sm text-muted-foreground">Loading...</p>;
  }
  if (authStatus !== "authenticated") {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
