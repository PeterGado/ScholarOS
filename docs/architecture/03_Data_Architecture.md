# Data Architecture

**Document:** 03_Data_Architecture.md

**Status:** Active

**Date:** 2026-08-04

---

## 1. Purpose

This document defines the conceptual data architecture for ScholarOS. It describes the major information domains the system must manage, their ownership, relationships, lifecycles, and flows of information.

This architecture is conceptual only. It does not define tables, schemas, SQL, or storage mechanisms.

---

## 2. Data Architecture Principles

The conceptual data architecture of ScholarOS is governed by the following principles:

* The research project is the primary unit of organization.
* The user retains ownership of research materials, project content, and derived knowledge.
* Data should preserve traceability between evidence, interpretation, and generated support.
* Project understanding should persist across sessions.
* Distinct data domains must remain conceptually separate so that they can evolve independently.

---

## 3. Major Data Domains

### 3.1 Projects

**Narrowed by ADR-009.** Project is no longer the primary workspace container — that role now belongs to Agent (§3.11). Project holds the raw input material only.

**Purpose**
* Represent the raw research material — identity, topic, and source documents — nested inside the user's owning Agent.

**Ownership**
* Owned by the user, via its owning Agent (1:1, permanent; ADR-009).

**Responsibilities**
* Establish the identity, topic, and lifecycle of a research undertaking.
* Own its source documents.

**Relationships**
* A project contains many documents.
* A project belongs to exactly one Agent, permanently (ADR-009) — see §3.11.

**Lifecycle**
* Created together with its owning Agent at Agent creation (ADR-009).
* Updated as new source materials are added.
* Closed or archived when the research undertaking concludes.

**Information Flow**
* Project's topic and documents flow into the owning Agent's knowledge, memory, drafting, and review processes (ADR-009).

---

### 3.2 Documents

**Purpose**
* Represent the research source materials supplied by the user.

**Ownership**
* Owned by the user and associated with a specific project.

**Responsibilities**
* Preserve source identity, metadata, and content.
* Provide the evidential basis for later interpretation and drafting support.

**Relationships**
* Documents contribute to knowledge elements and may be linked to drafts and memory entries where relevant.
* Documents may be related to one another through citation, reference, or thematic association.

**Lifecycle**
* Ingested into a project.
* Processed into interpretable knowledge.
* Retained as source evidence for the life of the project or until explicitly removed.

**Information Flow**
* Documents flow into knowledge extraction and retrieval processes.
* Evidence links from documents support drafting and review.

---

### 3.3 Knowledge

**Purpose**
* Represent the structured understanding derived from source materials and the evolving research context.

**Ownership**
* Shared ownership between the system and the user, with the user retaining authority over the research content and interpretation.

**Responsibilities**
* Capture concepts, themes, methods, relationships, and evidence-based insights.
* Support retrieval and context assembly for research assistance.

**Relationships**
* Knowledge is derived from documents.
* Knowledge is referenced by project memory, drafting support, and review activities.
* Knowledge may evolve as new materials are introduced.

**Lifecycle**
* Created through interpretation of source materials.
* Refined as the project evolves.
* Updated or superseded when new evidence alters prior understanding.

**Information Flow**
* Knowledge flows from documents into the retrieval and reasoning workflow.
* It informs drafting support and review outputs.

---

### 3.4 Knowledge Chunks

**Purpose**
* Represent discrete units of interpreted knowledge that can be retrieved and reused.

**Ownership**
* Associated with the project and derived from user-provided materials.

**Responsibilities**
* Provide modular units of evidence and understanding.
* Enable focused retrieval for specific tasks or questions.

**Relationships**
* Each knowledge chunk may connect to one or more source documents and to broader knowledge structures.
* Knowledge chunks may be grouped or linked to project memory or drafting context.

**Lifecycle**
* Created during knowledge processing.
* Relinked or revised as project knowledge changes.
* Retained as long as they remain relevant to the project's understanding.

**Information Flow**
* Knowledge chunks feed retrieval and context assembly.
* They support evidence-grounded draft generation and review.

---

### 3.5 Memory

**Purpose**
* Represent persistent project context, reasoning continuity, and decision history.

**Ownership**
* Owned by the project and the user, with the system preserving and organizing it.

**Responsibilities**
* Retain research objectives, methodological choices, terminology, rationale, and project decisions.
* Reduce the need to re-establish context across sessions.

**Relationships**
* Memory is linked to projects, knowledge, and drafts.
* Memory may reflect prior review decisions and revision history.

**Lifecycle**
* Created when project decisions or context are established.
* Updated as the project evolves.
* Sometimes superseded by newer decisions while retaining historical traceability.

**Information Flow**
* Memory flows into context assembly and drafting support.
* It also records outcomes from review and revision activities.

---

### 3.6 Conversations

**Purpose**
* Represent the interaction history between the user and the system over the course of the project.

**Ownership**
* Owned by the user and the project context, with the system preserving the interaction record.

**Responsibilities**
* Capture user intent, clarifications, requests, and system responses.
* Preserve the evolution of the research workflow over time.

**Relationships**
* Conversations may reference projects, documents, drafts, and memory elements.
* They provide context for understanding why certain decisions or revisions were made.

**Lifecycle**
* Created as the user interacts with the system.
* Retained as a continuity record for the project.
* May be summarized or linked to memory rather than stored verbatim indefinitely.

**Information Flow**
* Conversations inform memory updates, task context, and draft refinement.

---

### 3.7 Writing Profiles

**Purpose**
* Represent the stylistic characteristics of the author without copying prior work verbatim.

**Ownership**
* Owned by the user and associated with one or more projects.

**Responsibilities**
* Preserve writing patterns, vocabulary tendencies, structure preferences, and explanatory style.
* Support stylistic continuity without replacing authorial intent.

**Relationships**
* Writing profiles relate to projects and drafting artifacts.
* They are informed by authored samples and may be refined over time.

**Lifecycle**
* Created from supplied writing samples.
* Updated as the user refines the profile.
* Reused across future projects or sessions where appropriate.

**Information Flow**
* Writing profile signals flow into drafting and refinement workflows.

---

### 3.8 Capabilities

**Renamed from "Agents" by ADR-009**, to avoid collision with the new Agent workspace domain (§3.11). Meaning unchanged.

**Purpose**
* Represent the conceptual intelligence capabilities that support the workflow.

**Ownership**
* Architecture-level capability ownership rather than user ownership.

**Responsibilities**
* Support distinct workflow stages such as understanding, retrieval, drafting, review, and coordination.
* Operate as coordinated capabilities rather than a single monolithic actor.

**Relationships**
* Capabilities interact with Agents, knowledge, memory, drafts, and review states.
* They may coordinate with one another as the workflow progresses.

**Lifecycle**
* Active during workflow execution.
* Reconfigured or expanded as new capabilities are introduced.

**Information Flow**
* Capabilities receive contextual input and produce outputs that feed the drafting and review workflow.

---

### 3.9 Drafts

**Purpose**
* Represent the academic content generated or refined during the project.

**Ownership**
* Owned by the user and associated with their project.

**Responsibilities**
* Preserve draft content, structure, revisions, and review state.
* Support iterative refinement and human approval.

**Relationships**
* Drafts relate to projects, source evidence, knowledge, and memory.
* Drafts may be linked to specific review decisions and version history.

**Lifecycle**
* Created from a drafting task.
* Revised through iterative workflow cycles.
* Approved, rejected, or superseded as the project progresses.

**Information Flow**
* Drafts flow from context assembly and drafting support into review and memory updates.

---

### 3.10 Reviews

**Purpose**
* Represent the evaluation and approval state of drafts and supporting outputs.

**Ownership**
* Owned by the user as the final reviewer and approver.

**Responsibilities**
* Capture review feedback, revision requests, and approval decisions.
* Preserve evidence of human oversight and quality control.

**Relationships**
* Reviews relate to drafts, memory entries, and project workflow state.
* Review outcomes may influence future draft generation and memory updates.

**Lifecycle**
* Created during draft review.
* Updated through revision cycles.
* Preserved as part of the project history.

**Information Flow**
* Review results feed back into memory and future drafting cycles.

---

### 3.11 Agents

**Added by ADR-009.** Appended after §3.10 to preserve the numbering of the original ten domains.

**Purpose**
* Represent the user's permanent, specialized research workspace — the primary container of work, replacing Project in that role (ADR-009).

**Ownership**
* Owned by the user as the author and steward of the research effort.

**Responsibilities**
* Establish the identity and lifecycle of the workspace.
* Own exactly one Project (1:1, permanent) and anchor all knowledge, memory, drafts, conversations, and writing profile derived from or accumulated within it.
* Enforce the one-Agent-per-user MVP boundary.

**Relationships**
* An Agent owns exactly one Project, permanently.
* An Agent hosts many knowledge elements, memory records, conversations, drafts, and review states — relationships previously held directly by Project (ADR-009).

**Lifecycle**
* Created once per user in the MVP, together with its Project, from user-supplied topic, reference documents, and writing-style samples.
* Persists permanently; never replaced or reassigned to a different Project.
* A future, monetization-gated capability may allow additional Agents per user (ADR-009 Future Considerations).

**Information Flow**
* Agent context flows into memory, knowledge, drafting, and review processes — the role previously described for Project in §3.1.

---

## 4. Data Ownership Model

The conceptual ownership model is as follows (**corrected by ADR-009**: Agent replaces Project as the primary user-owned container for derived content):

* User-owned data: Agents, projects, documents, drafts, reviews, writing profiles, and Agent-scoped memory content.
* System-managed data: workflow state, orchestration context, derived knowledge structures, and traceability associations.
* Shared data: knowledge representations and memory records that are created through system processing but remain tied to user ownership and Agent context.

This model ensures that the platform remains supportive rather than replacing the researcher's authority over the work.

---

## 5. Relationship and Lifecycle Summary

The primary information flow is:

1. Documents enter the project as source materials.
2. Source materials inform knowledge and knowledge chunks.
3. Knowledge and memory support context assembly.
4. Context informs drafting and review activities.
5. Review outcomes update memory and future workflow state.
6. Conversations and review history preserve continuity across sessions.

This lifecycle reflects the product and architectural goals of understanding before generation, evidence grounding, continuity, and human oversight.

This conceptual data architecture is sufficient for documenting the data domains and ownership model. It is intentionally not a database design artifact and remains a boundary for later database design work rather than a substitute for it.

---

## 6. Traceability

This data architecture is aligned to the SRS data and workflow requirements:

* Project and lifecycle data: DR-001 to DR-003, WR-001 to WR-003, MVP-001 to MVP-002.
* Document and source material data: DR-004 to DR-006, WR-004 to WR-006, MVP-003 to MVP-004.
* Knowledge and knowledge chunk data: DR-007 to DR-009, AIR-007 to AIR-015, MVP-005 to MVP-008.
* Project memory data: DR-013 to DR-015, WR-013 to WR-015, MVP-011 to MVP-012.
* Draft and review data: DR-016 to DR-019, WR-022 to WR-025, MVP-018 to MVP-022.
* Author profile data: DR-010 to DR-012, AIR-016 to AIR-018, MVP-009 to MVP-010.
* ADR traceability: ADR-001 (separation of concerns); ADR-004 (storage and memory strategy) governs how these domains are persisted; ADR-009 (Agent workspace introduction, Project narrowing, Agents/Capabilities rename, §3.1, §3.8, §3.11).
