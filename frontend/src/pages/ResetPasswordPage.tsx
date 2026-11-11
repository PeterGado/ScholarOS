import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";
import { confirmPasswordReset } from "@/api/auth";
import { ApiError } from "@/lib/apiClient";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ResetPasswordPage() {
  useDocumentTitle("Reset your password");
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    setIsSubmitting(true);
    try {
      await confirmPasswordReset(token, newPassword);
      navigate("/login", { state: { passwordWasReset: true } });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reset your password. Check the backend is running.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-4">
        <div className="w-full max-w-sm space-y-4 rounded-xl border border-border p-6 text-center">
          <h1 className="text-lg font-semibold">Invalid reset link</h1>
          <p className="text-sm text-muted-foreground">
            This link is missing its token. Request a new one below.
          </p>
          <Link to="/forgot-password" className="text-sm font-medium text-primary underline-offset-4 hover:underline">
            Request a new reset link
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-4">
      <a
        href="#reset-password-form"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-lg focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>
      <div className="w-full max-w-sm">
        <Link to="/login" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeftIcon className="size-4" />
          Back to sign in
        </Link>
      </div>
      <form
        id="reset-password-form"
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-border p-6"
      >
        <h1 className="text-lg font-semibold">Choose a new password</h1>
        <div className="space-y-1">
          <label htmlFor="new-password" className="text-sm font-medium">
            New password
          </label>
          <Input
            id="new-password"
            size="lg"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="confirm-password" className="text-sm font-medium">
            Confirm new password
          </label>
          <Input
            id="confirm-password"
            size="lg"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Resetting..." : "Reset password"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          This also signs you out everywhere else you're currently signed in.
        </p>
      </form>
    </div>
  );
}
