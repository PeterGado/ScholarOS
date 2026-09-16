import { apiClient } from "../lib/apiClient";
import { tokenResponseSchema, type TokenResponse } from "./schemas";

export async function login(username: string, password: string): Promise<TokenResponse> {
  const response = await apiClient.post("/auth/login", { username, password });
  return tokenResponseSchema.parse(response.data);
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
}
