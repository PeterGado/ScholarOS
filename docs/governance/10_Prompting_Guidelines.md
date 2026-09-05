# Prompting Guidelines

**Document:** 10_Prompting_Guidelines.md

**Governance Framework:** Engineering Governance Framework v2.0

**Status:** Active

**Date:** 2026-07-29

**Authority:** Tenth, after Documentation Standards (09).

---

## 1. Purpose

This document defines the prompt engineering standards for interacting with AI Software Engineers within the ScholarOS project.

While the other governance documents define *what* AI engineers must do, this document defines *how to instruct them effectively*. It is intended for both human contributors and AI agents that need to delegate work to other AI agents.

Self-executing sessions are initiated with the Master Execution Prompt (12_Master_Execution_Prompt.md), which implements the principles in this document.

---

## 2. Prompt Engineering Principles

### 2.1 Context First

Before asking an AI to perform work, provide sufficient context:

- What is the task?
- Why is it necessary?
- Which requirements or governance documents govern it?
- What is the current state of the related work?

An AI provided with insufficient context will produce lower-quality results.

### 2.2 Clear Instructions

- State the task explicitly and unambiguously.
- Specify the expected output format.
- Define success criteria.
- Specify constraints and boundaries.

### 2.3 Reference Governance

When instructing an AI to perform engineering work:

- Reference the relevant governance documents.
- Reference the standing engineering responsibilities (11_Engineering_Responsibilities.md) instead of re-specifying their steps. In self-executing sessions, RSP-001 through RSP-006 execute automatically; the prompt supplies the task and boundaries only.
- Boot self-executing sessions with the Master Execution Prompt (12_Master_Execution_Prompt.md).
- For knowledge-transfer work, set the session type to Teaching (RSP-007).
- Reference the Definition of Done (05) as the completion criteria.
- Reference the Engineering Report requirement (06).

### 2.4 Boundary Definition

- Clearly define what the AI should and should not do.
- Specify which files may be modified.
- Specify which decisions are pre-made and which are left to the AI.
- Specify which documents must not be contradicted.

---

## 3. Prompt Structure

Effective engineering prompts should follow this structure:

```md
## Context

[Project context, current state, relevant background]

## Task

[Clear, unambiguous description of what needs to be done]

## Constraints

[Boundaries, pre-made decisions, files that must not be modified]

## References

[Relevant governance documents, requirements, ADRs]

## Success Criteria

[How the result will be evaluated]

## Output Requirements

[Expected format, deliverables, report requirements]
```

---

## 4. Instruction Templates

### 4.1 Implementation Task

```md
## Context
[Project and module context]

## Task
Implement [feature] as defined in [requirement reference].

## Constraints
- Must conform to architecture in [architecture document].
- Must follow 03_AI_Engineering_Standards.md.
- Do not modify [specific files].

## References
- [requirement reference]
- [architecture document]
- [ADR reference if applicable]

## Success Criteria
- All tests pass.
- DoD criteria (05) are satisfied.
- Engineering Report (06) is produced.
```

### 4.2 Documentation Task

```md
## Context
[Why this documentation is needed]

## Task
Create/update [document] covering [topics].

## Constraints
- Must follow 09_Documentation_Standards.md.
- Must cross-reference existing documents.
- Must not duplicate information in [related document].

## References
- [related documents to reference]
- [governance documents governing format]

## Success Criteria
- Cross-references are valid.
- Consistent with existing documentation.
- No contradictions with approved documents.
```

### 4.3 Review Task

```md
## Context
[What was implemented and why]

## Task
Review the changes against 07_Review_Checklist.md.

## Constraints
- Do not modify any files.
- Report all findings.

## References
- 07_Review_Checklist.md
- 03_AI_Engineering_Standards.md
- 05_Definition_of_Done.md

## Output Requirements
- List of issues found.
- Severity assessment for each issue.
- Recommendations for resolution.
```

### 4.4 Research Task

```md
## Context
[What information is needed and why]

## Task
Find information about [topic].

## Sources
[Where to look: documentation, web, code]

## Output Requirements
- Summary of findings.
- Source references.
- Relevance assessment.
```

### 4.5 Self-Executing Session (Master Execution Prompt)

The master template for initiating self-executing engineering sessions is defined in **12_Master_Execution_Prompt.md**.

Use it for any session that will produce or modify repository artifacts. Complete only the Session Title, Session Type, Task, and Task Boundaries fields; all other content is fixed governance text.

The template relies on the governance framework for all operational behavior. Do not append operational steps to it: operational steps belong to the standing responsibilities (11_Engineering_Responsibilities.md) and execute automatically. Appending them creates duplication and split ownership.

---

## 5. Multi-AI Prompting

When one AI agent prompts another AI agent:

### 5.1 Handoff Prompts

Include all context the receiving agent needs to continue work without re-reading the entire session:

- Current task state.
- Decisions made so far.
- Files affected.
- Remaining work.
- Governance documents that apply.

### 5.2 Delegation Prompts

When delegating a subtask:

- Define clear boundaries for the subtask.
- Specify how the result should be reported.
- Specify any coordination requirements with other agents.

---

## 6. Prohibited Prompting Practices

- Do not ask an AI to violate the governance framework.
- Do not ask an AI to bypass the Engineering Workflow.
- Do not ask an AI to modify protected files without documented justification.
- Do not ask an AI to introduce undocumented functionality.
- Do not provide ambiguous or contradictory instructions.

---

## 7. Prompt Quality Checklist

Before submitting a prompt to an AI engineer, verify:

- [ ] Context is sufficient for the AI to understand the task.
- [ ] Instructions are clear and unambiguous.
- [ ] Constraints and boundaries are defined.
- [ ] Governance documents are referenced.
- [ ] Success criteria are defined.
- [ ] Expected output format is specified.
- [ ] The prompt does not violate any governance rules.

---

## 8. Relationship to Other Governance Documents

| Document | Relationship |
|----------|-------------|
| 01_Project_Constitution.md | Prompts must not violate the Constitution's philosophy or principles. |
| 02_AI_Engineering_Contract.md | Prompts shall reference the Contract and its workflow. |
| 05_Definition_of_Done.md | Prompts should reference the DoD as success criteria. |
| 06_Engineering_Report_Standard.md | Prompts should require compliance with the report standard. |
| 07_Review_Checklist.md | Review prompts shall reference the checklist. |
| 08_AI_Roles_and_Responsibilities.md | Defines how to delegate work to different AI roles. |
| 11_Engineering_Responsibilities.md | Prompts reference the standing responsibilities instead of repeating their steps. |
| 12_Master_Execution_Prompt.md | The master template implements these prompting principles. |

---

## 9. References

- 01_Project_Constitution.md
- 02_AI_Engineering_Contract.md
- 05_Definition_of_Done.md
- 06_Engineering_Report_Standard.md
- 07_Review_Checklist.md
- 08_AI_Roles_and_Responsibilities.md
- 11_Engineering_Responsibilities.md
- 12_Master_Execution_Prompt.md
