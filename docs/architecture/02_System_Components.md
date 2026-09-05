# System Components

**Document:** 02_System_Components.md

**Status:** Active

**Date:** 2026-08-04

---

## 1. Purpose

This document defines the major conceptual components of ScholarOS architecture. Each component is described in implementation-agnostic terms, including its purpose, responsibilities, inputs, outputs, dependencies, interactions, and SRS traceability.

The intent is to describe the system's organization without prescribing code structure or technology choices.

---

## 2. Component Model

The ScholarOS architecture is organized around the following major components.

---

## 3. Component Definitions

### 3.1 Project Lifecycle Component

**Narrowed by ADR-009:** this component now manages only the raw research material (identity, topic, source documents) nested inside the user's Agent workspace — see §3.11 Agent Workspace Component.

**Purpose**
* Establish and maintain the identity, scope, and lifecycle state of a research project, nested inside its owning Agent.

**Responsibilities**
* Create and manage research projects.
* Preserve project identity and metadata.
* Track project lifecycle state across sessions.
* Support project-level configuration and continuity.

**Inputs**
* User-defined project name, topic, objectives, and scope.
* Project-level configuration and workflow preferences.

**Outputs**
* Project identity and state.
* Project metadata available to other components.
* Project lifecycle status for review and continuity.

**Dependencies**
* Project Memory Component.
* Context Assembly Component.

**Interactions**
* Receives user intent at project creation.
* Supplies project state to knowledge, drafting, and review flows.

**SRS Traceability**
* WR-001 to WR-003
* MVP-001 to MVP-002
* DR-001 to DR-003

---

### 3.2 Research Intake Component

**Purpose**
* Accept and register research materials supplied by the user.

**Responsibilities**
* Receive documents and supporting artifacts.
* Preserve source material identity and metadata.
* Track intake status and source relationships.
* Make source materials available for downstream processing.

**Inputs**
* User-supplied documents and research materials.
* Optional project-level classification or organization guidance.

**Outputs**
* Registered source materials.
* Source metadata and intake status.
* Traceable references from source materials to downstream knowledge.

**Dependencies**
* Project Lifecycle Component.
* Knowledge Management Component.

**Interactions**
* Receives user uploads and informs the knowledge pipeline.
* Supplies source material references to knowledge extraction and retrieval.

**SRS Traceability**
* WR-004 to WR-006
* MVP-003 to MVP-004
* DR-004 to DR-006

---

### 3.3 Knowledge Management Component

**Purpose**
* Transform source materials into usable and reusable knowledge for the research project.

**Responsibilities**
* Extract conceptual understanding from research materials.
* Structure knowledge into coherent relationships and categories.
* Maintain traceability from knowledge back to source evidence.
* Support knowledge reuse during drafting and review.

**Inputs**
* Registered source materials.
* Project context and current task focus.

**Outputs**
* Structured knowledge elements.
* Concept relationships and evidence associations.
* Knowledge access results for retrieval and context assembly.

**Dependencies**
* Research Intake Component.
* Retrieval Component.
* Project Memory Component.

**Interactions**
* Consumes source materials produced by research intake.
* Provides knowledge to retrieval and context assembly.

**SRS Traceability**
* AIR-007 to AIR-015
* AIR-022 to AIR-024
* MVP-005 to MVP-008
* DR-007 to DR-009

---

### 3.4 Retrieval Component

**Purpose**
* Locate and select relevant knowledge and evidence for the current task.

**Responsibilities**
* Retrieve relevant knowledge based on project objectives and current context.
* Preserve source traceability in retrieval results.
* Support evidence-grounded reasoning and drafting.

**Inputs**
* Current task request.
* Available project knowledge and memory.
* User-specified relevance criteria.

**Outputs**
* Relevant evidence and knowledge subsets.
* Ranked or prioritized retrieval results.
* Traceable supporting references.

**Dependencies**
* Knowledge Management Component.
* Project Memory Component.
* Context Assembly Component.

**Interactions**
* Serves as a support service for drafting, review, and context construction.
* Helps ensure that support content is grounded in project evidence.

**SRS Traceability**
* AIR-022 to AIR-024
* WR-017
* MVP-007 to MVP-008

---

### 3.5 Author Profile Component

**Purpose**
* Preserve the author's writing characteristics and stylistic preferences across the project lifecycle.

**Responsibilities**
* Derive writing profile characteristics from supplied author samples.
* Maintain stylistic signals without reproducing prior text verbatim.
* Make profile characteristics available to drafting and refinement activities.

**Inputs**
* Authored work samples.
* User review or profile refinement instructions.

**Outputs**
* Author profile representation.
* Stylistic guidance for drafting and revision.

**Dependencies**
* Project Lifecycle Component.
* Drafting Support Component.

**Interactions**
* Supplies style guidance to drafting and review workflows.
* Receives user updates and profile refinements.

**SRS Traceability**
* AIR-016 to AIR-018
* WR-010 to WR-012
* MVP-009 to MVP-010
* DR-010 to DR-012

---

### 3.6 Project Memory Component

**Purpose**
* Preserve persistent project understanding, decisions, and context across sessions.

**Responsibilities**
* Store project objectives, decisions, terminology, and findings.
* Preserve chronology and change history.
* Make memory available to later activities and sessions.
* Distinguish current project state from historical context.

**Inputs**
* User-entered project decisions and context.
* System-derived context from prior activities.
* Review feedback and revision decisions.

**Outputs**
* Persistent project memory records.
* Memory updates and historical context references.
* Context available for drafting and review.

**Dependencies**
* Project Lifecycle Component.
* Knowledge Management Component.
* Context Assembly Component.

**Interactions**
* Receives updates from the project workflow.
* Provides persistent context to drafting and review support.

**SRS Traceability**
* AIR-019 to AIR-021
* AIR-065 to AIR-066
* WR-013 to WR-015
* MVP-011 to MVP-012
* DR-013 to DR-015

---

### 3.7 Context Assembly Component

**Purpose**
* Assemble a task-specific working context for drafting, review, or analysis.

**Responsibilities**
* Combine project memory, knowledge, profile signals, and current task intent.
* Prepare a coherent context for downstream reasoning or generation.
* Preserve user control and review before execution.

**Inputs**
* Current task request.
* Relevant project memory.
* Retrieved knowledge.
* Author profile characteristics.

**Outputs**
* Assembled working context.
* Context review artifacts for the user.
* A structured basis for downstream drafting or review.

**Dependencies**
* Project Memory Component.
* Retrieval Component.
* Author Profile Component.
* Drafting Support Component.

**Interactions**
* Receives input from all knowledge-bearing components.
* Supplies assembled context to drafting and review flows.

**SRS Traceability**
* AIR-013 to AIR-015
* WR-016 to WR-018
* MVP-013 to MVP-014

---

### 3.8 Drafting Support Component

**Purpose**
* Generate or refine draft content that is informed by project context and evidence.

**Responsibilities**
* Produce draft assistance for specified sections or chapters.
* Preserve evidence grounding and author profile alignment.
* Support revision cycles and version-aware refinement.

**Inputs**
* Assembled context.
* Drafting objective and constraints.
* Evidence references and memory context.

**Outputs**
* Draft content.
* Draft revision options.
* Versioned draft artifacts for review.

**Dependencies**
* Context Assembly Component.
* Retrieval Component.
* Author Profile Component.

**Interactions**
* Produces draft content for review.
* Receives user revision instructions and refinement requests.

**SRS Traceability**
* AIR-031 to AIR-036
* WR-019 to WR-025
* MVP-015 to MVP-022
* DR-016 to DR-019

---

### 3.9 Review and Oversight Component

**Purpose**
* Ensure that outputs remain reviewable, evaluable, and subject to human approval.

**Responsibilities**
* Support review of drafts and supporting context.
* Preserve evidence references and state of approval.
* Track revision requests and approval decisions.

**Inputs**
* Draft content.
* Evidence references.
* User review instructions and approval decisions.

**Outputs**
* Review feedback.
* Approval or revision status.
* Updated draft state.

**Dependencies**
* Drafting Support Component.
* Project Memory Component.

**Interactions**
* Receives drafts from the drafting workflow.
* Returns review outcomes that influence project memory and future drafts.

**SRS Traceability**
* AIR-003
* WR-022 to WR-025
* MVP-018 to MVP-020

---

### 3.10 Intelligence Coordination Component

**Purpose**
* Orchestrate the interplay between understanding, retrieval, drafting, and review without collapsing the workflow into a single generation act.

**Responsibilities**
* Coordinate the lifecycle from intent to review.
* Maintain the distinction between raw input, interpreted knowledge, stored memory, and approved output.
* Preserve continuity and traceability across workflow stages.

**Inputs**
* User requests and workflow state.
* Context from knowledge, memory, and author profile components.

**Outputs**
* Coordinated reasoning and support actions.
* Structured workflow progression and traceable outputs.

**Dependencies**
* All major capability components.

**Interactions**
* Acts as the architectural orchestrator for the intelligence workflow.
* Ensures that understanding is established before drafting and that review remains central.

**SRS Traceability**
* AIR-001 to AIR-006
* AIR-063 to AIR-066
* WR-016 to WR-025

---

### 3.11 Agent Workspace Component

**Added by ADR-009.** Appended after §3.10 to preserve the numbering of the existing ten components.

**Purpose**
* Establish and maintain the user's permanent, specialized research workspace, wrapping exactly one Project.

**Responsibilities**
* Create an Agent together with its one Project from the user-supplied topic, reference documents, and writing-style samples.
* Enforce the one-Agent-per-user MVP boundary.
* Anchor identity for everything derived from or accumulated within the Project: knowledge, memory, conversations, writing profile, drafts, and reviews.

**Inputs**
* User-supplied research topic, reference documents, and writing-style samples.

**Outputs**
* Agent identity and state, available to all other components that previously scoped to Project directly.

**Dependencies**
* Project Lifecycle Component (§3.1) — owns exactly one Project, permanently.

**Interactions**
* Created once per user in the MVP; supplies its identity to Knowledge Management, Project Memory, Author Profile, Drafting Support, and Review and Oversight components, which now scope to the Agent rather than the Project.

**SRS Traceability**
* ADR-009 (no dedicated SRS chapter yet; recorded as a data-requirements and MVP-scope amendment per ADR-009 §Repository Impact).

---

## 4. Component Interaction Summary

The components form an integrated workflow:

1. The Project Lifecycle Component establishes the project context.
2. The Research Intake Component introduces source materials.
3. The Knowledge Management and Retrieval components transform and locate relevant knowledge.
4. The Project Memory and Author Profile components preserve continuity and voice.
5. The Context Assembly Component prepares the working context.
6. The Drafting Support and Review components produce and evaluate draft assistance.
7. The Intelligence Coordination Component maintains a coherent end-to-end workflow.

This arrangement satisfies the product philosophy of understanding before generation and human oversight throughout the workflow.

This component model is governed by ADR-001 (separation of concerns); component and service boundaries follow ADR-003 (modular monolith service organization) and the ADR set (ADR-002 to ADR-007). The Agent Workspace Component (§3.11) and the narrowing of the Project Lifecycle Component (§3.1) were added by ADR-009.
