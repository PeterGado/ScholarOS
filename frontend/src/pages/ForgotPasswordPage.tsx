import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";
import { requestPasswordReset } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// The request endpoint always returns 204 regardless of whether the email matched a real
// account (app/auth/password_reset.py's own docstring) - this page shows the same message
// either way, by design, so it can never be used to check which emails have an account here.
export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await requestPasswordReset(email);
    } finally {
      setIsSubmitting(false);
      setSubmitted(true);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-4">
      <a
        href="#forgot-password-content"
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
      <div id="forgot-password-content" className="w-full max-w-sm space-y-4 rounded-xl border border-border p-6">
        <h1 className="text-lg font-semibold">Reset your password</h1>
        {submitted ? (
          <p className="text-sm text-muted-foreground">
            If an account exists for that email, a reset link has been sent. It expires in an
            hour and can only be used once.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Enter the email on your account and we'll send you a link to reset your password.
            </p>
            <div className="space-y-1">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? "Sending..." : "Send reset link"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
