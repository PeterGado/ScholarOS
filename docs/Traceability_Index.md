# Traceability Index

**Purpose:** This lightweight index provides a navigation aid for the repository's governing documents, requirements, architecture, ADRs, and the next deferred milestones without creating a heavy maintenance burden.

## Authority and Governance

* [docs/governance/01_Project_Constitution.md](governance/01_Project_Constitution.md) — Highest authority; defines hierarchy, lifecycle, and separation of concerns.
* [docs/governance/04_Repository_Governance.md](governance/04_Repository_Governance.md) — Repository structure, naming, consistency rules, and frozen milestones.
* [docs/governance/11_Engineering_Responsibilities.md](governance/11_Engineering_Responsibilities.md) — Standing engineering responsibilities for self-executing sessions.
* [docs/Baseline_Register.md](Baseline_Register.md) — Baseline Register: frozen milestone baselines and their change paths.

## Product and Requirements

* [docs/vision/Vision.md](vision/Vision.md) — Product philosophy and long-term direction.
* [docs/srs/01_Introduction.md](srs/01_Introduction.md) — SRS purpose, scope, and traceability expectations.
* [docs/srs/04_Functional_Requirements.md](srs/04_Functional_Requirements.md) — Functional domain organization.
* [docs/srs/09_API_Requirements.md](srs/09_API_Requirements.md) — Conceptual API contract boundaries.

## Architecture and ADRs

* [docs/architecture/01_Architecture_Overview.md](architecture/01_Architecture_Overview.md) — Overall architecture baseline.
* [docs/architecture/03_Data_Architecture.md](architecture/03_Data_Architecture.md) — Conceptual data architecture baseline.
* [docs/architecture/05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) — Logical backend organization.
* [docs/adr/ADR-001_Separation_of_Requirements_Architecture_and_Implementation.md](adr/ADR-001_Separation_of_Requirements_Architecture_and_Implementation.md) — Foundational separation rule.
* [docs/adr/ADR-004_Storage_and_Memory_Strategy.md](adr/ADR-004_Storage_and_Memory_Strategy.md) — Storage and memory strategy for later design milestones.
* [docs/adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md](adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md) — API contracts are defined progressively during implementation, not a standalone milestone; architecturally significant API decisions still require a new ADR.
* [docs/adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md](adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md) — introduces Agent as the user's permanent workspace, narrows Project, and renames the capability registry to Capability/Capability Entry.
* [docs/adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md](adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md) — authorizes a real Authentication Boundary for the MVP's single pre-provisioned user, realized via the already-specified Session entity; not yet implemented.

## Database Design — COMPLETE AND FROZEN (Database Baseline v1)

* [docs/database/01_Database_Overview.md](database/01_Database_Overview.md) — Milestone constitution: purpose, scope, boundaries, layered document set (01–08), Authoritative Source Rule.
* [docs/database/02_Domain_Model.md](database/02_Domain_Model.md) — Business language: domains, purpose, responsibility, ownership, lifecycle, dependencies.
* [docs/database/03_Conceptual_Data_Model.md](database/03_Conceptual_Data_Model.md) — Conceptual entities, relationships, cardinalities, bounded contexts, business rules.
* [docs/database/04_Logical_Data_Model.md](database/04_Logical_Data_Model.md) — Logical relational structure: entities, attributes, keys, normalization, integrity, versioning/audit strategies.
* [docs/database/05_Constraints_and_Integrity.md](database/05_Constraints_and_Integrity.md) — Business-level integrity contract: state transitions, required/optional relationships, domain invariants.
* [docs/database/06_Physical_Design_Strategy.md](database/06_Physical_Design_Strategy.md) — Physical strategy: storage-category mapping, persistence, retention, archival, backup, recovery, growth.
* [docs/database/07_Database_Validation_and_Quality_Assurance.md](database/07_Database_Validation_and_Quality_Assurance.md) — Validation apparatus: review process, quality gates, acceptance criteria, defect catalog.
* [docs/database/08_Database_Design_Review_and_Readiness_Assessment.md](database/08_Database_Design_Review_and_Readiness_Assessment.md) — Milestone close-out: readiness verdict, freeze declaration, Database Baseline v1 definition, API design handoff.
* **Baseline:** Database Baseline v1 — frozen 2026-08-07 (see [Baseline Register](Baseline_Register.md)).

## Current Milestone Guidance

* **Backend Implementation (Milestone 6) — First vertical slice COMPLETE.** Ratified 2026-09-04 (see [docs/journal/2026-09-04.md](journal/2026-09-04.md) and [ADR-008](adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md)), implemented and validated 2026-09-04 to 2026-09-05 across Stages 1-6 (see [docs/Timeline.md](Timeline.md) Milestone 14). The completed vertical slice is Agent Creation (with its one Project) → Document Upload, in `backend/` — committed and pushed to `origin/main`; 66/66 tests passing. API contracts were defined progressively during implementation as code (not a standalone milestone), and remain traceable to SRS Chapter 9, `05_Backend_Architecture.md`, ADR-002, and the corrected Database Baseline v1 ([ADR-009](adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md)) via the handoff contract in document 08 §21/§23. The reconciled backend module structure, Slice-1 scope decision, API route shape, and naming corrections are recorded in [docs/Backend_Implementation_Plan.md](Backend_Implementation_Plan.md).
* **Real Authentication Boundary (Milestone 7) — Stage 6 of 8 complete.** [ADR-010](adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md) (2026-09-10) authorizes a real Authentication Boundary for the MVP's single pre-provisioned user, realized via the already-specified Session entity (`04_Logical_Data_Model.md` §3.2) rather than a new mechanism. The full implementation plan (current-state findings, boundary design, staging) is recorded in [docs/Authentication_Implementation_Plan.md](Authentication_Implementation_Plan.md). Stages 2-4 (Scaffolding, Persistence, Credential Provisioning), Stage 5 (`POST /auth/login`/`POST /auth/logout`, live over real HTTP), and Stage 6 (Authenticated Identity Integration — `get_current_user_id` now resolves real session identity; `/agents` and `/projects/{project_id}/documents` both require authentication; document upload enforces Project→Agent→User ownership; the bootstrap identity path is fully removed) are complete: 164/164 tests passing. Stage 8 (final regression/validation) remains, gated on explicit authorization.
* **Backend Slice 2 (Knowledge Processing Pipeline) — Stages 1-4 of 9 complete.** A readiness review (`docs/Backend_Slice2_AI_Readiness_Review.md`) confirmed every entity Slice 2 needs — Knowledge Element, Knowledge Chunk, Chunk Evidence Link, Work Item — is already specified in the frozen Database Baseline v1; no new ADR is required. The implementation plan (`docs/Backend_Slice2_Implementation_Plan.md`) records the two configuration-level realization choices ADR-002/ADR-004 deferred (first AI provider: OpenAI-compatible API; vector index: brute-force cosine over a plain table) and a staged build sequence, corrected to 9 stages after Stage 4 found a genuine conflict between Knowledge Chunk's not-null Knowledge Element FK and every Element type requiring semantic interpretation — resolved by introducing a transient `TextChunkCandidate` value object rather than persisting fake semantic records; real Knowledge Element/Chunk/Evidence Link persistence moved to a renamed Stage 5. Stage 2 (Work Item + Knowledge Element/Chunk/Evidence Link ORM realization), Stage 3 (Provider Abstraction gateway), Stage 4 (mechanical extraction/normalization/chunking, no AI call, no knowledge persisted), Stage 5 (Semantic Extraction & Persistence — one AI provider call per Stage 4 chunk, atomic and idempotent-by-detection, real evidence-linked Knowledge Element/Chunk persistence), Stage 6 (Async Dispatch — upload enqueues a Work Item; an in-process executor runs Stages 4+5 together; `processing_status` transitions are real), Stage 7 (Embedding & Vector Index — every persisted chunk is embedded and genuinely retrievable by similarity, brute-force cosine, no new dependency), Stage 8 (Retrieval Endpoint — `GET /knowledge/search`, authenticated and agent-scoped, vector-only per the project owner's explicit Stage 8 scope, a flagged partial realization of ADR-005's hybrid-retrieval decision with lexical+RRF fusion deferred, not abandoned), and **Stage 9 (Final Slice 2 Validation — complete)** are done: 311/311 tests passing, including a genuine real-provider end-to-end run against a live Gemini account (via a newly-added `GoogleGenAIProvider`, now the default provider) exercising the full upload→process→understand→retrieve path. A full architecture/ADR compliance sweep passed except the already-known ADR-005 partial realization, which remains open pending the project owner's decision on a future lexical+RRF fusion stage. **Slice 2 (Knowledge Processing Pipeline) is complete.** The next milestone, Project Writing, is explicitly out of Slice 2's scope and awaits its own authorization.
* Frontend implementation, testing at scale, deployment automation, and infrastructure — Deferred to their own future milestone scope.

## Maintenance Rule

This index is intentionally lightweight. It should be updated only when the authoritative documents above change in a way that materially affects navigation or traceability.
