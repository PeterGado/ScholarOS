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

`modules/author_profile` is not present yet - writing-style ingestion belongs to the Project
Writing milestone, not Slice 2. Retrieval (`GET /knowledge/search`) is currently vector-only,
not the full hybrid (lexical + semantic, fused) design ADR-005 specifies - a known, flagged,
deliberate gap, not an oversight; see the 2026-09-11 journal entries.
