# ScholarOS

ScholarOS is an AI-native workspace for research, writing, and grounded knowledge work. It helps teams and individuals turn files, notes, and source material into a searchable memory layer that an assistant can reason over in context.

The project combines a Python FastAPI backend with a React + TypeScript frontend, creating a full-stack application for:

- creating and managing workspaces
- uploading research documents and writing samples
- extracting and indexing knowledge for search and retrieval
- chatting with an AI assistant grounded in project context
- handling asynchronous background processing for document ingestion and model work

## Why ScholarOS?

Modern research and writing workflows are fragmented: documents live in folders, ideas live in chats, and important context gets lost in the flow of work. ScholarOS brings these pieces together so knowledge can be stored, searched, and reused across a project lifecycle.

Instead of forcing users into a rigid pipeline, ScholarOS centers the workflow around a conversational interface while still supporting document-based grounding, retrieval, and structured project setup.

## Core capabilities

- Workspace onboarding and project setup
- Authentication with email/password and Google sign-in
- Research document upload and processing
- Searchable knowledge retrieval over processed documents
- AI-assisted chat grounded in uploaded content
- Background job execution for long-running document and AI tasks
- SQLite-first configuration with PostgreSQL-ready architecture
- Modular backend services and a modern React frontend

## Architecture

This repository is split into two main application layers:

- `backend/` — FastAPI application, database models, integrations, and background workers
- `frontend/` — Vite + React app for the user experience
- `docs/` — architecture, requirements, and product documentation

The backend is organized around bounded application modules such as auth, documents, knowledge, projects, and AI-driven work execution. The frontend provides the product interface for onboarding, chat, and document workflows.

## Repository layout

```text
.
├── backend/          # FastAPI backend
├── frontend/         # React + TypeScript app
├── docs/             # architecture and product docs
├── .gitignore
├── .python-version
├── scholaros.db      # local SQLite database used during development
├── README.md         # project overview
└── ...
```

## Quick start

### 1) Backend

Requires Python 3.11+ and is validated against Python 3.12 in this repo.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload
```

The API will be available at:

- http://127.0.0.1:8000

### 2) Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The frontend will be available at:

- http://localhost:5173

Make sure the backend is running and that the frontend base URL points to the running API.

## Configuration notes

- The backend defaults to SQLite for local development and supports PostgreSQL via configuration.
- Document storage defaults to a local filesystem backend but can be swapped to S3-compatible storage.
- AI integrations are configured via environment variables and can use Google Gemini or an OpenAI-compatible provider.
- Authentication is configured through backend environment settings; secrets should never be committed to source control.

## Development scripts

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm run typecheck
npm run test
npm run build
```

## Documentation

The workspace includes product and engineering documentation under `docs/`, including architecture, requirements, and workflow references. These are useful if you want to understand the application design, historical decisions, and the intended behavior behind the current product surface.

## Status

ScholarOS is actively under development as a research and writing platform, with backend services, frontend flows, and knowledge processing all implemented as part of the current codebase.

## Contributing

Contributions are welcome. For practical development work, start with the backend and frontend setup above, then explore the docs and product requirements in `docs/` to understand the intended user flows before making changes.
