import axios, { AxiosError } from "axios";
import { getToken, setToken } from "./authToken";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const apiClient = axios.create({ baseURL });

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** The stable error envelope every non-2xx ScholarOS response returns
 * (app.api.exception_handlers.ErrorResponse) - never a generic frontend-invented message. */
export interface ApiErrorBody {
  error_type: string;
  detail: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly errorType: string;

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail);
    this.status = status;
    this.errorType = body.error_type;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401) {
      // The session token is missing/malformed/unknown/ended - it can never become valid
      // again without a fresh login (ADR-010: no refresh mechanism exists).
      setToken(null);
    }
    if (error.response?.data && typeof error.response.data.detail === "string") {
      return Promise.reject(new ApiError(error.response.status, error.response.data));
    }
    return Promise.reject(error);
  },
);
