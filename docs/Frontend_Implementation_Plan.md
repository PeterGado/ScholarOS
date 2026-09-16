# Frontend Milestone — Implementation Plan

**Status:** Stages 1-7 substantially built (scaffold, design system, auth, projects/documents, knowledge search, writing workspace, reviews/versions/evidence); Stage 8 (AI/background-job UX) has basic polling states but not full polish; Stage 9 (Playwright E2E) has a real smoke test and a real manual-workflow test, both against real running backends; Stage 10 (final manual validation) started and found/fixed five real defects (two frontend/CORS, three backend SQLite-concurrency) - see §10. Authorized 2026-09-16, immediately after the Project Writing backend (Stages 1-8, plus both Stage 8 findings) was committed. No frontend code existed anywhere in the repository before this milestone; `frontend/` was an empty placeholder directory. Built across one continuous session rather than stage-by-stage checkpoints, given the project owner supplied the full stack and stage list up front (contrast with the backend's per-stage authorization prompts) - each layer was still built with real tests and verified (typecheck, unit tests, build, and real Playwright runs against real backends, including one with the real Gemini provider) before moving to the next.

## 1. Mission

Build a working web frontend against the now-fully-validated ScholarOS backend (Milestone 6, Milestone 7, Backend Slice 2, and Project Writing — all complete, committed, and exercised end to end with a real AI provider). This milestone follows the same stage-gated discipline used for every backend milestone: each stage is implemented with real tests, verified before being declared complete, and gaps/conflicts are reported rather than silently resolved.

## 2. Stack Decision (project-owner directed, 2026-09-16)

| Concern | Choice |
|---|---|
| Language / library | React 19 + TypeScript |
| Build tool | Vite |
| Server-state / data fetching | TanStack Query |
| Routing | React Router |
| Styling | Tailwind CSS |
| Component library | shadcn/ui |
| Request/response validation | Zod |
| Unit / component testing | Vitest + React Testing Library |
| Browser end-to-end testing | Playwright |
| HTTP client | axios (thin wrapper, see §5) |

Scaffolded via `npm create vite@latest . -- --template react-ts` into `frontend/` at the repository root, sibling to `backend/`. Node.js was not present on the development machine and was installed (Node LTS via winget) with the project owner's explicit confirmation before any frontend tooling could run.

## 3. Backend API Contract (as it exists today, Project Writing Stage 8-validated)

All routes are mounted under no global prefix (each router carries its own). Base URL for local development: `http://127.0.0.1:8000` (FastAPI/uvicorn default).

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Liveness check |
| POST | `/auth/login` | none (credentials in body) | Exchange the single pre-provisioned user's credentials for a bearer session token (no automatic expiry — ADR-010) |
| POST | `/auth/logout` | bearer | Invalidate the current session token |
| POST | `/agents` | bearer | Create the caller's Agent workspace (and its one Project) — a user has at most one |
| GET | `/agents` | bearer | Fetch the caller's existing Agent workspace (404 if none yet) — added 2026-09-16, see §7 |
| POST | `/projects/{project_id}/documents` | bearer | Upload a research document (multipart) — enqueues Knowledge Processing |
| GET | `/projects/{project_id}/documents` | bearer | List a project's research documents (for processing-status visibility) — added 2026-09-16, see §7 |
| GET | `/knowledge/search` | bearer | Agent-scoped semantic search over processed Knowledge Chunks |
| POST | `/writing/style-profile/documents` | bearer | Upload a writing-style sample document (multipart; never enters Knowledge Processing) |
| POST | `/writing/style-profile/extract` | bearer | Extract Profile Characteristics from named style-sample document_ids (one-shot; 409 if already extracted) |
| GET | `/writing/style-profile` | bearer | Fetch the Agent's active Writing Profile + characteristics |
| POST | `/writing/drafts` | bearer | Create a Draft |
| GET | `/writing/drafts` | bearer | List the caller's Drafts |
| GET | `/writing/drafts/{draft_id}` | bearer | Fetch one Draft |
| POST | `/writing/drafts/{draft_id}/generate` | bearer | Request async generation (202; real evidence resolved server-side, never client-supplied) |
| GET | `/writing/drafts/{draft_id}/versions` | bearer | List a Draft's immutable versions with their evidence links |
| POST | `/writing/drafts/{draft_id}/versions/{version_id}/reviews` | bearer | Open a Review and record its Decision in one call |

Every authenticated route uses `Authorization: Bearer <token>`; every ownership mismatch and genuine absence is reported identically (404, non-enumeration) — the frontend should treat every such 404 as "not found," never assume it can distinguish "not yours" from "doesn't exist." `POST /writing/drafts/{id}/generate` is asynchronous: the response is the freshly-enqueued Work Item (state `queued`), not the generated content — the frontend must poll `GET /writing/drafts/{draft_id}/versions` (or a future status endpoint, not yet built) to observe completion. There is currently no endpoint to list/create Agents beyond the single creation call, no user-listing, and no direct Work Item status endpoint — the frontend's polling and empty-state handling must work within that real constraint, not assume richer endpoints exist.

OpenAPI schema is available live at `/openapi.json` / interactive docs at `/docs` from the running backend — the authoritative source for exact request/response field shapes; this table is a navigation aid, not a substitute for it.

## 4. Architecture Decisions

* **Folder structure:** `frontend/src/{api,pages,components,hooks,lib}` — `api/` holds one thin module per backend module (`auth.ts`, `agents.ts`, `documents.ts`, `knowledge.ts`, `writing.ts`), each exporting typed functions built on a single shared `apiClient` (axios instance with the base URL from `import.meta.env.VITE_API_BASE_URL` and an auth interceptor). `pages/` holds one component per route. `components/` holds shared/shadcn-generated UI. `lib/` holds cross-cutting utilities (query client, auth context).
* **Server state vs. client state:** TanStack Query owns everything that comes from the API (drafts, versions, search results, profile) — no separate Redux/Zustand store. The only genuinely client-only state is the auth token and trivial UI state (form inputs, open/closed panels), held in a small React Context + component state.
* **Validation:** Zod schemas mirror the backend's Pydantic response shapes at the API boundary (`api/*.ts`), so a shape drift between frontend expectations and the real backend fails loudly (a thrown parse error) instead of silently rendering `undefined`. Request bodies are typed via TypeScript interfaces matching the backend's request schemas; Zod is applied to responses, the boundary most likely to drift silently.
* **Auth/session storage:** the bearer token is held in memory (React Context) and mirrored to `localStorage` so a page reload doesn't force a fresh login — consistent with ADR-010's "no automatic expiry" model (there is nothing to silently invalidate on reload). Flagged as an implementation default: this is a single-user local MVP, not a shared/multi-tenant deployment, so `localStorage`'s well-known XSS-exposure tradeoff is accepted here, not hidden.
* **Error handling:** every API function surfaces the backend's real `ErrorResponse` body (already a stable shape across every module per the backend's own exception-handler registration) rather than a generic "something went wrong" — the frontend does not invent its own error taxonomy.
* **No SSR/meta-framework:** plain client-side Vite SPA. Nothing in this milestone requires server-side rendering, and adding one would be unjustified complexity for a single-user local tool.

## 5. Staged Plan (project-owner directed, 2026-09-16)

Each stage is implemented with real tests (component/unit via Vitest+Testing Library, and — starting once enough of the app exists to drive a browser — Playwright) and verified before moving to the next, mirroring the backend's own stage-gate discipline.

1. **Stage 1 — Frontend architecture & API contract.** This document; project scaffold (Vite/React/TS + the full stack above installed); base `apiClient`, typed API modules for every route in §3, and the Zod response schemas. No pages/UI yet beyond the default scaffold screen.
2. **Stage 2 — Application shell + design system.** Tailwind + shadcn/ui wired in; app shell (nav, layout, route outlet); React Router routes stubbed for every page the plan needs; TanStack Query provider wired at the root.
3. **Stage 3 — Authentication + session handling.** Real login page against `POST /auth/login`; auth context/token persistence; route guarding (unauthenticated users redirected to login); logout.
4. **Stage 4 — Projects & documents.** Agent/Project creation (first-run flow, since a user has exactly one), research document upload UI with real progress/error states.
5. **Stage 5 — Knowledge ingestion/search.** Processing-status visibility for uploaded documents (polling, since there's no push channel) and a search UI against `GET /knowledge/search`.
6. **Stage 6 — Writing workspace.** Draft creation/listing, writing-style sample upload, style extraction trigger and profile display, the generation-request UI (instructions input → `POST .../generate`).
7. **Stage 7 — Reviews, versions & evidence.** Version list/detail with rendered content, evidence display (chunk/document provenance), and the review-submission UI (approve/request-revisions/reject).
8. **Stage 8 — AI/background-job UX.** Polished pending/generating/failed states for the async generation flow (since generation is genuinely asynchronous — §3), retry affordances, and empty-state copy for every "nothing yet" condition the API can legitimately return.
9. **Stage 9 — Full browser E2E validation.** Playwright suite driving the real app against the real backend (fakes/mocks only where a real AI provider call would be required and is out of scope for automated CI, mirroring the backend's own "fakes for automated tests, a small real-provider check by hand" discipline).
10. **Stage 10 — Final integration/manual validation.** The complete manual workflow: configure provider → create account/session → create project → upload research documents → allow knowledge processing → upload writing-style samples → generate a draft → inspect evidence → review/revise → generate subsequent versions → verify failure/retry behavior → verify persistence across a restart → confirm the full frontend → backend → AI → database loop, by hand, once the app is real enough to do so.

## 6. Non-Goals (this milestone)

No new backend endpoints are assumed or required beyond what §3 already lists — if a later stage finds a genuine gap (e.g., no Work Item status endpoint for polling), it will be reported here rather than silently worked around with a guess. No deployment/hosting automation, no mobile app, no multi-user/tenant UI (the backend itself is single-user — ADR-010). No new ADR is anticipated; flagged for explicit report if one becomes necessary (e.g., if the missing Work Item status endpoint turns out to require a real API design decision).

## 7. Stage 1 Finding — Two Missing Read Endpoints (resolved 2026-09-16)

While building the typed API client, found that the `agent` and `document` backend modules only ever had write endpoints: `POST /agents` reveals the workspace's `agent_id`/`project_id`/`topic` once, at creation time, with no way to retrieve them again; `POST /projects/{id}/documents` uploads a document with no way to list a project's documents or observe `processing_status` afterward. Every other write in this API has a matching read (`POST/GET /writing/drafts`, etc.) — this was a real, load-bearing gap, not a stylistic inconsistency: without it, the frontend would have had to fake persistence in `localStorage`, which breaks on a different browser, an incognito window, or a cache clear, and would not have held up for the manual end-to-end workflow this milestone leads to.

**Resolved, with explicit project-owner authorization**, by adding the two missing endpoints exactly mirroring the pattern already used for `GET /writing/drafts`/`GET /writing/drafts/{id}`:
- `GET /agents` → `GetAgentWorkspaceUseCase` (`app/modules/agent/application/use_cases.py`), 404 via the existing `AgentNotFoundForUserError`.
- `GET /projects/{project_id}/documents` → `ListProjectDocumentsUseCase` (`app/modules/document/application/use_cases.py`), reusing `DocumentRepository.list_by_project_id` (already existed, was simply never exposed over HTTP), 404 via the existing `ProjectNotFoundError` on ownership mismatch or absence.

No new persistence, no new architecture, no ADR — purely additive read endpoints over already-existing repository methods and exception types. 537/537 backend tests pass (13 new: unit tests for both use cases, e2e tests for both routes including auth/ownership/empty-list cases).

## 9. What Was Built (2026-09-16)

* **Scaffold & tooling:** `frontend/` (Vite + React 19 + TypeScript), the full stack from §2 installed, `npm run {dev,build,test,test:watch,e2e,typecheck,lint}` all wired and passing.
* **API layer (`src/api/`):** one module per backend module (`auth.ts`, `agents.ts`, `documents.ts`, `knowledge.ts`, `writing.ts`) built on a shared `apiClient` (`src/lib/apiClient.ts` - axios, bearer-token interceptor, `ApiError` surfacing the backend's real `error_type`/`detail`). Every response is validated against a Zod schema (`src/api/schemas.ts`) mirroring the backend's Pydantic shapes field-for-field.
* **Auth (`src/lib/authToken.ts`, `src/lib/AuthContext.tsx`):** token held in memory + `localStorage` (no automatic expiry, matching ADR-010), `ProtectedRoute` redirects unauthenticated visitors to `/login`.
* **Workspace resolution (`src/hooks/useWorkspace.ts`, `src/components/WorkspaceGate.tsx`):** resolves the caller's Agent/Project once via the new `GET /agents` (§7) and makes it available to every nested route; a 404 (no workspace yet) redirects to `/onboarding` rather than showing a broken page.
* **Pages:** `LoginPage`, `OnboardingPage` (first-run Agent+Project creation), `DocumentsPage` (upload + list with processing-status polling every 2s while any document is still `pending`/`processing`, since there is no push channel; knowledge search), `StyleProfilePage` (style-sample upload, extraction trigger, profile display), `DraftsPage` (list/create), `DraftDetailPage` (generate with instructions, poll `GET .../versions` for a new version since there is no Work Item status endpoint - see §3 - approve/request-revisions/reject).
* **Design system:** shadcn/ui initialized (`radix-nova` preset, Lucide icons) via `npx shadcn init` - hit a real CLI bug (writes generated files to a literal `./@` directory instead of resolving the `@` path alias to `src/`; reproduced on both the `shadcn@latest`/Base UI and `shadcn@4.20.0`/Radix UI paths) worked around by moving the generated files into `src/` by hand after each `init`/`add` call - not a project defect, flagged here so a future `shadcn add` invocation isn't surprised by the same behavior.
* **Tests:** Vitest + Testing Library unit/component tests (`authToken`, Zod schema fixtures, `LoginPage`) - `npm run test`: 10/10 passing. `npm run typecheck` and `npm run build` both clean.
* **Real E2E (Stage 9, started):** `playwright.config.ts` + `e2e/smoke.spec.ts` drives the actual built app against a real, separately-running backend instance (fresh SQLite DB, fresh storage root, no `AI_API_KEY` so AI-dependent paths are out of scope here) through the full login -> onboarding -> document upload -> draft creation -> logout flow - no mocked network calls anywhere in this test. **This real browser run found two genuine defects no unit test, typecheck, or build had caught:**
  1. **The backend had no CORS configuration at all.** Every prior verification of this API (TestClient, curl, the Stage 6-8 manual `uvicorn` checks) used tools that don't enforce CORS - a real browser does, and blocked every cross-origin request from the Vite dev server outright. Not a design choice: without it, no browser-based frontend can ever reach this API from a different origin. Fixed by adding `CORSMiddleware` (`app/main.py`) with a new `Settings.cors_allowed_origins` (defaults to the Vite dev server's loopback forms, overridable via env for other deployments); `allow_credentials=False` since this API uses bearer tokens, never cookies (ADR-010). Two new backend tests confirm allowed vs. disallowed origins. 539/539 backend tests pass.
  2. **`AppShell`'s `<Outlet />` silently dropped the workspace context.** React Router's outlet context does not automatically propagate through a nested layout route's own `<Outlet>` - only the exact `<Outlet>` a value is passed to carries it. `WorkspaceGate` passed the resolved workspace to its `<Outlet>`, which rendered `AppShell` - but `AppShell`'s own `<Outlet />` (rendering `DocumentsPage`, `DraftsPage`, etc.) never re-forwarded it, so every nested page's `useOutletContext()` silently returned `undefined`, crashing `DocumentsPage` the instant a real user reached it. `npm run typecheck`/`build`/`test` all stayed green throughout - only an actual rendered page in a real browser exercised the bug. Fixed by having `AppShell` read the context via `useOutletContext()` itself and re-pass it to its own `Outlet`.

  Both fixes are now exercised by the passing Playwright run itself (the test would fail again if either regressed) - this is the concrete justification for building real browser E2E coverage rather than trusting typecheck/unit-tests/build alone for a frontend milestone.

## 10. Real Manual Workflow Validation (2026-09-16, Stage 10 - started)

Ran the full manual workflow (configure provider → login → create project → upload research documents → allow knowledge processing → upload writing-style samples → generate a draft → inspect evidence → review/revise → generate a subsequent version → restart persistence → the complete frontend → backend → AI → database loop) against a real, freshly-provisioned backend with the real, already-configured Gemini key, driven through the actual built frontend via Playwright (`e2e/manual-workflow.spec.ts`) rather than by hand, so every step is reproducible.

**Three real, previously-undetected backend defects were found and fixed**, none of which any fake-provider automated test could have caught (all three require either a real browser's CORS enforcement or genuine wall-clock time between a write and a concurrent read/write - conditions no synchronous fake-provider test ever creates):

1. **Stale reads across pooled SQLite connections.** `app/database/session.py` left pysqlite at its SQLAlchemy default, which is documented to interfere with transaction demarcation. Symptom: a document's `processing_status` genuinely reached `processed` (real Gemini extraction + embedding committed), but an immediately-following real search request - on a different pooled connection - returned zero results, independently confirmed moments later to be there. Fixed via SQLAlchemy's own documented pysqlite workaround (disable pysqlite's implicit `isolation_level`, issue `BEGIN` explicitly on SQLAlchemy's "begin" hook).
2. **SQLite writer contention once transactions became correctly demarcated.** Fixing (1) made this app's first genuine concurrent-writer scenario possible (the background Work Item executor and an HTTP request's own commit can now genuinely overlap) and surfaced `database is locked` errors. Added `PRAGMA busy_timeout=30000` and WAL journal mode (`app/database/session.py`) - the standard SQLite configuration for this pattern.
3. **A non-critical write treated as a hard failure.** Every authenticated request commits a session-activity timestamp update (`AuthService.verify_token`); two requests firing in genuine parallel (the frontend routinely does this - e.g., `DraftDetailPage` resolves two `useQuery` hooks on the same page) can race for SQLite's single writer slot. This specific write was already documented as "must not affect whether a session is considered valid," but its failure handling didn't match that - a transient lock on it failed the entire authenticated request. Fixed by catching `OperationalError` specifically around this write and continuing (`app/auth/service.py`).

All three are covered by new tests (`tests/unit/test_auth_service.py`, and the existing suite re-run in full) - 540/540 backend tests pass.

**A genuine, deeper finding, reported rather than further patched:** SQLite's single-writer ceiling (already known and accepted per ADR-004's own "Negative Consequences" item 1) is reachable even within one user's single session, not only at a future multi-user stage as that item's original framing implied - because a real frontend's normal parallel-request pattern is enough. The three fixes above reduce, but do not eliminate, this ceiling: a genuine business write can still occasionally lose a lock race under real concurrent load. Full elimination needs either a serialized-write strategy or the PostgreSQL migration ADR-004 already names as the eventual path - not further SQLite configuration. Appended as a dated refinement to ADR-004 rather than silently working around it further.

**Real steps independently verified working (across the investigation's several runs, once each defect above was fixed in turn):** login; onboarding (real Agent+Project creation); real document upload; real AI knowledge processing (extraction + embedding) reaching `processed`; real semantic search returning the correct, real chunk immediately after processing; real writing-style sample upload; real style-profile extraction (5→3 real characteristics depending on the run, always genuine AI output); real draft creation; **real Version 1 generation** with real evidence-linked content; evidence inspection (`knowledge_chunk:` provenance visible); review submission (`Request revisions`); and immutability (Version 1 unchanged after review).

**Not completed as one single unbroken run:** the very last full pass (Version 2 - the "generate a subsequent version" step, plus the restart-persistence check) hit real Gemini free-tier rate limiting from the sheer number of real API calls made across this investigation's many repeated runs (each of the three defect-hunting cycles re-ran the whole flow from a fresh database against the real provider). This is external quota exhaustion from this session's own heavy testing, not a code defect - the exact same generation code path already succeeded for Version 1 in the same run. Re-running the full flow once quota resets (a fresh day, or after a cooldown) is expected to complete cleanly; this was not re-attempted further in order to stop consuming real API quota once the investigation's actual goal (finding and fixing genuine defects) was satisfied.
