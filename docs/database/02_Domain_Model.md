# Domain Model

**Document:** 02_Domain_Model.md

**Status:** Active

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design

**Revision:** 1

---

## 1. Purpose

This document defines the **domain model** of ScholarOS: the business language of what information exists inside the system. It answers the question *"What information exists?"* at the level of business concepts — before any structure, relationship detail, or technology is introduced.

It is the second layer of the database design document set ([01_Database_Overview.md](01_Database_Overview.md) §12). Document 01 established *why* the database exists and the rules that govern this milestone. This document establishes *what* the database must know, in the vocabulary of the product.

This document is conceptual by construction:

* It names domains and explains their purpose, responsibility, ownership, lifecycle, and dependencies.
* It does not discuss tables, SQL, attributes, keys, or storage.
* It does not define how domains relate in detail — that is the responsibility of [03_Conceptual_Data_Model.md](03_Conceptual_Data_Model.md).

**Authoritative Source Rule:** per [01_Database_Overview.md](01_Database_Overview.md) §12.2, this document treats Document 01 as authoritative, extends it with the next level of detail, and does not duplicate its content.

---

## 2. How the Domains Were Identified

The domain inventory was not copied from any single source. It was derived by cross-validating the authoritative baselines:

| Source | Contribution |
|--------|--------------|
| SRS Chapter 7 (Data Requirements) | The seven data domains (DR-001 to DR-033, DR-035; DC-002, DC-003) |
| [03_Data_Architecture.md](../architecture/03_Data_Architecture.md) §3 | The ten conceptual data domains and the ownership model (§4) |
| [04_AI_Architecture.md](../architecture/04_AI_Architecture.md) | How knowledge, chunking, memory, conversation, and agents are consumed and produced by the intelligence layer (§7–§10, §14, §18) |
| [05_Backend_Architecture.md](../architecture/05_Backend_Architecture.md) §4 | The nine backend domain boundaries that will own this data |
| ADR-004, ADR-005, ADR-006 | Persistence-relevant decisions: memory as a first-class domain, chunk-level retrieval with evidence links, durable outbox |
| SRS Chapter 10 (MVP Scope) | Which domains the first release must realize |

Candidates from product intuition that were **not** supported by these baselines (e.g., standalone "Citations", "Prompt Assets", "Generated Responses", "Version History" domains) are discussed in §7 — validated against the baselines rather than copied.

---

## 3. Domain Model Overview

ScholarOS manages twelve domains. Each is a coherent area of information with a single business purpose:

| # | Domain | One-line purpose |
|---|--------|------------------|
| 1 | **Project** | The research undertaking as the primary unit of work. |
| 2 | **Research Document** | The source materials the researcher supplies as evidence. |
| 3 | **Knowledge** | The interpreted understanding derived from source materials. |
| 4 | **Knowledge Chunk** | The discrete, retrievable units of that understanding. |
| 5 | **Memory** | The persistent project context, decisions, and chronology. |
| 6 | **Conversation** | The interaction history between researcher and system. |
| 7 | **Writing Profile** | The author's preserved writing characteristics. |
| 8 | **Capability** | The catalog of intelligence capabilities (renamed from "Agent"; ADR-009). |
| 9 | **Draft** | The generated and refined academic content. |
| 10 | **Review** | The evaluation, decision, and approval of drafts. |
| 11 | **Configuration** | The operational settings governing system behavior. |
| 12 | **User and Session** | The identity and interaction boundary. |
| 13 | **Agent** | The user's permanent, specialized research workspace — added by ADR-009. |

This inventory was extended from twelve to thirteen domains by ADR-009 (2026-09-04), which introduced **Agent** as the user's permanent workspace and renamed the pre-existing capability-registry domain from "Agent" to "Capability" to free the name. Domain #13 (Agent) is listed last to preserve the numbering of domains #1–#12 exactly as reviewed and frozen at Milestone 5 close-out; its position in this table does not reflect its role in the ownership hierarchy — see §4.13 and the corrected relationships in §5.

---

## 4. Domain Definitions

Each domain below defines its **purpose** (why it exists), **responsibility** (what it is accountable for), **ownership** (who controls it), **lifecycle** (how it changes over time), and **dependencies** (what it requires from other domains).

### 4.1 Project

* **Purpose.** Represent the specific research undertaking's raw input material: its identity, topic, and the source documents supplied for it (DR-001 to DR-003; 03 §3.1; WR-001 to WR-003). **Corrected by ADR-009:** Project no longer anchors knowledge, memory, drafts, or writing profile directly — those are now owned by the Project's owning **Agent** (§4.13).
* **Responsibility.** Establish the identity, topic, and lifecycle state of a research undertaking, and own its raw source materials (Research Documents). Project is nested inside exactly one Agent (ADR-009).
* **Ownership.** User-owned, via its owning Agent. The researcher is the author and steward of the project and its contents (03 §4).
* **Lifecycle.** Created together with its owning Agent at Agent creation (ADR-009); updated as source materials are added; closed or archived when the research undertaking concludes (03 §3.1 lifecycle; WR-001 to WR-003).
* **Dependencies.** Depends on **Agent** (1:1, permanent; ADR-009). **Research Document** depends on **Project** for scoping.

### 4.2 Research Document

* **Purpose.** Represent the research source materials supplied by the user (DR-004 to DR-006; 03 §3.2; WR-004 to WR-006).
* **Responsibility.** Preserve source identity, metadata, content, and processing status; serve as the evidential basis for interpretation and drafting support (04 §18).
* **Ownership.** User-owned, associated with a specific project (03 §3.2).
* **Lifecycle.** Ingested into a project; processed into interpretable knowledge; retained as source evidence for the life of the project or until explicitly removed (07 §3.4; 05 §10).
* **Dependencies.** Depends on **Project**. Feeds **Knowledge** and **Knowledge Chunk**.

### 4.3 Knowledge

* **Purpose.** Represent the structured, interpreted understanding of the research domain: concepts, themes, methods, relationships, and evidence-based insights (DR-007 to DR-009; 03 §3.3; AIR-007 to AIR-012).
* **Responsibility.** Capture what the system understands about the domain; support retrieval and context assembly; preserve evidence linkage to source material (AIR-024, DR-008).
* **Ownership.** Shared: the system derives knowledge through processing, but the user retains authority over research content and interpretation (03 §3.3, §4).
* **Lifecycle.** Created through interpretation of source materials; refined as the project evolves; superseded when new evidence alters prior understanding, with history retained (07 §3.3; AIR-065).
* **Dependencies.** Derived from **Research Document**. Referenced by **Memory**, **Knowledge Chunk**, and **Draft**.

### 4.4 Knowledge Chunk

* **Purpose.** Represent discrete units of interpreted knowledge that can be retrieved and reused (03 §3.4; 04 §9; DR-007 to DR-009; MVP-007 to MVP-008).
* **Responsibility.** Provide modular, evidence-carrying units for focused retrieval; support the hybrid retrieval strategy of ADR-005.
* **Ownership.** Derived artifact associated with the project; sourced from user-provided materials (03 §3.4).
* **Lifecycle.** Created during knowledge processing; re-linked or revised as project knowledge evolves; retained while relevant, eligible for controlled removal per the data lifecycle (04 §9.2; DR-023 to DR-025).
* **Dependencies.** Derived from **Knowledge**; linked to **Research Document** (evidence); consumed by **Draft** (evidence annotations) and retrieval.

### 4.5 Memory

* **Purpose.** Represent persistent project context, reasoning continuity, and decision history (DR-013 to DR-015; 03 §3.5; 04 §8; AIR-019 to AIR-021, AIR-065 to AIR-066).
* **Responsibility.** Retain research objectives, methodological choices, terminology, rationale, and decisions; reduce the need to re-establish context across sessions; preserve chronology and supersession (DR-014).
* **Ownership.** Owned by the Agent and the user; the system preserves and organizes it (03 §3.5; ADR-009). Memory is a first-class persisted domain, never reconstructed from conversation logs (ADR-004).
* **Lifecycle.** Created when project decisions or context are established; updated as the project evolves; superseded by newer decisions while historical traceability is retained (04 §8.2; DR-014).
* **Dependencies.** Populated from user input and system-derived context (including review outcomes and conversation outcomes); referenced by context assembly and drafting (04 §8.3).

### 4.6 Conversation

* **Purpose.** Represent the interaction history between the researcher and the system over the course of the project (03 §3.6; 04 §10; WR-034; AIR-005).
* **Responsibility.** Capture user intent, clarifications, requests, and system responses; preserve the evolution of the research workflow as a continuity record.
* **Ownership.** User-owned, within the owning Agent's context; the system preserves the interaction record (03 §3.6; ADR-009).
* **Lifecycle.** Created as the user interacts; retained as a continuity record; may be summarized or linked to memory rather than stored verbatim indefinitely (03 §3.6; 04 §10.2).
* **Dependencies.** Scoped by **Project**; may reference **Research Document**, **Knowledge**, **Draft**, and **Memory** (04 §10.2); informs **Memory** only with user awareness (MVP-011).

### 4.7 Writing Profile

* **Purpose.** Represent the author's writing characteristics and stylistic attributes without copying prior work verbatim (DR-010 to DR-012; 03 §3.7; AIR-016 to AIR-018; MVP-009 to MVP-010).
* **Responsibility.** Preserve writing patterns, vocabulary tendencies, structure preferences, and citation habits; support stylistic continuity in drafting.
* **Ownership.** User-owned, associated with one or more Agents; in the MVP, scoped to the single Agent (03 §3.7; ADR-009).
* **Lifecycle.** Created from supplied writing samples; updated as the user refines it; reused across future projects or sessions where appropriate (03 §3.7).
* **Dependencies.** Derived from **User**-supplied samples; consumed by drafting; **Draft** depends on it for style application (AIR-016).

### 4.8 Capability

**Renamed from "Agent" by ADR-009** to free that name for the new user-workspace domain (§4.13). Meaning and function are unchanged.

* **Purpose.** Represent the catalog of intelligence capabilities that support the workflow (03 §3.8; 04 §14; AIR-058 to AIR-060; 05 §13).
* **Responsibility.** Maintain an inventory of capabilities (knowledge processing, retrieval, drafting, review, coordination); support routing and controlled extension of capabilities.
* **Ownership.** Architecture-level capability ownership; system-managed, configuration-governed (04 §14.2; AIR-055 to AIR-056).
* **Lifecycle.** Registered as named, replaceable units; updated through the controlled extension path (04 §14.2; AIR-058 to AIR-060).
* **Dependencies.** Governed by **Configuration**; consumed by the orchestration layer (05 §13).

### 4.9 Draft

* **Purpose.** Represent the academic content generated or refined during the project (DR-016 to DR-019; 03 §3.9; WR-019 to WR-021; MVP-015 to MVP-017).
* **Responsibility.** Preserve draft content, structure, revisions, and review state; support iterative refinement and human approval; retain version history (DR-017, MVP-021).
* **Ownership.** User-owned, associated with the owning Agent (03 §3.9; ADR-009).
* **Lifecycle.** Created from a drafting task; revised through iterative workflow cycles; approved, rejected, or superseded as the project progresses (03 §3.9; 04 §20).
* **Dependencies.** Built from **Knowledge Chunk** (evidence), **Memory** (context), and **Writing Profile** (style); reviewed by **Review**.

### 4.10 Review

* **Purpose.** Represent the evaluation and approval state of drafts and supporting outputs (DR-019; 03 §3.10; WR-022 to WR-025; AIR-037 to AIR-039; MVP-018 to MVP-020).
* **Responsibility.** Capture review feedback, revision requests, and approval decisions; preserve evidence of human oversight for audit (AIR-054).
* **Ownership.** User-owned; the researcher is the final reviewer and approver (03 §3.10; AIR-003, AIR-038).
* **Lifecycle.** Created during draft review; updated through revision cycles; preserved as part of project history (03 §3.10).
* **Dependencies.** Applies to **Draft**; consumes evidence references from **Knowledge Chunk**; outcomes update **Memory** (04 §19.3).

### 4.11 Configuration

* **Purpose.** Represent the operational settings that govern system behavior: system-level defaults, project-level settings, and user preferences (DR-020 to DR-022; SRS Ch7 §3.7; AIR-055 to AIR-057; NFR-031 to NFR-032; 05 §17).
* **Responsibility.** Manage provider selection, workflow parameters, and preference state without altering the approved product contract; preserve configuration history for audit (DR-021).
* **Ownership.** System-managed for system and project layers; user preferences are user-owned and persist across projects (DR-022).
* **Lifecycle.** Established during setup or modification; changed in a reviewable, auditable manner (AIR-056, AIR-057).
* **Dependencies.** Governs **Capability**, provider abstraction (ADR-002), and workflow behavior; referenced by all domains through the configuration model (05 §17). Configuration scope renamed from `project` to `agent` by ADR-009 (§5, §11.3).

### 4.12 User and Session

* **Purpose.** Represent the identity of the researcher and the interaction boundary of the system (05 §15; NFR-009, NFR-010; API-036, API-037; WR-038).
* **Responsibility.** Establish and verify identity before any service is accessed; authorize access to projects and project data; protect artifacts from unauthorized modification (05 §15.1).
* **Ownership.** User-owned identity. The MVP assumes a single authenticated user per deployment (SRS Ch10 §2; WR-038; MVP-001); the model is designed to extend to multi-user roles at later stages (07 §5).
* **Lifecycle.** Identity established at registration; sessions created and ended per interaction; the boundary is designed so multi-user can be added without reshaping the model (05 §15.2).
* **Dependencies.** **Project**, **Conversation**, and **Writing Profile** reference the user; **Session** provides the interaction context.

### 4.13 Agent

**Added by ADR-009.** Not part of the original twelve-domain inventory frozen at Milestone 5 close-out; introduced by a subsequent architecturally significant correction, following the product clarification recorded in `docs/journal/2026-09-04.md`.

* **Purpose.** Represent the user's permanent, specialized research workspace: the entity that wraps one Project and accumulates everything the system learns and produces around it over time (ADR-009).
* **Responsibility.** Anchor identity for everything derived from or accumulated within its one Project — Knowledge, Memory, Conversation, Writing Profile, Draft, and Review; enforce the MVP boundary of one Agent per User.
* **Ownership.** User-owned. The Agent is created by the user and never transferred or merged with another Agent.
* **Lifecycle.** Created together with its one Project at initiation, from the user-supplied topic, reference documents, and writing-style samples; persists permanently for the life of the user's engagement with that research undertaking; never replaced or reassigned to a different Project (ADR-009).
* **Dependencies.** Depends on **User** (1:1 for the MVP; additional Agents per user are a deferred, monetization-gated capability, not built now) and **Project** (1:1, permanent — the pairing never changes). Owns **Knowledge**, **Knowledge Chunk**, **Memory**, **Conversation**, **Writing Profile**, **Draft**, and **Review**.

---

## 5. High-Level Relationships Between Domains

The following relationships are stated at the business level. Their structural realization (entities, cardinality, resolution) belongs to [03_Conceptual_Data_Model.md](03_Conceptual_Data_Model.md) and [04_Logical_Data_Model.md](04_Logical_Data_Model.md).

| From | To | Nature of relationship |
|------|----|------------------------|
| User | Agent | A user owns exactly one Agent in the MVP (ADR-009). |
| Agent | Project | An Agent owns exactly one Project, permanently (ADR-009). |
| Project | Research Document | A project contains its source materials. |
| Agent | Knowledge | An Agent hosts its interpreted understanding (ADR-009). |
| Agent | Knowledge Chunk | An Agent hosts its retrievable chunks (ADR-009). |
| Agent | Memory | An Agent accumulates its memory records (ADR-009). |
| Agent | Conversation | An Agent scopes its interaction history (ADR-009). |
| Agent | Draft | An Agent produces its drafts (ADR-009). |
| Agent | Writing Profile | An Agent is associated with an author profile (ADR-009). |
| Research Document | Knowledge | Documents are the source from which knowledge is derived. |
| Knowledge | Knowledge Chunk | Knowledge is divided into retrievable chunks. |
| Knowledge Chunk | Research Document | Chunks are evidence-linked to source documents. |
| Knowledge Chunk | Draft | Drafts are evidence-grounded in chunks. |
| Memory | Draft | Memory supplies persistent context to drafting. |
| Writing Profile | Draft | The profile shapes draft style. |
| Draft | Review | Drafts are evaluated by reviews. |
| Review | Memory | Review outcomes inform memory. |
| Capability | Configuration | Capability sets are configuration-governed (renamed from "Agent"; ADR-009). |
| Conversation | Memory | Approved conversation outcomes enter memory with user awareness. |
| Configuration | All domains | Configuration governs behavior across all domains. |

These relationships mirror the conceptual relationships of SRS Chapter 7 §5 (DR-026 to DR-028) and the information flow of 03 §5, as corrected by ADR-009. Prior to ADR-009, the "Project | Knowledge/Memory/Conversation/Draft/Writing Profile" rows above read "User owns projects" and scoped these domains directly to Project; ADR-009 inserts Agent as an intermediate ownership layer.

---

## 6. Domain Vocabulary

The following terms are binding on all later database documents. They must be used consistently; no later document may introduce synonyms or conflicting names (01 §12.2).

| Term | Meaning |
|------|---------|
| **Domain** | A coherent area of information with a single business purpose (§3). |
| **Project** | The research undertaking; primary unit of work. |
| **Research Document** | A user-supplied source material; evidence. |
| **Knowledge** | Interpreted understanding derived from source materials. |
| **Knowledge Element** | An individual unit of knowledge (concept, theme, method, claim, relationship). |
| **Knowledge Chunk** | A discrete retrievable unit of interpreted knowledge carrying evidence. |
| **Memory** | Persistent project context, decisions, and chronology. |
| **Memory Record** | An individual persisted element of memory. |
| **Conversation** | Interaction history within a project. |
| **Message** | An individual exchange within a conversation (user request or system response). |
| **Writing Profile** | The author's preserved writing characteristics. |
| **Capability** | A registered intelligence capability (renamed from "Agent" by ADR-009). |
| **Draft** | Generated or refined academic content. |
| **Review** | Evaluation and approval of a draft. |
| **Review Decision** | The recorded outcome of a review (approve, revise, reject). |
| **Configuration** | Operational settings governing system behavior. |
| **Evidence Link** | The traceable association between interpreted/generated content and its source material. |
| **Supersession** | The replacement of an earlier record by a newer one with history retained. |
| **Agent** | The user's permanent, specialized research workspace, owning exactly one Project (added by ADR-009). |

---

## 7. Candidate Concepts Validated Out

The following candidate domains were considered and **validated out** against the authoritative baselines. They are not domains of the MVP model:

| Candidate | Decision | Rationale |
|-----------|----------|-----------|
| **Citations / References** | Not a standalone domain in the MVP | Evidence linkage is a first-class *relationship* (evidence links, ADR-005; 04 §18), not a separate domain. Automated citation management is explicitly out of MVP scope (SRS Ch10 out-of-scope list) and scheduled in the roadmap (SRS Ch11). |
| **Prompt Assets** | Not a user data domain | Prompt construction is a structured capability of the intelligence layer (04 §15; AIR-028 to AIR-030). Prompt and workflow assets are configuration-governed (AIR-055) and belong to **Configuration**. |
| **Generated Responses** | Not a separate domain | Substantive generated content is **Draft**; conversational responses are **Message** within **Conversation** (03 §3.6, §3.9; AIR-006 artifact distinction). |
| **Version History** | Not a separate domain | Versioning is a cross-cutting strategy realized in the logical model: draft versions (DR-017, MVP-021), memory chronology (DR-014), and knowledge supersession (07 §3.3). Document 04 defines it. |
| **Capability Configurations** | Part of **Configuration** | Capability sets and workflow parameters are configuration-governed and reviewable (AIR-055 to AIR-057). (Renamed from "Agent Configurations" by ADR-009.) |
| **Sessions (login)** | Part of **User and Session** | Session state supports the authentication boundary (05 §15) but is not a business domain. |

---

## 8. Traceability

This domain model is traceable to the approved baseline as follows:

* **Vision** — product principles that require persistence: understanding before writing, evidence before opinion, project memory, author preservation (§5, §6, §10).
* **SRS Chapter 2** — the capabilities these domains support (document intelligence, knowledge management, author style preservation, project memory, drafting, review).
* **SRS Chapter 4** — the functional domains that require persistent support.
* **SRS Chapter 6** — AI requirements: knowledge (AIR-007 to AIR-012), memory (AIR-019 to AIR-021, AIR-065 to AIR-066), profile (AIR-016 to AIR-018), retrieval and evidence (AIR-022 to AIR-027, AIR-046 to AIR-048), review (AIR-037 to AIR-039), provider and configuration (AIR-040 to AIR-042, AIR-055 to AIR-057).
* **SRS Chapter 7** — the seven data domains (DR-001 to DR-033, DR-035; DC-002, DC-003).
* **SRS Chapter 10** — MVP scope: which domains the first release realizes (MVP-001 to MVP-022).
* **Architecture 03** — the ten conceptual data domains and the ownership model (§3, §4).
* **Architecture 04** — knowledge processing (§7), memory (§8), chunking (§9), conversation (§10), agents (§14), evidence flow (§18), review (§19), writing (§20).
* **Architecture 05** — the nine backend domain boundaries (§4).
* **Architecture 07** — storage categories and retention (§3), scalability evolution (§5).
* **ADR-004** — memory as a first-class persisted domain.
* **ADR-005** — chunk-level retrieval with first-class evidence links.
* **ADR-006** — durable outbox for asynchronous work.
* **Database Overview (01)** — the governing rules and document set for this milestone (§8, §12).
* **ADR-009** — introduces the Agent domain, narrows Project's scope, and renames the capability-registry domain from "Agent" to "Capability."

---

## 9. Summary

The ScholarOS domain model, as corrected by ADR-009, consists of thirteen domains — Project, Research Document, Knowledge, Knowledge Chunk, Memory, Conversation, Writing Profile, Capability, Draft, Review, Configuration, User and Session, and Agent — each with a defined purpose, responsibility, ownership, lifecycle, and dependencies. Agent is the user's permanent, specialized workspace, owning exactly one Project and everything derived from or accumulated within it (Knowledge, Memory, Conversation, Writing Profile, Draft, Review); Project retains identity, topic, lifecycle, and Research Document ownership. Candidates that product intuition suggested but the baselines did not support (Citations, Prompt Assets, Generated Responses, Version History, Capability Configurations, login Sessions) were validated out with explicit rationale.

This document establishes the **business language** of ScholarOS. The next document in the layered set, [03_Conceptual_Data_Model.md](03_Conceptual_Data_Model.md), defines how these domains relate to one another.
