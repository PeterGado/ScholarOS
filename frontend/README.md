# ScholarOS Frontend

React + TypeScript + Vite frontend for the ScholarOS backend (`../backend`). See
`../docs/Frontend_Implementation_Plan.md` for the full architecture, API contract, and staged
build plan.

## Setup

```bash
npm install
cp .env.example .env   # point VITE_API_BASE_URL at your running backend
```

## Run

```bash
npm run dev             # dev server at http://localhost:5173
```

The backend must be running separately (`../backend`) and must allow this origin via
`CORS_ALLOWED_ORIGINS` (defaults already cover `http://localhost:5173` - see
`../backend/README.md` "Frontend / CORS Setup").

## Test

```bash
npm run typecheck       # tsc, no emit
npm run test            # Vitest + Testing Library (unit/component)
npm run e2e             # Playwright, against a real running backend - set
                         # PLAYWRIGHT_API_BASE_URL if it isn't on the default port
npm run build            # production build
```

## Layout

```
src/
├── api/        # typed API client per backend module + Zod response schemas
├── components/ # shared UI (shadcn/ui-generated primitives in components/ui/, plus app shell,
│                 route guards)
├── hooks/      # cross-cutting React hooks (workspace resolution)
├── lib/        # apiClient (axios), auth token/context, TanStack Query client
├── pages/      # one component per route
└── test/       # Vitest setup
e2e/            # Playwright specs (real backend, no mocked network)
```
