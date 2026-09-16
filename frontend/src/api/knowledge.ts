import { apiClient } from "../lib/apiClient";
import { searchResponseSchema, type SearchResultResponse } from "./schemas";

export async function searchKnowledge(query: string, topK = 10): Promise<SearchResultResponse[]> {
  const response = await apiClient.get("/knowledge/search", { params: { q: query, top_k: topK } });
  return searchResponseSchema.parse(response.data).results;
}
