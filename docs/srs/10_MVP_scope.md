# Software Requirements Specification (SRS)

## Chapter 10: MVP Scope

**Product:** ScholarOS

**Version:** 1.0.0

**Status:** Draft

---

## 1. Purpose

This chapter defines the scope boundaries of the ScholarOS Minimum Viable Product (MVP).

The purpose of this chapter is to establish precisely which capabilities are included in the first release, which are explicitly excluded, and what conditions define the completeness of the MVP. This chapter serves as the authoritative reference for scope decisions during MVP planning, implementation, and validation.

---

## 2. MVP Philosophy

The ScholarOS MVP is governed by the following principles:

1. **Correctness over completeness:** The MVP shall prioritize reliable, well-tested functionality over feature breadth.
2. **Core workflow first:** The MVP shall implement the essential research workflow from project creation through draft generation, enabling a complete user cycle.
3. **Backend-first implementation:** The MVP shall implement backend capabilities before user-facing interfaces, consistent with the approved project stage.
4. **Single-user focus:** The MVP shall support a single authenticated user per deployment.
5. **Personal research context:** The MVP shall support personal academic research projects, not institutional or collaborative workflows.
6. **Extensible foundation:** Every MVP capability shall be designed to support future expansion without requiring redesign.

---

## 3. In-Scope Capabilities

The following capabilities are included in the ScholarOS MVP scope.

### 3.1 Project Management

**Extended by ADR-009:** the MVP's research project is created together with, and permanently nested inside, the user's Agent workspace (§3.11).

- Create the user's Agent workspace, together with its one research project.
- Define research topic and scope.
- Store and retrieve project metadata.
- Delete the Agent's project (which, in the MVP, means archiving the Agent — see MVP-030).

**Limitation:** No multi-user or collaborative project management. In the MVP, a user has exactly one Agent and exactly one project — "list and select available projects" does not apply, since there is only one (ADR-009; see §3.11).

#### Requirement Statements

* MVP-001: The MVP shall support creation and management of single-user research projects as described in WR-001 through WR-003 (Project Initiation), with the additional constraint that only a single authenticated user per project is supported.
* MVP-002: The MVP shall allow definition of research topic and scope during project creation.

---

### 3.2 Document Ingestion

- Upload research documents in common academic formats.
- Register document metadata (title, author, source).
- Store document content for processing.
- List ingested documents within a project.
- Remove ingested documents.

**Limitation:** Document processing is limited to text-based academic documents. Binary or non-text formats are supported only to the extent that their textual content can be extracted.

#### Requirement Statements

* MVP-003: The MVP shall support ingestion of text-based research documents supplied by the user.
* MVP-004: The MVP shall register and preserve document metadata for ingested materials.

---

### 3.3 Knowledge Extraction

- Process ingested documents to derive conceptual understanding.
- Extract key concepts, themes, and relationships from source materials.
- Organize extracted knowledge for retrieval and use.

**Limitation:** Knowledge extraction quality depends on the quality and relevance of source materials supplied by the user. The system shall not guarantee completeness of extraction.

#### Requirement Statements

* MVP-005: The MVP shall support extraction of conceptual knowledge from ingested research documents.
* MVP-006: The MVP shall organize extracted knowledge to support retrieval and use in downstream activities.

---

### 3.4 Knowledge Retrieval

- Query the project knowledge base for relevant information.
- Retrieve knowledge elements related to a specified topic or context.
- Support evidence-grounded retrieval that preserves source traceability.

**Limitation:** Retrieval is limited to knowledge derived from user-supplied materials. The system shall not supplement project knowledge with external sources unless explicitly configured to do so.

#### Requirement Statements

* MVP-007: The MVP shall support retrieval of relevant knowledge from the project knowledge base.
* MVP-008: The MVP shall preserve source traceability in retrieval results.

---

### 3.5 Author Profile Creation

- Accept authored work samples from the user.
- Derive writing style characteristics from provided samples.
- Store and retrieve the author profile for use in drafting.

**Limitation:** The author profile shall be derived from user-supplied samples only. The system shall not collect or analyze writing data from external sources.

#### Requirement Statements

* MVP-009: The MVP shall support creation of an author profile from user-supplied writing samples.
* MVP-010: The MVP shall preserve profile characteristics without reproducing prior authored text verbatim.

---

### 3.6 Project Memory

- Store project decisions, objectives, and contextual information.
- Retrieve project memory across sessions.
- Update project memory as the project evolves.

**Limitation:** Project memory shall be populated through user input and system-derived context. The system shall not infer memory elements without user awareness.

#### Requirement Statements

* MVP-011: The MVP shall support storage and retrieval of project memory across sessions.
* MVP-012: The MVP shall allow the user to update project memory as the project evolves.

---

### 3.7 Context Assembly

- Assemble project context from memory, knowledge, and profile data.
- Support context assembly for drafting activities.
- Present assembled context to the user.

**Limitation:** Context assembly is limited to available project data. The system shall not incorporate external information without user direction.

#### Requirement Statements

* MVP-013: The MVP shall assemble task-specific context from available project data.
* MVP-014: The MVP shall present assembled context to the user for review.

---

### 3.8 Draft Generation

- Generate draft content for research sections within Chapters 1–3.
- Ground drafts in available project knowledge and evidence.
- Preserve author writing characteristics in generated drafts.

**Limitation:** Draft generation is limited to Chapters 1–3 of the academic writing process (Introduction, Literature Review, Methodology). Full-chapter and multi-chapter generation is not in MVP scope.

#### Requirement Statements

* MVP-015: The MVP shall support draft generation for sections within Chapters 1–3.
* MVP-016: The MVP shall ground generated drafts in available project evidence.
* MVP-017: The MVP shall apply author profile characteristics to generated drafts.

---

### 3.9 Draft Review

- Review generated drafts with evidence references.
- Request revisions and refinements.
- Approve final draft versions.

**Limitation:** Review is limited to drafts generated within the MVP. External document review is not supported.

#### Requirement Statements

* MVP-018: The MVP shall support user review of generated drafts.
* MVP-019: The MVP shall support iterative refinement of drafts based on user input.
* MVP-020: The MVP shall support user approval of final draft versions.

---

### 3.10 Version Management

- Preserve draft version history.
- Support access to previous draft versions.
- Track changes across revision cycles.

**Limitation:** Version management is limited to draft content. Full project state versioning is not in MVP scope.

#### Requirement Statements

* MVP-021: The MVP shall preserve version history for generated and revised draft content.
* MVP-022: The MVP shall support user access to previous draft versions.

---

### 3.11 Agent Workspace

**Added by ADR-009**, following a product clarification recorded in `docs/journal/2026-09-04.md`. Appended after §3.10 to preserve the numbering of the original ten MVP capability areas and their MVP-001 to MVP-028 requirement statements.

- Create the user's Agent — a permanent workspace wrapping one research project, built from the supplied topic, reference documents, and writing-style samples.
- Enforce exactly one Agent per user in the MVP.

**Limitation:** Additional Agents per user (e.g., for a second thesis topic) are explicitly out of MVP scope — see §4. A future paid/premium tier may lift this limit; the MVP does not build toward it beyond keeping the constraint additive (ADR-009).

#### Requirement Statements

* MVP-029: The MVP shall support creation of exactly one Agent per authenticated user, created together with its one, permanent research project.
* MVP-030: The MVP shall not support creating, transferring, or reassigning a second Agent, or repointing an Agent's Project, for any user.

---

## 4. Out-of-Scope Capabilities

The following capabilities are explicitly excluded from the MVP scope. They are documented here to prevent scope creep and to inform the Future Roadmap (Chapter 11).

| Capability | Rationale for Exclusion |
|------------|------------------------|
| Multi-user collaboration | MVP supports a single user. Collaboration introduces authentication, authorization, and concurrency complexity beyond MVP scope. |
| Full-chapter generation | MVP supports section-level generation within Chapters 1–3. Full chapter generation requires additional context and coordination capabilities. |
| Institutional deployment | MVP assumes personal use. Institutional deployment requires multi-tenant architecture, compliance, and administration features. |
| External knowledge source integration | MVP relies on user-supplied materials. External integration introduces provider dependencies and licensing considerations. |
| Advanced analytics and reporting | MVP focuses on core research workflow. Analytics capabilities are deferred to improve MVP delivery focus. |
| Supervisor or reviewer collaboration | MVP supports the primary author only. Reviewer workflows introduce feedback management and access control complexity. |
| Cross-project knowledge management | MVP manages knowledge within a single project. Cross-project capabilities are deferred. |
| Mobile or offline access | MVP assumes a desktop or server environment with network connectivity for AI service interaction. |
| Full text export and formatting | MVP supports draft content retrieval. Advanced export to specific academic formats is deferred. |
| Automated citation management | MVP supports citation awareness in drafts. Full citation management is deferred. |
| Multiple Agents per user | MVP supports exactly one Agent (permanent workspace) per user. Additional Agents are a future, monetization-gated capability (ADR-009). |

#### Requirement Statements

* MVP-023: Capabilities listed as out-of-scope in this chapter shall not be implemented during the MVP phase.
* MVP-024: Deferred capabilities shall be documented in the Future Roadmap (Chapter 11) for subsequent release planning.

---

## 5. MVP Target Workflow

The MVP target workflow encompasses the following complete cycle:

1. Create a research project.
2. Upload source materials.
3. Build project knowledge.
4. Create an author profile.
5. Build project memory.
6. Assemble context.
7. Generate a draft section (Chapters 1–3).
8. Review and refine the draft.
9. Approve the final version.
10. Save and resume across sessions.

The MVP is considered functionally complete when this cycle can be executed for a representative academic research project.

#### Requirement Statements

* MVP-025: The MVP shall support the complete target workflow from project creation through draft approval.
* MVP-026: The MVP shall support workflow continuity across multiple sessions.

---

## 6. MVP Quality Targets

The MVP shall meet the following quality targets.

| Attribute | Target | Rationale |
|-----------|--------|-----------|
| Correctness | All MVP functional requirements are testable and verified. | Correctness is prioritized over feature breadth per MVP philosophy. |
| Reliability | Documented deterministic behavior for equivalent inputs. | Research workflows require predictable system behavior. |
| Maintainability | All major components are independently testable per NFR-029. | Long-term platform evolution depends on maintainable architecture. |
| Extensibility | MVP capabilities are designed for future extension. | The MVP is the foundation for the full product roadmap. |
| User control | All generated content is reviewable and approvable. | Human oversight is a core product principle. |

---

## 7. MVP Out-of-Scope Summary

| Area | In Scope | Out of Scope |
|------|----------|--------------|
| Users | Single user | Multi-user, collaboration, supervisor roles |
| Chapters | Sections within Chapters 1–3 | Full chapters, Chapters 4–5, complete thesis |
| Documents | Text-based academic documents | Non-text formats beyond text extraction |
| Knowledge | User-supplied materials | External databases, live web sources |
| Author profile | Stylistic characteristics from samples | Cross-project profile sharing, automatic collection |
| Version management | Draft version history | Full project state versioning |
| Deployment | Personal/development environment | Institutional, cloud, or multi-tenant deployment |
| Workspace | Exactly one Agent per user, wrapping one permanent project (ADR-009) | Multiple Agents per user (monetization-gated, deferred) |

#### Requirement Statements

* MVP-027: The MVP scope boundaries defined in this chapter shall govern all MVP implementation decisions.
* MVP-028: Scope changes shall require documented justification and approval before implementation.

---

## 8. Relationship to Previous Chapters

This chapter defines the scope boundaries for the capabilities described in earlier SRS chapters.

- **Chapter 2 (Product Overview):** The MVP scope implements a subset of the product capabilities described in Chapter 2, Section 7 (Product Scope).
- **Chapter 4 (Functional Requirements):** The MVP scope selects a subset of functional areas for implementation, with the remainder deferred to the Future Roadmap.
- **Chapter 5 (Non-Functional Requirements):** The MVP quality targets in this chapter are derived from selected NFRs applicable to the first release.
- **Chapter 6 (AI Requirements):** The MVP implements the core AI capabilities required for evidence-grounded drafting within Chapters 1–3, deferring advanced intelligence features.
- **Chapter 7 (Data Requirements):** The MVP implements the core data domains necessary to support the in-scope workflow, deferring advanced data management capabilities.
- **Chapter 8 (User Workflows):** The MVP implements the complete primary workflow cycle for single-user, single-project scenarios.
- **Chapter 9 (API Requirements):** The MVP implements the API domains required to support the in-scope workflow capabilities.

---

## 9. Requirement Traceability

The MVP scope requirements defined in this chapter are traceable to the following sources:

- **Vision Document v1.0** — Sections 9 (Target Users), 14 (Success Criteria)
- **SRS Chapter 1** — Section 8 (Assumptions), Section 9 (Constraints)
- **SRS Chapter 2** — Section 7 (Product Scope)
- **SRS Chapter 4** — All functional domains
- **SRS Chapter 5** — Relevant NFRs for MVP quality targets
- **SRS Chapter 6** — Core AI requirements implementable within MVP constraints
- **SRS Chapter 8** — Workflow stages that the MVP target workflow implements
- **SRS Chapter 9** — API domains required to support in-scope workflow capabilities
- **SRS Chapter 11** — Future Roadmap for out-of-scope capabilities
- **ADR-001** — Separation of scope definition from implementation decisions
- **ADR-009** — Agent workspace introduction and the one-Agent-per-user MVP constraint (§3.11)

---

## 10. Summary

Chapter 10, as corrected by ADR-009, defines the MVP scope for ScholarOS. It establishes eleven in-scope capability areas (project management, document ingestion, knowledge extraction, knowledge retrieval, author profile creation, project memory, context assembly, draft generation, draft review, version management, and the Agent workspace) and explicitly documents excluded capabilities with rationale, including multiple Agents per user.

The chapter defines the MVP target workflow, quality targets, and scope boundaries that govern the first release. All decisions in this chapter are based on the approved product philosophy of correctness over completeness and the goal of establishing an extensible foundation for future capabilities.

Capabilities deferred from the MVP are documented in Chapter 11 (Future Roadmap).
