import { apiClient } from "../lib/apiClient";
import { aiUsageResponseSchema, type AiUsageResponse } from "./schemas";

// Shared so every place that changes AI usage (uploads, sends, extraction, the widget's own
// query) invalidates the exact same key instead of each spelling it out - a typo in one of them
// would silently leave the sidebar stale.
export const AI_USAGE_QUERY_KEY = ["ai-usage"] as const;

export async function getAiUsage(): Promise<AiUsageResponse> {
  const response = await apiClient.get("/ai/usage");
  return aiUsageResponseSchema.parse(response.data);
}
