# AI Roles and Responsibilities

**Document:** 08_AI_Roles_and_Responsibilities.md

**Governance Framework:** Engineering Governance Framework v1.0

**Status:** Active

**Date:** 2026-07-29

**Authority:** Eighth, after the Review Checklist (07).

---

## 1. Purpose

This document defines the roles that AI Software Engineers may assume within the ScholarOS project, the responsibilities of each role, and the protocols for multi-AI collaboration.

ScholarOS may be developed by multiple AI assistants operating concurrently or sequentially. Clear role definitions and handoff protocols are required to maintain consistency and prevent conflicting work.

---

## 2. Role Definitions

### 2.1 Lead AI Software Engineer

**Scope:** The primary engineer responsible for a task or session.

**Responsibilities:**

- Understand the full context of the task before beginning work.
- Plan and orchestrate the implementation.
- Delegate subtasks to supporting AI agents when appropriate.
- Ensure all work conforms to the governance framework.
- Produce the Engineering Report.
- Update the Journal.

**Authority:** Full change authority as defined in 02_AI_Engineering_Contract.md.

### 2.2 Supporting AI Engineer

**Scope:** An AI agent assigned to assist with a specific subtask.

**Responsibilities:**

- Complete the assigned subtask within the boundaries defined by the Lead.
- Report findings and results back to the Lead.
- Do not modify files outside the assigned scope without consulting the Lead.

**Limitations:**

- Must not make independent architectural decisions.
- Must not modify governance documents without Lead approval.
- Must report all changes to the Lead for review.

### 2.3 AI Reviewer

**Scope:** An AI agent assigned to review completed work.

**Responsibilities:**

- Review changes against the criteria in 07_Review_Checklist.md.
- Identify inconsistencies, quality issues, and governance violations.
- Report findings to the Lead.

**Limitations:**

- Does not make changes directly.
- Does not have change authority.

### 2.4 AI Researcher

**Scope:** An AI agent assigned to gather information.

**Responsibilities:**

- Search documentation, code, or external resources.
- Summarize findings in a structured format.
- Report results without making changes.

**Limitations:**

- Does not modify any files.
- Does not make decisions.

---

## 3. Multi-AI Workflow

When multiple AI agents collaborate on a task, the following workflow applies:

### 3.1 Initiation

1. The Lead AI Software Engineer reviews the task and plans the work.
2. The Lead identifies subtasks that can be delegated.
3. The Lead assigns each subtask to a Supporting AI Engineer with clear boundaries.

### 3.2 Execution

1. Each Supporting AI Engineer completes their assigned subtask.
2. The Supporting Engineer reports results back to the Lead.
3. The Lead reviews the results and integrates them into the overall work.

### 3.3 Review

1. The Lead may assign an AI Reviewer to review the completed work.
2. The AI Reviewer reports findings to the Lead.
3. The Lead addresses any issues identified.

### 3.4 Completion

1. The Lead ensures all work is consistent and complete.
2. The Lead produces the Engineering Report.
3. The Lead updates the Journal.

---

## 4. Handoff Protocols

### 4.1 Context Preservation

When handing off work between AI agents:

- The handing-off agent shall provide a complete context summary.
- The context summary shall include: task state, decisions made, files affected, and remaining work.
- The receiving agent shall read the context summary before proceeding.

### 4.2 Session Transfer

When a session ends and another session will continue the work:

- The Journal shall be updated with the current state.
- The Engineering Report shall document incomplete work.
- Outstanding decisions and unresolved issues shall be documented.

### 4.3 Conflict Resolution

If two AI agents produce conflicting work:

1. The Lead determines which approach is correct.
2. The incorrect work is reverted.
3. The root cause of the conflict is documented in the Journal.

---

## 5. Tool Usage Guidelines

### 5.1 Permitted Tools

AI agents may use any tool available within their environment, subject to the following constraints:

- **Read tools** (read files, search, list directories): Always permitted.
- **Write tools** (create, modify files): Permitted within the scope assigned by the Lead.
- **Execute tools** (run commands, tests): Permitted when necessary for the task.
- **Research tools** (web search, docs search): Permitted for gathering information.

### 5.2 Prohibited Tool Usage

- No tool shall be used to bypass governance constraints.
- No tool shall be used to introduce undocumented functionality.
- No tool shall be used to modify protected files without documented justification.

---

## 6. Relationship to Other Governance Documents

| Document | Relationship |
|----------|-------------|
| 02_AI_Engineering_Contract.md | Defines the base responsibilities for all AI engineers. |
| 07_Review_Checklist.md | AI Reviewers use this checklist for reviews. |
| 10_Prompting_Guidelines.md | Defines how to prompt AI agents effectively. |

---

## 7. References

- 02_AI_Engineering_Contract.md
- 07_Review_Checklist.md
- 10_Prompting_Guidelines.md
