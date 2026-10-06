import { Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { Button } from "@/components/ui/button";

// Replaces the previous silent redirect-to-/chat catch-all (2026-10-06) - a dead link used to
// bounce an unauthenticated visitor straight to the login page with no explanation of what
// happened.
export function NotFoundPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      <p className="text-sm font-medium text-muted-foreground">404</p>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Page not found</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        The page you're looking for doesn't exist or may have moved.
      </p>
      <Button asChild>
        <Link to={isAuthenticated ? "/chat" : "/"}>
          {isAuthenticated ? "Back to your workspace" : "Back to home"}
        </Link>
      </Button>
    </div>
  );
}
