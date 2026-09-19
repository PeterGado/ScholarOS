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

EXPOSE 8000

# --workers 1: the in-process Work Item executor loop (ADR-006) assumes exactly one process -
# running more would mean multiple executors polling the same queue redundantly. Fly.io scales
# by running more machines, not more uvicorn workers per machine, for this reason.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
