# Conceptual Data Model

**Document:** 03_Conceptual_Data_Model.md

**Status:** Active

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design

**Revision:** 1

---

## 1. Purpose

This document defines the **conceptual data model** of ScholarOS: the entities of the system and the relationships among them, expressed in the language of the business. It answers the question *"How are those information domains related?"*

It is the third layer of the database design document set ([01_Database_Overview.md](01_Database_Overview.md) §12). Document 02 defined *what* information exists as business domains. This document transforms those domains into conceptual entities and describes how they relate — without any structural or technical commitment.

This document is conceptual by construction:

* It describes entities, relationships, cardinalities, aggregation, composition, inheritance, bounded contexts, business rules, and lifecycle relationships in text.
* It does **not** define primary keys, indexes, datatypes, SQL, or storage decisions.
* It expresses the language of the business; structural refinement belongs to [04_Logical_Data_Model.md](04_Logical_Data_Model.md).

**Authoritative Source Rule:** per [01_Database_Overview.md](01_Database_Overview.md) §12.2, this document treats Documents 01 and 02 as authoritative, uses their vocabulary (§6 of 02), extends the design, and does not duplicate their content.

---

## 2. Conceptual Entities

Each domain of [02_Domain_Model.md](02_Domain_Model.md) is realized as one or more conceptual entities. An entity is a thing about which the system records information; it is expressed by name and definition only.

| # | Conceptual entity | Domain (02) | Definition |
|---|-------------------|-------------|------------|
| 1 | **User** | User and Session | The researcher whose identity anchors the system (05 §15). |
| 2 | **Session** | User and Session | A bounded interaction context of a user. |
| 3 | **Project** | Project | The research undertaking; container of all project-scoped work. |
| 4 | **Research Document** | Research Document | A user-supplied source material retained as evidence. |
| 5 | **Knowledge Element** | Knowledge | An individual unit of interpreted understanding (concept, theme, method, claim, relationship). |
| 6 | **Knowledge Chunk** | Knowledge Chunk | A discrete retrievable unit of interpreted knowledge carrying evidence. |
| 7 | **Memory Record** | Memory | An individual persisted element of project context or decision history. |
| 8 | **Conversation** | Conversation | The interaction history of a project. |
| 9 | **Message** | Conversation | An individual exchange within a conversation (user request or system response). |
| 10 | **Writing Profile** | Writing Profile | The author's preserved writing characteristics. |
| 11 | **Profile Characteristic** | Writing Profile | A single preserved stylistic attribute (structure preference, terminology tendency, citation habit). |
| 12 | **Capability** | Capability | A registered intelligence capability (renamed from "Agent"; ADR-009). |
| 13 | **Capability Entry** | Capability | A registered capability entry of the capability registry (04 §14). (Renamed from "Agent Capability"; ADR-009.) |
| 14 | **Draft** | Draft | Generated or refined academic content, existing as a series of versions. |
| 15 | **Draft Version** | Draft | An immutable state of a draft produced by one writing or revision cycle. |
| 16 | **Review** | Review | An evaluation round applied to a draft version. |
| 17 | **Review Decision** | Review | The recorded outcome of a review (approve, revise, reject). |
| 18 | **Configuration Item** | Configuration | A single governed operational setting. |
| 19 | **Work Item** | (system-managed, ADR-006) | A unit of asynchronous work recorded durably before execution (the outbox). |
| 20 | **Agent** | Agent | The user's permanent, specialized research workspace, owning exactly one Project (added by ADR-009). |

The following cross-cutting concepts appear as **relationships and rules**, not as standalone entities:

* **Evidence Link** — the association between interpreted/generated content and its source material (ADR-005; 04 §18). It connects chunks and drafts to research documents and knowledge.
* **Supersession** — the replacement of an earlier record by a newer one with history retained (DR-014; 07 §3.3). It connects a memory record (or knowledge element) to the record it supersedes.

---

## 3. Relationships

The relationships below are expressed in text-ER form. Cardinality notation: **1 : N** (one to many), **N : M** (many to many), **1 : 1** (one to one), **0..1** (optional one). Direction is stated from the "parent" to the "child".

### 3.1 User Relationships

* **User — Session: 1 : N.** A user has many sessions over time; each session belongs to exactly one user.
* **User — Agent: 1 : 1 (MVP).** A user owns exactly one Agent in the MVP; additional Agents per user are a deferred, monetization-gated capability, not built now (ADR-009). **Corrected by ADR-009** — previously "User — Project: 1 : N."
* **User — Writing Profile: 1 : N.** A user's profiles are created across Agents; each profile references the user who supplied the writing samples.

### 3.2 Project Relationships

**Narrowed by ADR-009.** Project no longer directly hosts knowledge, memory, conversations, drafts, writing profiles, or configuration — those relationships moved to Agent (§3.11). Project retains only:

* **Project — Research Document: 1 : N.** A project contains many source documents; each document belongs to exactly one project.

The Project entity itself is now owned by exactly one Agent — see **Agent — Project: 1 : 1** in §3.11.

### 3.3 Research Document Relationships

* **Research Document — Knowledge Element: 1 : N.** A document informs the derivation of many knowledge elements; each element traces to the document(s) it was derived from (DR-006, DR-008; AIR-024).
* **Research Document — Knowledge Chunk: N : M.** A document supports many chunks, and a chunk may draw evidence from several documents. This evidence linkage is first-class (ADR-005; 04 §18).

### 3.4 Knowledge Relationships

* **Knowledge Element — Knowledge Chunk: 1 : N.** A knowledge element is divided into one or more retrievable chunks; each chunk derives from one knowledge element (04 §9).
* **Knowledge Element — Knowledge Element: N : M (semantic).** Knowledge elements relate to one another through conceptual relationships (hierarchies, associations, dependencies; DR-009). The model records that these relationships exist; their full structural treatment is refined in the logical model.
* **Knowledge Element — Memory Record: N : M (provenance).** Memory records may reference the knowledge that informs them (DR-015).

### 3.5 Memory Relationships

* **Memory Record — Memory Record: 0..1 : N (supersession).** A memory record may supersede an earlier record; a record may be superseded by at most one newer record (at any time), and may be superseded again over time. History is retained (DR-014; 04 §8.2).
* **Memory Record — Knowledge Element / Research Document / Draft Version / Review Decision: N : M (provenance).** A memory record traces to the activities and artifacts that produced it (DR-015).

### 3.6 Conversation Relationships

* **Conversation — Message: 1 : N (composition).** A conversation is composed of an ordered series of messages; a message cannot exist outside its conversation.
* **Message — Project artifacts (Reference): N : M.** A message may reference research documents, knowledge elements, knowledge chunks, drafts, or memory records (04 §10.2). The structural realization of this polymorphic association is resolved in the logical model.
* **Conversation — Memory Record: N : M (approved outcomes).** Approved conversation outcomes enter memory only with user awareness (MVP-011; 04 §10.3).

### 3.7 Writing Profile Relationships

* **Writing Profile — Profile Characteristic: 1 : N (composition).** A profile is composed of its preserved characteristics; a characteristic cannot exist outside its profile (DR-010, DR-012).
* **Profile Characteristic — Research Document (provenance): N : M.** Profile characteristics trace to the authored samples that informed them (DR-012).
* **Writing Profile — Draft: N : M.** A profile shapes the drafting of many drafts; a draft is styled by the active profile of its project.

### 3.8 Capability Relationships

**Renamed from "Agent Relationships" by ADR-009.** Meaning unchanged; this describes the capability registry, not the new Agent workspace entity (§3.11).

* **Capability — Capability Entry: 1 : N (composition).** A capability registration is described by its registered entries; an entry cannot exist without its capability (04 §14.1).
* **Capability — Configuration Item: N : M.** Capabilities and their entry sets are configuration-governed and reviewable (AIR-055 to AIR-057).

### 3.9 Draft Relationships

* **Draft — Draft Version: 1 : N (composition).** A draft exists as an ordered series of versions; a version cannot exist without its draft (DR-017; MVP-021; AIR-035).
* **Draft Version — Knowledge Chunk / Research Document (Evidence Link): N : M.** Draft content is annotated with the evidence that supports it (DR-018; AIR-027; 04 §18.1 stage 4).
* **Draft Version — Memory Record: N : M.** A draft version draws on persistent context from memory (04 §20.1).
* **Draft Version — Writing Profile: N : M.** Drafting applies the project's active profile (AIR-016).

### 3.10 Review Relationships

* **Draft Version — Review: 1 : N.** A draft version is evaluated by one or more review rounds; each review applies to exactly one draft version (WR-022 to WR-025).
* **Review — Review Decision: 1 : 1.** Each review produces one recorded decision (approve, revise, reject) with rationale (DR-019; AIR-054).
* **Review Decision — Memory Record: N : M (outcome).** Review outcomes inform memory with user awareness (04 §19.3).

### 3.11 Agent Relationships

**Added by ADR-009.** Agent is the user's permanent workspace, inserted as an ownership layer between User and the domains previously scoped directly to Project.

* **Agent — Project: 1 : 1 (permanent).** An Agent owns exactly one Project for its entire life; the pairing is never replaced (ADR-009).
* **Agent — Knowledge Element: 1 : N.** An Agent hosts the knowledge derived within its Project; each knowledge element belongs to exactly one Agent. **Moved from Project (§3.2) by ADR-009.**
* **Agent — Knowledge Chunk: 1 : N.** An Agent hosts its retrievable chunks. **Moved from Project by ADR-009.**
* **Agent — Memory Record: 1 : N.** An Agent accumulates many memory records. **Moved from Project by ADR-009.**
* **Agent — Conversation: 1 : N.** An Agent scopes many conversations. **Moved from Project by ADR-009.**
* **Agent — Draft: 1 : N.** An Agent produces many drafts. **Moved from Project by ADR-009.**
* **Agent — Writing Profile: 1 : N.** An Agent is associated with the profiles that inform its drafting; in the MVP an Agent has at most one active profile, but the relationship is modeled as one-to-many to allow evolution (03 §3.7). **Moved from Project by ADR-009.**
* **Agent — Configuration Item: 1 : N.** An Agent may override system defaults with agent-level settings (DR-003). **Moved from Project by ADR-009; Configuration Item scope value renamed from `project` to `agent`.**

---

## 4. Cardinality Summary

| From | To | Cardinality | Nature |
|------|----|-------------|--------|
| User | Session | 1 : N | Owns |
| User | Agent | 1 : 1 (MVP) | Owns *(corrected by ADR-009; was User→Project 1:N)* |
| User | Writing Profile | 1 : N | Provides samples |
| Agent | Project | 1 : 1 (permanent) | Owns *(added by ADR-009)* |
| Project | Research Document | 1 : N | Contains |
| Agent | Knowledge Element | 1 : N | Hosts *(moved from Project by ADR-009)* |
| Agent | Knowledge Chunk | 1 : N | Hosts *(moved from Project by ADR-009)* |
| Agent | Memory Record | 1 : N | Accumulates *(moved from Project by ADR-009)* |
| Agent | Conversation | 1 : N | Scopes *(moved from Project by ADR-009)* |
| Agent | Draft | 1 : N | Produces *(moved from Project by ADR-009)* |
| Agent | Writing Profile | 1 : N | Associates *(moved from Project by ADR-009)* |
| Agent | Configuration Item | 1 : N | Configures *(moved from Project by ADR-009)* |
| Research Document | Knowledge Element | 1 : N | Informs (derivation) |
| Research Document | Knowledge Chunk | N : M | Supports (evidence) |
| Knowledge Element | Knowledge Chunk | 1 : N | Divides into |
| Knowledge Element | Knowledge Element | N : M | Relates to (semantic) |
| Knowledge Element | Memory Record | N : M | Informs (provenance) |
| Memory Record | Memory Record | 0..1 : N | Supersedes (self) |
| Conversation | Message | 1 : N | Composes (ordered) |
| Message | Project artifacts | N : M | References (polymorphic) |
| Conversation | Memory Record | N : M | Contributes (approved) |
| Writing Profile | Profile Characteristic | 1 : N | Composes |
| Profile Characteristic | Research Document | N : M | Traces to (provenance) |
| Writing Profile | Draft | N : M | Styles |
| Capability | Capability Entry | 1 : N | Composes *(renamed from Agent/Agent Capability by ADR-009)* |
| Capability | Configuration Item | N : M | Is governed by |
| Draft | Draft Version | 1 : N | Composes (ordered) |
| Draft Version | Knowledge Chunk / Research Document | N : M | Is evidence-grounded by |
| Draft Version | Memory Record | N : M | Draws on |
| Draft Version | Writing Profile | N : M | Is styled by |
| Draft Version | Review | 1 : N | Is evaluated by |
| Review | Review Decision | 1 : 1 | Produces |

---

## 5. Aggregation and Composition

The model distinguishes two kinds of whole–part relationships:

**Composition** (the part cannot exist without the whole; the whole owns the part's lifecycle):

* **Conversation — Message**: deleting a conversation removes its messages; messages are meaningless outside their conversation.
* **Draft — Draft Version**: versions are states of a draft; a version cannot exist without its draft.
* **Writing Profile — Profile Characteristic**: characteristics are attributes of a profile; they exist only within it.
* **Capability — Capability Entry**: entries exist only within their capability. *(Renamed from Agent/Agent Capability by ADR-009.)*
* **Agent — Project**: the Project cannot exist without its owning Agent, and the pairing is permanent (ADR-009) — this is composition, not aggregation, distinguishing it from Project's own (aggregation) relationship to Research Document below.

**Aggregation** (the part can exist independently; the whole references it):

* **Project — Research Document**: documents are removed independently (explicit removal, DR-025); the project aggregates them.
* **Agent — Knowledge Element / Knowledge Chunk**: knowledge is derived and can be removed or superseded independently of the Agent's own lifecycle. *(Moved from Project by ADR-009.)*
* **Draft Version — Knowledge Chunk**: evidence links reference chunks that exist independently of the draft.

This distinction directly informs the delete semantics of the logical model (04 §9).

---

## 6. Inheritance and Generalization

The conceptual model uses one deliberate generalization and one subtyping:

**Generalization — "Traceable Record".** Knowledge Elements, Knowledge Chunks, Memory Records, Draft Versions, and Review Decisions all share the property of *carrying provenance*: each is created by a system activity or user action, references the source that produced it, and participates in the evidence chain (ADR-005; 04 §18). Conceptually, these are **Traceable Records**. This is a conceptual generalization only — it is not intended to be implemented as table inheritance (the logical model flattens the shared attributes; see 04 §14).

**Subtyping — Message Direction.** Messages within a conversation are either *user requests* or *system responses* (03 §3.6; AIR-006). This is a role distinction on one entity, realized in the logical model as an enumerated discriminator, not as separate entities.

**Subtyping — Evidence Target.** Evidence links may target a Research Document, a Knowledge Element, or a Knowledge Chunk. Conceptually one relationship ("is supported by"); structurally resolved in the logical model.

No other inheritance is applicable: the domains of Document 02 do not form a type hierarchy.

---

## 7. Bounded Contexts

Each domain of the logical backend ([05_Backend_Architecture.md](../architecture/05_Backend_Architecture.md) §4.1) is a **bounded context** owning its conceptual entities:

| Bounded context (05 §4.1) | Owned entities |
|---------------------------|----------------|
| Agent | Agent, agent-scoped configuration *(new bounded context; ADR-009)* |
| Project | Project *(narrowed by ADR-009; no longer owns configuration)* |
| Document | Research Document |
| Knowledge | Knowledge Element, Knowledge Chunk |
| Memory | Memory Record |
| Conversation | Conversation, Message |
| Capability | Capability, Capability Entry *(renamed from Agent/Agent Capability by ADR-009)* |
| Review | Review, Review Decision |
| Author Profile | Writing Profile, Profile Characteristic |
| Configuration | Configuration Item |
| Authentication (05 §15) | User, Session |

Context rules (from 05 §18 and ADR-003):

* Each context owns its data and behavior; no context reaches into another context's state.
* Cross-context relationships (e.g., a Draft Version referencing Knowledge Chunks; a Memory Record referencing Review outcomes) are realized through the orchestration layer and the data access layer — never through direct access to another context's internals.
* The **data access layer** (05 §16, API-032, API-033) is the single boundary through which all contexts persist; per-module data ownership follows 03 §4 (Data Ownership Model).

---

## 8. Business Rules

The conceptual model is governed by the following business rules, each grounded in the approved baseline:

1. **Understand before generate.** A draft is produced only after the assembled context is sufficient; the model records context assembly as a precondition, not an assumption (AIR-031; 04 §20.1).
2. **Evidence before assertion.** Every knowledge element, knowledge chunk, and draft version carries evidence links to source material; content without an evidence path is not retrievable as supported (AIR-024, AIR-027; ADR-005).
3. **Artifact distinction.** Raw input (messages), interpreted knowledge (knowledge elements/chunks), stored memory (memory records), and approved output (draft versions) remain distinguishable at all times (AIR-006).
4. **Memory is user-aware.** Memory records are populated through user input and system-derived context; the system does not infer memory without user awareness (MVP-011; 04 §8.2).
5. **Review is user-owned.** Approval, revision, and rejection are the researcher's decisions; review decisions are preserved for audit and never overridden by the system (AIR-003, AIR-038, AIR-054).
6. **Supersession retains history.** When a memory record or knowledge element is superseded, the earlier record remains traceable (DR-014; 07 §3.3).
7. **Evidence is retained.** Research documents are retained for the life of the project or until explicitly removed; removal preserves the integrity of referencing data (07 §3.4; 05 §10; DR-025).
8. **Conversation outcomes require approval.** Conversation content is a continuity record, not memory, until approved and entered with user awareness (03 §3.6; AIR-006).
9. **Single-user scoping in the MVP.** All project data is scoped to a single authenticated user in the MVP; multi-user tenancy is a later-stage decision (SRS Ch10; WR-038; 07 §5).
10. **One Agent per user in the MVP.** A user owns exactly one Agent; additional Agents per user are a deferred, monetization-gated capability, not an MVP requirement (ADR-009).

---

## 9. Lifecycle Relationships

The lifecycle of each entity follows the domains of Document 02 (§4 of 02) and the research workflow of 04 §5.2:

```md
Agent creation, with its one permanent Project (ADR-009)
    ↓
Document collection (Research Document: ingested → processed → available)
    ↓
Knowledge processing (Knowledge Element: derived → refined → superseded)
    ↓
Knowledge chunking (Knowledge Chunk: created → re-linked → retained/superseded)
    ↓
Memory building (Memory Record: established → updated → superseded)
    ↓
Conversations (Conversation: created → active → summarized/retained)
    ↓
Capability registration (Capability: registered → configured → updated)
    ↓
Writing (Draft: drafted → revised → superseded)
    ↓
Review (Review: created → decision → preserved; Review Decision: recorded)
    ↓
Approved outcome enters Memory with user awareness
```

**Corrected by ADR-009:** the lifecycle previously began "Project creation" and referred to "Agent registration" for the capability registry. It now begins "Agent creation, with its one permanent Project," and the capability-registry step is relabeled "Capability registration" to avoid ambiguity.

Data lifecycle stages (SRS Ch7 §4; DR-023 to DR-025) apply uniformly: **ingestion → storage/persistence → retrieval → archival/deletion**, with provenance preserved across the lifecycle.

---

## 10. Traceability

This conceptual data model is traceable to the approved baseline as follows:

* **SRS Chapter 7** — the data domains and relationships this model realizes (DR-001 to DR-033, DR-035; DC-002, DC-003), especially data relationships (DR-026 to DR-028) and lifecycle (DR-023 to DR-025).
* **SRS Chapter 6** — evidence linkage (AIR-024, AIR-027, AIR-046 to AIR-048), memory (AIR-019 to AIR-021, AIR-065 to AIR-066), profile (AIR-016 to AIR-018), review (AIR-037 to AIR-039), artifact distinction (AIR-006).
* **SRS Chapter 10** — MVP scope (MVP-001 to MVP-022).
* **Architecture 03** — conceptual domains, ownership model, and lifecycle summary (§3–§5).
* **Architecture 04** — knowledge processing (§7), memory (§8), chunking (§9), conversation (§10), agent registry (§14), evidence flow (§18), review (§19), writing (§20).
* **Architecture 05** — bounded contexts (§4), orchestration (§6), data access layer (§16).
* **Architecture 07** — retention and lifecycle (§3.4), consistency and integrity (§3.3).
* **ADR-004** — memory as a first-class domain.
* **ADR-005** — chunk-level retrieval and first-class evidence links.
* **ADR-006** — durable work items (the outbox).
* **Database Overview (01)** — governing rules (§8, §12); **Domain Model (02)** — domain vocabulary (§6 of 02).
* **ADR-009** — introduces Agent, narrows Project's scope, renames Agent/Agent Capability to Capability/Capability Entry.

---

## 11. Summary

The conceptual data model, as corrected by ADR-009, transforms the thirteen domains of Document 02 into twenty conceptual entities and the relationships among them: ownership (User → Agent → Project), containment (Agent → knowledge, memory, conversations, drafts, writing profile; Project → research documents), derivation (documents → knowledge → chunks), evidence grounding (chunks → drafts), context (memory → drafting), oversight (draft versions → reviews → decisions), and configuration governance. Composition, aggregation, one generalization (Traceable Record), two subtypings, bounded contexts aligned to the backend domains, and ten business rules complete the model.

This document expresses the language of the business and its relationships. The next document, [04_Logical_Data_Model.md](04_Logical_Data_Model.md), refines this model into the logical relational structure — entities, attributes, keys, and integrity rules — still without implementation details.
