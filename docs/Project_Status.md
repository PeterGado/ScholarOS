# ScholarOS — Project Dashboard

**Status:** Active
**Current Phase:** Backend Slice 2 (Knowledge Processing Pipeline) — **Stages 1-9 of 9 complete; Slice 2 validated end-to-end.** Full architecture/ADR compliance sweep passed except one already-known, deliberate exception: ADR-005's hybrid (lexical + semantic) retrieval decision is only partially realized (vector-only) — flagged in Stage 8, re-confirmed in Stage 9, awaiting the project owner's decision on when to complete it. Real-provider end-to-end verification performed against a genuine Gemini account via a newly-added `GoogleGenAIProvider` (`app/ai/providers/google_genai.py`, now the default provider — the original OpenAI-compatible-shim choice required live discovery of Gemini-specific model names and was corrected mid-validation at the project owner's direction). See `docs/Backend_Slice2_AI_Readiness_Review.md`, `docs/Backend_Slice2_Implementation_Plan.md`, and `docs/Backend_Slice2_Stage5_Implementation_Plan.md`. 311/311 tests passing. Next milestone (Project Writing) is explicitly out of Slice 2's scope and awaits its own authorization. Milestone 7 (Real Authentication Boundary) Stage 6 is complete — `get_current_user_id` resolves real session identity, `/agents`/`/projects/{project_id}/documents` both require authentication with document ownership enforced; Stages 7-8 remain, gated. Milestone 6 (Backend Implementation: First Vertical Slice) is complete, committed, and pushed to `origin/main`.
**Last Updated:** 2026-09-11

---

## Current Phase

| Phase | Status |
| ----- | ------ |
| ✅ Vision Approved | Complete |
| ✅ Governance Framework v2.0 (Self-Executing Sessions) | Complete |
| ✅ ADR-001 (Separation Rule) | Complete |
| ✅ Repository Documentation Refactor | Complete |
| ✅ **Architecture** | **Complete and FROZEN** (Phase 1 + Milestone 2 + Milestone 4; close-out audit passed; per 04 §4.4) |
| ✅ Repository Independence Finalization | Documentation and governance hardening complete; milestone boundaries clarified; no implementation work introduced |
| ✅ Database Design | Complete and FROZEN — Database Baseline v1 (documents 01–08) |
| ✅ Independent Repository Audit & Ratification | Complete — concluded READY FOR BACKEND IMPLEMENTATION; standalone API Design milestone superseded by ADR-008 (`docs/journal/2026-09-04.md`) |
| ✅ **Backend Implementation (Milestone 6)** | **First vertical slice COMPLETE: Agent Creation (with its one Project) → Document Upload — 66/66 tests passing, validated over real HTTP from a fresh environment; committed and pushed to `origin/main`** |
| → **Real Authentication Boundary (Milestone 7)** | **ADR-010 accepted (2026-09-10); implementation not started** — replaces the `get_current_user_id` placeholder with a real, single-pre-provisioned-user session mechanism |
| → Frontend Implementation | Pending (deferred until explicit authorization; backend-first per `decision_01.md`) |
| → Backend Slice 2 (Knowledge / Writing-Style ingestion) | Pending (needs the AI provider seam and async outbox, per `docs/Backend_Implementation_Plan.md` §6) |
| → Release | Pending |

---

## Progress Summary

| Area | Items | Status |
| ---- | ----- | ------ |
| **SRS** | 11 chapters (01–11) | ✅ Complete |
| **Governance** | 12 documents (01–12) | ✅ Active |
| **ADRs** | ADR-001 to ADR-007 (foundational set) | ✅ Accepted |
| **Journal** | `docs/journal/` directory | ✅ Active |
| **Timeline** | `docs/Timeline.md` | ✅ Active |
| **Architecture** | `docs/architecture/` | ✅ Complete and FROZEN (Phase 1 + Milestone 2 + Milestone 4) |
| **Database** | `docs/database/` | ✅ 01–08 complete and FROZEN (Database Baseline v1) |
| **API** | `docs/api/` (reserved; not a prerequisite milestone) | ➖ Folded into Backend Implementation — contracts defined progressively as code (ADR-008) |
| **Implementation** | Backend + Frontend | ✅ Backend: first vertical slice complete (66/66 tests, committed and pushed); Real Auth: ADR-010 accepted, implementation pending; Frontend: deferred |

---

## Active Work

* Architecture documentation Phase 1 (`docs/architecture/01–03`) — **Complete**
* Architecture documentation Milestone 2 (Intelligence Architecture,   `docs/architecture/04–06`) — **Complete**
* Governance Framework v2.0 (Self-Executing Engineering Sessions) — **Complete**: standing responsibilities (11) and Master Execution Prompt (12) adopted; all framework documents and repository documentation synchronized
* Milestone 4 — Architecture & ADR Foundation — **Complete and FROZEN** (04 §4.4; close-out audit Session 4 passed 2026-08-06): `07_Operational_Architecture.md` added (storage, deployment, scalability evolution); ADR-002 to ADR-007 accepted (technology stack, modular monolith, storage/memory, retrieval, async, deployment); independent audit findings R1–R6 resolved; architecture review, scalability review, final completion pass, and close-out audit performed. Architecture changes now require new ADRs, not edits to frozen documents
* Repository Independence Finalization — **Complete**: authority chain, milestone boundaries, traceability links, governance references, and documentation navigation were hardened without introducing database, API, implementation, or infrastructure work
* Milestone 5 — Database Design — **Complete and FROZEN (Database Baseline v1)**: the layered document set `docs/database/01`–`08` was produced in numeric order under the Authoritative Source Rule — constitution (01), Domain Model (02), Conceptual Data Model (03), Logical Data Model (04), Constraints and Integrity (05), Physical Design Strategy (06), Database Validation and Quality Assurance (07), and the close-out Readiness Assessment (08). All documents are implementation-independent; the frozen architecture and ADR baseline were preserved. Database Baseline v1 is recorded in `docs/Baseline_Register.md`. No implementation artifacts introduced
* Independent Repository Audit & Ratification — **Complete (2026-09-04)**: an independent, from-scratch engineering-readiness audit (`docs/journal/2026-09-04.md`) concluded the repository is READY FOR BACKEND IMPLEMENTATION and that a standalone `docs/api/` API Design milestone is not justified. The decision was ratified as **ADR-008 (API Contract Governance During Backend Implementation)**: API contracts are now defined progressively during backend implementation as Pydantic/FastAPI code, remain traceable to SRS Chapter 9, `05_Backend_Architecture.md`, ADR-002, and the Database Baseline v1, and architecturally significant API decisions still require a new ADR. No frozen SRS, Architecture, ADR (001–007), or Database artifact was rewritten; ADR-008 is a new, additive ADR per `04_Repository_Governance.md` §4.4
* No frozen architecture, ADR, requirements, or database artifact was modified for this task beyond the permitted cross-reference addition of ADR-008 to ADR-001's Related ADRs table; only documentation and governance-state artifacts were updated

---

## Current Milestone Boundary

### Milestone 5 — Database Design

| Dependency | Status |
| ---------- | ------ |
| SRS (all chapters) | ✅ Complete |
| ADR-001 (Separation Rule) | ✅ Complete |
| Governance Framework v2.0 (Self-Executing Sessions) | ✅ Active |
| Architecture (01–07) | ✅ Complete and FROZEN |
| ADR-002 to ADR-007 (foundational ADRs) | ✅ Accepted and FROZEN |

**Readiness:** The database design milestone is **complete and frozen as Database Baseline v1** (`docs/database/01`–`08`, recorded in `docs/Baseline_Register.md`). This section is preserved as the historical record of Milestone 5's close-out; its "next milestone — API Design" statement was superseded on 2026-09-04 by ADR-008 (see Milestone 6, below).

---

### Milestone 6 — Backend Implementation

| Dependency | Status |
| ---------- | ------ |
| Database Baseline v1 (`docs/database/01`–`08`) | ✅ Complete and FROZEN |
| Architecture Baseline v1 (`docs/architecture/01`–`07` + ADR-001–007) | ✅ Complete and FROZEN |
| ADR-008 (API Contract Governance During Backend Implementation) | ✅ Accepted (2026-09-04) |
| ADR-009 (Agent and Project Domain Model Introduction) | ✅ Accepted (2026-09-04); corrects Database Baseline v1 and Architecture Baseline v1 |
| Independent Repository Audit & Ratification | ✅ Complete (`docs/journal/2026-09-04.md`) |

**Readiness:** The first vertical slice is **complete**. There was no standalone API Design milestone to wait on — per ADR-008, API contracts were defined progressively during implementation as Pydantic/FastAPI code, traceable to SRS Chapter 9, `05_Backend_Architecture.md`, ADR-002, and the Database Baseline v1's handoff contract (`docs/database/08` §21). The completed first vertical slice is **Agent Creation (with its one Project) → Document Upload** (see the Backend Implementation Readiness Report in `docs/journal/2026-09-04.md`, Session 2, and the Stage 6 final validation in Session 8). Frontend implementation, real authentication, Slice 2 (Knowledge/Writing-Style ingestion), testing at scale, and deployment automation remain deferred until explicitly authorized.

**Stage 1 — Implementation Planning: Complete.** A backend architecture review reconciled a proposed directory structure against the corrected baseline and narrowed Slice 1's scope to Research Document upload only (Knowledge/Author Profile ingestion, which need the AI provider seam and async outbox, deferred to Slice 2). Module structure, API routes, and naming corrections are recorded in [docs/Backend_Implementation_Plan.md](Backend_Implementation_Plan.md).

**Stage 2 — Scaffolding: Complete.** `backend/` now exists as a runnable FastAPI application: app skeleton (`main.py`, `core/`, `api/`), Slice-1 module skeletons (`modules/{agent,project,document}`, no domain logic yet), `database/` and `storage/` placeholders (real wiring is Stage 3), and a `tests/` tree with a passing boot smoke test. Verified with a real dependency install and an actual `uvicorn` boot (not just an in-process test client). Nothing has been committed to git yet.

**Stage 3 — Database Integration: Complete.** SQLAlchemy engine/session (`app/database/session.py`, `base.py`), Agent/Project/ResearchDocument ORM models (plus a minimal supporting `User` model for the FK graph), and a content-addressed filesystem object store (`app/storage/filesystem.py`) are implemented against `04_Logical_Data_Model.md` and `05_Constraints_and_Integrity.md`. 21/21 tests pass (engine/session, persistence, integrity constraints, filesystem storage); the app still boots and `/health` still responds. No domain, application, or API logic was added — see `docs/journal/2026-09-04.md` for the full report, including two open items (undocumented `format` enum values; `User`'s long-term module home). Nothing has been committed to git yet.

**Stage 4 — Domain and Application Logic: Complete.** Each module (`agent`, `project`, `document`) now has a framework-free `domain/` layer (entities, exceptions, repository interfaces) and an `application/` layer (use cases): `CreateAgentWorkspaceUseCase` (one-Agent-per-user, atomic Agent+Project creation via a new `UnitOfWork` abstraction), `CreateProjectUseCase` (one-Project-per-Agent, required topic/title), `UploadResearchDocumentUseCase` (Project must exist, content written to storage before the DB row). 56/56 tests pass (21 Stage 3 + 35 new business-behavior tests, both isolated unit tests with in-memory fakes and real-database/real-filesystem integration tests). Dependency direction verified clean (no domain/application file imports FastAPI or SQLAlchemy); app still boots and `/health` still responds. No FastAPI route, AI call, or background worker was added — see `docs/journal/2026-09-04.md` for the full report. Nothing has been committed to git yet.

**Stage 5 — API Layer: Complete.** Exposed `POST /agents` (Create Agent Workspace) and `POST /projects/{project_id}/documents` (Upload Research Document) as thin FastAPI routes over the Stage 4 use cases; Create Project was deliberately not exposed standalone (no such flow exists in the reconciled model). Exception-to-HTTP translation is centralized (409 duplicate Agent, 404 missing Project, 422 invalid input, 500 storage/unexpected failure), with a consistent `{error_type, detail}` envelope that never leaks internals. `core/dependencies.py` now wires the full DI chain, including a clearly-flagged placeholder (`get_current_user_id`, a single bootstrap user standing in for the not-yet-built Authentication Boundary, per the MVP's single-user invariant). Exercising the app over real HTTP (not just TestClient) surfaced a genuine gap — no schema-bootstrap on startup — fixed with an `init_db()` lifespan hook. 66/66 tests pass (56 Stage 3-4 + 10 new API tests); OpenAPI inspected and confirmed accurate (real status codes, no ORM/SQLAlchemy leakage, `content_reference` withheld from responses). See `docs/journal/2026-09-04.md` for the full report. Nothing has been committed to git yet.

**Stage 6 — Testing, Integration & Final Backend Validation: Complete.** Full regression (66/66 tests, 0 failed, 0 skipped) reconfirmed; a genuine fresh-environment run (brand-new database, never-used storage path) exercised the entire slice over real HTTP including both failure paths (409, 404), confirming the Stage 5 schema-bootstrap fix holds. OpenAPI reconfirmed accurate. `get_current_user_id` traced to exactly one call site with zero domain/application coupling — clean isolation, not a concern. Dependency-direction audit confirmed no circular dependencies (`agent → project`, `document → project`, one-directional). Comprehensive scope-creep sweep found nothing beyond the approved slice. A temporary static-analysis pass found only style-only nits (no defects; nothing changed, per this stage's instruction against style refactoring). **The first backend vertical slice is complete.** See `docs/journal/2026-09-04.md` (Session 8) and `docs/Timeline.md` (Milestone 14) for the full report.

**Post-completion (2026-09-06 to 2026-09-10):** manually verified end-to-end via `/docs` and real HTTP (confirmed the intended behavior of the one-Agent-per-user rule and a document upload). Committed to git as two commits — the pre-existing documentation backlog (governance, SRS, architecture, database, ADR-009) and the backend implementation itself — and pushed to `origin/main` on GitHub (`https://github.com/PeterGado/ScholarOS`).

---

### Milestone 7 — Real Authentication Boundary

| Dependency | Status |
| ---------- | ------ |
| Milestone 6 (Backend Implementation) | ✅ Complete, committed, and pushed |
| ADR-010 (Authentication Boundary — Single-User Session Model) | ✅ Accepted (2026-09-10); corrects Database Baseline v1 (`User.password_hash`) and Architecture Baseline v1 (§15.4) |

**Readiness:** ADR-010 is accepted. It authorizes a real Authentication Boundary for the MVP's single, pre-provisioned user — real login via the already-specified Session entity (`04_Logical_Data_Model.md` §3.2, previously designed but unimplemented), password hashing via `bcrypt`, credentials synced from configuration (`AUTH_USERNAME`, `AUTH_PASSWORD_HASH`) rather than hard-coded or self-registered. No registration, password reset, email verification, or multi-account capability is in scope — those are explicitly deferred, matching the MVP's own multi-user exclusion.

**Stage 1 — Implementation Planning: Complete.** Full current-state inspection, boundary design, credential-provisioning semantics, session-token-storage recommendation (hashed, not raw), authorization/ownership strategy, file impact matrix, and an 8-stage implementation staging proposal recorded in [docs/Authentication_Implementation_Plan.md](Authentication_Implementation_Plan.md). Verdict: READY FOR STAGE 2. A self-review afterward found and fixed 7 completeness/precision issues in ADR-010 (no substantive decision changed).

**Stage 2 — Authentication Boundary Scaffolding: Complete.** `backend/app/auth/` now exists as a self-contained boundary package (`entities.py`, `identity.py`, `exceptions.py`, `hashing.py`, `tokens.py`, `repository.py` [interfaces only], `service.py`, `schemas.py`) — `AuthService.login()/logout()/verify_token()` are fully implemented and unit-tested against fakes, but not yet wired to real persistence (Stage 3) or HTTP routes (Stage 5). `bcrypt` added as a dependency; `Settings` gained `auth_username`/`auth_password_hash`; `backend/README.md` documents how to generate the required hash (no real credential anywhere in source, `.env.example`, or tests). Before scaffolding, a real contradiction in ADR-010 was found and fixed: its Compliance Rules and Consequences referenced "expiry/idle-timeout" language that contradicted Decision item 2's actual rule (no automatic expiry, ever, in this milestone) — corrected directly in ADR-010 (not a new ADR; a same-day drafting-error fix, not a reconsideration of the decision). 87/87 tests pass (66 prior + 21 new); app still boots; dependency direction verified clean (`app/auth` has zero FastAPI/HTTP dependency and zero coupling to `app/modules`; domain/application layers remain completely unaware of it). `core/dependencies.py`, `app/api/router.py`, `app/database/session.py`, and `main.py` are all deliberately untouched — that wiring is Stages 3-6. Nothing committed to git yet.

**Stage 3 — Authentication Persistence: Complete.** `app/auth/models.py` (`AuthSession` ORM, table `sessions`, no `expires_at` or timeout column by design) and `app/auth/infrastructure.py` (`SqlAlchemyAuthSessionRepository`, `SqlAlchemyUserCredentialLookup`) implement Stage 2's interfaces against real SQLite. `User` gained `password_hash` (ADR-010-authorized; a transitional empty-string default keeps the untouched bootstrap path working — never a valid bcrypt hash, overwritten with a real one by Stage 4). `AuthSession` registered in `init_db()`. **105/105 tests pass** (87 prior + 18 new), including the mandatory regression test proving a session with a year-stale `last_active_at` remains valid against real persistence — no automatic expiry, exactly as decided. Dependency direction, no-secret-logging, and fresh-database initialization (via `sqlalchemy.inspect`, not assumption) all verified. `core/dependencies.py`/`api/router.py`/`main.py` confirmed untouched via `git diff`. Nothing committed to git yet.

**Stage 4 — Credential Provisioning & Synchronization: Complete.** `app/auth/provisioning.py`'s `sync_configured_user()` implements ADR-010's "database row is a cache of configuration" rule directly: create-if-missing, update-if-changed (including a changed username — the existing row is renamed, not duplicated, per that same wording), fail-fast validation (blank/malformed/partial config all raise before touching the database, never silently falling back), a no-op when unconfigured (acceptable pre-Stage-6). Wired into `main.py`'s real startup lifespan. Caught and fixed a real latent bug in the process: a stale `SessionLocal` import binding that would have been invisible to this codebase's own test-monkeypatching convention. **134/134 tests pass** (105 prior + 29 new), including real full-lifespan startup tests (fresh config, four repeated startups still produce exactly one user, fail-fast on a malformed hash). `User.password_hash`'s transitional empty-string default is now only relevant when auth is left unconfigured. `core/dependencies.py`, `api/router.py`, and both business routes confirmed untouched via `git diff`. Nothing committed to git yet.

**Stage 5 — Login / Logout HTTP API: Complete.** `POST /auth/login` (200, returns `{access_token, token_type}`) and `POST /auth/logout` (204) are live, thin routes over `AuthService`; every "no valid session presented" case (missing/malformed/wrong-scheme header, unknown token, ended token) collapses into one `InvalidSessionError` → 401, documented as a deliberate simplification. **A real bug was found and fixed via real-HTTP testing, not papered over:** `AuthSessionRepository` only ever flushed, never committed — invisible across Stage 2-4's shared-session tests, fatal the moment login and logout became genuinely separate HTTP requests (login would succeed, logout on that same token would then 401 instead of 204). Fixed by giving `AuthService` a `UnitOfWork`, the same pattern every other use case in this codebase already uses. All six mandatory manual scenarios (successful login, wrong password, unknown username, token accepted, logout, token-reuse-fails) verified over real `uvicorn`, not just `TestClient`. **153/153 tests pass** (134 prior + 19 new). `get_current_user_id`'s body, both business routes, and both application use cases confirmed untouched via `git diff` — its docstring was corrected (no behavior change) since it previously said "no such module exists," which is no longer true. Nothing committed to git yet.

---

## Risks

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| Architecture details may need refinement during design phases | Could delay downstream design work | Continue traceability checks; ADR set now records decisions for database/API design |
| Technology decisions unvalidated by implementation | Stack choices (ADR-002) may need adjustment during backend engineering | Validate during implementation; changes recorded via ADR amendment process |
| Retrieval is vector-only, not hybrid (ADR-005 Decision 1 requires lexical + semantic, fused) | Retrieval quality may be lower for exact-term/quotation queries than the fully hybrid design targets; a real, deliberate gap, not an oversight — flagged in Stage 8, re-confirmed in Stage 9 | Scope and authorize a dedicated lexical + RRF fusion stage before treating retrieval as feature-complete; ADR-005's fusion contract was designed to make this addable without a redesign |
| Governance framework exercised once | May reveal gaps during implementation | Continue self-executing session protocol; record lessons in journal |
| No standalone API contract review gate before code (ADR-008) | Contract review now happens via code review (L1/L2) rather than a dedicated document milestone | Escalate any architecturally significant API decision (auth model, versioning, protocol, service-boundary change) to a new ADR per ADR-008 item 5, rather than deciding it silently |
| No formal human (non-AI) review of Database Baseline v1 yet | Milestone-level assurance rests on recorded AI review passes (per `docs/database/08` §13) | Recommended before or during early backend implementation |
| No migration tooling (Alembic) exists yet; schema changes rely on `create_all` | Acceptable at MVP/SQLite scale (ADR-004); would block a real PostgreSQL cutover | Introduce Alembic before any production multi-environment deployment |

---

## Immediate Next Steps

Milestone 6 is complete, committed, and pushed. Milestone 7 (Real Authentication Boundary) has an accepted ADR (ADR-010), a complete implementation plan, and Stages 2-6 complete (`app/auth/` boundary, persistence, credential provisioning, login/logout HTTP API, and now real authenticated identity wired into `get_current_user_id`, `/agents`, and document upload with ownership enforcement) — Stage 7-8 remain, gated on explicit authorization:

1. **Await explicit authorization for the next stage.** The originally-sketched Stage 7 (Authorization/Ownership) is now substantially covered by Stage 6 Phase 5's document-ownership check; what remains per `docs/Authentication_Implementation_Plan.md`'s 8-stage table is Stage 8 (full regression, fresh-environment real-HTTP exercise, security review re-confirmation, OpenAPI re-inspection, governance sync) — subject to whatever the next stage prompt actually specifies.
2. Continue escalating any architecturally significant API decision (authentication model, versioning scheme, protocol, service-boundary change) to a new ADR before implementing it, per ADR-008 item 5 — unchanged going forward.
3. Other next-milestone choices remain open and unstarted: frontend integration, Backend Slice 2 (Knowledge/Writing-Style ingestion), a human L3 review of Database Baseline v1 (carried over from `docs/database/08` §14 and the 2026-09-04 audit).
4. Known open items to resolve opportunistically, not urgently: document `format`'s accepted values are undocumented above the implementation layer; no migration tooling (Alembic) exists yet.

---

## References

* [Documentation Index](READme.md)
* [Baseline Register](Baseline_Register.md)
* [Engineering Journal](journal/README.md)
* [Engineering Timeline](Timeline.md)
* [ADR-001](adr/ADR-001_Separation_of_Requirements_Architecture_and_Implementation.md)
* [ADR-008 — API Contract Governance During Backend Implementation](adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md)
* [ADR-010 — Authentication Boundary, Single-User Session Model](adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md)
* [Governance Framework](governance/)
* [SRS](srs/)
