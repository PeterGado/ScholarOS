# ScholarOS Backend

Milestone 6 (Backend Implementation, Slice 1: Agent Creation → Research Document Upload), Milestone 7 (Real Authentication Boundary), and Backend Slice 2 (Knowledge Processing Pipeline: upload → process → understand → retrieve) are implemented.

See [`docs/Backend_Implementation_Plan.md`](../docs/Backend_Implementation_Plan.md) for Slice 1's module structure and scope rationale, [`docs/Authentication_Implementation_Plan.md`](../docs/Authentication_Implementation_Plan.md) for the Authentication Boundary, [`docs/Backend_Slice2_Implementation_Plan.md`](../docs/Backend_Slice2_Implementation_Plan.md) for the Knowledge Processing Pipeline, and [`docs/architecture/05_Backend_Architecture.md`](../docs/architecture/05_Backend_Architecture.md) for the governing service boundaries.

## Setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -e ".[dev]"
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

Health check: `GET /health`

## Test

```bash
pytest
```

Real-Postgres compatibility tests (`tests/integration/test_postgres_dialect_compatibility.py`)
are skipped unless `POSTGRES_TEST_URL` is set to a real, reachable connection string - see
"Database (SQLite / PostgreSQL)" below.

## Authentication Setup

The backend has exactly one pre-provisioned user account (ADR-010) — no registration, no
password reset. Its credentials are read from configuration, never hard-coded. Generate the
required bcrypt hash and put both values in your `.env` (never commit real values):

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your-chosen-password', bcrypt.gensalt()).decode())"
```

```env
AUTH_USERNAME=your-chosen-username
AUTH_PASSWORD_HASH=<the hash the command above printed>
```

The account is synced from these two values on every application startup (create-if-missing,
update-if-changed) — configuration is always the source of truth.

## AI Provider Setup (Knowledge Processing Pipeline)

Document processing (extraction → AI semantic classification → embedding) requires an AI
provider API key. The default provider is Google Gemini via the native `google-genai` SDK; an
OpenAI-compatible HTTP shim is available as an alternative. Without a key configured, the
backend still runs normally — document upload works, but the background executor that
processes documents into knowledge stays off (a no-op, not an error).

```env
AI_PROVIDER=google_genai
AI_API_KEY=<your real key - never commit it>
AI_MODEL=gemini-3.6-flash
AI_EMBEDDING_MODEL=gemini-embedding-001
```

To use the OpenAI-compatible shim instead (e.g. against OpenAI itself, or another
OpenAI-compatible endpoint), set `AI_PROVIDER=openai_compatible` and `AI_BASE_URL` accordingly.

## Database (SQLite / PostgreSQL)

SQLite is the default (`DATABASE_URL=sqlite:///./scholaros.db`) and needs no setup. To run
against PostgreSQL instead (ADR-004's named eventual path, realized 2026-09-18):

```env
DATABASE_URL=postgresql://user:password@localhost:5432/scholaros
```

(a bare `postgresql://` is normalized to the installed driver, psycopg3, automatically - no
need to write `postgresql+psycopg://` yourself). Schema changes are managed by
[Alembic](https://alembic.sqlalchemy.org/), not `create_all()`, against a real database:

```bash
alembic upgrade head      # apply every migration up to the latest
alembic revision --autogenerate -m "describe the change"   # after changing an ORM model
```

`create_all()` (via `init_db()`) remains in place for ephemeral test/dev databases that
bootstrap fresh on every run (the entire pytest suite's own fixtures) - it and Alembic are
deliberately parallel paths for two different purposes, not meant to replace each other.

The lexical retrieval index (ADR-005 Decision 1) is dialect-specific: SQLite FTS5, or a
generated `tsvector` column + GIN index on Postgres - both are created automatically by either
`init_db()` or `alembic upgrade head`, whichever bootstraps the database.

## Object Storage (local filesystem / S3-compatible)

Local filesystem is the default (`STORAGE_BACKEND=filesystem`, `STORAGE_ROOT=./data/documents`).
To use an S3-compatible backend instead (any real S3-compatible endpoint - AWS S3, Cloudflare
R2, or a local mock such as `moto`'s server - selected by configuration alone, never a code
change):

```env
STORAGE_BACKEND=s3
S3_BUCKET=your-bucket-name
S3_ENDPOINT_URL=https://your-endpoint.example   # omit for real AWS S3
S3_REGION=auto
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
```

## Frontend / CORS Setup

A browser-based frontend on a different origin (e.g. the Vite dev server) cannot reach this API
at all unless its origin is explicitly allowed — every cross-origin browser request is blocked
by default, unlike `TestClient`/curl-based checks, which don't enforce CORS. Defaults already
cover the Vite dev server's default port (`http://localhost:5173` / `http://127.0.0.1:5173`); to
allow a different origin, set:

```env
CORS_ALLOWED_ORIGINS=["http://localhost:5173", "https://your-deployed-frontend.example"]
```

(a JSON array — pydantic-settings' own default parsing for a list-typed setting).

## Layout

```
app/
├── main.py            # FastAPI app entrypoint - also starts the Work Item executor when AI_API_KEY is configured
├── core/               # config, shared dependencies, base exceptions
├── api/                 # HTTP interface: router + route modules
├── modules/             # bounded-context modules (domain/application/infrastructure/interface per module)
│   ├── agent/            # Agent Service (Architecture 05 §22, ADR-009)
│   ├── project/           # Project Service (Architecture 05 §11)
│   ├── document/           # Document Service (Architecture 05 §10)
│   └── knowledge/           # Knowledge Service (Architecture 05 §8) - extraction, chunking,
│                             # semantic classification, embedding, retrieval (Backend Slice 2)
├── database/             # structured-core persistence (SQLAlchemy)
├── storage/               # object store (local filesystem, ADR-004)
├── auth/                   # Authentication Boundary (ADR-010) - a boundary, not a modules/
│                             # bounded context (see docs/Authentication_Implementation_Plan.md)
├── ai/                     # Provider Abstraction gateway (ADR-002) - app/ai/providers/
│                             # holds concrete providers (google_genai, openai_compatible);
│                             # domain/application code depends only on app/ai/providers/base.py
└── workers/                 # Durable outbox / Work Item executor (ADR-006)
```

Retrieval (`GET /knowledge/search`) is hybrid (lexical + semantic, fused via Reciprocal Rank
Fusion) per ADR-005, realized 2026-09-18 - see `docs/Project_Status.md`'s Risks table.
