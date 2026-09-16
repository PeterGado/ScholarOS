import { apiClient } from "../lib/apiClient";
import { agentWorkspaceResponseSchema, type AgentWorkspaceResponse } from "./schemas";

export interface CreateAgentWorkspaceRequest {
  project_title: string;
  project_topic: string;
  project_description?: string | null;
}

export async function createAgentWorkspace(
  request: CreateAgentWorkspaceRequest,
): Promise<AgentWorkspaceResponse> {
  const response = await apiClient.post("/agents", request);
  return agentWorkspaceResponseSchema.parse(response.data);
}

/** Throws ApiError with status 404 if the caller has no Agent workspace yet. */
export async function getAgentWorkspace(): Promise<AgentWorkspaceResponse> {
  const response = await apiClient.get("/agents");
  return agentWorkspaceResponseSchema.parse(response.data);
}
