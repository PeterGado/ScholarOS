import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { confirmEmailVerification } from "@/api/auth";
import { ApiError } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";

type Status = "verifying" | "verified" | "failed" | "missing";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>(token ? "verifying" : "missing");
  const [error, setError] = useState<string | null>(null);
  // StrictMode runs effects twice in dev; the token is single-use, so only confirm once.
  const attemptedRef = useRef(false);

  useEffect(() => {
    if (!token || attemptedRef.current) return;
    attemptedRef.current = true;
    confirmEmailVerification(token)
      .then(() => setStatus("verified"))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Could not verify your email.");
        setStatus("failed");
      });
  }, [token]);

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-4">
      <div className="w-full max-w-sm space-y-4 rounded-xl border border-border p-6">
        <h1 className="text-lg font-semibold">Verify your email</h1>
        {status === "verifying" && <p className="text-sm text-muted-foreground">Verifying...</p>}
        {status === "verified" && (
          <>
            <p className="text-sm text-muted-foreground">Your email is verified. You can now upload documents and use AI.</p>
            <Button asChild className="w-full">
              <Link to="/chat">Continue to ScholarOS</Link>
            </Button>
          </>
        )}
        {status === "failed" && (
          <>
            <p className="text-sm text-destructive">{error}</p>
            <p className="text-sm text-muted-foreground">
              Sign in and use "Resend verification email" from the app to get a fresh link.
            </p>
            <Link to="/login" className="text-sm font-medium text-primary underline-offset-4 hover:underline">
              Go to sign in
            </Link>
          </>
        )}
        {status === "missing" && (
          <p className="text-sm text-muted-foreground">This page needs a verification link from your email.</p>
        )}
      </div>
    </div>
  );
}
