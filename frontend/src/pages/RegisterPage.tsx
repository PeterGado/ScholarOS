import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { register, loginWithGoogle } from "@/api/auth";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { ApiError } from "@/lib/apiClient";
import { useAuth } from "@/lib/AuthContext";

// The invite_code field is always rendered, even though it's only enforced when the backend
// has REGISTRATION_INVITE_CODE configured (ADR-011) - the frontend never needs to know whether
// one is required; an unconfigured backend simply ignores whatever's typed here (or nothing).
export function RegisterPage() {
  const { isAuthenticated, setToken } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { access_token } = await register(username, password, inviteCode);
      setToken(access_token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Check the backend is running.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleGoogleCredential(idToken: string) {
    setError(null);
    try {
      // Reuses this page's own invite-code field - a brand-new Google account is held to the
      // same friends-only gate as a brand-new password account; a returning one ignores it.
      const { access_token } = await loginWithGoogle(idToken, inviteCode);
      setToken(access_token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Google sign-in failed. Check the backend is running.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 rounded-lg border border-border p-6">
        <h1 className="text-lg font-semibold">Create your ScholarOS account</h1>
        <div className="space-y-1">
          <label htmlFor="username" className="text-sm font-medium">
            Username
          </label>
          <input
            id="username"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="invite-code" className="text-sm font-medium">
            Invite code (if you have one)
          </label>
          <input
            id="invite-code"
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value)}
            autoComplete="off"
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {isSubmitting ? "Creating account..." : "Create account"}
        </button>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="h-px flex-1 bg-border" />
          or
          <div className="h-px flex-1 bg-border" />
        </div>
        <GoogleSignInButton onCredential={handleGoogleCredential} />
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
