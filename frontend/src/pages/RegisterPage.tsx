import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";
import { register, loginWithGoogle } from "@/api/auth";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { ApiError } from "@/lib/apiClient";
import { useAuth } from "@/lib/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Google is the primary path (2026-10-06) - no password to manage or forget, and a real
// verified email on file automatically. Email/password stays available underneath it as a
// real alternative, not just a fallback for when Google fails to load - some researchers won't
// use Google, and institutions may require a different identity provider. Registration collects
// an email, not a username (external security review) - a username is still synthesized
// server-side, but it's never user-chosen or shown as the account's real identity. Registration
// is fully open either way - no invite code anywhere in this flow; REGISTRATION_INVITE_CODE is
// unset in production.
export function RegisterPage() {
  const { isAuthenticated, setToken } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [googleUnavailable, setGoogleUnavailable] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { access_token } = await register(email, password);
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
      const { access_token } = await loginWithGoogle(idToken);
      setToken(access_token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Google sign-in failed. Check the backend is running.");
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-4">
      <a
        href="#register-form"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-lg focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>
      <div className="w-full max-w-sm">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          Back to home
        </Link>
      </div>
      <div className="w-full max-w-sm space-y-4 rounded-xl border border-border p-6">
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">Create your ScholarOS account</h1>
          <p className="text-sm text-muted-foreground">
            Your research workspace for reading, writing, and thinking with AI.
          </p>
        </div>

        <div className="flex justify-center">
          <GoogleSignInButton onCredential={handleGoogleCredential} onUnavailable={() => setGoogleUnavailable(true)} />
        </div>
        {googleUnavailable && (
          <p className="text-center text-xs text-muted-foreground">
            Google sign-in isn't loading - use the form below instead.
          </p>
        )}

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="h-px flex-1 bg-border" />
          or
          <div className="h-px flex-1 bg-border" />
        </div>

        <form id="register-form" onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <Input
              id="email"
              type="email"
              size="lg"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <Input
              id="password"
              size="lg"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? "Creating account..." : "Create account"}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
