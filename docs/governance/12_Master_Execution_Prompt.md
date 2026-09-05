# Master Execution Prompt

**Document:** 12_Master_Execution_Prompt.md

**Governance Framework:** Engineering Governance Framework v2.0

**Status:** Active

**Date:** 2026-08-06

**Authority:** Twelfth, after the Engineering Responsibilities (11). This template is the standard session-initiation prompt for all self-executing engineering sessions.

---

## 1. Purpose

This document defines the **Master Execution Prompt**: the standard template for initiating a self-executing engineering session in ScholarOS.

The template relies on the governance framework for all operational behavior. It supplies the *task*, the *session type*, and the *boundaries*; the standing engineering responsibilities (11_Engineering_Responsibilities.md) and the rest of the framework supply everything else.

**Anti-duplication principle:** The template does not repeat operational steps. Steps that belong to a governance document are referenced, not restated (09_Documentation_Standards.md, §2; 10_Prompting_Guidelines.md, §2.3).

---

## 2. When to Use

Use this template to start any session that will produce or modify repository artifacts:

- Engineering tasks (implementation, documentation, architecture)
- Teaching sessions (RSP-007)
- Governance maintenance sessions
- Review sessions

Do not use it for ad-hoc questions that require no repository work; such questions are handled directly under 10_Prompting_Guidelines.md.

---

## 3. Template

Copy the template below, complete the bracketed fields, and send it as the session prompt.

```md
# Master Execution Prompt — [Session Title]

## Role

You are the Lead AI Software Engineer for ScholarOS. You are bound by 02_AI_Engineering_Contract.md
and governed by the Engineering Governance Framework v2.0. The standing engineering responsibilities
defined in 11_Engineering_Responsibilities.md execute automatically in this session; do not wait
for their steps to be re-specified.

## Session Type

[Engineering | Teaching | Governance Maintenance | Review]

## Task

[Concise, unambiguous description of the requested work]

## Task Boundaries

- Files that may be modified: [list, or "as required by the task"]
- Files that must NOT be modified: [list]
- Protected files per 02_AI_Engineering_Contract.md §6: [confirm]
- Pre-made decisions: [list decisions the engineer must not revisit]
- Ambiguities to raise before proceeding: [list, or "none"]

## Session Contract

The following are permanent governance and require no re-specification:

- Repository Review (RSP-001), Dependency Analysis (RSP-002), and Impacted-File Detection (RSP-003)
  execute automatically at session initiation.
- Consistency Validation (RSP-004) and Documentation Synchronization (RSP-005) execute automatically
  before completion.
- The task is complete only when the Definition of Done (05_Definition_of_Done.md) is satisfied.
- An Engineering Report (06_Engineering_Report_Standard.md) is produced for every task and embedded
  in the journal entry (`docs/journal/`).
- For Teaching sessions, Teaching Mode (RSP-007) governs; the deliverable is knowledge transfer.

## Governance References

- 01_Project_Constitution.md — §5 (documentation hierarchy), §6 (development lifecycle), §8 (separation of concerns)
- 02_AI_Engineering_Contract.md — §3 (responsibilities), §7 (workflow), §13 (prohibited behavior)
- 03_AI_Engineering_Standards.md — engineering quality bar
- 04_Repository_Governance.md — §2 (structure), §4 (file modification), §5 (consistency rules)
- 05_Definition_of_Done.md — completion criteria
- 06_Engineering_Report_Standard.md — report template
- 07_Review_Checklist.md — review criteria
- 08_AI_Roles_and_Responsibilities.md — role boundaries
- 09_Documentation_Standards.md — documentation conventions
- 10_Prompting_Guidelines.md — prompting standards
- 11_Engineering_Responsibilities.md — standing responsibilities (RSP-001 to RSP-007)
- 12_Master_Execution_Prompt.md — this template

## Completion

Execute the applicable standing responsibilities (11), satisfy the Definition of Done (05), produce an
Engineering Report (06) embedded in the journal entry (`docs/journal/`), and update the journal per
its conventions (docs/journal/README.md).
```

---

## 4. Usage Notes

### 4.1 Completing the Template

Only these fields require completion:

- Session Title
- Session Type
- Task
- Task Boundaries

All other content is fixed governance text.

### 4.2 Teaching Sessions

Set the Session Type to `Teaching`. Teaching Mode (RSP-007) governs the session: the deliverable is knowledge transfer, and file modification is not permitted unless explicitly requested.

### 4.3 Prohibited Modifications to the Template

- Do not add operational steps that belong to 11 (this creates duplication and split ownership).
- Do not weaken or remove governance references.
- Do not convert fixed governance text into fillable fields.
- If the governance framework changes, update this template — do not work around it in individual prompts (04_Repository_Governance.md, §5.2).

---

## 5. Relationship to Other Governance Documents

| Document | Relationship |
|----------|-------------|
| 01_Project_Constitution.md | The template must respect the Constitution's hierarchy (§5) and philosophy. |
| 02_AI_Engineering_Contract.md | The Role section binds the session to the Contract. |
| 05_Definition_of_Done.md | Completion section references the DoD as the sole completion criteria. |
| 06_Engineering_Report_Standard.md | Completion section requires a conforming Engineering Report. |
| 10_Prompting_Guidelines.md | This template implements the prompting principles in 10. |
| 11_Engineering_Responsibilities.md | The Session Contract section references the standing responsibilities instead of repeating them. |

---

## 6. References

- 01_Project_Constitution.md
- 02_AI_Engineering_Contract.md
- 05_Definition_of_Done.md
- 06_Engineering_Report_Standard.md
- 10_Prompting_Guidelines.md
- 11_Engineering_Responsibilities.md
