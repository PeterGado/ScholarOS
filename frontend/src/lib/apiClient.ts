import axios, { AxiosError } from "axios";
import { getToken, setToken } from "./authToken";

// The dev server has the API on the developer's own machine; a deployed build does not.
// Falling back to 127.0.0.1:8000 unconditionally is what produced "Could not reach the server"
// on the deployed site whenever VITE_API_BASE_URL was missing from the build env (2026-11-07):
// the bundle asked the visitor's browser for its own localhost, which is never the backend.
const PRODUCTION_BASE_URL = "https://scholaros-backend.fly.dev";
const DEV_BASE_URL = "http://127.0.0.1:8000";

const configuredBaseURL = import.meta.env.VITE_API_BASE_URL?.trim();

if (!configuredBaseURL && !import.meta.env.DEV) {
  // eslint-disable-next-line no-console
  console.warn(
    `[apiClient] VITE_API_BASE_URL is not set for this build. Falling back to ${PRODUCTION_BASE_URL}.`,
  );
}

export const baseURL = configuredBaseURL || (import.meta.env.DEV ? DEV_BASE_URL : PRODUCTION_BASE_URL);

// Fail visibly instead of hanging forever (2026-11-06). Without a timeout a request to a
// backend that accepts the socket but never answers (a cold start, a wedged worker, a dropped
// upstream) stayed pending indefinitely: spinners ran forever and no error branch ever fired.
export const REQUEST_TIMEOUT_MS = 20_000;

export const apiClient = axios.create({ baseURL, timeout: REQUEST_TIMEOUT_MS });

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

export type ApiErrorCause = unknown;

export class ApiError extends Error {
  readonly status: number;
  readonly errorType: string;
  // The raw upstream error (network failure, timeout, CORS rejection) - only set for the
  // non-2xx / non-response cases, so callers can inspect the original error without it leaking
  // into JSON serialization.
  readonly originalError?: unknown;

  constructor(
    status: number,
    body: ApiErrorBody,
    options?: ErrorOptions,
  ) {
    super(body.detail, options);
    this.status = status;
    this.errorType = body.error_type;
    this.originalError = options?.cause;
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
    // No response at all - offline, DNS failure, CORS rejection, or our own timeout.
    // The raw AxiosError message ("timeout of 20000ms exceeded", "Network Error") is not
    // something the UI can act on, so surface a stable sentence instead, carrying the original
    // error on `cause` for anyone who wants it.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const original = (error as any).originalError ?? error;
    return Promise.reject(
      new ApiError(
        0,
        {
          error_type: original.code === "ECONNABORTED" ? "timeout" : "network_error",
          detail:
            original.code === "ECONNABORTED"
              ? "The server took too long to respond. That usually means it is down or overloaded - start it again and retry."
              : "Could not reach the server. Check your connection and try again.",
        },
        { cause: original },
      ),
    );
  },
);
