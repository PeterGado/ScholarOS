FROM python:3.12-slim

WORKDIR /app

# psycopg[binary] and building wheels for some deps need build tools; kept minimal.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.lock ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Pinned, hash-free lockfile (2026-10-10, production-readiness pass: "no dependency lockfile -
# what's installed can silently drift between environments"), regenerate via
# `pip-compile --output-file=requirements.lock pyproject.toml` whenever pyproject.toml's
# dependencies change. --no-deps on the second install: requirements.lock already pins every
# transitive dependency, so the editable install of this package itself must not let pip
# re-resolve (and potentially drift) them.
RUN pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps -e .

# 2026-09-21 production security pass: no USER directive existed before this - the container
# ran as root with no reason to (production writes go to Postgres/S3, never local disk; nothing
# here needs root). Not a currently-exploited issue, but a real hardening gap - a process
# compromise no longer starts with root inside the container.
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# --workers 1: this is about uvicorn's own per-container worker processes, a different axis
# from Fly's machine count (ADR-014, 2026-10-10, now 2 machines) - running more than one
# uvicorn worker *inside this one container* would start multiple WorkItemExecutorLoop
# instances redundantly polling from the same process group with no benefit (Fly already
# scales by running more machines/containers, each with its own single worker, not by packing
# more workers into one). Work Item claiming is concurrency-safe across however many
# executors actually exist (`SELECT ... FOR UPDATE SKIP LOCKED`, see ADR-014), so this flag
# controls redundancy-avoidance within one container, not cross-machine safety.
# --proxy-headers: Fly.io terminates TLS and proxies every request to this container, so without
# this flag every request appears to come from Fly's internal proxy IP - the IP-based rate
# limiting added 2026-09-19 needs the real client IP from X-Forwarded-For instead.
#
# Migration (`alembic upgrade head`) no longer runs here (ADR-014, 2026-10-10) - it used to run
# on every container's own boot, which would race if multiple machines ever started
# concurrently. It now runs exactly once per deploy via fly.toml's `[deploy] release_command`.
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers
