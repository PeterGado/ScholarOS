import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";

// Placeholder (2026-10-06) - no real terms of service exist yet. States that plainly rather
// than fabricating legal text, per the footer-links fix from the frontend redesign audit.
export function TermsPage() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" />
        Back to home
      </Link>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Terms of service</h1>
      <p className="mt-4 text-sm text-muted-foreground">
        Full terms of service are in progress. Contact support with any questions in the
        meantime.
      </p>
    </div>
  );
}
