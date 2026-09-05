# Frontend Architecture

**Document:** 06_Frontend_Architecture.md

**Status:** Active

**Date:** 2026-08-05

---

## 1. Purpose

This document defines the logical user experience architecture of ScholarOS. It describes how the user navigates the research workflow, how workspaces are organized, and how the user interacts with knowledge, memory, agents, and conversations.

This document is a logical architecture. It does not prescribe user interface technology, component libraries, styling systems, or layout tools. It defines the interaction model, information structure, and experience principles that an implementation must satisfy.

It complements the Milestone 1 and Milestone 2 architecture set:

* [01_Architecture_Overview.md](01_Architecture_Overview.md) — overall layered architecture
* [02_System_Components.md](02_System_Components.md) — conceptual components
* [03_Data_Architecture.md](03_Data_Architecture.md) — conceptual data domains
* [04_AI_Architecture.md](04_AI_Architecture.md) — intelligence operating model
* [05_Backend_Architecture.md](05_Backend_Architecture.md) — logical backend organization

---

## 2. UX Philosophy

ScholarOS presents a research operating environment, not a chat tool or a text editor.

The UX philosophy is:

* **The research workflow is the spine.** Every screen and interaction serves the journey from project creation through writing, review, and revision.
* **Understanding before writing is visible.** The user can see what the system understands — knowledge, memory, evidence — before it writes.
* **Human oversight is effortless.** Context, evidence, and drafts are presented in ways that make review natural, not burdensome.
* **Continuity is felt, not managed.** Returning to a project resumes work in place, with context intact.
* **Progressive disclosure.** Advanced capabilities appear as needed; complexity is not forced on the user (SRS Chapter 8, workflow philosophy).
* **The researcher stays in control.** The interface makes the user's authority over decisions explicit and comfortable.

This philosophy is aligned with the Vision, SRS Chapter 5 usability requirements (NFR-019, NFR-020), and accessibility requirements (NFR-021, NFR-022).

---

## 3. Navigation Model

Navigation is organized around the research workflow stages rather than around application features.

### 3.1 Navigation Principles

* **Stage-based navigation.** The user moves through the project lifecycle: initiation, materials, knowledge, memory, conversation, writing, review.
* **Cross-cutting access.** Knowledge exploration, memory, and settings remain reachable from any stage without losing workflow position (WR-032).
* **State preservation.** Navigating among stages never loses project state (WR-032, WR-034).
* **Progress visibility.** The current stage and completed activities are visible (WR-033).
* **Targeted entry.** The user may enter the workflow at a specific stage when context is sufficient (WR-031).

### 3.2 Navigation Structure

| Navigation Area | Purpose |
|-----------------|---------|
| Project list | Enter an existing project or create a new one (WR-001, MVP-001) |
| Project workspace | The current stage of the research workflow for a project |
| Stage rail | Move among workflow stages without losing state (WR-032) |
| Persistent sidebars | Knowledge exploration, memory, and context, accessible from any stage |
| Global settings | User preferences, provider configuration, and project configuration |

### 3.3 Continuity Behaviors

* Resuming a project presents its current state with accumulated knowledge and memory (WR-026).
* Interruption and resumption cause no data loss or context degradation (WR-034).
* Guidance on available actions and expected outcomes is available at each stage (WR-035).

---

## 4. Workspace Organization

The workspace is the primary working surface of the frontend.

### 4.1 Workspace Model

Each research project is presented as a set of workspaces, one per major workflow stage:

| Workspace | Primary Purpose | Workflow Stage |
|-----------|----------------|----------------|
| Project Workspace | Project identity, scope, and lifecycle | Stage 1 |
| Research Workspace | Materials, knowledge processing, and knowledge building | Stages 2–3 |
| Memory Workspace | Project memory building and review | Stage 5 |
| Conversation Workspace | Research conversations and agent interaction | Ongoing |
| Writing Workspace | Context assembly, drafting, and refinement | Stages 6–7 |
| Review Workspace | Draft review, revision, and approval | Stage 8 |

Workspaces share a common shell so that navigation, progress, and context panels behave consistently across stages.

### 4.2 Workspace Principles

* Each workspace presents the actions and information relevant to its stage; unrelated complexity is hidden (progressive disclosure).
* Workspaces reflect the current project state and are resumable (WR-028).
* Cross-workspace artifacts (documents, knowledge, memory) are linked, not duplicated; the user navigates to them rather than re-entering them (per 09_Documentation_Standards, avoid duplication).

---

## 5. Project Workspace

The project workspace establishes and maintains the identity of the research undertaking.

### 5.1 Responsibilities

* Create a new project with topic and scope (WR-001, WR-002, MVP-001, MVP-002).
* Present project identity, metadata, and lifecycle state (DR-001, DR-002).
* Provide project-level configuration entry points (DR-003).
* List projects and allow selection of an existing project (WR-026, MVP-001).

### 5.2 Experience Principles

* Project creation is a single, guided interaction; the project becomes ready for materials immediately.
* The initial project definition remains visible and editable throughout the lifecycle (WR-003).

---

## 6. Research Workspace

The research workspace supports material collection and knowledge building.

### 6.1 Responsibilities

* Upload and register research documents (WR-004, MVP-003).
* Show processing status of materials (WR-005, API-010).
* Support organizing and classifying uploaded materials (WR-006).
* Initiate knowledge processing (WR-007).
* Present processed knowledge for review and validation (WR-008).
* Support user refinements to the knowledge base (WR-009).

### 6.2 Experience Principles

* Intake feedback is immediate and continuous: the user always knows what has been processed and what remains.
* Knowledge results are presented with their source provenance visible, so the user can validate accuracy and relevance (AIR-024, AIR-052).
* Refinement is lightweight: the user can correct, supplement, or remove knowledge elements.

---

## 7. Writing Workspace

The writing workspace supports context assembly, drafting, and refinement.

### 7.1 Responsibilities

* Specify the activity or section to be drafted or reviewed (WR-016).
* Present the assembled context before proceeding (WR-018, MVP-014).
* Request draft generation for a specified content area (WR-019, MVP-015).
* Present generated drafts grounded in context (WR-020, MVP-016).
* Support acceptance, rejection, or revision requests (WR-021).
* Apply author profile characteristics to drafts (MVP-017).

### 7.2 Experience Principles

* **Context is visible before writing.** The user reviews assembled context — knowledge, memory, evidence — before a draft is produced (WR-018).
* **Evidence is attached.** Drafts surface the evidence and memory that informed them (AIR-027, AIR-052, WR-022).
* **Revision is iterative.** Refinement preserves evidence and user intent across cycles (AIR-034, AIR-035).
* **Version history is accessible.** Prior versions remain available (WR-024, MVP-021, MVP-022).

---

## 8. Review Workspace

The review workspace supports evaluation, revision, and approval.

### 8.1 Responsibilities

* Present drafts with evidence references for review (WR-022, MVP-018).
* Support revision instructions and direct edits (WR-023).
* Preserve version history across revision cycles (WR-024, MVP-021).
* Record user approval of the final version (WR-025, MVP-020).
* Support retrieval of approved content for export, with advanced formatting and full-text export deferred beyond the MVP (MVP out-of-scope).

### 8.2 Experience Principles

* Review surfaces confidence distinctions: supported evidence, inferred interpretation, and open questions are visually distinct (AIR-067, AIR-068).
* Every claim can be traced to its supporting material with a single interaction (AIR-053).
* Approval is an explicit, recorded action that the user owns (AIR-003, AIR-038).
* Revision requests flow back into drafting without losing the original evidence and intent (AIR-034).

---

## 9. Memory Visualization

Memory visualization makes persistent project understanding visible and inspectable.

### 9.1 Responsibilities

* Present project memory: objectives, decisions, terminology, methodology, and chronology (WR-013, DR-013, DR-014).
* Distinguish current project state from historical context (AIR-021).
* Support review and update of memory throughout the lifecycle (WR-015, MVP-012).
* Show how memory connects to knowledge, evidence, and drafts.

### 9.2 Experience Principles

* Memory is explorable: the user can browse by topic, chronology, or relationship.
* Memory updates are user-aware: nothing is inferred into memory without user visibility (MVP-011 limitation).
* Continuity is visible: on return, the user sees what the project knows and where work left off (WR-026).

---

## 10. Agent Interaction Model

The agent interaction model governs how the user interacts with the system's intelligence capabilities.

### 10.1 Interaction Model

* The user interacts with capabilities through the conversation and workspace surfaces; the underlying agent structure remains visible enough to be understood (AIR-049, AIR-050).
* Capability activity (understanding, retrieval, drafting, review) is surfaced as stages, not hidden as a single opaque generation act (AIR-004).
* The user can inspect what a capability used — context, evidence, memory — and why (AIR-050, AIR-053).
* Capability selection and behavior reflect configuration-approved settings (AIR-055, AIR-056).

### 10.2 Experience Principles

* Explanations accompany assistance: the user understands the relationship between context and output (AIR-049).
* The user directs work; capabilities respond within their defined boundaries (AIR-003).
* New capabilities appear through the controlled extension path and remain reviewable (AIR-058, AIR-059).

---

## 11. Conversation Model

The conversation model defines how research conversations are presented and preserved.

### 11.1 Responsibilities

* Present sequential and iterative interaction with continuity of understanding (AIR-005).
* Support targeted entry: the user can ask about a section, evidence, or decision without restarting (WR-031).
* Preserve conversation history as a continuity record across sessions (WR-034).
* Distinguish conversational exchanges from persistent project changes (AIR-006).

### 11.2 Experience Principles

* Conversations are anchored in the project; references to documents, knowledge, and drafts are navigable.
* Approved conversation outcomes flow into memory with user awareness.
* Conversations are reviewable as part of the project's continuity record.

---

## 12. Knowledge Exploration

Knowledge exploration provides a way to browse, query, and understand the project knowledge base.

### 12.1 Responsibilities

* Browse knowledge elements by concept, theme, and relationship (MVP-006, DR-007 to DR-009).
* Query the knowledge base for relevant information (WR-017, MVP-007).
* View evidence provenance for every knowledge element (MVP-008, AIR-024).
* Support comparison and synthesis views where appropriate (AIR-011).

### 12.2 Experience Principles

* Exploration is non-destructive: browsing knowledge never alters it.
* Provenance is always one step away: any knowledge element links to its source material.
* Exploration informs conversation and writing: the user can carry a knowledge element into a drafting or review activity.

---

## 13. Document Management

Document management presents the project's source materials.

### 13.1 Responsibilities

* List documents within a project (API-008).
* Show document metadata and processing status (WR-005, API-010).
* Support organization and classification of materials (WR-006).
* Support removal of documents with integrity safeguards (DR-025).

### 13.2 Experience Principles

* Document state is always visible: registered, processing, processed, or failed.
* Documents are linked to the knowledge they produced, and vice versa (DR-006).
* Removal is deliberate and preserves project integrity (DR-025).

---

## 14. Settings Architecture

Settings govern user preferences, provider configuration, and project configuration.

### 14.1 Settings Domains

| Domain | Content | Requirements |
|--------|---------|--------------|
| User preferences | Interface, workflow, and notification preferences | DR-022 |
| Provider configuration | External service selection and parameters | AIR-055, DR-020 |
| Project configuration | Project-specific behavior | DR-003 |
| Operational parameters | System-level behavior | NFR-031 |

### 14.2 Experience Principles

* The active configuration state is visible (AIR-056).
* Configuration changes are reviewable and traceable (AIR-057, NFR-032).
* Settings never expose choices that would change the approved product philosophy.
* Provider settings are presented so the user understands what is configured without requiring technical knowledge (NFR-019).

---

## 15. Accessibility Principles

The frontend supports accessible interaction by design.

### 15.1 Accessibility Responsibilities

* Support accessible interaction patterns and content delivery suitable for diverse user needs (NFR-021).
* Provide adequate support for navigation, readability, and review of project outputs (NFR-022).
* Ensure all essential research functions remain usable without excluding any user (NFR-021).

### 15.2 Experience Principles

* Keyboard-operable navigation across all workspaces and stages.
* Text alternatives for non-text content; semantic structure for screen readers.
* Sufficient contrast, legible typography, and resizable content.
* Focus management that preserves workflow position (WR-032, WR-034).
* Language that is clear, consistent, and free of unnecessary jargon.

Accessibility applies to every workspace and interaction described in this document, and is validated as part of the review process.

---

## 16. State Management Philosophy

State management governs how the frontend represents and preserves workflow and project state.

### 16.1 State Categories

| Category | Content | Persistence |
|----------|---------|-------------|
| Workflow state | Current stage, completed activities, position within the project | Preserved across sessions (WR-033, WR-034) |
| Project state | Project identity, knowledge, memory, drafts | Preserved by the backend; reflected in the frontend (WR-027) |
| View state | Current selection, scroll position, open panels | Session-local; restored on resume |
| UI preferences | User interface preferences | Persisted per user (DR-022) |

### 16.2 Principles

* **Single source of truth.** The backend owns project data; the frontend reflects it and coordinates interaction (WR-027).
* **No loss on interruption.** Interruption and resumption cause no data loss or context degradation (WR-034).
* **Consistency across views.** The same project state is presented consistently regardless of the workspace (NFR-020).
* **Recoverability.** User actions are understandable and recoverable (NFR-020).
* **Optimistic clarity.** The frontend communicates pending operations (e.g., processing status) honestly rather than presenting unverified state as final.

---

## 17. Component Hierarchy

The frontend is organized as a hierarchy of logical components.

### 17.1 Hierarchy

| Level | Components | Responsibility |
|-------|-----------|----------------|
| 1. Shell | Application shell, navigation rail, global settings | Frame the product; preserve workflow position |
| 2. Workspace | Project, research, memory, conversation, writing, review workspaces | Realize each workflow stage |
| 3. Feature panels | Document list, knowledge explorer, memory browser, context panel, evidence panel | Present domain content |
| 4. Interaction components | Conversation thread, draft editor, review surfaces, configuration forms | Support specific interactions |
| 5. Presentation components | Shared, reusable building blocks for consistent display | Enforce consistency and accessibility |

### 17.2 Hierarchy Principles

* **High cohesion, low coupling.** Each component owns a single responsibility; components interact through well-defined boundaries.
* **Reusability.** Shared presentation components avoid duplication and enforce consistency (per 09_Documentation_Standards, avoid duplicated information).
* **Replaceability.** A workspace or panel can be refined without redesigning the shell.
* **Accessibility by construction.** Accessibility is a property of every component, not an overlay.
* **Alignment to capabilities.** The hierarchy mirrors the backend service boundaries so that frontend components map cleanly to backend capabilities (per [05_Backend_Architecture.md](05_Backend_Architecture.md)).

---

## 18. Traceability

The frontend architecture is traceable to the approved requirements as follows:

* UX philosophy and navigation: NFR-019, NFR-020, WR-032 to WR-035.
* Project workspace: WR-001 to WR-003, DR-001 to DR-003, MVP-001 to MVP-002.
* Research workspace: WR-004 to WR-009, API-008 to API-013, MVP-003 to MVP-008, DR-004 to DR-009.
* Writing workspace: WR-016 to WR-021, AIR-016, AIR-031 to AIR-036, MVP-013 to MVP-017, DR-016 to DR-018.
* Review workspace: WR-022 to WR-025, AIR-037 to AIR-039, AIR-067 to AIR-068, MVP-018 to MVP-022, DR-019.
* Memory visualization: WR-013 to WR-015, WR-026 to WR-028, AIR-019 to AIR-021, MVP-011 to MVP-012, DR-013 to DR-015.
* Agent interaction model: AIR-004, AIR-049 to AIR-051, AIR-058 to AIR-060.
* Conversation model: AIR-005, AIR-006, WR-031, WR-034.
* Knowledge exploration: WR-017, AIR-022 to AIR-024, AIR-052 to AIR-053, MVP-007 to MVP-008.
* Document management: WR-004 to WR-006, API-008 to API-010, DR-004 to DR-006, DR-025.
* Settings architecture: AIR-055 to AIR-057, DR-003, DR-020 to DR-022, NFR-031 to NFR-032.
* Accessibility: NFR-021, NFR-022.
* State management: WR-026 to WR-028, WR-032 to WR-034, NFR-020, DR-022.
* Component hierarchy: NFR-015 to NFR-018 (modularity and extensibility), alignment to backend service boundaries.
* ADR traceability: ADR-001 (separation of concerns); ADR-002 to ADR-007 (backend and operational decisions the frontend consumes through the API).

These traceability links ensure the user experience architecture remains accountable to the approved requirements.
