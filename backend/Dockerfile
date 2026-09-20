FROM python:3.12-slim

WORKDIR /app

# psycopg[binary] and building wheels for some deps need build tools; kept minimal.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir -e .

# 2026-09-21 production security pass: no USER directive existed before this - the container
# ran as root with no reason to (production writes go to Postgres/S3, never local disk; nothing
# here needs root). Not a currently-exploited issue, but a real hardening gap - a process
# compromise no longer starts with root inside the container.
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# --workers 1: the in-process Work Item executor loop (ADR-006) assumes exactly one process -
# running more would mean multiple executors polling the same queue redundantly. Fly.io scales
# by running more machines, not more uvicorn workers per machine, for this reason.
# --proxy-headers: Fly.io terminates TLS and proxies every request to this container, so without
# this flag every request appears to come from Fly's internal proxy IP - the IP-based rate
# limiting added 2026-09-19 needs the real client IP from X-Forwarded-For instead.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers
