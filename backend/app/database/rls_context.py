from contextvars import ContextVar

# Row-Level Security (2026-09-21, second infra/scaling security pass): the current request's
# authenticated user id, set by app.core.dependencies.get_current_user_id once identity is
# resolved and read by the Postgres-only "begin" event listener in app.database.session
# (build_engine) to populate the `app.current_user_id` session variable every RLS policy
# checks. A plain module-level ContextVar, not a request attribute, because the listener fires
# from inside SQLAlchemy's own connection-checkout machinery, which has no direct handle on the
# current FastAPI request. Reset to None in app.database.session.get_db's own `finally` so it
# never leaks into whatever request a worker task handles next.
current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
