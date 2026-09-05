# Logical Data Model

**Document:** 04_Logical_Data_Model.md

**Status:** Active

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design

**Revision:** 1

---

## 1. Purpose

This document defines the **logical data model** of ScholarOS: the logical relational structure into which the conceptual model of [03_Conceptual_Data_Model.md](03_Conceptual_Data_Model.md) is refined. It answers the question *"How will those concepts become a logical relational model?"*

It is the fourth layer of the database design document set ([01_Database_Overview.md](01_Database_Overview.md) §12). Document 02 defined the business language; Document 03 defined the conceptual relationships; this document defines the structural design contract — entities, attributes, keys, integrity, and strategies — that a Senior Backend Engineer can use to begin physical schema design, and that API design will define contracts against (01 §13.1).

This document is **implementation-independent**:

* It uses logical type families and logical constructs only.
* It does **not** produce SQL, CREATE TABLE statements, migrations, indexes, or storage-engine selections.
* It does not discuss ORM implementation (ADR-002 keeps the ORM behind the data access layer).
* Physical realization — schema, indexes, engine configuration — belongs to implementation, bounded by this contract and by the storage decisions of ADR-004, ADR-005, and ADR-007 (01 §9.4).

**Authoritative Source Rule:** per [01_Database_Overview.md](01_Database_Overview.md) §12.2, this document treats Documents 01–03 as authoritative, uses their vocabulary, extends the design, and does not duplicate their content.

---

## 2. Logical Model Conventions

### 2.1 Logical Type Families

Attributes are expressed with **logical type families** — implementation-neutral categories that physical design maps to engine-specific types:

| Logical type | Meaning |
|--------------|---------|
| **Identifier** | A surrogate identity value assigned by the system. |
| **Reference** | A logical foreign key to another entity. |
| **Short Text** | A brief label, name, or code. |
| **Long Text** | Substantive prose or structured content. |
| **Timestamp** | A point in time (creation, change, decision). |
| **Boolean** | A binary condition. |
| **Numeric** | A number (count, weight, confidence). |
| **Enumerated** | A value drawn from a fixed, documented set. |

### 2.2 Entity Families

**Corrected by ADR-009:** Agent added as a new core entity; Agent/Agent Capability renamed to Capability/Capability Entry to free the name.

* **Core entities** hold the primary information of each domain (Agent, Project, Research Document, Knowledge Element, Knowledge Chunk, Memory Record, Conversation, Message, Writing Profile, Profile Characteristic, Capability, Capability Entry, Draft, Draft Version, Review, Review Decision, Configuration Item, User, Session).
* **Link entities** resolve many-to-many and polymorphic relationships (Chunk Evidence Link, Draft Evidence Link, Memory Provenance Link, Message Context Link, Profile Characteristic Source). The **Knowledge Element Relationship** — the junction that resolves element-to-element semantic relationships — is presented alongside the entity it associates in §3.6 and counts toward the core entity total in §16.
* **System entities** support the approved operational model (Work Item — the durable outbox of ADR-006).

### 2.3 Content Payloads

Content payloads (document content, chunk content, draft content) are modeled as logical attributes with a content reference; the *category* in which each payload is physically stored (structured core vs object store) is governed by 07 §3.2 and mapped in document 06. This document defines only the logical structure.

---

## 3. Core Logical Entities

### 3.1 User

**Purpose:** identity of the researcher; anchor of the authentication boundary (05 §15).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| user_id | Identifier | Not null | Surrogate identifier. |
| username | Short Text | Not null | Credential identifier (candidate key). |
| display_name | Short Text | Nullable | Human-readable name. |
| status | Enumerated | Not null | active / suspended. |
| created_at | Timestamp | Not null | Registration time. |
| updated_at | Timestamp | Nullable | Last change. |

**Keys:** primary key `user_id`; candidate key `username`.

### 3.2 Session

**Purpose:** bounded interaction context of a user (05 §15).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| session_id | Identifier | Not null | Surrogate identifier. |
| user_id | Reference | Not null | → User. |
| session_token | Short Text | Not null | Exchanged credential (candidate key). |
| started_at | Timestamp | Not null | Session start. |
| last_active_at | Timestamp | Nullable | Last observed activity. |
| ended_at | Timestamp | Nullable | Session end (null while active). |

**Keys:** primary key `session_id`; candidate key `session_token`. **FK:** `user_id` → User.

### 3.3 Project

**Purpose:** the raw input material of a research undertaking — its identity, topic, and source documents (DR-001 to DR-003). **Narrowed by ADR-009:** Project no longer directly hosts knowledge, memory, conversations, drafts, writing profile, or configuration — see §3.21 Agent. Project is now owned by exactly one Agent.

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| project_id | Identifier | Not null | Surrogate identifier. |
| agent_id | Reference | Not null | → Agent (owner; 1:1, permanent). **Replaces `user_id` — ADR-009.** |
| title | Short Text | Not null | Project name. |
| description | Long Text | Nullable | Project description. |
| topic | Long Text | Not null | Research topic and scope (MVP-002). Single source of truth for the owning Agent's specialization (ADR-009) — Agent does not carry its own copy. |
| status | Enumerated | Not null | active / closed / archived. |
| created_at | Timestamp | Not null | Creation time. |
| updated_at | Timestamp | Nullable | Last change. |
| closed_at | Timestamp | Nullable | Closure/archival time. |
| deleted_at | Timestamp | Nullable | Soft-delete tombstone (null while active). |

**Keys:** primary key `project_id`; candidate key `agent_id` (unique — one Project per Agent, permanent; ADR-009). **FK:** `agent_id` → Agent.

### 3.4 Research Document

**Purpose:** user-supplied source material retained as evidence (DR-004 to DR-006).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| document_id | Identifier | Not null | Surrogate identifier. |
| project_id | Reference | Not null | → Project. |
| title | Short Text | Not null | Document title. |
| author | Short Text | Nullable | Document author as supplied. |
| source | Short Text | Nullable | Origin of the material. |
| format | Enumerated | Not null | Supplied format family. |
| content_reference | Short Text | Not null | Reference to the content payload (category mapped in 06). |
| processing_status | Enumerated | Not null | pending / processing / processed / failed. |
| ingested_at | Timestamp | Not null | Intake time. |
| processed_at | Timestamp | Nullable | Processing completion. |
| deleted_at | Timestamp | Nullable | Soft-delete tombstone. |

**Keys:** primary key `document_id`. **FK:** `project_id` → Project.

### 3.5 Knowledge Element

**Purpose:** an individual unit of interpreted understanding (DR-007 to DR-009; 04 §7).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| element_id | Identifier | Not null | Surrogate identifier. |
| agent_id | Reference | Not null | → Agent. **Replaces `project_id` — ADR-009.** |
| element_type | Enumerated | Not null | concept / theme / method / claim / relationship. |
| label | Short Text | Not null | Element name. |
| description | Long Text | Nullable | Interpreted meaning. |
| status | Enumerated | Not null | current / superseded. |
| created_at | Timestamp | Not null | Derivation time. |
| created_by | Enumerated | Not null | system (capability) / user. |
| superseded_element_id | Reference | Nullable | Self-reference: the element this one supersedes (predecessor in the supersession chain). |
| superseded_at | Timestamp | Nullable | Time of supersession. |

**Keys:** primary key `element_id`. **FKs:** `agent_id` → Agent; `superseded_element_id` → Knowledge Element (self).

### 3.6 Knowledge Element Relationship

**Purpose:** resolve the many-to-many semantic relationships among knowledge elements (DR-009).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| relationship_id | Identifier | Not null | Surrogate identifier. |
| element_from_id | Reference | Not null | → Knowledge Element. |
| element_to_id | Reference | Not null | → Knowledge Element. |
| relationship_type | Enumerated | Not null | hierarchy / association / dependency. |
| created_at | Timestamp | Not null | Recognition time. |

**Keys:** primary key `relationship_id`; candidate key (`element_from_id`, `element_to_id`, `relationship_type`). **FKs:** both element references → Knowledge Element.

### 3.7 Knowledge Chunk

**Purpose:** discrete retrievable unit of interpreted knowledge (03 §3.4; 04 §9; ADR-005).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| chunk_id | Identifier | Not null | Surrogate identifier. |
| agent_id | Reference | Not null | → Agent. **Replaces `project_id` — ADR-009.** |
| element_id | Reference | Not null | → Knowledge Element (derivation). |
| content | Long Text | Not null | Interpreted chunk content. |
| summary | Short Text | Nullable | Concise description for retrieval context. |
| status | Enumerated | Not null | current / superseded. |
| created_at | Timestamp | Not null | Chunking time. |
| updated_at | Timestamp | Nullable | Re-link or revision time. |

**Note:** the chunk's embedding (retrieval vector) is persisted in the vector index, keyed by `chunk_id` (ADR-005); it is not an attribute of this logical entity in the structured core. Its mapping is refined in document 06.

**Keys:** primary key `chunk_id`. **FKs:** `agent_id` → Agent; `element_id` → Knowledge Element.

### 3.8 Memory Record

**Purpose:** persistent project context and decision history with supersession (DR-013 to DR-015; 04 §8; ADR-004).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| record_id | Identifier | Not null | Surrogate identifier. |
| agent_id | Reference | Not null | → Agent. **Replaces `project_id` — ADR-009.** |
| record_type | Enumerated | Not null | objective / hypothesis / method / decision / terminology / guidance / other. |
| content | Long Text | Not null | Recorded context or decision. |
| rationale | Long Text | Nullable | Why this was established. |
| status | Enumerated | Not null | current / superseded. |
| created_at | Timestamp | Not null | Establishment time. |
| created_by | Enumerated | Not null | system / user. |
| superseded_record_id | Reference | Nullable | Self-reference: the record this one supersedes (predecessor in the supersession chain). |
| superseded_at | Timestamp | Nullable | Time of supersession. |

**Keys:** primary key `record_id`. **FKs:** `agent_id` → Agent; `superseded_record_id` → Memory Record (self).

### 3.9 Conversation

**Purpose:** project-scoped interaction history (03 §3.6; 04 §10; WR-034).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| conversation_id | Identifier | Not null | Surrogate identifier. |
| agent_id | Reference | Not null | → Agent. **Replaces `project_id` — ADR-009.** |
| title | Short Text | Nullable | Optional conversation label. |
| status | Enumerated | Not null | active / summarized / retained. |
| started_at | Timestamp | Not null | First message time. |
| summarized_at | Timestamp | Nullable | Compaction time (if summarized). |
| deleted_at | Timestamp | Nullable | Soft-delete tombstone. |

**Keys:** primary key `conversation_id`. **FK:** `agent_id` → Agent.

### 3.10 Message

**Purpose:** an individual exchange within a conversation (03 §3.6; AIR-006).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| message_id | Identifier | Not null | Surrogate identifier. |
| conversation_id | Reference | Not null | → Conversation. |
| sequence | Numeric | Not null | Ordinal position within the conversation. |
| direction | Enumerated | Not null | user_request / system_response. |
| content | Long Text | Not null | Message content. |
| origin | Short Text | Nullable | Capability or provider that produced a system response (observability). |
| created_at | Timestamp | Not null | Message time. |

**Keys:** primary key `message_id`; candidate key (`conversation_id`, `sequence`). **FK:** `conversation_id` → Conversation.

### 3.11 Writing Profile

**Purpose:** the author's preserved writing characteristics (DR-010 to DR-012; 03 §3.7).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| profile_id | Identifier | Not null | Surrogate identifier. |
| agent_id | Reference | Not null | → Agent. **Replaces `project_id` — ADR-009.** |
| user_id | Reference | Not null | → User (provider of samples). |
| name | Short Text | Not null | Profile label. |
| status | Enumerated | Not null | active / inactive. |
| created_at | Timestamp | Not null | Creation time. |
| updated_at | Timestamp | Nullable | Last refinement. |
| deleted_at | Timestamp | Nullable | Soft-delete tombstone. |

**Keys:** primary key `profile_id`. **FKs:** `agent_id` → Agent; `user_id` → User.

### 3.12 Profile Characteristic

**Purpose:** a single preserved stylistic attribute (DR-010, DR-012).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| characteristic_id | Identifier | Not null | Surrogate identifier. |
| profile_id | Reference | Not null | → Writing Profile. |
| characteristic_type | Enumerated | Not null | structure / vocabulary / transitions / explanation / citation. |
| signal | Long Text | Not null | The preserved characteristic description. |
| confidence | Numeric | Nullable | Derived confidence indicator (DR-012). |
| created_at | Timestamp | Not null | Extraction time. |

**Keys:** primary key `characteristic_id`. **FK:** `profile_id` → Writing Profile.

### 3.13 Capability

**Renamed from "Agent" by ADR-009** to free that name for the new Agent workspace entity (§3.21). Meaning unchanged.

**Purpose:** registered intelligence capability (03 §3.8; 04 §14; AIR-058 to AIR-060).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| capability_id | Identifier | Not null | Surrogate identifier. **Renamed from `agent_id` — ADR-009.** |
| name | Short Text | Not null | Capability name (candidate key). |
| purpose | Short Text | Not null | What the capability does. |
| status | Enumerated | Not null | registered / active / retired. |
| created_at | Timestamp | Not null | Registration time. |
| updated_at | Timestamp | Nullable | Last change. |

**Keys:** primary key `capability_id`; candidate key `name`.

### 3.14 Capability Entry

**Renamed from "Agent Capability" by ADR-009.** Meaning unchanged.

**Purpose:** a registered entry of a capability (04 §14.1).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| entry_id | Identifier | Not null | Surrogate identifier. **Renamed from `capability_id` — ADR-009.** |
| capability_id | Reference | Not null | → Capability. **Renamed from `agent_id` — ADR-009.** |
| capability_name | Short Text | Not null | Entry name. |
| description | Short Text | Nullable | Inputs, outputs, boundaries. |
| status | Enumerated | Not null | enabled / disabled. |
| created_at | Timestamp | Not null | Registration time. |

**Keys:** primary key `entry_id`; candidate key (`capability_id`, `capability_name`). **FK:** `capability_id` → Capability.

### 3.15 Draft

**Purpose:** generated/refined academic content as a series of versions (DR-016 to DR-019; 04 §20).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| draft_id | Identifier | Not null | Surrogate identifier. |
| agent_id | Reference | Not null | → Agent. **Replaces `project_id` — ADR-009.** |
| title | Short Text | Not null | Draft title. |
| target | Short Text | Nullable | Chapter/section context within Chapters 1–3 (MVP-015). |
| status | Enumerated | Not null | drafting / in_review / approved / superseded. |
| created_at | Timestamp | Not null | Creation time. |
| updated_at | Timestamp | Nullable | Last change. |
| deleted_at | Timestamp | Nullable | Soft-delete tombstone. |

**Keys:** primary key `draft_id`. **FK:** `agent_id` → Agent.

### 3.16 Draft Version

**Purpose:** an immutable state of a draft produced by one writing or revision cycle (DR-017; MVP-021; AIR-035).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| version_id | Identifier | Not null | Surrogate identifier. |
| draft_id | Reference | Not null | → Draft. |
| version_number | Numeric | Not null | Ordinal within the draft. |
| content | Long Text | Not null | Version content (immutable after creation). |
| created_at | Timestamp | Not null | Version time. |
| created_by | Enumerated | Not null | system (generated) / user (authored/edited). |

**Keys:** primary key `version_id`; candidate key (`draft_id`, `version_number`). **FK:** `draft_id` → Draft.

### 3.17 Review

**Purpose:** an evaluation round applied to a draft version (DR-019; WR-022 to WR-025).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| review_id | Identifier | Not null | Surrogate identifier. |
| draft_version_id | Reference | Not null | → Draft Version. |
| status | Enumerated | Not null | open / decided. |
| notes | Long Text | Nullable | Reviewer's feedback and revision requests. |
| opened_at | Timestamp | Not null | Review start. |
| decided_at | Timestamp | Nullable | Decision time. |

**Keys:** primary key `review_id`. **FK:** `draft_version_id` → Draft Version.

### 3.18 Review Decision

**Purpose:** the recorded outcome of a review, preserved for audit (DR-019; AIR-054; MVP-018 to MVP-020).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| decision_id | Identifier | Not null | Surrogate identifier. |
| review_id | Reference | Not null | → Review (one-to-one). |
| outcome | Enumerated | Not null | approved / revisions_requested / rejected. |
| rationale | Long Text | Nullable | Justification. |
| decided_by | Reference | Not null | → User (the researcher). |
| decided_at | Timestamp | Not null | Decision time. |

**Keys:** primary key `decision_id`; candidate key `review_id` (one decision per review). **FKs:** `review_id` → Review; `decided_by` → User.

### 3.19 Configuration Item

**Purpose:** a single governed operational setting at system, agent, or user scope (DR-020 to DR-022; AIR-055 to AIR-057; 05 §17). **Scope value renamed from `project` to `agent` by ADR-009** — configuration follows the Agent (which owns workflow/drafting behavior), not the narrower Project.

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| config_id | Identifier | Not null | Surrogate identifier. |
| scope | Enumerated | Not null | system / agent / user. **Renamed from `system / project / user` — ADR-009.** |
| agent_id | Reference | Nullable | → Agent (required when scope = agent). **Renamed from `project_id` — ADR-009.** |
| user_id | Reference | Nullable | → User (required when scope = user). |
| config_key | Short Text | Not null | Setting name. |
| config_value | Long Text | Not null | Setting value. |
| version_number | Numeric | Not null | History version of this setting. |
| is_active | Boolean | Not null | Whether this version is the active value. |
| changed_by | Reference | Not null | → User (or system marker). |
| changed_at | Timestamp | Not null | Change time. |

**Keys:** primary key `config_id`; candidate key (`scope`, `agent_id`, `user_id`, `config_key`, `version_number`). **FKs:** `agent_id` → Agent; `user_id` → User.

### 3.20 Work Item (Durable Outbox)

**Purpose:** a unit of asynchronous work recorded durably before execution (ADR-006; 07 §3.5).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| work_item_id | Identifier | Not null | Surrogate identifier. |
| kind | Enumerated | Not null | pipeline_stage / domain_event. |
| state | Enumerated | Not null | queued / running / succeeded / failed. |
| payload_reference | Short Text | Not null | Reference to the work payload. |
| idempotency_key | Short Text | Not null | Deduplication key (candidate key). |
| attempts | Numeric | Not null | Retry count. |
| last_error | Long Text | Nullable | Last failure context. |
| created_at | Timestamp | Not null | Enqueue time. |
| executed_at | Timestamp | Nullable | First execution. |
| completed_at | Timestamp | Nullable | Terminal state time. |

**Keys:** primary key `work_item_id`; candidate key `idempotency_key`.

### 3.21 Agent

**Added by ADR-009.** Not part of the twenty-five-entity set frozen at Milestone 5 close-out.

**Purpose:** the user's permanent, specialized research workspace, owning exactly one Project and everything derived from or accumulated within it (ADR-009).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| agent_id | Identifier | Not null | Surrogate identifier. |
| user_id | Reference | Not null | → User (owner). |
| status | Enumerated | Not null | active / archived. |
| created_at | Timestamp | Not null | Creation time. |
| updated_at | Timestamp | Nullable | Last change. |
| deleted_at | Timestamp | Nullable | Soft-delete tombstone (null while active). |

**Note:** Agent has no `topic` attribute of its own — it reads its specialization through its owned Project's `topic` (§3.3), which remains the single source of truth (ADR-009).

**Keys:** primary key `agent_id`; candidate key `user_id` (unique — at most one Agent per User in the MVP; ADR-009). **FK:** `user_id` → User.

---

## 4. Link Logical Entities

### 4.1 Chunk Evidence Link

**Purpose:** first-class evidence association between a Knowledge Chunk and the Research Documents it draws from (ADR-005; DR-008; 04 §18).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| link_id | Identifier | Not null | Surrogate identifier. |
| chunk_id | Reference | Not null | → Knowledge Chunk. |
| document_id | Reference | Not null | → Research Document. |
| created_at | Timestamp | Not null | Link creation. |
| created_by | Enumerated | Not null | system (pipeline) / user. |

**Keys:** primary key `link_id`; candidate key (`chunk_id`, `document_id`). **FKs:** `chunk_id` → Knowledge Chunk; `document_id` → Research Document. Links are immutable.

### 4.2 Draft Evidence Link

**Purpose:** evidence annotation connecting a Draft Version to the Knowledge Chunks or Research Documents that support it (DR-018; AIR-027; 04 §18.1 stage 4).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| link_id | Identifier | Not null | Surrogate identifier. |
| draft_version_id | Reference | Not null | → Draft Version. |
| target_type | Enumerated | Not null | knowledge_chunk / research_document. |
| chunk_id | Reference | Nullable | → Knowledge Chunk (set when target_type = knowledge_chunk). |
| document_id | Reference | Nullable | → Research Document (set when target_type = research_document). |
| created_at | Timestamp | Not null | Annotation time. |
| created_by | Enumerated | Not null | system / user. |

**Keys:** primary key `link_id`; candidate key (`draft_version_id`, `target_type`, `chunk_id`, `document_id`). **FKs:** `draft_version_id` → Draft Version; `chunk_id` → Knowledge Chunk; `document_id` → Research Document. **Rule:** exactly one target reference is set (exclusive arc; §8).

### 4.3 Memory Provenance Link

**Purpose:** trace a Memory Record to the artifacts and activities that produced it (DR-015).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| link_id | Identifier | Not null | Surrogate identifier. |
| record_id | Reference | Not null | → Memory Record. |
| source_type | Enumerated | Not null | user_input / review_decision / conversation / knowledge_element / document / draft_version. |
| review_decision_id | Reference | Nullable | → Review Decision. |
| conversation_id | Reference | Nullable | → Conversation. |
| element_id | Reference | Nullable | → Knowledge Element. |
| document_id | Reference | Nullable | → Research Document. |
| draft_version_id | Reference | Nullable | → Draft Version. |
| created_at | Timestamp | Not null | Link creation. |

**Keys:** primary key `link_id`; candidate key (`record_id`, `source_type`, target reference). **FKs:** per source type. **Rule:** exactly one target reference is set (exclusive arc).

### 4.4 Message Context Link

**Purpose:** reference from a Message to the project artifacts it concerns (04 §10.2).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| link_id | Identifier | Not null | Surrogate identifier. |
| message_id | Reference | Not null | → Message. |
| target_type | Enumerated | Not null | research_document / knowledge_element / knowledge_chunk / draft_version / memory_record. |
| document_id | Reference | Nullable | → Research Document. |
| element_id | Reference | Nullable | → Knowledge Element. |
| chunk_id | Reference | Nullable | → Knowledge Chunk. |
| draft_version_id | Reference | Nullable | → Draft Version. |
| memory_record_id | Reference | Nullable | → Memory Record. |
| created_at | Timestamp | Not null | Reference time. |

**Keys:** primary key `link_id`. **FKs:** per target type. **Rule:** exactly one target reference is set (exclusive arc).

### 4.5 Profile Characteristic Source

**Purpose:** provenance of a profile characteristic to the authored samples that informed it (DR-012).

| Attribute | Logical type | Nullability | Description |
|-----------|--------------|-------------|-------------|
| link_id | Identifier | Not null | Surrogate identifier. |
| characteristic_id | Reference | Not null | → Profile Characteristic. |
| document_id | Reference | Not null | → Research Document (authored sample). |
| created_at | Timestamp | Not null | Link creation. |

**Keys:** primary key `link_id`; candidate key (`characteristic_id`, `document_id`). **FKs:** `characteristic_id` → Profile Characteristic; `document_id` → Research Document.

---

## 5. Relationship Mapping

The conceptual relationships of Document 03 §3 are realized as follows:

| Conceptual relationship (03) | Realization |
|------------------------------|-------------|
| User — Session (1:N) | Reference `Session.user_id`. |
| User — Agent (1:1, MVP) | Reference `Agent.user_id` (unique). *(Corrected by ADR-009; was User — Project 1:N.)* |
| User — Writing Profile (1:N) | Reference `WritingProfile.user_id`. |
| Agent — Project (1:1, permanent) | Reference `Project.agent_id` (unique). *(Added by ADR-009.)* |
| Project — Research Document (1:N) | Reference `ResearchDocument.project_id`. |
| Agent — Knowledge Element (1:N) | Reference `KnowledgeElement.agent_id`. *(Moved from Project by ADR-009.)* |
| Agent — Knowledge Chunk (1:N) | Reference `KnowledgeChunk.agent_id`. *(Moved from Project by ADR-009.)* |
| Agent — Memory Record (1:N) | Reference `MemoryRecord.agent_id`. *(Moved from Project by ADR-009.)* |
| Agent — Conversation (1:N) | Reference `Conversation.agent_id`. *(Moved from Project by ADR-009.)* |
| Agent — Draft (1:N) | Reference `Draft.agent_id`. *(Moved from Project by ADR-009.)* |
| Agent — Writing Profile (1:N) | Reference `WritingProfile.agent_id`. *(Moved from Project by ADR-009.)* |
| Agent — Configuration Item (1:N) | Reference `ConfigurationItem.agent_id` (agent scope). *(Moved from Project by ADR-009; scope value renamed `project` → `agent`.)* |
| Research Document — Knowledge Element (1:N) | Reference `KnowledgeElement` — the derivation is expressed by the evidence chain (Element ← Chunk ← ChunkEvidenceLink → Document). |
| Research Document — Knowledge Chunk (N:M) | **Chunk Evidence Link** (junction). |
| Knowledge Element — Knowledge Chunk (1:N) | Reference `KnowledgeChunk.element_id`. |
| Knowledge Element — Knowledge Element (N:M) | **Knowledge Element Relationship** (junction). |
| Knowledge Element — Memory Record (N:M) | **Memory Provenance Link** (source_type = knowledge_element). |
| Memory Record — Memory Record (supersession) | Self-reference `MemoryRecord.superseded_record_id`. |
| Conversation — Message (1:N, composition) | Reference `Message.conversation_id`. |
| Message — project artifacts (N:M, polymorphic) | **Message Context Link** (exclusive arc). |
| Conversation — Memory Record (approved outcomes) | **Memory Provenance Link** (source_type = conversation). |
| Writing Profile — Profile Characteristic (1:N) | Reference `ProfileCharacteristic.profile_id`. |
| Profile Characteristic — Research Document (N:M) | **Profile Characteristic Source** (junction). |
| Writing Profile — Draft (N:M) | Realized indirectly: a draft's project associates it with the project's active profile (see §7, rule 4). |
| Capability — Capability Entry (1:N) | Reference `CapabilityEntry.capability_id`. *(Renamed from Agent/Agent Capability by ADR-009.)* |
| Capability — Configuration Item (N:M) | Configuration Item with scope = agent (capability entry sets). |
| Draft — Draft Version (1:N, composition) | Reference `DraftVersion.draft_id`. |
| Draft Version — Chunk/Document (N:M, evidence) | **Draft Evidence Link** (exclusive arc). |
| Draft Version — Memory Record (N:M) | Realized indirectly through context assembly; provenance retained via Memory Provenance Link where the draft is a source. |
| Draft Version — Writing Profile (N:M) | Indirect via project profile (see Writing Profile — Draft). |
| Draft Version — Review (1:N) | Reference `Review.draft_version_id`. |
| Review — Review Decision (1:1) | Reference `ReviewDecision.review_id` (unique). |

---

## 6. Normalization Rationale

The logical model is normalized to **third normal form (3NF)** as the baseline, with deliberate, documented deviations only where the approved baseline demands them:

* **No repeating groups.** Draft versions, messages, profile characteristics, and capability entries are separate entities rather than repeated attributes (1NF).
* **No partial dependencies.** All attributes depend on the full primary key (2NF); e.g., a Message depends on its conversation context via reference, never via duplicated attributes.
* **No transitive dependencies.** Derived values are not stored where they can be derived; e.g., a project's "current" draft version is the latest version_number, not a stored attribute (3NF).

**Deliberate deviations:**

1. **Configuration Item is an entity–attribute–value (EAV) pattern.** Configuration entries are heterogeneous and extensible (system, agent, user scope — renamed from "project" scope by ADR-009; DR-020 to DR-022). Storing them as typed columns would force schema churn for every new setting. The EAV form is accepted for *configuration only*, with strong key discipline (§7) and versioned history (§11). All other domains remain conventionally normalized.
2. **Content payloads are referenced, not embedded.** Document, chunk, and draft-version content is a long-form payload referenced by the logical entity; this is required by the storage-category separation of 07 §3.2 (mapped in document 06). The logical model retains the reference; the physical separation is not a normalization decision.
3. **Evidence links are explicit entities, not columns.** Because evidence is many-to-many and first-class (ADR-005), links are entities. This is the relational-normal form for M:N relationships and preserves referential integrity (DR-028).
4. **No denormalized read projections in the structured core.** Retrieval snapshots, counts, or summaries that future scale may warrant are *derived* artifacts of the retrieval strategy (ADR-005) and belong to the derived stores mapped in document 06, not the structured core.

**Deferred:** any normalization change driven by future multi-user stages (07 §5) is deferred; the model is designed so those changes are additive (new reference columns, new link entities), not restructuring.

---

## 7. Constraints and Uniqueness

* **Identifiers.** Every entity has a surrogate `*_id` primary key; identifiers are system-assigned and never reused.
* **Unique candidate keys.**
  * `User.username` — one account per username.
  * `Session.session_token` — one active token per session value.
  * `Agent.user_id` — at most one Agent per User in the MVP (ADR-009).
  * `Project.agent_id` — exactly one Project per Agent, permanent (ADR-009).
  * `KnowledgeElementRelationship(element_from_id, element_to_id, relationship_type)` — no duplicate relationship statements.
  * `ChunkEvidenceLink(chunk_id, document_id)` — no duplicate evidence links.
  * `Message(conversation_id, sequence)` — messages are strictly ordered per conversation.
  * `DraftVersion(draft_id, version_number)` — versions are strictly ordered per draft.
  * `ReviewDecision.review_id` — one decision per review.
  * `Capability.name`, `CapabilityEntry(capability_id, capability_name)` — registry entries are uniquely named. *(Renamed from Agent/AgentCapability by ADR-009.)*
  * `ConfigurationItem(scope, agent_id, user_id, config_key, version_number)` — one history entry per key per scope. *(Renamed from `project_id` by ADR-009.)*
  * `WorkItem.idempotency_key` — at-most-once processing (ADR-006).
* **State rules.**
  * At most one **open** Review per Draft Version at any time.
  * At most one **active** Writing Profile per Agent in the MVP. *(Renamed from "per project" by ADR-009.)*
  * A superseding Memory Record or Knowledge Element references its predecessor; at most one record may reference a given record as its predecessor (one active successor per record).
  * Configuration Item: exactly one `is_active = true` version per (scope, owner, key).
* **Check rules (stated as logical invariants, not DDL).**
  * `DraftEvidenceLink`: exactly one of `chunk_id` / `document_id` is set, consistent with `target_type`.
  * `MessageContextLink` and `MemoryProvenanceLink`: exactly one target reference is set, consistent with `target_type` / `source_type`.
  * `ConfigurationItem`: `agent_id` set iff scope = agent; `user_id` set iff scope = user. *(Renamed from `project_id`/scope = project by ADR-009.)*
  * Draft versions are immutable after creation; revision creates a new version.

---

## 8. Nullability Principles

* **Identifiers and creation timestamps are never null** on any entity.
* **Provenance fields** (`created_by`, `changed_by`, `decided_by`) are never null where the baseline requires actor traceability (AIR-054, DR-021).
* **Optional references are null only when genuinely absent** — never as a placeholder. A link entity's unset target references are *structural* (exclusive-arc members), not semantic nulls.
* **"Unknown vs not applicable" is distinguished by design:** e.g., a Research Document's `author` is null when unknown; `format` is never null because every document has a format.
* **Temporal nulls are meaningful:** `ended_at`, `closed_at`, `decided_at`, `deleted_at` are null while the condition has not occurred.
* **Supersession state lives in the chain, not in duplicated flags:** the newer record carries the reference to the record it supersedes; a record is superseded when a newer record references it (and its own `superseded_*_id` is null). Where a status value is stored (§3.5, §3.8), it is a projection kept in step with the chain, never an independent source of truth.

---

## 9. Integrity Rules

* **Referential integrity applies to every reference** (DR-028): no dangling project, document, chunk, version, or link references.
* **Evidence links are immutable and non-cascading.** Chunk Evidence Links and Draft Evidence Links may not be cascade-deleted; deleting an evidence target (soft or hard) does not delete the links that reference it, preserving the audit record (ADR-005; 07 §3.4).
* **Composition cascade.** Messages are removed with their conversation only under the documented retention policy (03 §3.6); draft versions are removed with their draft only under the documented deletion policy. All other references are **restrict**.
* **Deletion preserves integrity (DR-025).** Soft-deleting a Research Document retains its identity and evidence links; referential integrity to remaining data is preserved.
* **Supersession is monotonic.** A superseded Memory Record or Knowledge Element becomes read-only; its successor references it; the chain is never rewritten.
* **Supersession writes are atomic.** Creating a record that supersedes an earlier one updates the new record's predecessor reference and the predecessor's status in the same logical transaction, so the stored status projection never diverges from the chain (§8).
* **Message ordering.** Message sequences are monotonic within a conversation and immutable once assigned.
* **Outbox atomicity.** A Work Item is recorded in the same logical transaction as the state change that triggers it (dual-write via the outbox, ADR-006); idempotency keys prevent duplicate execution.

---

## 10. Soft Delete Strategy

* **Tombstoned entities (user-visible, removable):** Project, Research Document, Conversation, Writing Profile, Draft. These carry `deleted_at` (and `deleted_by` via the audit model). Active queries and API responses exclude tombstones.
* **Never tombstoned (history-bearing):** Memory Record, Knowledge Element, Knowledge Chunk, Draft Version, Review, Review Decision, Profile Characteristic, evidence links. These are superseded or retained, never deleted, per the traceability requirements (DR-014, DR-017, DR-019; 07 §3.3–§3.4).
* **Document removal** is explicit user action (05 §10); it tombstones the document while preserving the evidence chain (integrity rule above).
* **Project deletion** tombstones the project and (per the documented retention policy, refined in document 07) its user-visible contents; history-bearing records are preserved for the retention window.
* **Hard delete** is deferred and governed by the archival/deletion policy of SRS Ch7 §4.4 and document 07; it is never implicit.
* **Rationale:** the MVP must preserve exportability and user ownership (03 §4; 07 §3.1), support recovery (07 §3.5), and preserve the evidence-to-output chain (ADR-001 traceability). Tombstones are the minimum structure that satisfies all three.

---

## 11. Versioning Strategy

* **Draft Version — immutable version chain.** Each writing or revision cycle creates a new Draft Version with the next `version_number`; content is immutable after creation (AIR-035, MVP-021). The current version is the latest. Branching is deferred (not an MVP requirement).
* **Memory Record — supersession chain.** Evolving decisions create a new record that references its predecessor via `superseded_record_id`; chronology and history are retained (DR-014; 04 §8.2).
* **Knowledge Element / Chunk — supersession with retained history.** When new evidence refines understanding, the earlier element/chunk is marked superseded and remains traceable (07 §3.3; AIR-065); re-chunking is coordinated by the knowledge pipeline (ADR-005, ADR-006).
* **Configuration Item — versioned on change.** Every change appends a new version; exactly one version is active per key (DR-021).
* **Conversation — compaction, not versioning.** Conversations may be summarized (compaction) and linked to memory rather than versioned (03 §3.6; 04 §10.2).
* **Not versioned:** User, Session, Project, Agent, Capability, Capability Entry, Work Item (state machines, not versioned content). *(Capability/Capability Entry renamed from Agent/Agent Capability, and Agent added, by ADR-009.)*

---

## 12. Audit Strategy

* **Creation audit:** every entity carries `created_at` and, where actor traceability is required, `created_by` (system capability or user).
* **Change audit:** mutable entities carry `updated_at` where change timing matters, and `*_by` actor references where the baseline requires actor traceability (AIR-054, DR-021); the most audit-sensitive changes are append-only by design (Review Decision, evidence links, Configuration Item history).
* **Immutability as audit:** Draft Version content, Memory Record content, Knowledge Element content, and all link entities are immutable — the audit trail is the entity history itself (append-only records).
* **Human oversight records:** Review Decisions record the reviewer (user), outcome, rationale, and time (AIR-054); they are never modified once recorded.
* **Configuration audit:** every configuration change records who changed what and when (DR-021; AIR-057).
* **Observability linkage:** Work Items record failure context for the diagnostics baseline (API-040; NFR-027 to NFR-028).

---

## 13. Naming Conventions

The following conventions are binding on the physical schema and API payloads that realize this model:

* **Entity names:** singular, PascalCase logical names (Project, ResearchDocument, KnowledgeChunk, DraftVersion). Junction entities are compound names ending in a relationship word (ChunkEvidenceLink, MemoryProvenanceLink, MessageContextLink).
* **Attributes:** lower_snake_case. Suffix conventions: `*_id` for identifiers and references (project_id, draft_version_id); `*_at` for timestamps (created_at, decided_at); `*_by` for actor references (decided_by, changed_by); `is_*` for booleans (is_active); enumerated state fields are named `*_type`, `*_status`, or `outcome` where appropriate.
* **Reference names:** `<target_entity>_id`; when an entity carries more than one reference to the same target, the role prefix disambiguates (element_from_id / element_to_id; superseded_record_id).
* **Keys:** primary key is always `<entity>_id`; candidate keys are named for their meaning (session_token, idempotency_key).
* **Generalization handling:** shared provenance attributes are repeated on each entity (created_at, created_by) rather than inherited from a supertype (see §14).
* **Enumeration values:** lower_snake_case, documented with the entity (e.g., outcome: approved / revisions_requested / rejected).

---

## 14. Relationship Resolution

* **1 : N relationships** are resolved by a reference column on the child entity (Section 5).
* **N : M relationships** are resolved by junction entities: Chunk Evidence Link (chunk–document), Knowledge Element Relationship (element–element), Profile Characteristic Source (characteristic–document), and the exclusive-arc link entities for polymorphic associations.
* **Polymorphic associations** (Draft Evidence Link, Message Context Link, Memory Provenance Link) use the **exclusive-arc pattern**: a `target_type`/`source_type` discriminator plus one nullable reference per possible target, with a rule that exactly one is set. This was chosen over a generic polymorphic foreign key because it preserves strong referential integrity per target (DR-028) while remaining engine-portable. Trade-off: one link entity per association; accepted for the MVP.
* **Self-referential relationships** (Memory Record supersession, Knowledge Element supersession) use a nullable self-reference plus status; the chain is monotonic and history-bearing.
* **Generalization ("Traceable Record", 03 §6) is flattened.** Shared provenance attributes are repeated on each member entity. The alternative — a supertype entity with subtype tables — was rejected: it adds join complexity and inheritance-dependent querying that provide no MVP benefit, and it reduces engine portability (ADR-004 migration path). If a future requirement (e.g., cross-entity audit traversal) justifies a supertype, it is an additive change, not a redesign.
* **Subtyping (Message direction; evidence target kind)** uses enumerated discriminators on the entity itself, not separate entities.

---

## 15. Traceability

This logical data model is traceable to the approved baseline as follows:

* **SRS Chapter 7** — the data domains realized here (DR-001 to DR-033, DR-035; DC-002, DC-003), especially identifiers (DR-001), lifecycle (DR-002, DR-023 to DR-025), provenance (DR-012, DR-015, DR-018), versioning (DR-014, DR-017), review state (DR-019), configuration (DR-020 to DR-022), and referential integrity (DR-028).
* **SRS Chapter 6** — evidence linkage (AIR-024, AIR-027, AIR-046 to AIR-048), memory persistence (AIR-019 to AIR-021, AIR-065 to AIR-066), profile provenance (AIR-016 to AIR-018), review audit (AIR-037 to AIR-039, AIR-054), artifact distinction (AIR-006), configuration (AIR-055 to AIR-057), draft versioning (AIR-035).
* **SRS Chapter 10** — MVP scope: draft version history (MVP-021, MVP-022), review and approval (MVP-018 to MVP-020), memory (MVP-011, MVP-012), retrieval (MVP-007, MVP-008), profile (MVP-009, MVP-010).
* **Architecture 03** — ownership model (§4) and lifecycle (§5).
* **Architecture 04** — memory (AIR-019 to AIR-021, 04 §8), chunking (04 §9), conversation (04 §10), evidence flow (04 §18), review (04 §19), writing and version awareness (04 §20), learning and chronology (04 §22).
* **Architecture 05** — domain boundaries (§4), orchestration (§6), data access layer (§16), configuration model (§17), authentication (§15).
* **Architecture 07** — consistency (§3.3), retention (§3.4), backup assumptions (§3.5).
* **ADR-002** — ORM abstraction (the model must be expressible behind the data access layer).
* **ADR-003** — modular boundaries (per-module data ownership; link entities cross contexts only through the data access layer).
* **ADR-004** — memory as a first-class persisted domain.
* **ADR-005** — chunk-level retrieval; first-class evidence links (Chunk Evidence Link).
* **ADR-006** — durable outbox (Work Item) and idempotent processing.
* **Database Overview (01)** — governing rules and document set (§8, §12, §13); **Domain Model (02)** — vocabulary (§6 of 02); **Conceptual Data Model (03)** — entities and relationships (§3, §4 of 03).
* **ADR-009** — adds Agent (§3.21); narrows Project (§3.3); renames Agent/Agent Capability to Capability/Capability Entry (§3.13–§3.14); re-points Knowledge Element, Knowledge Chunk, Memory Record, Conversation, Writing Profile, and Draft from `project_id` to `agent_id`; renames Configuration Item's `project` scope to `agent`.

---

## 16. Summary

The logical data model, as corrected by ADR-009, refines the conceptual model into twenty-six logical entities — twenty-one core and system entities and five link entities — with logical attributes, surrogate identifiers, candidate keys, references, and integrity rules. Agent is the user's permanent workspace (1:1 with User in the MVP), owning exactly one Project (1:1, permanent) and everything derived from or accumulated within it (Knowledge Element, Knowledge Chunk, Memory Record, Conversation, Writing Profile, Draft); Project retains identity, topic, lifecycle, and Research Document ownership. The pre-existing capability registry is renamed Capability/Capability Entry to free the Agent name. The model resolves every conceptual relationship of Document 03: one-to-many via references, many-to-many and polymorphic associations via junction and exclusive-arc link entities, and supersession via self-references. It establishes normalization to 3NF with two documented deviations, nullability principles, integrity and soft-delete strategies that protect the evidence chain, versioning strategies for drafts, memory, knowledge, and configuration, an audit model grounded in immutability, and naming conventions binding on the physical schema and API payloads.

This document is implementation-independent: no SQL, no DDL, no migrations, no engine selection, no ORM discussion. A Senior Backend Engineer can begin physical schema design from this contract. The next documents in the layered set — 05 (Constraints and Integrity) through 08 (Validation and Review) — will progressively refine and validate this design, and their own ADR-009 corrections follow in this same session.
