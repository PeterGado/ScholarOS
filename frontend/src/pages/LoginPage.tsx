import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";
import { login, loginWithGoogle } from "@/api/auth";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { ApiError } from "@/lib/apiClient";
import { useAuth } from "@/lib/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function LoginPage() {
  const { isAuthenticated, setToken } = useAuth();
  const location = useLocation();
  const passwordWasReset = Boolean((location.state as { passwordWasReset?: boolean } | null)?.passwordWasReset);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
      const { access_token } = await login(username, password);
      setToken(access_token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Check the backend is running.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleGoogleCredential(idToken: string) {
    setError(null);
    try {
      // No invite code here - a returning Google user is never asked for one, same as a
      // returning password user never re-enters one on /auth/login.
      const { access_token } = await loginWithGoogle(idToken);
      setToken(access_token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Google sign-in failed. Check the backend is running.");
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-4">
      <a
        href="#login-form"
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
      <form
        id="login-form"
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-border p-6"
      >
        <h1 className="text-lg font-semibold">Sign in to ScholarOS</h1>
        {passwordWasReset && (
          <p className="text-sm text-muted-foreground">
            Your password was reset. Sign in with your new password below.
          </p>
        )}
        <div className="space-y-1">
          <label htmlFor="username" className="text-sm font-medium">
            Username
          </label>
          <Input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <Link to="/forgot-password" className="text-xs text-muted-foreground hover:text-foreground">
              Forgot password?
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Signing in..." : "Sign in"}
        </Button>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="h-px flex-1 bg-border" />
          or
          <div className="h-px flex-1 bg-border" />
        </div>
        <GoogleSignInButton onCredential={handleGoogleCredential} />
        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link to="/register" className="font-medium text-primary underline-offset-4 hover:underline">
            Register
          </Link>
        </p>
      </form>
    </div>
  );
}

