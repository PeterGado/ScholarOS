// Shared shape every paginated list endpoint normalizes to, regardless of the backend
// wrapper's own field name (`documents`/`conversations`/`messages`/`records`) - callers work
// with one consistent type instead of five slightly different ones. Mirrors the backend's own
// shared `app/core/pagination.py` defaults (2026-09-23, real-traffic audit).
export interface Page<T> {
  items: T[];
  hasMore: boolean;
}

export const DEFAULT_LIST_LIMIT = 50;

export interface PageParams {
  limit?: number;
  offset?: number;
}
