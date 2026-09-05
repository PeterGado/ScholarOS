# ScholarOS — Project Dashboard

**Status:** Active
**Current Phase:** Milestone 6 — Backend Implementation: First Vertical Slice COMPLETE (Agent Creation (with its one Project) → Document Upload); awaiting authorization for the next milestone
**Last Updated:** 2026-09-05

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
| ✅ **Backend Implementation (Milestone 6)** | **First vertical slice COMPLETE: Agent Creation (with its one Project) → Document Upload — 66/66 tests passing, validated over real HTTP from a fresh environment; not committed to git** |
| → Frontend Implementation | Pending (deferred until explicit authorization; backend-first per `decision_01.md`) |
| → Real Authentication | Pending (current backend uses a disclosed single-user placeholder, `get_current_user_id`; not designed or implemented) |
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
| **Implementation** | Backend + Frontend | ✅ Backend: first vertical slice complete (66/66 tests, not committed); Frontend: deferred |

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

**Stage 6 — Testing, Integration & Final Backend Validation: Complete.** Full regression (66/66 tests, 0 failed, 0 skipped) reconfirmed; a genuine fresh-environment run (brand-new database, never-used storage path) exercised the entire slice over real HTTP including both failure paths (409, 404), confirming the Stage 5 schema-bootstrap fix holds. OpenAPI reconfirmed accurate. `get_current_user_id` traced to exactly one call site with zero domain/application coupling — clean isolation, not a concern. Dependency-direction audit confirmed no circular dependencies (`agent → project`, `document → project`, one-directional). Comprehensive scope-creep sweep found nothing beyond the approved slice. A temporary static-analysis pass found only style-only nits (no defects; nothing changed, per this stage's instruction against style refactoring). **The first backend vertical slice is complete.** See `docs/journal/2026-09-04.md` (Session 8) and `docs/Timeline.md` (Milestone 14) for the full report. Nothing has been committed to git. No subsequent milestone (frontend, real authentication, Slice 2, deployment) has begun.

---

## Risks

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| Architecture details may need refinement during design phases | Could delay downstream design work | Continue traceability checks; ADR set now records decisions for database/API design |
| Technology decisions unvalidated by implementation | Stack choices (ADR-002) may need adjustment during backend engineering | Validate during implementation; changes recorded via ADR amendment process |
| Retrieval quality unproven | Hybrid retrieval (ADR-005) needs empirical tuning | Create a golden query evaluation set during implementation |
| Governance framework exercised once | May reveal gaps during implementation | Continue self-executing session protocol; record lessons in journal |
| No standalone API contract review gate before code (ADR-008) | Contract review now happens via code review (L1/L2) rather than a dedicated document milestone | Escalate any architecturally significant API decision (auth model, versioning, protocol, service-boundary change) to a new ADR per ADR-008 item 5, rather than deciding it silently |
| No formal human (non-AI) review of Database Baseline v1 yet | Milestone-level assurance rests on recorded AI review passes (per `docs/database/08` §13) | Recommended before or during early backend implementation |
| `get_current_user_id` is a single-bootstrap-user placeholder, not real authentication | Every request currently resolves to the same identity; a second Agent-creation call in any session is always a 409, and there is no way for a real second user to exist yet | Design a real Authentication Boundary (05_Backend_Architecture.md §15) before any multi-user work; the placeholder is isolated to one `core/dependencies.py` function with one call site, so replacing it should not require touching domain/application code |
| Backend implementation exists only on disk, not in git | Work could be lost if the environment is reset before a deliberate commit | Commit only when explicitly instructed (per session convention); nothing has been committed as of this entry |

---

## Immediate Next Steps

The first backend vertical slice (Milestone 6) is complete. Remaining items are next-milestone choices, not blockers on what has been built:

1. **Await explicit authorization** for whichever comes next — frontend integration, a real Authentication Boundary design, Backend Slice 2 (Knowledge/Writing-Style ingestion), or a human L3 review of Database Baseline v1 (carried over from `docs/database/08` §14 and the 2026-09-04 audit). None of these have been started.
2. Continue escalating any architecturally significant API decision (authentication model, versioning scheme, protocol, service-boundary change) to a new ADR before implementing it, per ADR-008 item 5 — unchanged going forward.
3. When a commit is explicitly requested, review `git status`/`git diff` on `backend/` first (nothing has been committed yet).
4. Known open items to resolve opportunistically, not urgently: document `format`'s accepted values are undocumented above the implementation layer; `User`'s long-term module home (a real Authentication Boundary) is unresolved; no migration tooling (Alembic) exists yet.

---

## References

* [Documentation Index](READme.md)
* [Baseline Register](Baseline_Register.md)
* [Engineering Journal](journal/README.md)
* [Engineering Timeline](Timeline.md)
* [ADR-001](adr/ADR-001_Separation_of_Requirements_Architecture_and_Implementation.md)
* [ADR-008 — API Contract Governance During Backend Implementation](adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md)
* [Governance Framework](governance/)
* [SRS](srs/)
