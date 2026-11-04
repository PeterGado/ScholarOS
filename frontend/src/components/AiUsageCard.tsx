import { useQuery } from "@tanstack/react-query";
import { AI_USAGE_QUERY_KEY, getAiUsage } from "@/api/usage";
import { ApiError } from "@/lib/apiClient";

// Rounded to whole hours, from the backend's own window (app.ai.usage_guard.USAGE_WINDOW) - the
// widget never hardcodes "24h" itself, so it cannot drift from the window actually enforced.
function windowLabel(windowHours: number): string {
  return `last ${Math.round(windowHours)}h`;
}

function formatTokens(tokens: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(tokens);
}

/**
 * The user's AI budget for the current rolling window (GET /ai/usage). Sits in the sidebar so
 * it is visible from every page, not only Settings - the backend enforces this cap and rejects
 * work with a 429 once it is reached, so a user needs to be able to see it coming.
 *
 * Unlimited (no cap configured server-side) is rendered as "Unlimited", never as "0 left": the
 * two mean opposite things and remaining_tokens is deliberately null in that case.
 */
export function AiUsageCard() {
  const usageQuery = useQuery({
    queryKey: AI_USAGE_QUERY_KEY,
    queryFn: getAiUsage,
    // This is a budget the user watches while working, not real-time telemetry: a minute of
    // staleness costs nothing, while polling harder would spend a request per tab per second.
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  return (
    <section aria-labelledby="ai-usage-heading" className="border-t border-sidebar-border px-3 py-2">
      <h2 id="ai-usage-heading" className="text-xs font-medium text-sidebar-foreground/60">
        AI usage
      </h2>

      {usageQuery.isPending && (
        <>
          <div className="mt-1.5 h-1.5 animate-pulse rounded-full bg-sidebar-accent" aria-hidden="true" />
          <p className="sr-only">Loading AI usage.</p>
        </>
      )}

      {usageQuery.isError && (
        <div className="mt-1">
          <p role="alert" className="text-xs text-destructive">
            {usageQuery.error instanceof ApiError ? usageQuery.error.message : "Could not load AI usage."}
          </p>
          <button
            type="button"
            className="mt-1 text-xs underline text-sidebar-foreground/70 hover:text-sidebar-foreground"
            onClick={() => usageQuery.refetch()}
          >
            Try again
          </button>
        </div>
      )}

      {usageQuery.data && usageQuery.data.daily_token_cap === null && (
        <p className="mt-1 text-xs text-sidebar-foreground/60">
          {formatTokens(usageQuery.data.used_tokens)} used in the {windowLabel(usageQuery.data.window_hours)} · Unlimited
        </p>
      )}

      {usageQuery.data && usageQuery.data.daily_token_cap !== null && (
        <CappedUsage
          used={usageQuery.data.used_tokens}
          cap={usageQuery.data.daily_token_cap}
          remaining={usageQuery.data.remaining_tokens ?? 0}
          windowHours={usageQuery.data.window_hours}
        />
      )}
    </section>
  );
}

function CappedUsage({
  used,
  cap,
  remaining,
  windowHours,
}: {
  used: number;
  cap: number;
  remaining: number;
  windowHours: number;
}) {
  // Clamped for the bar only: usage can legitimately overshoot the cap between the pre-call
  // check and the recorded actual (or after a retry), and a >100%-wide bar would just look broken.
  const percentUsed = cap > 0 ? Math.min(100, Math.round((used / cap) * 100)) : 0;

  return (
    <>
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="text-xs tabular-nums text-sidebar-foreground/60">{formatTokens(remaining)} left</span>
        <span className="text-xs tabular-nums text-sidebar-foreground/60">{percentUsed}%</span>
      </div>
      <div
        role="progressbar"
        aria-label={`AI tokens used in the ${windowLabel(windowHours)}`}
        aria-valuemin={0}
        aria-valuemax={cap}
        aria-valuenow={used}
        aria-valuetext={`${used} of ${cap} tokens used, ${remaining} left`}
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-sidebar-accent"
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300"
          style={{ width: `${percentUsed}%` }}
        />
      </div>
    </>
  );
}
