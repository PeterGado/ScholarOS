# Database Overview

**Document:** 01_Database_Overview.md

**Status:** Active

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design

**Revision:** 2 (2026-08-07) — elevated to the milestone constitution; layered document set (01–08) and Authoritative Source Rule adopted

---

## 1. Purpose

This document is the constitutional document of the ScholarOS database design milestone. It establishes the philosophy, scope, objectives, authority, assumptions, and engineering boundaries of the ScholarOS database before any structural design work begins.

It answers the questions that every later database document will inherit:

* Why does ScholarOS require a database?
* What information will the database manage?
* What problems must the database solve?
* How does database design fit between Architecture and API Design?
* What documents govern this design?
* What decisions are intentionally deferred?

This document is design-only. It does not define SQL, DDL, storage engines, indexes, migration scripts, ORM models, API payloads, or any implementation-specific persistence code. Those artifacts belong to later milestones and remain governed by the architecture and ADR set established here.

A Senior Backend Engineer should be able to read only this document and understand the purpose of the ScholarOS database, its role within the system, what this milestone will produce, what later milestones will produce, where database decisions belong, and what must never be implemented before database design is complete.

---

## 2. Scope

This document covers the database design discipline that sits between the frozen architecture baseline (Milestone 4) and the later API design and implementation milestones.

Its scope includes:

* explaining why ScholarOS requires a persistent information foundation;
* defining the role of database design in the approved software development lifecycle;
* clarifying the relationship between conceptual data architecture, logical database design, and physical persistence implementation;
* establishing the layered structure of the database design document set and the rules that govern its construction;
* establishing the design boundaries that protect the architecture and ADR set from reinterpretation during implementation;
* describing the persistence contract that later API design and backend implementation must respect.

This document does not define the database schema, entity inventory, storage engine internals, indexing strategy, or runtime access mechanics. Those concerns are addressed by later documents in this milestone (`01_Database_Overview.md` §12).

---

## 3. Objectives

The database design milestone exists to accomplish the following objectives:

1. Translate the conceptual data architecture ([../architecture/03_Data_Architecture.md](../architecture/03_Data_Architecture.md)) into a durable, logical persistence design.
2. Preserve the traceability chain from requirements to architecture to data design to implementation.
3. Ensure that persistent information is treated as a first-class architectural concern rather than an incidental implementation detail.
4. Define the design contract that later API design and backend implementation must respect.
5. Produce a layered, progressively refined database design that is reviewable at each level before any physical or implementation work begins.
6. Preserve the separation of concerns established in ADR-001 while enabling later implementation work to proceed with clarity.

The objective of this milestone is therefore not to implement persistence, but to make persistence intelligible, governable, and traceable before code is written.

---

## 4. Position in the Software Development Lifecycle

ScholarOS follows the approved lifecycle ([../governance/01_Project_Constitution.md](../governance/01_Project_Constitution.md) §6):

```md
Vision
↓
SRS
↓
Architecture
↓
Database Design
↓
API Design
↓
Implementation
↓
Testing
↓
Documentation Review
```

Database design occupies the critical transition point between architecture and implementation. Architecture defines the system's organization, responsibilities, and constraints. Database design translates that architectural understanding into a persistence model that is consistent with the requirements, the information domains, and the later service-contract work.

ADR-001 explicitly classifies Database Design as an **architecture concern** (ADR-001, "Development Lifecycle Integration"): the database design documents describe how the system's information is organized, and they reside alongside the architecture documentation in `docs/database/`. This classification is decisive — it means the database design is part of the architectural layer, not the implementation layer, and is therefore subject to architectural governance rather than being defined implicitly during coding.

This milestone exists so that the system's persistent information model is documented, reviewed, and approved before backend implementation begins. It ensures that later work does not silently define the data model through code alone.

---

## 5. Relationship to the SRS

This database overview is grounded in the approved SRS and remains accountable to it. The database design milestone exists to support the SRS without redefining it.

The relevant SRS concerns are primarily:

* Chapter 2: Product Definition and Overview
* Chapter 3: Overall System Description
* Chapter 4: Functional Requirements
* Chapter 5: Non-Functional Requirements
* Chapter 6: AI Requirements
* Chapter 7: Data Requirements
* Chapter 8: User Workflows
* Chapter 9: API Requirements
* Chapter 10: MVP Scope

The database design phase is especially responsible for translating the SRS emphasis on persistent project state, evidence grounding, traceability, continuity, and human oversight into a coherent persistence strategy. It does so without changing the product requirements themselves.

In particular:

* **SRS Chapter 7** defines the seven conceptual data domains (project, source material, knowledge, author profile, project memory, draft and content, configuration and preference) and their requirement statements (DR-001 to DR-033, DR-035, and the design constraints DC-002 and DC-003, which superseded DR-034 and DR-036). These domains are the information inventory the database design must support.
* **SRS Chapter 4** defines the functional domains that depend on persistent state (project lifecycle, knowledge management, author profile, project memory, drafting, review, versioning, evidence traceability).
* **SRS Chapter 6** defines the AI requirements that depend on persisted memory, knowledge, and evidence (AIR-019 to AIR-021, AIR-022 to AIR-027, AIR-065 to AIR-068).
* **SRS Chapter 10** defines the MVP scope that bounds how much of the data model the first release must realize.

The database design milestone operates strictly below the SRS in authority. It interprets the requirements into a structural design; it never alters them.

---

## 6. Relationship to the Architecture

This milestone is derived from the frozen architecture baseline (Milestone 4, closed out and frozen per [../governance/04_Repository_Governance.md](../governance/04_Repository_Governance.md) §4.4) and must not contradict it.

The architecture documents define the system organization, responsibilities, and information domains. The database design milestone takes those architectural boundaries as its starting point and turns them into a persistence design contract.

In particular:

* [../architecture/01_Architecture_Overview.md](../architecture/01_Architecture_Overview.md) establishes the overall layered architecture, including the Data and Knowledge Layer as the home of the conceptual information domains.
* [../architecture/03_Data_Architecture.md](../architecture/03_Data_Architecture.md) defines the conceptual data domains (projects, documents, knowledge, knowledge chunks, memory, conversations, writing profiles, agents, drafts, reviews) and the data ownership model. This is the primary conceptual input to database design.
* [../architecture/04_AI_Architecture.md](../architecture/04_AI_Architecture.md) defines the intelligence operating model whose retrieval, memory, and knowledge-processing pipelines consume and produce persisted data.
* [../architecture/05_Backend_Architecture.md](../architecture/05_Backend_Architecture.md) defines the backend domains and the data access layer — the controlled boundary through which all persistence is realized (API-032, API-033).
* [../architecture/07_Operational_Architecture.md](../architecture/07_Operational_Architecture.md) establishes the storage categories (structured core, vector index, object store, working cache), consistency model, retention rules, backup assumptions, and the scalability evolution path that constrain persistence design.

Database design must remain subordinate to this architecture baseline. It must not reinterpret component boundaries, service responsibilities, storage categories, or operational assumptions.

---

## 7. Relationship to the ADR Set

The database design milestone is governed by the accepted ADR set (ADR-001 to ADR-007) and must preserve the decisions already made. The ADR set is frozen; architectural changes now require new ADRs, not edits to existing ones.

The most relevant ADRs are:

* [../adr/ADR-001_Separation_of_Requirements_Architecture_and_Implementation.md](../adr/ADR-001_Separation_of_Requirements_Architecture_and_Implementation.md) — classifies database design as an architecture concern and preserves the separation of requirements, architecture, and implementation.
* [../adr/ADR-002_Technology_Stack_and_Provider_Abstraction.md](../adr/ADR-002_Technology_Stack_and_Provider_Abstraction.md) — records the ORM abstraction behind the data access layer; the logical data model must remain expressible within that abstraction.
* [../adr/ADR-003_Service_Organization_Modular_Monolith.md](../adr/ADR-003_Service_Organization_Modular_Monolith.md) — preserves the modular service boundaries; the logical model must support per-module data ownership (shared data access layer, no shared internals).
* [../adr/ADR-004_Storage_and_Memory_Strategy.md](../adr/ADR-004_Storage_and_Memory_Strategy.md) — decides the persistence engines (structured core: SQLite for the MVP with PostgreSQL migration path; embedded vector index; local object store; in-process cache) and mandates that memory persists as a first-class domain.
* [../adr/ADR-005_Retrieval_and_Search_Strategy.md](../adr/ADR-005_Retrieval_and_Search_Strategy.md) — establishes chunk-level hybrid retrieval with first-class evidence links; the knowledge-chunk structure and evidence linkage are constraints on the logical model.
* [../adr/ADR-006_Async_Processing_and_Event_Coordination.md](../adr/ADR-006_Async_Processing_and_Event_Coordination.md) — governs the durable outbox and event model; the persistence design must accommodate durable work items and event records in the structured core.
* [../adr/ADR-007_Deployment_Strategy.md](../adr/ADR-007_Deployment_Strategy.md) — establishes the local-first single-node deployment that bounds the MVP persistence envelope and its migration path.

This document does not replace those ADRs. It uses them as the governing architectural context for the database design milestone.

---

## 8. Governing Principles

The database design milestone shall be guided by the following principles:

* **Persistence must preserve the integrity of the research workflow.** The database exists to make understanding, evidence, and oversight durable — not to optimize storage convenience.
* **Data ownership must remain aligned with the architecture.** User-owned data (projects, documents, drafts, reviews, profiles, memory content) and system-managed data (derived knowledge, processing state, configuration) remain distinct, per the ownership model of 03_Data_Architecture.md §4.
* **Traceability must survive across the full record.** Project state, knowledge, memory, drafts, reviews, and conversations must retain the evidence-to-interpretation-to-output chain (AIR-046 to AIR-048, DR-006, DR-008, DR-018).
* **Continuity is a persistence requirement, not a feature.** Project understanding must persist across sessions by design, not by convention (AIR-065, AIR-066).
* **The database model remains subordinate to the SRS and the architecture.** Requirements and architecture are authoritative; the data model serves them, never redefines them.
* **Physical implementation choices remain deferred.** Storage engines, index mechanics, and schema realization stay behind the design contract until the logical design is complete and reviewed.
* **The data access layer is the only realization boundary.** Persistence is realized through the data access layer (05_Backend_Architecture.md §16); the logical model must be realizable behind that boundary (API-032, API-033).
* **Each database document extends the previous one.** Database documents are built as a layered set; each later document treats all earlier completed database documents as authoritative sources and adds the next level of detail without duplication (see §12).

---

## 9. Database Design Philosophy

### 9.1 Why Database Design Exists

ScholarOS is not a transient application workflow. It is an evidence-grounded research operating environment that must retain continuity over time. Its product principles — understand before writing, evidence before opinion, preserve the author, project memory, human oversight — all depend on persistent state:

* **Understanding** must accumulate across sessions (project memory, knowledge, author profile).
* **Evidence** must remain linked to the interpretation and the output it supports.
* **Oversight** requires a durable record of drafts, revisions, reviews, and approvals.
* **Continuity** requires that no context is lost between sessions.

A database is how these commitments become durable. If the persistence design is left to emerge during coding, the model becomes invisible, unreviewed, and ungovernable — exactly the failure ADR-001 exists to prevent. Database design therefore exists as its own discipline within the architecture concern: it makes the system's information structure explicit, reviewable, and traceable before implementation.

### 9.2 The Conceptual Model

The conceptual model describes **what information the system must understand and why**. It is the domain view established by the SRS and the architecture: projects, documents, knowledge, knowledge chunks, memory, conversations, writing profiles, agents, drafts, reviews, and configuration.

This level is already documented — it exists in SRS Chapter 7 (data domains and requirements) and in [../architecture/03_Data_Architecture.md](../architecture/03_Data_Architecture.md) (conceptual domains, ownership, relationships, lifecycles). The conceptual model answers "what exists" and "why it exists" without any structural or technical commitment.

### 9.3 The Logical Model

The logical model describes **how those information domains relate to one another** in a consistent, traceable, and maintainable way. It defines the structural design contract for persistence without prescribing implementation details: entities, attributes, identifiers, relationships, cardinality, integrity rules, and the constraints that keep the record coherent over time.

This is the level at which the database design milestone must operate. The logical model is technology-independent: it must hold whether the structured core is SQLite or PostgreSQL, whether the vector index is embedded or hosted, and regardless of ORM choices. It is the contract that API design will define interfaces against and that backend implementation will realize through the data access layer.

### 9.4 The Physical Model

The physical model describes **the concrete persistence realization**: storage engines, schema layout, indexes, partitioning, migration mechanics, and runtime access patterns.

The physical model is intentionally deferred in this milestone. The design documents of this milestone may map the logical model onto the approved storage categories of 07_Operational_Architecture.md §3 — indicating which information belongs in the structured core, the vector index, the object store, or the working cache — but they must not select or configure engines, define schema layout, indexes, or access mechanics. Physical realization (schema, indexes, migration scripts, engine configuration) belongs to implementation, bounded by the design contract and by the engine and deployment decisions already recorded in ADR-004, ADR-005, and ADR-007. What must never happen is physical choices being made first, silently, in code, and then treated as the design.

### 9.5 Why Implementation Is Intentionally Deferred

Implementation is deferred for four reasons, each grounded in the approved governance:

1. **ADR-001 classification.** Database design is an architecture concern. Implementation is a separate concern. Producing implementation artifacts now would conflate them and undermine the traceability chain the ADR set protects.
2. **Reviewability.** A design can be reviewed, corrected, and approved at a fraction of the cost of a schema that is already embedded in code and migrations. The lifecycle requires review before implementation, not after.
3. **Provider and engine independence.** The logical model must be validated independently of engines (ADR-004) so that the SQLite-to-PostgreSQL migration path and the embedded-to-hosted vector index path remain configuration- and data-layer changes, not rewrites.
4. **Requirements protection.** If implementation defines the model, the model tends to reflect implementation convenience rather than requirements (ADR-001: "Implementation shall not redefine requirements"). Deferral protects the SRS and architecture from being silently reshaped.

---

## 10. Database Quality Attributes

The database design milestone must preserve the quality attributes that matter to ScholarOS:

| Attribute | Definition | Governing Reference |
|-----------|-----------|---------------------|
| **Integrity** | Persistent state must not silently corrupt or lose traceability; no silent data corruption. | NFR-004; 07 §3.3 |
| **Traceability** | Every important state transition preserves the relationship between source evidence, interpreted knowledge, memory, and output. | DR-008, DR-015, DR-018; AIR-046 to AIR-048 |
| **Continuity** | Research context persists across sessions; memory is a first-class domain, never reconstructed from logs. | AIR-019 to AIR-021, AIR-065, AIR-066; ADR-004 |
| **Consistency** | Strong consistency where correctness depends on ordering and exclusivity (project lifecycle, draft versioning, review state, memory updates); eventual consistency only for derived artifacts. | 07 §3.3; ADR-006 |
| **Evolvability** | The design supports growth (teams, universities, enterprise, SaaS) without redesign; migration paths are contractual. | 07 §5; ADR-004, ADR-007 |
| **Separation of concerns** | Persistence concerns remain behind the data access layer boundary; modules share the boundary, not internals. | API-032, API-033; ADR-003 |
| **Recoverability** | The design supports scheduled backups and point-in-time recovery of the structured core. | 07 §3.5; NFR-033, NFR-034 |
| **Reviewability** | The data model supports the human review, revision, and approval workflow, including version and review state. | DR-016 to DR-019; MVP-018 to MVP-022 |

---

## 11. Separation of Concerns

### 11.1 The Concern Boundaries Around Persistence

The concerns surrounding persistence are distinct and must remain distinct:

* The **SRS** defines what the system must do (including what information it must manage).
* The **architecture** defines how the system is organized (including the conceptual data domains and storage categories).
* **Database design** defines how persistent information is structurally organized and governed.
* **API design** defines the service contract over the data and workflow boundaries.
* **Implementation** realizes the design in code.

### 11.2 How Database Design Preserves ADR-001

ADR-001 draws the boundary between requirements (SRS), architecture (architecture documents + database design + API design), and implementation (code). The database design milestone preserves that boundary by:

* producing the persistence design **before** implementation, so the model is never defined implicitly in code;
* keeping the design **implementation-agnostic** (no SQL, DDL, or engine-specific decisions in the design documents);
* remaining **traceable** to the SRS and architecture at every level of the design;
* recording engine and technology decisions in the **ADRs**, which already exist, rather than reintroducing them into design documents.

If implementation began without a documented database design contract, the data model would be defined indirectly in application code — weakening maintainability, traceability, and architectural discipline, and breaching ADR-001, which classifies database design as an architecture concern and forbids implementation from redefining requirements. This milestone is the mechanism that prevents that failure.

### 11.3 Why Storage Decisions Must Follow the Architecture

Storage decisions are already made at the architectural level and must not be re-decided during database design:

* The **storage categories** — structured core, vector index, object store, working cache — are defined by 07_Operational_Architecture.md §3.2.
* The **engines** for the MVP — SQLite structured core, embedded vector index, local object store, in-process cache, with documented migration paths — are decided by ADR-004.
* The **retrieval indexing** decision — chunk-level hybrid retrieval with first-class evidence links — is decided by ADR-005.
* The **deployment envelope** — local-first, single-node — is decided by ADR-007.

The database design milestone maps the logical model onto these already-decided categories. It may refine how domains map to categories (which data belongs in the structured core versus the vector index versus the object store), but it must not contradict the categories, the engines, the migration paths, or the deployment envelope. Any genuinely new storage decision that is architecturally significant must be recorded in a new ADR, not slipped into a design document.

### 11.4 Why Backend Implementation Must Not Redefine the Database Model

Backend implementation must realize the approved database design; it must not invent it. The reasons:

1. **The model is architecture.** ADR-001 classifies database design as an architecture concern. A backend that redefines the model in code effectively rewrites architecture without governance, review, or approval.
2. **Traceability breaks.** If the implemented schema diverges from the designed model, the chain from requirement to architecture to design to code becomes untraceable, and the design documents become fiction.
3. **Migration cost.** Redefinition after implementation means the "design" is whatever the first implementation produced — a schema-shaped-by-codebase, with no principled basis for the changes later needed for teams, universities, or SaaS stages (07 §5).
4. **Review is lost.** A model defined in code is invisible to reviewers and future contributors. The whole point of this milestone is that the model is reviewed before it is realized.

The enforcement mechanism is already in place: the data access layer boundary (05 §16, API-032, API-033) means the model is realized behind a controlled interface, and implementation discipline is verified by the Review Checklist (07) and Definition of Done (05 §2.4).

---

## 12. The Database Design Document Set

### 12.1 Layered Construction

Database design differs from the SRS and Architecture phases in one structural respect: **every database document builds directly on the documents before it**. Each document is a layer: it takes the previous layer as complete and authoritative, and adds the next level of detail. The set is therefore produced in order and reviewed as a progression, not as independent documents.

The planned document set is:

| # | Document | Layer | Answers |
|---|----------|-------|---------|
| 01 | `01_Database_Overview.md` | **Why** | Why does the database exist? What are its boundaries, authority, and governing rules? *(This document.)* |
| 02 | `02_Domain_Model.md` | **What** | What information exists? The business language of ScholarOS: the complete inventory of domains the system manages, derived from SRS Chapter 7 and 03_Data_Architecture.md, with no structural commitments. |
| 03 | `03_Conceptual_Data_Model.md` | **How related** | How do those concepts relate? The conceptual entities, relationships, cardinalities, aggregation, bounded contexts, and business rules — still no structure or technology. |
| 04 | `04_Logical_Data_Model.md` | **Logical model** | The logical data model: entities, attributes, identifiers, integrity rules, and the structural design contract, still technology-independent. |
| 05 | `05_Constraints_and_Integrity.md` | **Refinement** | Refinement of constraints, integrity, validation, and consistency rules; how the model enforces the quality attributes of §10. |
| 06 | `06_Storage_and_Retrieval_Mapping.md` | **Refinement** | Mapping of the logical model onto the approved storage categories and engines (07 §3, ADR-004, ADR-005); retention and lifecycle mapping; still design-level, no DDL. |
| 07 | `07_Operational_Data_Design.md` | **Refinement** | Operational refinement: backup/recovery assumptions, archival, the durable outbox (ADR-006), and the migration path constraints. |
| 08 | `08_Validation_and_Review.md` | **Validation** | Validation of the completed design against the SRS, architecture, and ADR set; gap analysis; design review and milestone close-out. |

This structure follows the enterprise practice of building database specifications in layers — from why, to what, to how related, to the logical model, then through progressive refinement and validation. The titles of documents 02–04 were confirmed on 2026-08-07 (`02_Domain_Model.md`, `03_Conceptual_Data_Model.md`, `04_Logical_Data_Model.md`) and recorded in the journal. The exact titles and content of documents 05–08 will be confirmed as the milestone proceeds, recorded in the journal, and may be adjusted without altering the layering.

### 12.2 Authoritative Source Rule

Every database design document after `01_Database_Overview.md` — and every engineering session that produces one — shall apply the following rule:

> **Treat all previously completed database documents as authoritative sources. Do not duplicate their content. Extend the design by adding the next level of detail while maintaining consistency with everything already established.**

Consequences of this rule:

* A later document may reference an earlier document's decisions; it must not restate them.
* If a later document needs to correct an earlier one, the correction is recorded in the journal rather than silently edited, per the consistency-violation record rule (04_Repository_Governance.md §5.3) and the minor-corrections clause (01_Project_Constitution.md §9).
* Terminology established in earlier documents (domain names, attribute vocabulary, relationship language) is binding on later documents.
* Each document is expected to add one level of detail and be consistent with the whole — a reviewer should be able to read the set from 01 to 08 as a single, continuously refined specification.

### 12.3 Document Dependency Rules

* Documents are produced in numeric order; no document may be finalized before its predecessors are reviewed and consistent.
* Each document traces back to the SRS, the architecture, and the ADR set (§16), and forward to the documents that depend on it.
* Design-only discipline (§15) applies to every document in the set; none may introduce SQL, DDL, or implementation artifacts.
* The set remains subordinate to the frozen architecture and ADR baseline; any conflict is resolved by the document hierarchy (01_Project_Constitution.md §5) and recorded in the journal.
* Documents 05–07 map the logical model only onto the storage categories of 07_Operational_Architecture.md §3 and reference the governing ADRs; they never select, configure, or specify engines, schemas, or indexes.

---

## 13. Downstream Dependencies: What This Milestone Enables

### 13.1 How API Design Depends on This Milestone

The API design milestone (SRS Chapter 9, 05_Backend_Architecture.md §3.1) will define the service contracts through which the frontend and external actors interact with the system. Those contracts cannot be stable until the persistence model beneath them is stable:

* **Payloads reflect the logical model.** API request and response payloads (API-041 to API-043) describe entities, identifiers, and relationships. If the logical model is undefined, payload design either invents the model or floats disconnected from it.
* **Service boundaries map to data ownership.** The service boundaries of 05 §4 correspond to the domains the logical model organizes; API design formalizes the interface over that ownership.
* **Data access contracts presume a model.** The data access layer (API-032, API-033) exposes persistence operations over the designed model. API design defines the semantics; database design defines the structure those semantics operate on.
* **Versioning and review semantics are structural.** Draft versioning, review state, memory supersession, and evidence annotations (DR-016 to DR-019, DR-014) are structural properties first and interface properties second. API design consumes the structural decisions made here.

Database design therefore produces the stable structural foundation that API design formalizes into contracts. Reversing the order — designing APIs against an undefined model — produces interfaces that either leak implementation detail or must be redesigned once the model is finally specified.

### 13.2 What Must Never Be Implemented Before Database Design Is Complete

The following must never be implemented (code, migrations, or schema) before the database design milestone is complete and reviewed:

* The relational schema of the structured core, including tables, columns, and keys.
* The knowledge-chunk and evidence-link structures (ADR-005 constraints).
* The memory record structure, including versioning and supersession semantics (ADR-004).
* The draft version and review state structures.
* The durable outbox and event record structures (ADR-006).
* Any migration scripts or data-access code that assumes a schema.
* Any ORM models that define the persistence structure.
* Any API payloads that encode persistence structure decisions.

Backend implementation may begin only after the database design set (01–08) is complete and reviewed, per the approved lifecycle (§4) and the Definition of Done (05).

---

## 14. Design Assumptions

The database design milestone operates under the following assumptions:

* The architecture set (01–07) and the ADR set (ADR-001 to ADR-007) remain the authoritative, frozen design baseline.
* The repository remains implementation-agnostic at the conceptual and logical levels.
* Persistence must support the MVP (single authenticated user, single-node deployment) while preserving a credible path to teams, universities, enterprise, and SaaS stages (07 §5).
* The storage categories and engines are fixed by 07 §3 and ADR-004/ADR-005; the milestone refines mapping, not categories.
* Project memory is a first-class persisted domain, never reconstructed from conversation logs (ADR-004).
* Retrieval operates over knowledge chunks with first-class evidence links (ADR-005).
* Long-running work is coordinated through durable events and an outbox in the structured core (ADR-006).
* The database design contract must remain compatible with the later API design and backend implementation milestones.
* The MVP assumes a single authenticated user; multi-user tenancy decisions are deferred to the stage that requires them (07 §5, ADR-007) and will be recorded in future ADRs.

These assumptions preserve the current milestone's discipline without overstepping into implementation design.

---

## 15. Out of Scope

The following items are explicitly out of scope for this document and for the design documents of this milestone:

* SQL, DDL, or any concrete schema definition.
* Schema creation scripts, migration scripts, or seed data.
* Index design, tuning strategy, or query plans.
* ORM mappings or application-level persistence code.
* API payload definitions or service contracts.
* Framework-specific implementation decisions.
* Storage engine configuration, replication, or deployment-specific infrastructure beyond the approved architectural and ADR context.
* Multi-tenant data isolation design (deferred to the stage that requires it; future ADR).

These concerns may be created later, but they are not part of the database design milestone's documents. Where a physical concern must be acknowledged (engines, migration paths), the design references the governing ADR rather than specifying the realization.

---

## 16. Traceability

This database overview is traceable to the approved repository baseline as follows:

* **Vision** — product intent: continuity, evidence grounding, project memory, and author preservation (§5 Product Philosophy, §6 Core Principles, §10 User Workflow, §13 Long-Term Vision).
* **SRS Chapter 2** — product scope and capabilities that the database must support.
* **SRS Chapter 3** — system-level context and responsibilities.
* **SRS Chapter 4** — functional domains that require persistent support.
* **SRS Chapter 5** — quality attributes (NFR-003 to NFR-008, NFR-013 to NFR-018, NFR-023 to NFR-034).
* **SRS Chapter 6** — AI and memory persistence expectations (AIR-019 to AIR-027, AIR-046 to AIR-048, AIR-055 to AIR-068).
* **SRS Chapter 7** — data requirements and conceptual information management (DR-001 to DR-035).
* **SRS Chapter 8** — workflow continuity and persistence expectations.
* **SRS Chapter 9** — the later API contract boundary that depends on a stable persistence model (API-032, API-033, API-041 to API-043).
* **SRS Chapter 10** — MVP scope boundaries for the data model.
* **Architecture 01** — layered architecture and the Data and Knowledge Layer.
* **Architecture 03** — conceptual data domains and ownership model.
* **Architecture 04** — intelligence operating model and retrieval/memory pipelines.
* **Architecture 05** — backend domains and the data access layer boundary.
* **Architecture 07** — storage categories, consistency model, retention, backup, and scalability evolution.
* **ADR-001** — separation of concerns; database design classified as an architecture concern.
* **ADR-002** — ORM abstraction behind the data access layer.
* **ADR-003** — modular service boundaries and per-module data ownership.
* **ADR-004** — storage engines and memory persistence strategy.
* **ADR-005** — retrieval and search strategy constraints on the knowledge model.
* **ADR-006** — async processing and the durable outbox.
* **ADR-007** — deployment envelope and migration path.
* **Governance** — the development lifecycle (01 §6), documentation standards (09), and the standing engineering responsibilities (11) that govern how this milestone is executed.

The database design milestone must remain accountable to these references. It is not an independent design activity; it is the next formal step in the approved lifecycle.

---

## 17. Summary

ScholarOS requires a database design milestone because its product is built around persistent research context, evidence, memory, author continuity, and traceable workflow state. The persistence layer is not an implementation shortcut; it is a core architectural concern (ADR-001).

This document establishes the database design milestone as a disciplined bridge between architecture and later implementation. It defines the purpose of database design, its boundaries, its traceability obligations, its relationship to the SRS, the architecture, and the ADR set, and the specific concerns it must not preempt.

The milestone will be executed as a layered document set (01–08), where each document treats all previously completed database documents as authoritative sources and adds the next level of detail — from why the database exists, to what information it manages, to how that information relates, to the logical data model, and through progressive refinement and validation. This structure keeps the design reviewable at every level and guarantees that when implementation finally begins, the database model is already decided, documented, and approved — never invented in code.

The database design phase exists to make persistence understandable, reviewable, and governable before backend implementation begins. That is the central purpose of this document.
