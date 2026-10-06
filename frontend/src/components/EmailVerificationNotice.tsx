import { useState } from "react";
import { requestEmailVerification } from "@/api/auth";
import { useToast } from "@/lib/ToastContext";
import { Button } from "@/components/ui/button";

// Shown wherever a mutation fails with EmailNotVerifiedError (document upload, sending a chat
// message, 2026-10-06) - the message alone leaves the caller stuck with no path forward, so
// this always pairs it with a way to actually get unblocked.
export function EmailVerificationNotice() {
  const { showToast } = useToast();
  const [isSending, setIsSending] = useState(false);

  async function handleResend() {
    setIsSending(true);
    try {
      await requestEmailVerification();
      showToast("Verification email sent - check your inbox.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <p className="text-sm text-destructive">Verify your email to use this feature.</p>
      <Button type="button" size="sm" variant="outline" disabled={isSending} onClick={handleResend}>
        {isSending ? "Sending..." : "Resend verification email"}
      </Button>
    </div>
  );
}
