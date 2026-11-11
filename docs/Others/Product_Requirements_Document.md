# Product Requirements Document

**Document:** Product_Requirements_Document.md

**Status:** Active

**Date:** 2026-10-10

---

## 1. Purpose

This document synthesizes ScholarOS's product-level sources — the Vision Document, the SRS, the MVP scope, and the ADR record of how the product has evolved since those were written — into a single, concise product reference.

It is not an authoritative requirements source. Per the documentation hierarchy (`docs/READme.md`), the [Vision Document](vision/Vision.md) and the [SRS](srs/01_Introduction.md) remain authoritative; this PRD cross-references them rather than restating their content, and exists so a reader can understand the product in 10–15 minutes before going to the source documents for full detail.

---

## 2. What ScholarOS Is

ScholarOS is an intelligent research operating system for academic writing — **"Research. Reason. Write."** It combines document intelligence, project memory, structured reasoning, retrieval, and personalized author-style preservation into a unified workflow that supports a researcher from project conception through drafting Chapters 1–3.

Its governing philosophy, stated identically in the [Vision](vision/Vision.md#5-product-philosophy) and [SRS Chapter 2](srs/02_Product_Overview.md#4-product-philosophy), is:

> **Understand First. Write Second.**

The system builds understanding of the research topic, the user's source material, and the user's own writing style before it generates any content.

**ScholarOS is:** an intelligent research assistant, a document intelligence platform, a personalized academic writing assistant, a project memory system, a knowledge management platform, a structured research workflow engine (Vision §7).

**ScholarOS is not:** a generic chatbot, an AI humanizer, a plagiarism tool, a one-click thesis generator, or a detector-evasion system (Vision §8). This distinction matters because the live product's primary interface is now a chat surface (§7 below) — the product is conversational in *interaction model* without being a "generic chatbot" in the sense the Vision rejects, since every reply is grounded in the user's own uploaded sources rather than open-ended generation.

---

## 3. The Problem It Solves

Academic writing requires researchers to repeatedly search literature, compare findings, identify gaps, organize ideas, maintain cross-chapter consistency, follow institutional conventions, and preserve their own voice. General-purpose LLMs generate fluent text but have no persistent understanding of a project, don't remember prior decisions, and produce generic rather than context-aware writing — pushing the effort back onto the researcher to restructure and validate everything the model produces.

ScholarOS addresses this by placing understanding, retrieval, reasoning, and project memory *before* generation (Vision §4).

---

## 4. Target Users

| Scope | Users |
|---|---|
| MVP (primary) | Professional academic writers, undergraduate researchers, master's students, doctoral researchers, independent researchers |
| Future expansion | Universities, research institutes, academic supervisors, research consultancies, institutional research centers |

Source: [Vision §9](vision/Vision.md#9-target-users), [SRS Chapter 2 §6](srs/02_Product_Overview.md#6-target-users).

**Gap:** no formal user personas, journey maps, or user research artifacts exist anywhere in the repository. The target-user description above is a role list, not a researched persona set. Treat it as directional, not validated.

---

## 5. Core Product Principles

From [Vision §6](vision/Vision.md#6-core-principles):

1. **Research Before Writing** — no content is generated without first understanding the research domain.
2. **Evidence Before Opinion** — significant claims are grounded in retrieved research materials, not asserted.
3. **Preserve the Author** — the system learns stylistic characteristics (paragraph organization, rhythm, terminology, citation habits) without imitating or reproducing prior text.
4. **Project Memory** — the system remembers objectives, variables, decisions, and terminology so the researcher never re-explains project context.
5. **Structured Intelligence** — intelligence emerges from specialized modules (document understanding, extraction, planning, retrieval, context construction, writing, review, memory), not a single prompt.
6. **Human Oversight** — ScholarOS assists; the researcher remains responsible for reviewing, editing, validating, and approving all generated content.

---

## 6. Product Scope: MVP vs. Future

### 6.1 MVP Philosophy

Per [SRS Chapter 10 §2](srs/10_MVP_scope.md#2-mvp-philosophy): correctness over completeness, core workflow first, backend-first implementation, single-user focus, personal (non-institutional) research context, and an extensible foundation requiring no later redesign.

### 6.2 In-Scope Capability Areas (MVP)

The MVP defines eleven capability areas, each with its own `MVP-###` requirement statements in [SRS Chapter 10 §3](srs/10_MVP_scope.md#3-in-scope-capabilities):

| Area | Representative requirements |
|---|---|
| Project management | MVP-001, MVP-002 |
| Document ingestion | MVP-003, MVP-004 |
| Knowledge extraction | MVP-005, MVP-006 |
| Knowledge retrieval | MVP-007, MVP-008 |
| Author profile creation | MVP-009, MVP-010 |
| Project memory | MVP-011, MVP-012 |
| Context assembly | MVP-013, MVP-014 |
| Draft generation | MVP-015 – MVP-017 |
| Draft review | MVP-018 – MVP-020 |
| Version management | MVP-021, MVP-022 |
| Agent workspace (added by [ADR-009](adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md)) | MVP-029, MVP-030 — exactly one Agent per user, wrapping one permanent research project |

### 6.3 Out of Scope (MVP)

Multi-user collaboration, full-chapter generation, institutional deployment, external knowledge-source integration, advanced analytics, supervisor/reviewer collaboration, cross-project knowledge management, mobile/offline access, full export/formatting, automated citation management, and multiple Agents per user. Full rationale per exclusion: [SRS Chapter 10 §4](srs/10_MVP_scope.md#4-out-of-scope-capabilities).

### 6.4 Future Roadmap

[SRS Chapter 11](srs/11_Future_Roadmap.md) defines six post-MVP phases (Expanded Drafting, Advanced Knowledge Management, Collaborative Research, Extended Research Lifecycle, Institutional/Commercial Readiness, Advanced Intelligence), plus the long-term module concepts named in [Vision §13](vision/Vision.md#13-long-term-vision) (ThesisMind, LiteratureMind, MethodMind, CitationMind, JournalMind, ResearchMemory, SupervisorHub, KnowledgeGraph). These are directional and explicitly not committed delivery (SRS Ch.11 §7).

---

## 7. Where the Live Product Has Evolved Past the SRS

The SRS and Vision describe the product's *original* requirements. The live, deployed system has moved past several of them. The authoritative record of current state is [`docs/READme.md`](READme.md); the clearest and most significant divergence is:

### 7.1 The Chat/Memory Pivot (ADR-012)

The original MVP scope specified a formal `Draft → Draft Version → Review → Review Decision` pipeline (SRS Ch.10 §3.9–§3.10, MVP-018 through MVP-022): generated drafts as versioned artifacts passing through an explicit human approval gate. This pipeline was built, tested, and validated against the frozen Database Baseline — then removed entirely in September 2026 and replaced by a conversational model: the user writes by chatting with their Agent, replies generate asynchronously per message, and a `Memory Record` (automatic extraction from conversation content) carries forward persistent context that `Review Decision` used to carry. Evidence grounding is preserved through `Message Context Link` rather than `Draft Evidence Link`.

[ADR-012](adr/ADR-012_Chat_Memory_Model_Replaces_Draft_Review_Pipeline.md) records this retroactively: the product decision was made and shipped in an uncommitted working session (2026-09-16 – 2026-09-18) with no contemporaneous decision record, and the ADR closes that governance gap after the fact. The rationale: a conversational surface is a better fit for a single-researcher, iterative writing workflow than a formal versioned-approval pipeline borrowed from document-review processes. "Draft review," "draft version," and "formal approval gate" language elsewhere in the SRS and MVP scope should be read through this correction — the live product's writing surface is chat, not a review pipeline.

### 7.2 Other Material Evolutions Since the SRS

- **Authentication and multi-user access**: the SRS assumed single-user, personal deployment. [ADR-010](adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md) added a real authentication boundary; [ADR-011](adr/ADR-011_Self_Service_Registration_and_Multi_User_Access.md) then superseded the single-account exclusion with open self-service registration (`POST /auth/register`), plus Google Sign-In, password reset, email verification, and account linking — none of which the original SRS specifies, since it predates this direction.
- **Agent workspace model**: [ADR-009](adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md) introduced the Agent entity (one per user, wrapping the one permanent research project) as the organizing concept the frontend and backend are now both built around.
- **Database platform**: cut over to PostgreSQL (Neon) with Alembic-owned migrations and Row-Level Security enforced via a restricted application role — the SRS and original Database Baseline describe the data model, not this specific operational platform.
- **A full frontend exists and is deployed** (React/Vite SPA on Vercel, backend on Fly.io) — the SRS's "backend-first" assumption (§8.3 MVP Philosophy) reflects the project's starting point, not its current state.

See [`docs/READme.md`](READme.md) for the complete, current milestone-by-milestone status, and §10 below for a summary.

---

## 8. Functional Areas

[SRS Chapter 4](srs/04_Functional_Requirements.md) organizes system behavior into eleven functional domains: Project Setup and Lifecycle Management, Research Source Acquisition, Knowledge Management (parent domain, with Knowledge Extraction, Knowledge Structuring, and Knowledge Retrieval as subdomains), Author Profile and Writing Style Preservation, Project Memory and Continuity, Context Assembly, Drafting Support, Draft Refinement and Revision, Review/Validation/Human Oversight, Evidence Traceability and Source Grounding, and Versioning and Project Evolution.

**Gap:** Chapter 4, as currently written, is explicitly organizational — it defines these domains and their scope boundaries but has not yet decomposed them into individually numbered `FR-###` requirement statements (the chapter states it is "intentionally high-level" and that functional areas "shall later be decomposed into specific functional requirements with unique identifiers," which has not happened). The MVP's actual testable requirement statements live under the `MVP-###` identifiers cited in §6.2, and workflow-level requirements under `WR-###` in [SRS Chapter 8](srs/08_User_Workflows.md). There is no `FR-###` identifier series to cite in this repository today.

---

## 9. Success Criteria

**From [Vision §14](vision/Vision.md#14-success-criteria):** the first version is successful if it builds meaningful understanding from uploaded materials, maintains persistent project memory across Chapters 1–3, preserves the user's writing style via an Author Style Profile, generates coherent evidence-informed drafts for individual sections, and reduces repetitive writing effort while keeping the researcher in control.

**From [SRS Chapter 2 §12](srs/02_Product_Overview.md#12-success-criteria):** the MVP is successful if it lets a researcher create a project, upload materials, build an author profile, maintain project memory, generate evidence-informed drafts, preserve writing consistency across Chapters 1–3, and efficiently review/refine content.

**Gap:** both success-criteria statements are qualitative. No quantitative success metrics — adoption targets, latency thresholds, retention numbers, accuracy benchmarks — are specified anywhere in the Vision, SRS, or governance documentation. Any such metric would be an invention not grounded in the repository.

---

## 10. Current Implementation Status (Summary)

As of `docs/READme.md` v1.9.0 (2026-10-09): Milestones 1–7 (governance, vision, SRS, architecture, database baseline, backend implementation, authentication boundary) are complete. Backend Slice 2 (knowledge processing, hybrid retrieval) and Project Writing (Stages 1–8, now superseded in mechanism by the chat/memory model per §7.1) are complete and validated. The database runs on PostgreSQL/Neon with Alembic migrations and Row-Level Security. CI runs backend lint/type-check, pytest, frontend lint/typecheck/build/unit tests, and a partial Playwright e2e suite. A full React/Vite frontend is deployed to Vercel with the backend on Fly.io — covering landing, auth, onboarding, chat, documents, writing style, segments, memory, and settings.

**Known documentation gap** (stated directly in `docs/READme.md`): no journal entry exists after `docs/journal/2026-09-16.md`, so the Postgres/Neon cutover, the RLS rollout, the frontend's own build-out, and the chat/memory pivot all happened without contemporaneous journaling. `docs/READme.md` and ADR-012 correct the record after the fact; they do not reconstruct the missing day-by-day history.

For full detail, see [`docs/READme.md`](READme.md) and [`docs/Project_Status.md`](Project_Status.md).

---

## 11. References

- [Vision Document](vision/Vision.md)
- [SRS Chapter 2 — Product Overview](srs/02_Product_Overview.md)
- [SRS Chapter 3 — Overall System Description](srs/03_Overall_System_Description.md)
- [SRS Chapter 4 — Functional Requirements](srs/04_Functional_Requirements.md)
- [SRS Chapter 10 — MVP Scope](srs/10_MVP_scope.md)
- [SRS Chapter 11 — Future Roadmap](srs/11_Future_Roadmap.md)
- [ADR-009 — Agent and Project Domain Model Introduction](adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md)
- [ADR-010 — Authentication Boundary, Single-User Session Model](adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md)
- [ADR-011 — Self-Service Registration and Multi-User Access](adr/ADR-011_Self_Service_Registration_and_Multi_User_Access.md)
- [ADR-012 — Chat/Memory Model Replaces the Draft/Review Pipeline](adr/ADR-012_Chat_Memory_Model_Replaces_Draft_Review_Pipeline.md)
- [docs/READme.md](READme.md) — current project state and version
- [docs/Project_Status.md](Project_Status.md) — current phase, milestones, risks, next steps
