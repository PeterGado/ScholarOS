import { apiClient } from "../lib/apiClient";
import { profileResponseSchema, tokenResponseSchema, type ProfileResponse, type TokenResponse } from "./schemas";

export async function login(username: string, password: string): Promise<TokenResponse> {
  const response = await apiClient.post("/auth/login", { username, password });
  return tokenResponseSchema.parse(response.data);
}

export async function register(email: string, password: string): Promise<TokenResponse> {
  const response = await apiClient.post("/auth/register", { email, password });
  return tokenResponseSchema.parse(response.data);
}

export async function loginWithGoogle(idToken: string, inviteCode?: string): Promise<TokenResponse> {
  const response = await apiClient.post("/auth/google", {
    id_token: idToken,
    invite_code: inviteCode || null,
  });
  return tokenResponseSchema.parse(response.data);
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
}

export async function getProfile(): Promise<ProfileResponse> {
  const response = await apiClient.get("/auth/profile");
  return profileResponseSchema.parse(response.data);
}

export async function updateEmail(email: string): Promise<void> {
  await apiClient.put("/auth/email", { email });
}

export async function requestPasswordReset(email: string): Promise<void> {
  await apiClient.post("/auth/password-reset/request", { email });
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/password-reset/confirm", { token, new_password: newPassword });
}

export async function requestEmailVerification(): Promise<void> {
  await apiClient.post("/auth/email-verification/request");
}

export async function confirmEmailVerification(token: string): Promise<void> {
  await apiClient.post("/auth/email-verification/confirm", { token });
}

export async function connectGoogleAccount(idToken: string): Promise<void> {
  await apiClient.post("/auth/google/connect", { id_token: idToken });
}

export async function setPassword(password: string): Promise<void> {
  await apiClient.post("/auth/password/set", { password });
}
