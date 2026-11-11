import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Shown above the recovery actions, to say which part of the app failed. */
  label?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/** Stops one failed render from blanking the whole app (2026-11-06).
 *
 * Before this existed there was no boundary anywhere in the tree, so any throw during render -
 * an unexpected API payload, a null slipping past a type assertion, a bad `[0]` on an empty
 * array - unmounted the entire application and left a white page with no message and no way
 * back except editing the URL by hand.
 *
 * Two instances are used, on purpose:
 *   - around the routes, keyed by pathname, so navigating to another page clears the error;
 *   - around everything in main.tsx, so a crash in a provider or the router itself still
 *     produces a recoverable screen instead of nothing.
 *
 * Errors are logged to the console because this app has no error-reporting service wired up -
 * the browser console is currently the only place a production stack trace can be recovered
 * from. That is a real limitation, not a design choice to celebrate.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info.componentStack);
  }

  private handleReload = () => {
    window.location.reload();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex min-h-dvh items-center justify-center bg-background px-6">
        <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm">
          <h1 className="text-lg font-semibold">Something went wrong</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {this.props.label ?? "This page"} stopped responding while rendering. Your saved work is
            not affected.
          </p>
          {/* The message is shown deliberately: without any error reporting, hiding it makes the
              failure impossible to describe in a bug report. */}
          <p className="mt-3 rounded-lg bg-muted px-3 py-2 font-mono text-xs break-words text-muted-foreground">
            {error.message || error.name}
          </p>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={this.handleReload}
              className="inline-flex h-8 items-center justify-center rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              Reload the page
            </button>
            <a
              href="/"
              className="inline-flex h-8 items-center justify-center rounded-lg border border-border px-3 text-sm font-medium transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              Go to the start page
            </a>
          </div>
        </div>
      </div>
    );
  }
}
