import { Navigate, Outlet, useOutletContext } from "react-router-dom";
import { useWorkspace, isNotFoundError } from "@/hooks/useWorkspace";
import type { AgentWorkspaceResponse } from "@/api/schemas";

/** Resolves the caller's Agent workspace once and makes it available to every nested route via
 * `useWorkspaceContext()`. A user with no workspace yet is redirected to onboarding - the only
 * way to reach any of the Documents/Style/Drafts pages, since every one of them needs a real
 * project_id/agent_id the backend already resolved, never one the frontend guesses. */
export function WorkspaceGate() {
  const { data, isLoading, isError, error } = useWorkspace();

  if (isLoading) {
    return <p className="p-6 text-sm text-muted-foreground">Loading your workspace...</p>;
  }

  if (isError) {
    if (isNotFoundError(error)) {
      return <Navigate to="/onboarding" replace />;
    }
    return <p className="p-6 text-sm text-destructive">Could not load your workspace. Is the backend running?</p>;
  }

  return <Outlet context={data} />;
}

export function useWorkspaceContext(): AgentWorkspaceResponse {
  return useOutletContext<AgentWorkspaceResponse>();
}
