# Backend Implementation Plan

**Status:** Active — Stage 1 (Implementation Planning)
**Milestone:** Milestone 6 — Backend Implementation
**Governs:** The first vertical slice only. Not a new architecture document; not frozen; supersedable by later planning sessions as later slices are scoped. Does not modify any frozen baseline.
**Authoritative sources:** `docs/architecture/05_Backend_Architecture.md` (§4.1 Domain Inventory, §7 AI Service Layer, §10 Document Service, §11 Project Service, §22 Agent Service), `docs/database/04_Logical_Data_Model.md`, ADR-002, ADR-003, ADR-004, ADR-006, ADR-008, ADR-009.

---

## 1. Purpose

This document records the reconciled backend directory structure and scope decisions for the **first vertical slice**, following a review of a proposed structure against the corrected Database Baseline v1 / Architecture Baseline v1. It exists so implementation does not re-litigate module boundaries, upload scope, or naming while Stages 2–6 are underway.

---

## 2. First Vertical Slice — Scope Decision

**Slice: Agent Creation (with its one Project, topic captured at creation) → Research Document Upload.**

Three upload categories exist in the frozen model: Research Document (Project-scoped, via Document Service §10), reference/similar documents (Agent-scoped, via Knowledge Service §8), and writing-style documents (Agent-scoped, via Author Profile). Only **Research Document upload** is in scope for this first slice.

**Rationale:**
- Document Service (§10) is CRUD-only — register, metadata, status, list, remove — with no AI Service Layer or Provider Abstraction dependency.
- Knowledge and Author Profile ingestion both require the AI Service Layer (§7), Provider Abstraction, and (per ADR-006) asynchronous processing via Work Item/outbox — materially more machinery.
- A first slice should prove the full stack (API → domain → application → infrastructure → database → file storage) on the simplest possible path before introducing the AI provider seam and async dispatch.
- Reference-document and writing-style ingestion become **Slice 2**, scoped separately once this slice is validated.

This is a scope/sequencing decision within already-approved MVP requirements (MVP-029, MVP-030, DR-037–039), not a new architectural decision — no ADR required (ADR-008's escalation criteria: auth model, versioning, protocol, service-boundary change — none apply here).

---

## 3. Module Structure (corrected)

Each module mirrors one Domain Inventory row (§4.1) and carries its own `domain/`, `application/`, `infrastructure/`, `interface/` layers per §3 (Layered Architecture). Only the modules needed for Slice 1 are scaffolded now; the rest of the Domain Inventory (Knowledge, Memory, Conversation, Capability, Review, Author Profile, Configuration) is scaffolded when its slice arrives.

```
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   └── exceptions.py
│   │
│   ├── api/
│   │   ├── router.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── agents.py
│   │       └── documents.py
│   │
│   ├── modules/
│   │   ├── agent/          # Agent Service, §22
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── interface/
│   │   ├── project/        # Project Service, §11 — depends on agent
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   ├── infrastructure/
│   │   │   └── interface/
│   │   └── document/       # Document Service, §10 — depends on project
│   │       ├── domain/
│   │       ├── application/
│   │       ├── infrastructure/
│   │       └── interface/
│   │
│   ├── database/
│   │   ├── session.py
│   │   └── base.py
│   │
│   └── storage/
│       └── filesystem.py   # ADR-004 object store, MVP: local filesystem
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── pyproject.toml
├── .env.example
└── README.md
```

**Deferred, not scaffolded in Slice 1:** `app/ai/` (Provider Abstraction, §7.3, AIR-040 to AIR-042), `app/workers/` (Work Item / outbox, ADR-006), `modules/knowledge/`, `modules/author_profile/`, `modules/capability/`, `modules/memory/`, `modules/conversation/`, `modules/review/`, `modules/configuration/`. Each is introduced when its owning slice starts — not before.

**Boundary rule carried from §4.2:** each module owns its data and behavior; cross-module calls go through application-layer interfaces, not direct infrastructure access (e.g., `document` reaches `project` only through `project`'s application layer, never its ORM models directly).

---

## 4. API Routes (Slice 1)

Reflects Agent as the aggregate root/entry point for the MVP's 1:1:1 (User–Agent–Project) shape:

| Route | Service | Notes |
|---|---|---|
| `POST /agents` | Agent + Project | Creates Agent and its one permanent Project atomically; topic supplied in the request body, stored on Project (ADR-009 — Agent carries no topic copy). |
| `GET /agents/{agent_id}` | Agent | Retrieve workspace identity. |
| `POST /agents/{agent_id}/documents` | Document | Upload a Research Document (§10.1). |
| `GET /agents/{agent_id}/documents` | Document | List Research Documents for the Project. |
| `DELETE /agents/{agent_id}/documents/{document_id}` | Document | Remove, preserving referential integrity (DR-025). |

Routine API decision under ADR-008 — no new ADR. Nesting documents under `/agents/{agent_id}` rather than a separate `/projects/{project_id}` path is a Slice-1 convenience given the 1:1 permanent relationship; revisit only if a future slice needs direct Project addressing.

---

## 5. Naming Corrections

Applied against the workspace sketch reviewed in Step 2, to stay traceable to `04_Logical_Data_Model.md`:

- **"Project Topic"** → **Project** (topic is an attribute of Project, not a peer node; Agent carries no topic copy — ADR-009).
- **"Generated Content"** → **Draft / Draft Version / Review** (Logical Data Model vocabulary; out of scope for Slice 1 and Slice 2, applies to a future drafting slice).

---

## 6. What Slice 2 Will Need (forward note, not started)

Reference-document and writing-style-document upload, when scoped: `app/ai/providers/` (Provider Abstraction, ADR-002), `app/workers/work_items.py` (outbox dispatcher, ADR-006), `modules/knowledge/`, `modules/author_profile/`. Recorded here so Slice 1 scaffolding doesn't need to be reshaped to accommodate them — the module/layer pattern established in Section 3 already generalizes.

---

## 7. Traceability

- `docs/architecture/05_Backend_Architecture.md` §4.1, §7, §10, §11, §22
- `docs/database/04_Logical_Data_Model.md` §3.3 (Project), §3.19–3.21 (Configuration, Agent)
- ADR-002 (Technology Stack and Provider Abstraction), ADR-003 (Modular Monolith), ADR-004 (Storage and Memory Strategy), ADR-006 (Async Processing and Event Coordination), ADR-008 (API Contract Governance), ADR-009 (Agent and Project Domain Model Introduction)
- `docs/srs/10_MVP_scope.md` §3.11 (Agent Workspace, MVP-029, MVP-030)
