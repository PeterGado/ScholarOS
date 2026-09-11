# ScholarOS Documentation

**Version:** 1.7.0  
**Status:** Active  
**Last Updated:** 2026-09-10  
**Latest ADR:** ADR-010 — Authentication Boundary, Single-User Session Model
**Governance Framework:** Engineering Governance Framework v2.0 — Active

---

## Overview

Welcome to the official documentation for **ScholarOS**.

This documentation serves as the single source of truth for the design, development, implementation, and future evolution of ScholarOS.

All contributors—human or AI—must consult these documents before proposing, implementing, or modifying any feature.

---

## Documentation Hierarchy

If multiple documents appear to conflict, the following order of precedence shall apply:

1. Project Constitution
2. AI Engineering Contract
3. AI Engineering Standards
4. Repository Governance
5. Vision Document
6. Software Requirements Specification (SRS)
7. Architecture Documentation
8. Architecture Decision Records (ADR)
9. Source Code

Higher-level documents always take precedence over lower-level documents.

**Note:** The active governance framework consists of 12 documents (01–12). In the full hierarchy, the governance layer sits between the ADR layer and Source Code. See `docs/governance/01_Project_Constitution.md` Section 5 for the complete, authoritative hierarchy.

---

## Repository Independence and Milestone Boundaries

This repository now explicitly distinguishes between documentation/governance hardening and the future milestone artifacts that follow it.

* Milestone 5: Database Design is **complete and frozen** as Database Baseline v1 (`docs/database/01`–`08`, recorded in [docs/Baseline_Register.md](Baseline_Register.md)).
* An Independent Repository Audit (`docs/journal/2026-09-04.md`) concluded the repository is **READY FOR BACKEND IMPLEMENTATION**, and this was ratified as **[ADR-008](adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md)**: API Design is **not** a standalone documentation milestone. **Milestone 6 (Backend Implementation) is complete**, committed, and pushed to `origin/main` — the first vertical slice, Agent Creation (with its one Project) → Document Upload (corrected 2026-09-04 by ADR-009).
* **Milestone 7 (Real Authentication Boundary) is in progress.** [ADR-010](adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md) (2026-09-10) authorizes a real Authentication Boundary for the MVP's single pre-provisioned user, realized via the Database Baseline's already-specified Session entity. Stages 2-6 are complete — login/logout are live over real HTTP, and `get_current_user_id` now resolves real authenticated identity, with `/agents` and document upload both requiring authentication and enforcing ownership; see `docs/Authentication_Implementation_Plan.md` for the full staged plan.
* **Backend Slice 2 (Knowledge Processing Pipeline) is complete and validated (2026-09-11)**, built on Milestone 7's authentication boundary. Real document upload → mechanical extraction/chunking → AI semantic extraction → evidence-linked Knowledge Element/Chunk persistence → embedding → agent-scoped authenticated retrieval (`GET /knowledge/search`), verified with both fake providers (311 automated tests) and a real Gemini account end to end. One deliberate, flagged gap remains open: retrieval is vector-only, not yet the full hybrid (lexical + semantic, fused) design ADR-005 specifies — see `docs/Backend_Slice2_Implementation_Plan.md` and the 2026-09-11 journal entries for the full staged history and compliance review. The next milestone, Project Writing, is out of Slice 2's scope and not yet started.
* The authoritative chain is now: Project Constitution → Governance Framework → Vision → SRS → Architecture and ADRs → Database design milestone documents (frozen baseline) → Implementation, with API contracts defined progressively during implementation as code (Pydantic/FastAPI models, per ADR-002 and ADR-008), remaining traceable to SRS Chapter 9 and `05_Backend_Architecture.md`.
* The architecture set (01–07), the ADR set (ADR-001 to ADR-010), and the database set (01–08) remain the authoritative baseline for the current repository phase.
* API contracts are an engineering activity within implementation, not a prerequisite milestone (ADR-008); architecturally significant API decisions (authentication model, versioning scheme, protocol, service-boundary changes) still require a new ADR.
* Frontend implementation, testing at scale, and deployment automation remain intentionally deferred.
* A lightweight cross-reference index is maintained in [docs/Traceability_Index.md](Traceability_Index.md) to support navigation and traceability without creating a heavy maintenance burden.

## Reading Order

All contributors should review the documentation in the following order before beginning work.

### Phase 0 — Engineering Governance Framework (Read First)

```md
docs/governance/
```

| Document | Purpose |
| --------- | --------- |
| 01_Project_Constitution.md | Foundational project identity, philosophy, and governing principles. Highest authority. |
| 02_AI_Engineering_Contract.md | Binding contract for all AI Software Engineers. |
| 03_AI_Engineering_Standards.md | Quality and engineering standards. |
| 04_Repository_Governance.md | Repository structure, naming, and consistency rules. |
| 05_Definition_of_Done.md | Mandatory completion criteria for all tasks. |
| 06_Engineering_Report_Standard.md | Mandatory Engineering Report template. |
| 07_Review_Checklist.md | Review and validation process. |
| 08_AI_Roles_and_Responsibilities.md | Multi-AI collaboration framework. |
| 09_Documentation_Standards.md | Documentation formatting and conventions. |
| 10_Prompting_Guidelines.md | Prompt engineering standards. |
| 11_Engineering_Responsibilities.md | Standing engineering responsibilities executed automatically in self-executing sessions. |
| 12_Master_Execution_Prompt.md | Standard session-initiation template for self-executing engineering sessions. |

---

### Phase 1 — Product Vision

```md
docs/vision/
```

| Document | Purpose |
| --------- | --------- |
| Vision.md | Defines why ScholarOS exists, the problem it solves, product philosophy, and long-term vision. |

---

### Phase 2 — Software Requirements Specification

```md
docs/srs/
```

| Document | Purpose |
| --------- | --------- |
| 01_Introduction.md | Defines the purpose, scope, terminology, and governance of the SRS. |
| 02_Product_Overview.md | Defines ScholarOS as a product, its users, objectives, and boundaries. |
| 03_Overall_System_Description.md | Describes the system from a high-level engineering perspective. |
| 04_Functional_Requirements.md | Defines what the system must do. |
| 05_Non-Functional_Requirements.md | Defines quality requirements such as performance, security, and scalability. |
| 06_AI_Requirements.md | Defines AI-specific behaviors and constraints. |
| 07_Data_Requirements.md | Defines the data model and information managed by ScholarOS. |
| 08_User_Workflows.md | Defines user interactions and workflows. |
| 09_API_Requirements.md | Defines system interfaces and service contracts. |
| 10_MVP_scope.md | Defines the boundaries of the first release. |
| 11_Future_Roadmap.md | Defines planned future capabilities. |

---

### Phase 3 — Architecture

```md
docs/architecture/
```

Contains:

* Architecture Overview (01)
* System Components (02)
* Data Architecture (03)
* AI Architecture (04)
* Backend Architecture (05)
* Frontend Architecture (06)
* Operational Architecture (07)
* Future architecture extensions and ADRs

**Set status:** Architecture documents 01–07 were frozen at Milestone 4 (04_Repository_Governance.md, §4.4). The close-out audit (journal Session 4) passed on 2026-08-06, formally freezing the architecture set (01–07) and the ADR set (ADR-001 to ADR-007). Future architecture documents will be numbered sequentially (08, 09, …) and created only when a later milestone genuinely requires them; new architectural decisions are recorded as ADRs. **Corrected 2026-09-04 by ADR-009** (Agent workspace introduction; Agent/Agent Capability renamed to Capability/Capability Entry) — documents 02, 03, 04, 05 updated in place per the frozen-baseline correction discipline; the freeze itself is preserved, not lifted. **Further corrected 2026-09-10 by ADR-010** (Authentication Boundary realized mechanism) — document 05 gained §15.4.

---

### Phase 4 — Database

```md
docs/database/
```

Contains:

* 01_Database_Overview.md — milestone constitution: purpose, scope, principles, boundaries, layered document set (01–08), and the Authoritative Source Rule
* 02_Domain_Model.md — complete: the business language of ScholarOS (twelve domains: purpose, responsibility, ownership, lifecycle, dependencies)
* 03_Conceptual_Data_Model.md — complete: conceptual entities, relationships, cardinalities, bounded contexts, and business rules
* 04_Logical_Data_Model.md — complete: the implementation-independent logical relational contract (entities, attributes, keys, integrity, versioning, audit)
* 05_Constraints_and_Integrity.md — complete: state transitions, required/optional relationships, and thirteen domain invariants
* 06_Physical_Design_Strategy.md — complete: mapping onto the approved storage categories; persistence, retention, archival, backup, recovery, growth strategies
* 07_Database_Validation_and_Quality_Assurance.md — complete: review process, quality gates, acceptance criteria, defect catalog
* 08_Database_Design_Review_and_Readiness_Assessment.md — complete: close-out, readiness verdict, freeze declaration, API design handoff
* **Set status: COMPLETE AND FROZEN as Database Baseline v1** (recorded in [Baseline_Register.md](Baseline_Register.md)); **corrected 2026-09-04 by ADR-009** (Agent workspace introduction, Project narrowing, Capability rename) — see `08` §23 for the full correction record; **further corrected 2026-09-10 by ADR-010** (`User.password_hash`) — see `08` §24
* Every database document after 01 treats all previously completed database documents as authoritative sources and extends the design by adding the next level of detail, without duplicating content

---

### Phase 5 — API

```md
docs/api/
```

**Not a prerequisite milestone.** Per [ADR-008](adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md), API contracts are defined progressively during backend implementation as Pydantic/FastAPI code; the generated OpenAPI schema is the living API contract, traceable to SRS Chapter 9 and `05_Backend_Architecture.md`. `docs/api/` remains reserved for a future, architecturally significant, externally-published API specification (e.g., at the institutional/multi-tenant stage, SRS Chapter 11 Phase 6) — it is not populated during the MVP.

---

### Phase 6 — AI Agents

```md
docs/agents/
```

Contains documentation for the intelligent subsystems that power ScholarOS.

Examples include:

* Knowledge Manager
* Author Profile Builder
* Context Builder
* Writing Engine
* Review Engine
* Citation Assistant
* Project Memory

---

### Phase 7 — Architecture Decision Records

```md
docs/adr/
```

Contains significant engineering decisions made throughout the project's lifecycle:

* ADR-001 — Separation of Requirements, Architecture, and Implementation (foundational)
* ADR-002 — Technology Stack and Provider Abstraction
* ADR-003 — Service Organization (Modular Monolith)
* ADR-004 — Storage and Memory Strategy
* ADR-005 — Retrieval and Search Strategy
* ADR-006 — Async Processing and Event Coordination
* ADR-007 — Deployment Strategy
* ADR-008 — API Contract Governance During Backend Implementation
* ADR-009 — Agent and Project Domain Model Introduction (corrects Database Baseline v1 and Architecture Baseline v1)
* ADR-010 — Authentication Boundary, Single-User Session Model (further corrects Database Baseline v1 and Architecture Baseline v1; Milestone 7, Stage 6 of 8 complete — `get_current_user_id` resolves real authenticated identity; `/agents` and document upload require authentication and enforce ownership)

---

## Development Principles

All contributors should follow these principles.

* Documentation is the source of truth.
* Requirements precede implementation.
* Architecture precedes code.
* Every feature must map to an approved requirement.
* Components should remain modular.
* AI providers should remain replaceable.
* Human review is required before approving major documentation or code changes.

---

## AI Contributor Guidelines

AI assistants contributing to ScholarOS should:

1. Read the documentation before performing work.
2. Avoid contradicting approved documents.
3. Raise ambiguities rather than making assumptions.
4. Preserve consistency across documentation.
5. Recommend updates when requirements appear incomplete.
6. Clearly distinguish between requirements, design, and implementation.

---

## Current Project Status

Refer to the following files for the active development state:

| File | Purpose |
| ---- | ------- |
| `docs/Project_Status.md` | Current phase, milestones, progress, risks, next steps |
| `docs/Baseline_Register.md` | Frozen milestone baselines and their change paths |
| `docs/journal/README.md` | Engineering journal index and daily session records |
| `docs/Timeline.md` | Milestone history and dependency graph |

These files identify:

* Current milestone
* Current task
* Completed work
* Upcoming work

---

## Documentation Maintenance

Documentation is a living artifact.

Whenever a requirement, architecture decision, or implementation changes, the corresponding documentation should be reviewed and updated to maintain consistency across the project.

---

## Final Principle

ScholarOS follows one core engineering philosophy:

> **Understand First. Build Second.**

Every contributor—human or AI—should fully understand the approved documentation before proposing new designs or implementing code.
