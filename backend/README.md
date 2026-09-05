# ScholarOS Backend

Stage 2 scaffold for Milestone 6 (Backend Implementation), Slice 1: Agent Creation (with its one Project) → Research Document Upload.

See [`docs/Backend_Implementation_Plan.md`](../docs/Backend_Implementation_Plan.md) for the module structure, API route plan, and scope rationale, and [`docs/architecture/05_Backend_Architecture.md`](../docs/architecture/05_Backend_Architecture.md) for the governing service boundaries.

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

## Layout

```
app/
├── main.py            # FastAPI app entrypoint
├── core/               # config, shared dependencies, base exceptions
├── api/                 # HTTP interface: router + route modules
├── modules/             # bounded-context modules (domain/application/infrastructure/interface per module)
│   ├── agent/            # Agent Service (Architecture 05 §22, ADR-009)
│   ├── project/           # Project Service (Architecture 05 §11)
│   └── document/           # Document Service (Architecture 05 §10)
├── database/             # structured-core persistence (SQLAlchemy) - wired in Stage 3
└── storage/               # object store (local filesystem, ADR-004) - wired in Stage 3
```

`modules/knowledge`, `modules/author_profile`, `app/ai`, and `app/workers` are intentionally not present yet - they belong to Slice 2, per `docs/Backend_Implementation_Plan.md` §6.
