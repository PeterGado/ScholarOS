# Engineering Responsibilities

**Document:** 11_Engineering_Responsibilities.md

**Governance Framework:** Engineering Governance Framework v2.0

**Status:** Active

**Date:** 2026-08-06

**Authority:** Eleventh, after the Prompting Guidelines (10). Converts recurring engineering behaviors into permanent governance responsibilities that execute automatically in self-executing engineering sessions.

---

## 1. Purpose

This document converts the recurring engineering behaviors that were previously re-specified in every session prompt into **permanent governance responsibilities** that execute automatically within self-executing engineering sessions.

The behaviors formalized here are:

* Repository review
* Dependency analysis
* Consistency validation
* Impacted-file detection
* Documentation synchronization
* Engineering reporting
* Teaching mode

Previously, prompts had to remind the AI engineer of each behavior and restate its steps (see the former practice described in 10_Prompting_Guidelines.md, §2.3). Under this framework, a prompt supplies the *task* and the *boundaries*; the *behavior* is defined once in this document and executes automatically.

**Single ownership:** Each responsibility is defined exactly once in this document. Other governance documents, templates, and prompts reference these definitions rather than repeating them (per 09_Documentation_Standards.md, §2).

---

## 2. Self-Executing Engineering Sessions

### 2.1 Definition

A **self-executing engineering session** is a session initiated with the Master Execution Prompt (12_Master_Execution_Prompt.md) in which the standing engineering responsibilities defined in this document execute automatically according to their triggers, without being re-specified in the prompt.

### 2.2 Principle: Governance, Not Prompts

Operational steps are defined once in the governance framework and execute automatically. A prompt shall:

* State the **task**.
* Define the **boundaries** (files, pre-made decisions, constraints).
* Reference the **governance documents** that govern the behavior.

A prompt shall never re-specify the operational steps of a standing responsibility (10_Prompting_Guidelines.md, §6).

### 2.3 Session Lifecycle

Every self-executing session follows this lifecycle:

```md
Initiation (Master Execution Prompt, 12)
    │
    ▼
Automatic initiation responsibilities
    ├── RSP-001 Repository Review
    ├── RSP-002 Dependency Analysis
    └── RSP-003 Impacted-File Detection
    │
    ▼
Task work (engineering or teaching, per the session type)
    │
    ▼
Automatic completion responsibilities
    ├── RSP-004 Consistency Validation
    ├── RSP-005 Documentation Synchronization
    ├── RSP-006 Engineering Reporting
    └── Journal update (05_Definition_of_Done.md, §2.10)
```

Teaching sessions (RSP-007) replace task work with knowledge-transfer activity.

### 2.4 Responsibility Triggers

| Trigger Phase | Responsibilities |
|  |  |
| Session initiation (automatic) | RSP-001, RSP-002, RSP-003 |
| During work | As applicable to the task |
| Session completion (automatic) | RSP-004, RSP-005, RSP-006, journal update (05 §2.10) |
| Session type = Teaching | RSP-007 |

---

## 3. Standing Engineering Responsibilities

### 3.1 RSP-001 — Repository Review

| Field | Definition |
|  |  |
| **Identifier** | RSP-001 |
| **Name** | Repository Review |
| **Definition** | The standing obligation to review the repository before any work begins: the governance framework, Vision, SRS, ADRs, architecture, and current project state. |
| **Trigger** | Automatically at session initiation. |
| **Procedure** | 1. Read the governance documents (01–12) in the prescribed order (docs/READme.md, Phase 0). 2. Read the Vision, the relevant SRS chapters, ADRs, and architecture documents. 3. Read Project Status, Timeline, journal, and the documentation index (docs/READme.md). 4. Confirm the current repository state before planning the work. |
| **Output** | Review notes recorded in the Engineering Report (06_Engineering_Report_Standard.md, §2.3 Files Reviewed). |
| **Authority** | 02_AI_Engineering_Contract.md, §4 (Repository Authority); 04_Repository_Governance.md. |

| **Boundary Note** | Repository-hardening tasks may update governance, documentation, and traceability artifacts only. They must not create future milestone artifacts such as database design documents, API specifications, implementation code, tests, deployment plans, or infrastructure documentation. |

### 3.2 RSP-002 — Dependency Analysis

| Field | Definition |
|  |  |
| **Identifier** | RSP-002 |
| **Name** | Dependency Analysis |
| **Definition** | The standing obligation to determine, before any modification, which repository elements depend on the planned change: directly affected files, indirectly affected files, and potential future impacts. |
| **Trigger** | Automatically at session initiation, after RSP-001. |
| **Procedure** | 1. Identify the files the task will touch. 2. Identify files that reference them and files they reference (04_Repository_Governance.md, §4.2). 3. Identify future impacts (e.g., downstream milestones, planned ADRs, roadmap items). 4. Include all consistency-required files in the implementation plan. |
| **Output** | Dependency map recorded in the Engineering Report (06_Engineering_Report_Standard.md, §2.2 Pre-Implementation Analysis and §2.6 Repository Impact Assessment). |
| **Authority** | 02_AI_Engineering_Contract.md, §7 (Engineering Workflow); 04_Repository_Governance.md, §4.2. |

### 3.3 RSP-003 — Impacted-File Detection

| Field | Definition |
|  |  |
| **Identifier** | RSP-003 |
| **Name** | Impacted-File Detection |
| **Definition** | The standing obligation to detect every file that must be updated to keep the repository internally consistent when a change occurs — cross-references, indexes, status files, and related documentation. |
| **Trigger** | Automatically at session initiation, after RSP-002; refined during work as the change scope becomes concrete. |
| **Procedure** | 1. From the dependency analysis (RSP-002), compile the affected-file list. 2. Include the repository navigation and status artifacts: documentation index (docs/READme.md), Project Status, Timeline, journal index (docs/journal/README.md), and module README files. 3. Verify each candidate against 04_Repository_Governance.md, §4.2 before including it. |
| **Output** | Affected-file list consumed by Documentation Synchronization (RSP-005) and recorded in the Engineering Report (06 §2.5 Files Modified). |
| **Authority** | 04_Repository_Governance.md, §4.2 (Cross-Reference Updates). |

### 3.4 RSP-004 — Consistency Validation

| Field | Definition |
|  |  |
| **Identifier** | RSP-004 |
| **Name** | Consistency Validation |
| **Definition** | The standing obligation to validate repository consistency before completion: cross-references are valid, terminology is consistent, naming conventions are followed, no contradictions exist, and no placeholders remain. |
| **Trigger** | Automatically at session completion, before the Engineering Report is finalized. |
| **Procedure** | 1. Validate all cross-references to and from modified files (09_Documentation_Standards.md, §4.2). 2. Check terminology against established vocabulary. 3. Check naming conventions (04_Repository_Governance.md, §3). 4. Check for contradictions with the Constitution, Vision, SRS, and other governance documents. 5. Scan for unresolved placeholders (TBD, TODO). |
| **Output** | Validation results recorded in the Engineering Report (06_Engineering_Report_Standard.md, §2.12 Validation Results). |
| **Authority** | 04_Repository_Governance.md, §5 (Repository Consistency Rules); 07_Review_Checklist.md; 09_Documentation_Standards.md, §4.2. |

### 3.5 RSP-005 — Documentation Synchronization

| Field | Definition |
|  |  |
| **Identifier** | RSP-005 |
| **Name** | Documentation Synchronization |
| **Definition** | The standing obligation to keep repository documentation synchronized with every change: the documentation index, Project Status, Timeline, journal, and module README files. |
| **Trigger** | Automatically at session completion, after consistency validation (RSP-004). |
| **Procedure** | 1. Update the affected files identified by RSP-003. 2. Update only files genuinely affected (02_AI_Engineering_Contract.md, §7). 3. Record each synchronization update and its reason in the Engineering Report (06 §2.7 Repository Synchronization). |
| **Output** | Synchronized repository documentation; synchronization explanation in the Engineering Report (06 §2.7). |
| **Authority** | 04_Repository_Governance.md, §5 (Repository Consistency Rules); 02_AI_Engineering_Contract.md, §7 (Engineering Workflow). |

### 3.6 RSP-006 — Engineering Reporting

| Field | Definition |
|  |  |
| **Identifier** | RSP-006 |
| **Name** | Engineering Reporting |
| **Definition** | The standing obligation to produce an Engineering Report conforming to 06_Engineering_Report_Standard.md for every completed task. The report is part of the engineering deliverable; no task is complete without it. |
| **Trigger** | Automatically at session completion. |
| **Procedure** | 1. Produce the report using the template in 06_Engineering_Report_Standard.md, §3. 2. Embed the report in the journal entry ( `docs/journal/YYYY-MM-DD.md` ) per the journal conventions (docs/journal/README.md). 3. Include the outputs of RSP-001 through RSP-005 and RSP-007 where applicable. |
| **Output** | Engineering Report embedded in the journal entry. |
| **Authority** | 06_Engineering_Report_Standard.md; 05_Definition_of_Done.md, §2.9. |

### 3.7 RSP-007 — Teaching Mode

| Field | Definition |
|  |  |
| **Identifier** | RSP-007 |
| **Name** | Teaching Mode |
| **Definition** | The standing responsibility that governs sessions whose primary deliverable is **knowledge transfer** rather than repository modification. In Teaching Mode the engineer explains the governance framework, requirements, architecture, or code to a human or AI audience; onboards new AI engineers and contributors; and provides guided walkthroughs grounded in the actual repository. |
| **Trigger** | The session type is set to Teaching (12_Master_Execution_Prompt.md); or the user explicitly requests explanation, onboarding, or training. |
| **Procedure** | 1. Determine the audience (human contributor, AI engineer, or mixed) and its current knowledge level. 2. Select the authoritative materials to explain: governance documents, Vision, SRS, architecture, ADRs, or code. 3. Explain topics in order, grounding every statement in the governing document (single ownership; 09_Documentation_Standards.md, §2). 4. Walk through examples drawn from the actual repository. 5. Answer follow-up questions by pointing to the authoritative document, not by paraphrasing conflicting content. 6. Record the session in the journal ( `docs/journal/` ). |
| **Boundaries** | Default is explanation only — no file modification. Files may be modified only when the user explicitly requests a teaching artifact (e.g., onboarding notes, a tutorial document), and protected files (02_AI_Engineering_Contract.md, §6) shall never be modified. Teaching must not simplify to the point of inaccuracy and must not contradict the governance framework. |
| **Output** | A Teaching Report: audience, topics covered, materials used, open questions, and follow-ups. Embedded in the Engineering Report (06) where engineering work also occurred; standalone journal entry where no repository modification took place. |
| **Authority** | 08_AI_Roles_and_Responsibilities.md §2.5 (AI Teacher role); 10_Prompting_Guidelines.md (prompting standards). |

---

## 4. Responsibility Execution Rules

1. RSP-001, RSP-002, and RSP-003 execute automatically at session initiation; RSP-004, RSP-005, and RSP-006 execute automatically at session completion. Neither the prompt nor the user needs to request them.
2. A responsibility may be skipped only when it is genuinely not applicable to the task; the skip and its reason must be documented in the Engineering Report.
3. The responsibilities define *how* the session behaves; they never expand the scope of the task beyond the prompt's boundaries.
4. If executing a responsibility reveals a conflict with an approved document, the document hierarchy in 01_Project_Constitution.md, §5 governs, and the conflict shall be resolved per 04_Repository_Governance.md, §5.3.
5. The outputs of all responsibilities are recorded in the Engineering Report (RSP-006), which is the permanent record of the session's governance compliance.

---

## 5. Responsibility Summary

| ID | Responsibility | Trigger | Output | Authority |
|  |  |---------|  |  |
| RSP-001 | Repository Review | Session initiation | Review notes (report §2.3) | 02 §4; 04 |
| RSP-002 | Dependency Analysis | Session initiation | Dependency map (report §2.2, §2.6) | 02 §7; 04 §4.2 |
| RSP-003 | Impacted-File Detection | Session initiation | Affected-file list (report §2.5) | 04 §4.2 |
| RSP-004 | Consistency Validation | Session completion | Validation results (report §2.12) | 04 §5; 07; 09 §4.2 |
| RSP-005 | Documentation Synchronization | Session completion | Synchronized docs (report §2.7) | 04 §5; 02 §7 |
| RSP-006 | Engineering Reporting | Session completion | Engineering Report | 06; 05 §2.9 |
| RSP-007 | Teaching Mode | Session type = Teaching | Teaching Report | 08; 10 |

---

## 6. Relationship to Other Governance Documents

| Document | Relationship |
|  |  |
| 01_Project_Constitution.md | Responsibilities must never contradict the Constitution's philosophy or hierarchy (§5). |
| 02_AI_Engineering_Contract.md | The Contract's workflow (§7) executes these responsibilities; the Contract grants the change authority they operate under. |
| 04_Repository_Governance.md | Repository rules define the procedures RSP-002 through RSP-005 execute against. |
| 05_Definition_of_Done.md | DoD §2.11 verifies that the applicable responsibilities were executed. |
| 06_Engineering_Report_Standard.md | RSP-006 produces reports conforming to this standard. |
| 07_Review_Checklist.md | Review verifies that responsibility outputs (validation, synchronization, reporting) are complete. |
| 08_AI_Roles_and_Responsibilities.md | Role boundaries govern who executes each responsibility in multi-AI sessions. |
| 09_Documentation_Standards.md | Documentation conventions govern how responsibility outputs are recorded. |
| 10_Prompting_Guidelines.md | Prompts reference these responsibilities instead of repeating their steps. |
| 12_Master_Execution_Prompt.md | Self-executing sessions are booted with this template. |

---

## 7. References

* 01_Project_Constitution.md — §5 (Documentation Hierarchy)
* 02_AI_Engineering_Contract.md — §4 (Repository Authority), §6 (Protected Files), §7 (Engineering Workflow)
* 04_Repository_Governance.md — §3 (Naming Conventions), §4.2 (Cross-Reference Updates), §5 (Repository Consistency Rules)
* 05_Definition_of_Done.md — §2.9 (Engineering Report), §2.10 (Journal), §2.11 (Self-Executing Session Compliance)
* 06_Engineering_Report_Standard.md
* 07_Review_Checklist.md
* 08_AI_Roles_and_Responsibilities.md
* 09_Documentation_Standards.md — §2 (Documentation Principles), §4.2 (Cross-Reference Validation)
* 10_Prompting_Guidelines.md — §2.3 (Reference Governance), §6 (Prohibited Prompting Practices)
* 12_Master_Execution_Prompt.md
* ADR-001: Separation of Requirements, Architecture, and Implementation
