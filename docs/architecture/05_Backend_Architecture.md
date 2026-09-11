# Backend Architecture

**Document:** 05_Backend_Architecture.md

**Status:** Active

**Date:** 2026-08-05

---

## 1. Purpose

This document defines the logical organization of the ScholarOS backend. It describes how backend responsibilities are partitioned into domains and services, how those services coordinate, and how the intelligence layer connects to the rest of the system.

This document is a logical architecture. It does not prescribe programming languages, frameworks, deployment models, storage technologies, or API protocols. It defines the boundaries, responsibilities, and interaction principles that an implementation must satisfy.

It complements the Milestone 1 architecture set:

* [01_Architecture_Overview.md](01_Architecture_Overview.md) — overall layered architecture
* [02_System_Components.md](02_System_Components.md) — conceptual components
* [03_Data_Architecture.md](03_Data_Architecture.md) — conceptual data domains
* [04_AI_Architecture.md](04_AI_Architecture.md) — intelligence operating model

---

## 2. Backend Philosophy

The ScholarOS backend exists to protect the integrity, continuity, and traceability of the research workflow.

The backend philosophy is:

* **The workflow is the contract.** Backend organization follows the research workflow, not implementation convenience.
* **Domains remain distinct.** Research material, knowledge, memory, conversation, drafting, and review concerns stay separated.
* **Intelligence is a service, not the core.** The intelligence layer supports the workflow through well-defined service boundaries.
* **Everything is traceable.** The backend preserves provenance from source to output.
* **The backend is replaceable in parts.** Each service is independently understandable and replaceable.
* **The backend is testable.** Service boundaries are defined so that behavior can be validated in isolation.

This philosophy aligns with SRS Chapter 5 (NFR-013 to NFR-018: maintainability, modularity, extensibility) and the MVP philosophy of backend-first implementation (SRS Chapter 10, Section 2).

---

## 3. Layered Architecture

The backend is organized into logical layers. Each layer depends only on the layers below it.

### 3.1 Backend Layers

| Layer | Responsibility |
|-------|---------------|
| 1. Service Boundary Layer | Exposes the system's capabilities to the frontend and external actors through conceptual service contracts (SRS Chapter 9) |
| 2. Orchestration Layer | Coordinates multi-service workflows, including the intelligence lifecycle |
| 3. Domain Service Layer | Implements the functional domains: project, document, knowledge, memory, conversation, agent, review |
| 4. Intelligence Layer | Provides reasoning, retrieval, context assembly, and generation support (see [04_AI_Architecture.md](04_AI_Architecture.md)) |
| 5. Data Access Layer | Provides a technology-independent boundary for persistence across all data domains (API-032, API-033) |

### 3.2 Layering Rules

* Dependencies flow downward only. Upper layers depend on lower layers through their defined boundaries.
* No layer reaches across another layer except through defined interfaces.
* The intelligence layer is accessed through the orchestration layer so that intelligence behavior remains coordinated and observable.
* The data access layer isolates persistence technology behind a stable boundary (API-032, API-033).

---

## 4. Domain Boundaries

The backend is partitioned into the following logical domains, aligned with the data domains of [03_Data_Architecture.md](03_Data_Architecture.md) and the SRS.

### 4.1 Domain Inventory

| Domain | Core Responsibility | Primary Requirements |
|--------|---------------------|----------------------|
| Agent | The user's permanent workspace identity; owns Project and scopes Knowledge, Memory, Conversation, Writing Profile, Draft, and Review (added by ADR-009) | ADR-009 |
| Project | Project identity, topic, raw source material scope (narrowed by ADR-009 — no longer owns knowledge, memory, drafts, or configuration) | WR-001 to WR-003, DR-001 to DR-003, MVP-001 to MVP-002 |
| Document | Source material intake, metadata, processing status | WR-004 to WR-006, DR-004 to DR-006, MVP-003 to MVP-004 |
| Knowledge | Extraction, structuring, chunking, retrieval of knowledge | AIR-007 to AIR-012, DR-007 to DR-009, MVP-005 to MVP-008 |
| Memory | Persistent project context and decision history | AIR-019 to AIR-021, DR-013 to DR-015, MVP-011 to MVP-012 |
| Conversation | Interaction history and continuity | WR-034, conversation data domain |
| Capability | Capability inventory and orchestration support (renamed from "Agent" by ADR-009) | AIR-058 to AIR-060, Capability data domain |
| Review | Draft evaluation, approval state, revision records | WR-022 to WR-025, DR-019, MVP-018 to MVP-020 |
| Author Profile | Writing characteristics preservation | AIR-016 to AIR-018, DR-010 to DR-012, MVP-009 to MVP-010 |
| Configuration | Operational and provider configuration, scoped to Agent (renamed from Project scope by ADR-009) | DR-020 to DR-022, NFR-031 to NFR-032 |

### 4.2 Boundary Rules

* Each domain owns its data and its behavior; no domain reaches into another domain's state.
* Cross-domain operations are composed through the orchestration layer, not by direct domain-to-domain coupling.
* Domain boundaries are drawn to preserve the SRS distinctions: source material, interpreted knowledge, stored memory, and approved output remain conceptually separate (AIR-006).

---

## 5. Service Responsibilities

Each domain is realized through one or more service units with a defined responsibility set. Services are described in implementation-agnostic terms; the number of service units per domain is an implementation decision, provided the boundaries and responsibilities below are preserved.

### 5.1 Service Boundary Principles

* Each service has a single coherent responsibility (high cohesion).
* Services interact only through defined boundaries (low coupling).
* Services are independently replaceable without redefining the workflow (NFR-016).
* Services are independently testable (NFR-029).

---

## 6. Internal Orchestration

Internal orchestration coordinates services to execute the research workflow.

### 6.1 Responsibilities

* Sequence multi-step operations such as: intake → processing → memory building → context assembly → drafting → review.
* Invoke the intelligence layer only when the workflow requires it, in the order defined by the intelligence lifecycle ([04_AI_Architecture.md](04_AI_Architecture.md), Section 5).
* Preserve traceability across service handoffs so that provenance is not lost between steps (AIR-052 to AIR-054).
* Enforce the "understand before generate" constraint: drafting services are not invoked until context sufficiency is established (AIR-031).

### 6.2 Orchestration Principles

* Orchestration logic is thin: it coordinates, it does not implement domain behavior.
* Orchestration remains visible and reviewable; it never silently bypasses human oversight points.
* Orchestration supports sequential, iterative, and targeted workflow variations (WR-029 to WR-031).

---

## 7. AI Service Layer

The AI service layer is the backend's boundary to the intelligence operating model.

### 7.1 Responsibilities

* Expose intelligence capabilities (reasoning, retrieval, context assembly, drafting, review support) to the orchestration layer.
* Enforce the intelligence lifecycle stages defined in [04_AI_Architecture.md](04_AI_Architecture.md).
* Preserve the distinction between raw input, interpreted knowledge, stored memory, and approved output (AIR-006).
* Keep provider-specific behavior behind the Provider Abstraction boundary (AIR-040 to AIR-042).

### 7.2 Structure

The AI service layer mirrors the intelligence capabilities:

| Capability | Responsibility | Architecture Reference |
|-----------|---------------|------------------------|
| Context assembly | Constructs task-specific context | AI Architecture, Section 6 |
| Knowledge processing | Transforms materials into knowledge | AI Architecture, Section 7 |
| Retrieval | Selects relevant knowledge and evidence | AI Architecture, Section 16 |
| Reasoning | Answers research questions and supports planning | AI Architecture, Sections 11–12 |
| Drafting | Generates and refines draft content | AI Architecture, Section 20 |
| Review support | Assists evaluation and evidence checks | AI Architecture, Section 19 |

### 7.3 Interaction Rules

* The AI service layer consumes domain data through the data access layer; it does not own project, document, or draft data.
* All provider interaction flows through the Provider Abstraction capability (AIR-041, API-029 to API-031).
* The AI service layer reports confidence and provenance distinctions so downstream review can act on them (AIR-067, AIR-068).

---

## 8. Knowledge Service

The knowledge service realizes the knowledge domain.

### 8.1 Responsibilities

* Initiate and manage knowledge processing of source materials (WR-007, MVP-005).
* Preserve extracted concepts, relationships, and evidence linkages (DR-007 to DR-009).
* Manage knowledge chunks and their provenance (AI Architecture, Section 9).
* Support retrieval queries over the project knowledge base (API-011 to API-013, MVP-007).
* Incorporate user refinements to knowledge elements (WR-009).

### 8.2 Dependencies

* Depends on the document service for source material access.
* Invokes the knowledge processing capability of the AI service layer.
* Depends on the data access layer for knowledge persistence.

### 8.3 Interaction Rules

* Knowledge service results always preserve source traceability (AIR-024, DR-008).
* Knowledge processing is initiated explicitly and its status is observable (WR-005).

---

## 9. Memory Service

The memory service realizes the project memory domain.

### 9.1 Responsibilities

* Store and retrieve persistent project context across sessions (WR-013, WR-014, MVP-011).
* Support update and supersession of memory elements with chronology preserved (WR-015, DR-014).
* Support querying memory elements relevant to the current activity (API-017 to API-019).
* Record review decisions and reflection outputs (AIR-064, AI Architecture, Section 22).

### 9.2 Dependencies

* Depends on the project service for project identity.
* Depends on the data access layer for memory persistence.

### 9.3 Interaction Rules

* Memory is populated through user input and system-derived context; the system does not infer memory elements without user awareness (MVP-011 limitation).
* Memory distinguishes current project state from historical context (AIR-021, AIR-066).

---

## 10. Document Service

The document service realizes the source material domain.

### 10.1 Responsibilities

* Accept and register research documents (WR-004, MVP-003).
* Preserve document identity, metadata, and content (DR-004, DR-005).
* Report processing status of documents (WR-005, API-010).
* Support listing and removal of documents within a project (API-008).
* Provide source material to the knowledge processing pipeline.

### 10.2 Dependencies

* Depends on the project service for project association.
* Depends on the data access layer for document persistence.

### 10.3 Interaction Rules

* Documents are retained as source evidence for the life of the project or until explicitly removed (data lifecycle).
* Removal preserves the integrity of referenced data (DR-025).

---

## 11. Project Service

The project service realizes the project domain. **Narrowed by ADR-009:** the project service now manages only project identity, topic, and raw source material scope — it no longer manages configuration or workflow continuity for knowledge/memory (moved to the Agent service, §22).

### 11.1 Responsibilities

* Create and manage the research project nested inside its owning Agent (WR-001, MVP-001; ADR-009).
* Preserve project identity, topic, scope, and lifecycle state (WR-002, WR-003, DR-001, DR-002).
* Support listing, retrieval, and deletion of the project's Research Documents (API-001 to API-007).

### 11.2 Dependencies

* Depends on the data access layer for project persistence.
* Depends on the Agent service for its owning Agent's identity (1:1, permanent; ADR-009).

### 11.3 Interaction Rules

* The project is the raw-input container for its owning Agent; Research Document is scoped to Project (DR-001, data philosophy). All other domains previously scoped to Project are now scoped to Agent (§22; ADR-009).

---

## 12. Conversation Service

The conversation service realizes the interaction history domain.

### 12.1 Responsibilities

* Preserve conversation history within a project context.
* Provide continuity of interaction across sessions (WR-034).
* Support association of conversations with documents, drafts, and memory elements.
* Support summarization or compaction of conversation history for continuity purposes.

### 12.2 Dependencies

* Depends on the project service for project scoping.
* Depends on the AI service layer for conversation intelligence behavior (AI Architecture, Section 10).
* Depends on the data access layer for persistence.

### 12.3 Interaction Rules

* Conversation content is preserved as a continuity record; it is not treated as persistent project memory until approved (AIR-006).
* Conversations inform memory updates only with user awareness.

---

## 13. Capability Service

**Renamed from "Agent Service" by ADR-009**, to avoid collision with the new Agent workspace domain (§22). Meaning and function unchanged: this service realizes the capability registry and supports capability coordination.

### 13.1 Responsibilities

* Maintain the registry of intelligence capabilities (AI Architecture, Section 14).
* Support routing of work to registered capabilities.
* Provide a controlled extension path for new capabilities (AIR-058, AIR-059).
* Keep capability definitions independent of any single workflow stage (AIR-060).

### 13.2 Dependencies

* Depends on the AI service layer for capability definitions.
* Depends on the orchestration layer for workflow context.

### 13.3 Interaction Rules

* Capability registration is configuration-governed and reviewable (AIR-055 to AIR-057).
* The capability service does not execute domain behavior; it coordinates capability selection.

---

## 14. Review Service

The review service realizes the review domain.

### 14.1 Responsibilities

* Support user review of drafts with evidence references (WR-022, MVP-018).
* Record revision requests and approval decisions (WR-025, API-026 to API-028, DR-019).
* Preserve review state and version history across revision cycles (WR-024, MVP-021).
* Surface confidence and provenance distinctions from the intelligence layer (AIR-067).
* Support retrieval of approved content for downstream export, with advanced formatting and full-text export deferred beyond the MVP (MVP out-of-scope).

### 14.2 Dependencies

* Depends on the document and knowledge services for evidence references.
* Depends on the AI service layer for review support capability.
* Depends on the data access layer for review state persistence.

### 14.3 Interaction Rules

* Review decisions are user-owned and preserved for audit (AIR-054).
* The review service never overrides the researcher's approval authority (AIR-003, AIR-038).

---

## 15. Authentication Boundary

The authentication boundary controls access to the backend.

### 15.1 Responsibilities

* Establish and verify the identity of the user before any service is accessed (NFR-009).
* Authorize access to projects and project data (API-036, API-037).
* Protect project artifacts from unauthorized modification or deletion (NFR-010).

### 15.2 Boundary Model

* Authentication applies at the service boundary layer: no domain service assumes an unauthenticated caller.
* The MVP assumes a single authenticated user per project (WR-038, MVP-001); the boundary is designed to extend to multi-user roles in later phases (RDM-003).
* Authorization decisions are recorded where required for audit and observability (NFR-027, NFR-028).

### 15.3 Interaction Rules

* Domain services receive authenticated, authorized requests only.
* The authentication boundary is independent of domain logic so that future authentication schemes can be introduced without changing the workflow (NFR-024).

### 15.4 Realized Mechanism (ADR-010)

For the MVP's single pre-provisioned user, the boundary is realized as a DB-backed opaque session token, using the Session entity already specified in `04_Logical_Data_Model.md` §3.2: `POST /auth/login` verifies a bcrypt-hashed password and issues a `session_token`; subsequent requests present it as a bearer credential; `POST /auth/logout` ends the session. The single account's username and password hash are synced from configuration on every startup, never hard-coded and never created through a public registration endpoint. Domain services (Agent, Project, Document) remain unaware of this mechanism — they receive only a resolved `user_id`, exactly as the boundary model in §15.2 requires.

---

## 16. Infrastructure Boundary

The infrastructure boundary isolates operational concerns from domain logic.

### 16.1 Responsibilities

* Provide persistence services through the data access layer (API-032, API-033).
* Support observability: logs, diagnostics, and monitoring signals (NFR-027, NFR-028).
* Support backup and recovery of project state (NFR-033, NFR-034).
* Support configuration provisioning and operational parameter management (NFR-031, NFR-032).

### 16.2 Boundary Model

* Domain services depend on the data access boundary, not on specific infrastructure.
* Observability is emitted at service boundaries; it does not expose unnecessary user content (NFR-028).
* Recovery procedures restore project continuity after routine faults (NFR-034).

### 16.3 Interaction Rules

* Infrastructure changes do not alter the research workflow (NFR-023, NFR-024).
* Operational capacity can be extended in a controlled manner (NFR-008).

---

## 17. Configuration Management

Configuration management governs the operational parameters of the backend.

### 17.1 Responsibilities

* Manage provider selection and workflow parameters without changing the product contract (AIR-055).
* Preserve configuration state in a recoverable, auditable manner (DR-021).
* Maintain user preferences separately from project data (DR-022).
* Keep configuration changes observable and reviewable (AIR-056, AIR-057, NFR-032).

### 17.2 Configuration Model

* Configuration is layered: system-level defaults, project-level settings (DR-003), and user preferences (DR-022).
* Configuration governs workflow behavior, provider integration, and project context handling (NFR-031).
* The active configuration state is visible to the user (AIR-056).

### 17.3 Interaction Rules

* Configuration never alters the approved product philosophy or workflow assumptions.
* Configuration changes are traceable and can be reviewed (AIR-057).

---

## 18. Dependency Principles

The backend is governed by the following dependency principles:

* **Downward dependencies.** Upper layers depend on lower layers; no upward dependencies.
* **Boundary-based interaction.** Services interact through defined boundaries, never through shared state.
* **Domain isolation.** Domains do not reach into each other's data.
* **Provider independence.** Intelligence and persistence providers are interchangeable (AIR-040, API-033).
* **Minimal coupling.** A change to one capability must not require uncontrolled changes elsewhere (NFR-013).
* **Explicit orchestration.** Multi-service flows are composed in the orchestration layer, keeping services independent and testable (NFR-029).

---

## 19. Error Propagation

Error handling in the backend follows a defined propagation model.

### 19.1 Principles

* **Preserve integrity.** Failures never silently corrupt or lose project knowledge (NFR-004).
* **Fail toward human oversight.** When an action cannot complete, the user is informed and given a recovery path (WR-036).
* **No fabrication.** Provider or retrieval failures do not result in unsupported generation being substituted (AIR-044).
* **Observable failures.** Failures are recorded in observability channels for diagnosis (NFR-027, NFR-028).

### 19.2 Propagation Model

| Error Origin | Propagation Behavior |
|--------------|---------------------|
| Service boundary | Meaningful error information returned to the caller (API-035) |
| Orchestration | Workflow state preserved; user informed of the blocked step and recovery options |
| AI service layer | Failure surfaced; degraded-mode behavior per NFR-006; no unsupported output |
| Data access layer | Integrity preserved; retry or recovery per NFR-004, NFR-034 |

### 19.3 Interaction Rules

* Errors are normalized at service boundaries so callers receive consistent, meaningful failure information (API-035).
* Degraded modes keep the user a safe path to continue review or recover work (NFR-006).

---

## 20. Scalability Principles

The backend scales according to the following principles.

### 20.1 Growth Model

* The domain model and workflow design remain valid as project size, source volume, and knowledge volume grow (NFR-007).
* Operational capacity is extended in a controlled manner as projects, users, or knowledge assets increase (NFR-008).
* Performance degrades within documented, observable thresholds as data volume grows (NFR-002, API-039).

### 20.2 Scaling Levers

| Lever | Effect |
|-------|--------|
| Service separation | Individual services can be scaled independently |
| Stateless boundaries | Service interactions are self-contained, preserving state management for the system (SRS Chapter 9, API philosophy) |
| Asynchronous processing | Long-running knowledge processing is decoupled from interactive requests |
| Bounded context assembly | Context window management bounds reasoning work (AI Architecture, Section 17) |

### 20.3 Interaction Rules

* Scaling decisions must not change the research workflow or product behavior (NFR-007, NFR-023).
* Observability must remain available at any scale to detect abnormal behavior (NFR-027).

---

## 21. Traceability

The backend architecture is traceable to the approved requirements as follows:

* Backend philosophy and layering: NFR-013 to NFR-018, SRS Chapter 9 API philosophy, ADR-001 (separation of architecture from implementation).
* Project service: WR-001 to WR-003, DR-001 to DR-003, API-001 to API-007, MVP-001 to MVP-002.
* Document service: WR-004 to WR-006, DR-004 to DR-006, API-008 to API-010, MVP-003 to MVP-004.
* Knowledge service: AIR-007 to AIR-012, DR-007 to DR-009, API-011 to API-013, MVP-005 to MVP-008.
* Memory service: AIR-019 to AIR-021, WR-013 to WR-015, DR-013 to DR-015, API-017 to API-019, MVP-011 to MVP-012.
* Conversation service: WR-034, conversation data domain, AI Architecture Section 10.
* Capability service (renamed from "Agent service" by ADR-009): AIR-058 to AIR-060, AI Architecture Section 14.
* Agent service (new domain, ADR-009): the user's workspace identity; owns Project (1:1, permanent) and scopes Knowledge, Memory, Conversation, Writing Profile, Draft, Review — see §22.
* Review service: WR-022 to WR-025, DR-019, API-026 to API-028, MVP-018 to MVP-021.
* AI service layer: AIR-001 to AIR-068, API-029 to API-031, AI Architecture (all sections).
* Authentication boundary: NFR-009, NFR-010, API-036, API-037, WR-038; realized mechanism per ADR-010 — see §15.4.
* Infrastructure boundary: API-032, API-033, NFR-023, NFR-024, NFR-027 to NFR-028, NFR-033 to NFR-034.
* Configuration management: AIR-055 to AIR-057, DR-020 to DR-022, NFR-031 to NFR-032.
* Error propagation: NFR-003 to NFR-006, NFR-027 to NFR-028, API-035, WR-036.
* Scalability: NFR-001 to NFR-002, NFR-007 to NFR-008, API-038 to API-039.
* ADR traceability: ADR-002 to ADR-007 govern the technology, service organization, storage, retrieval, async, and deployment decisions this architecture depends on; ADR-009 governs the Agent workspace domain introduced in §22 and the Capability rename in §13; ADR-010 governs the Authentication Boundary's realized mechanism in §15.4.

These traceability links ensure the backend organization remains accountable to the approved requirements.

---

## 22. Agent Service

**Added by ADR-009.** Appended after §21 (Traceability) to preserve the numbering of all existing sections; it is not the traceability section's successor in reading order — see §4.1 for the Agent domain's place in the domain inventory and §11 for the narrowed Project service it now sits above.

The Agent service realizes the Agent domain: the user's permanent, specialized research workspace.

### 22.1 Responsibilities

* Create an Agent together with its one, permanent Project from the user-supplied topic, reference documents, and writing-style samples (ADR-009).
* Enforce the one-Agent-per-user MVP boundary (ADR-009; a future monetization-gated capability may relax this).
* Own and scope Knowledge, Memory, Conversation, Writing Profile, Draft, and Review to the Agent (moved from the Project service by ADR-009).
* Own agent-scoped Configuration (moved from the Project service; Configuration Item scope renamed `project` → `agent` by ADR-009).

### 22.2 Dependencies

* Depends on the data access layer for Agent persistence.
* Depends on the Project service for its one, permanent Project (§11).
* Composed by the Knowledge, Memory, Conversation, Author Profile, Review, and Configuration services, which now scope their data to `agent_id` rather than `project_id` (ADR-009).

### 22.3 Interaction Rules

* The Agent–Project pairing is permanent; no service may repoint an Agent to a different Project or vice versa (ADR-009).
* The Agent service does not itself implement knowledge processing, memory, conversation, drafting, or review behavior — those remain the responsibility of their own services (§8, §9, §12, §14 [Capability Service — renamed], Review service), scoped to the Agent.
* Multi-Agent-per-user, when built, is a change to this service's uniqueness enforcement only — not a redesign (ADR-009 Future Considerations).
