# Operational Architecture

**Document:** 07_Operational_Architecture.md

**Status:** Active

**Date:** 2026-08-06

---

## 1. Purpose

This document defines the logical **operational architecture** of ScholarOS: how the conceptual data domains of `03_Data_Architecture.md` are persisted, how the system is assumed to be deployed and operated, and how the architecture evolves from a single user to a SaaS platform.

It completes the architecture set by covering three concerns the earlier documents deliberately deferred: **storage strategy**, **deployment assumptions**, and the **scalability evolution path**.

This document is implementation-agnostic. It describes storage *categories*, deployment *assumptions*, and scaling *levers* — not specific technologies. Technology decisions are recorded in the ADR set (ADR-004 Storage and Memory Strategy, ADR-007 Deployment Strategy).

---

## 2. Relationship to the Architecture Set

| Concern | Document | Role |
|---------|----------|------|
| Conceptual data domains | 03_Data_Architecture.md | What data exists and who owns it |
| Storage strategy | This document, §3 | How those domains are persisted and operated |
| Infrastructure boundary | 05_Backend_Architecture.md §16 | Where infrastructure concerns sit behind a stable boundary |
| Scalability principles | 05_Backend_Architecture.md §20 | The scaling principles the implementation must honor |
| Deployment assumptions | This document, §4 | The operating model assumed by the architecture |
| Scalability evolution | This document, §5 | How the system scales from one user to a platform |

---

## 3. Storage Strategy

### 3.1 Storage Principles

1. **Persistent understanding.** Project understanding, memory, and decisions must persist across sessions (Persistence principle, 01_Architecture_Overview.md §5).
2. **Class-by-access-pattern separation.** Data with different access patterns and consistency needs is stored in different storage categories; no single store is forced to serve every pattern.
3. **Evidence integrity.** Stored data must preserve the traceability chain between source evidence, interpretation, and generated support (DR-004 to DR-009, DR-016 to DR-019).
4. **User ownership and exportability.** User-owned domains (03 §4) remain retrievable and exportable; the platform must never trap user work.
5. **Technology independence.** Persistence is accessed only through the data access layer boundary (05_Backend_Architecture.md §16, API-032, API-033), so the storage implementation can evolve without changing domain logic.

### 3.2 Data Classes and Storage Categories

| Storage Category | Data Domains (03) | Access Pattern | Consistency Model |
|------------------|-------------------|----------------|-------------------|
| **Structured core** | Projects, documents (metadata), knowledge, knowledge chunks, memory, conversations, writing profiles, drafts, reviews, configuration | Transactional create/read/update; relational queries; state transitions | Strong consistency for project and workflow state |
| **Vector index** | Knowledge chunk embeddings and retrieval indexes | Similarity search during retrieval (04 §16) | Eventually consistent; rebuilt or updated asynchronously as knowledge changes |
| **Object store** | Source document files, exports, large artifacts | Write-once, read-anytime; blob access | Immutable or versioned; strong on metadata, content addressed |
| **Working cache** | Assembled context, conversation working state, interim pipeline results | Ephemeral; high-frequency read/write | Loose consistency; loss must be recoverable from the structured core |

### 3.3 Consistency and Integrity

- **Strong consistency** applies where correctness depends on ordering and exclusivity: project lifecycle transitions, draft versioning, review state, memory updates (DR-001 to DR-003, DR-016 to DR-019).
- **Eventual consistency** is acceptable for derived artifacts: retrieval indexes, knowledge summaries, conversation compilations. Async pipelines (ADR-006) may lag the source of truth.
- **Integrity guarantees:** no silent data corruption (NFR-004); knowledge and drafts retain version history so superseded understanding remains traceable (DR-023 to DR-025); source documents are retained as evidence for the life of the project or until explicitly removed (05 §10).

### 3.4 Retention and Lifecycle

The storage strategy maps the lifecycles of 03 §5 onto persistence rules:

- **Documents:** retained as evidence; removal only explicit (WR-004 to WR-006).
- **Knowledge and chunks:** superseded versions retain traceability (DR-007 to DR-009, DR-023 to DR-025).
- **Conversations:** retained as continuity record; may be summarized and linked to memory rather than stored verbatim indefinitely (03 §3.6).
- **Drafts and reviews:** version history preserved (DR-016 to DR-019).
- **Exports:** user-owned content is exportable at project level (user ownership model, 03 §4).

### 3.5 Backup and Recovery Assumptions

- The MVP assumes **automated, scheduled backups** of the structured core and object store, and **point-in-time recovery** for the structured core.
- Recovery targets are documented as assumptions, not over-engineered guarantees: the MVP does not assume multi-region replication, zero-downtime failover, or cross-region DR (NFR-027 to NFR-028 define the integrity bar; ADR-007 defines the operational envelope).

---

## 4. Deployment Assumptions

### 4.1 Initial Deployment Model

- **Backend-first personal MVP.** The system is deployed as a single-node backend serving the API and intelligence pipelines; the frontend is a client of that API (05_Backend_Architecture.md §3, §15).
- **Development topology ≈ production topology.** For the MVP, the local development environment matches the single-node production layout, simplifying debugging and reducing environmental drift. This assumption is explicit and intentionally narrow; it is re-evaluated at the cloud stage (ADR-007).

### 4.2 Boundaries

- **Authentication boundary:** one user in the MVP (NFR-009, NFR-010, API-036, API-037); the boundary is designed so multi-user can be added without reshaping the API (05 §15).
- **Infrastructure boundary:** all persistence and external services sit behind the data access layer and provider abstraction (05 §16; 04 §23).
- **Provider egress:** the backend calls external AI providers over HTTPS (04 §23, AIR-040 to AIR-042). Provider availability is an external dependency; failures are handled per 04 §24 (Failure Handling) and must not cascade into data corruption (NFR-003 to NFR-006).
- **Secrets management:** provider keys and configuration are externalized (AIR-055 to AIR-057, NFR-031, NFR-032); no secrets are embedded in the repository.

### 4.3 Operations Assumptions

- **Observability:** the system produces sufficient diagnostic information for monitoring, troubleshooting, and operational understanding (API-040), including pipeline progress, provider calls, and errors.
- **Single operator:** the MVP operator is the researcher-developer; operational tooling is minimal but present (backups, logs, health checks).

### 4.4 Path to Cloud

The single-node model is the seed of the cloud model. What stays constant across the migration:

- The layered architecture, domain boundaries, and service responsibilities (01, 05).
- The data access layer and provider abstraction boundaries.
- The storage *categories* (§3.2) — only their concrete implementations change (ADR-004, ADR-007).

What changes: process packaging (containerization), managed persistence, horizontal scaling of workers, and (later) multi-tenant isolation (ADR-007; §5 below).

---

## 5. Scalability Evolution

ScholarOS must realistically scale from a single user to a SaaS platform without a redesign. The evolution path maps to the SRS roadmap phases (11_Future_Roadmap.md).

### 5.1 Evolution Stages

| Stage | Users / Scope | Multi-tenancy | What changes | Roadmap (SRS 11) |
|-------|---------------|---------------|--------------|------------------|
| **1. Single user (MVP)** | One researcher; all data project-scoped, no sharing | None — data isolated per project | — | MVP |
| **2. Research teams** | Multiple users per project | Workspace-level tenancy: shared projects, per-user roles, concurrency, shared review workflows | Authorization model, concurrency control, collaboration events | Phase 4 (Collaborative Research) |
| **3. Universities** | Institutional deployment, many projects | Organization-level tenancy: SSO, org-wide knowledge graph, institutional governance | Identity federation, organizational data isolation, compliance | Phase 5–6 |
| **4. Enterprise** | Large organizations | Enterprise tenancy: audit, SLAs, advanced security | Audit trails, SLA guarantees, dedicated/on-prem options | Phase 6 |
| **5. SaaS platform** | Public multi-tenant service | Infrastructure-level tenancy: per-tenant isolation, metering, usage governance | Metering, tenant-aware scaling, cost governance | Phase 6+ |

### 5.2 What Must Not Change

The following are invariant across all stages; any evolution proposal that compromises them is rejected:

- **Evidence grounding and traceability** (04 §18; AIR-046 to AIR-048).
- **Memory architecture** — the project memory model survives tenancy because memory is project-scoped (04 §8).
- **Provider abstraction** — external AI providers remain interchangeable (04 §23; ADR-002).
- **Separation of concerns** (ADR-001).
- **Human oversight** (04 §25).

### 5.3 Scaling Levers

The architecture absorbs growth through the following levers, without redesign:

1. **Async processing** — long-running intelligence work is decoupled from interactive requests (05 §20; ADR-006); workers scale independently.
2. **Modular boundaries** — the modular monolith (ADR-003) permits selective extraction of services when a boundary proves to be a scaling or team bottleneck.
3. **Stateless API tier** — state lives in the structured core, not in process memory, so API instances scale horizontally.
4. **Index partitioning** — retrieval indexes (ADR-005) partition by project/tenant when volume demands, without changing the retrieval contract.
5. **Persistence swap** — the data access layer (API-032, API-033) allows the storage implementations (ADR-004) to move from single-node to managed services.

---

## 6. Traceability

This operational architecture is traceable to the approved requirements as follows:

* Storage strategy: DR-001 to DR-025, API-032, API-033, NFR-023, NFR-024, NFR-027, NFR-028.
* Deployment assumptions: NFR-003 to NFR-006, NFR-009, NFR-010, NFR-031 to NFR-034, API-035 to API-037, API-040, AIR-040 to AIR-042, AIR-055 to AIR-057.
* Scalability evolution: NFR-001, NFR-002, NFR-007, NFR-008, API-038, API-039, RDM-001 to RDM-010, SRS Chapter 11 roadmap phases.
* ADR traceability: ADR-004 (Storage and Memory Strategy), ADR-007 (Deployment Strategy).

These traceability links keep the operational architecture accountable to the approved product requirements rather than to implementation convenience.
