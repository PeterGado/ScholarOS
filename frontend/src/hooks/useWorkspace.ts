import { useQuery } from "@tanstack/react-query";
import { getAgentWorkspace } from "@/api/agents";
import { ApiError } from "@/lib/apiClient";

export function useWorkspace() {
  return useQuery({
    queryKey: ["agent-workspace"],
    queryFn: getAgentWorkspace,
    retry: false,
  });
}

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
