# Repository Governance

**Document:** 04_Repository_Governance.md

**Governance Framework:** Engineering Governance Framework v2.0

**Status:** Active

**Date:** 2026-07-29

**Authority:** Fourth, after the AI Engineering Standards (03).

---

## 1. Purpose

This document defines the rules governing the ScholarOS repository structure, naming conventions, file modification policies, and consistency requirements.

It ensures that the repository remains navigable, maintainable, and internally consistent as it grows.

---

## 2. Directory Structure

The ScholarOS repository is organized as follows:

```mdmd
.claude/                    # AI assistant configuration and Base Instructions
docs/                       # All project documentation
├── READme.md               # Documentation index and entry point
├── Contributing.md         # Contribution guide (references governance)
├── journal/                # Engineering journal directory
│   ├── README.md           # Journal index and conventions
│   └── YYYY-MM-DD.md       # Daily session entries
├── Project_Status.md       # Current project dashboard
├── Timeline.md             # Milestone history
├── adr/                    # Architecture Decision Records
├── agents/                 # AI agent documentation
├── api/                    # API specifications
├── architecture/           # System architecture documentation
├── database/               # Database design and schema
├── decsion/                # Pre-governance decisions (legacy)
├── governance/             # Engineering Governance Framework
├── prompts/                # Prompt templates and guidelines (the Master Execution Prompt is 12_Master_Execution_Prompt.md)
├── roadmaps/               # Development roadmaps
├── srs/                    # Software Requirements Specification
└── vision/                 # Vision Document
```

All new documentation shall be placed in the appropriate directory. If a directory does not exist, one shall be created following the established naming conventions.

---

## 3. Naming Conventions

### 3.1 Documentation Files

* Use lowercase with hyphens or underscores (kebab_case preferred for multi-word names).
* Prefix sequentially numbered files with zero-padded numbers: `01_`,  `02_`, etc.
* Use descriptive names that reflect content: `01_Project_Constitution.md` not `01_Constitution.md`.
* The READme.md at the root of `docs/` serves as the documentation index. New document categories shall be added there.

### 3.2 Source Code Files

* Follow language-specific conventions (e.g.,  `PascalCase` for Python classes,  `camelCase` for JavaScript functions).
* File names shall match their primary export where applicable.
* Test files shall be named `{module_name}.test.{ext}` or `test_{module_name}.{ext}` following language conventions.

### 3.3 Commit Messages

Use clear, descriptive commit messages following conventional commits format:

* `docs:` — Documentation changes
* `arch:` — Architecture decisions or documentation
* `feat:` — New features
* `fix:` — Bug fixes
* `test:` — Test additions or changes
* `chore:` — Maintenance, configuration, tooling
* `governance:` — Governance framework changes
* `refactor:` — Code refactoring

Examples:

```md
docs: complete SRS Chapter 3
arch: define AI orchestration layer
feat: implement document ingestion
governance: adopt Engineering Governance Framework v2.0
```

Avoid generic messages such as `update` , `changes` , `fix` , `misc` .

---

## 4. File Modification Policies

### 4.1 General Rules

* No file shall be modified without a documented justification.
* Modifications must maintain consistency with all related files.
* When a file is modified, all files that reference it must be checked for required updates.

### 4.2 Cross-Reference Updates

Whenever a file is modified:

1. Check all files that reference the modified file.
2. Check all files that the modified file references.
3. Update all cross-references that the change invalidates.
4. Document cross-reference updates in the Engineering Report.

### 4.3 File Deletion

* No file shall be deleted without first verifying that no other file references it.
* If a file is superseded, add a deprecation notice rather than deleting it.
* Superseded files shall remain in the repository for at least one milestone cycle.

### 4.4 Frozen Milestones

When a milestone is declared complete, its primary artifacts are **frozen** (within the change authority granted by 02_AI_Engineering_Contract.md, §5):

* A frozen artifact set (e.g., the architecture document set, the ADR set) shall not be modified except for **corrections**: typos, broken references, factual errors, and consistency fixes required by the review process.
* New artifact sets belonging to later milestones (e.g.,  `docs/database/`,  `docs/api/`) are created fresh when their milestone begins; they are new documents, not edits to frozen ones.
* Repository-hardening tasks that clarify governance, traceability, documentation hierarchy, or milestone boundaries are permitted without creating future-milestone artifacts; such work is explicitly documentation-only and must not introduce database design, API design, implementation, testing, deployment, or infrastructure artifacts.
* Architectural changes that a later milestone genuinely requires shall be recorded in **new ADRs**, not by continuously rewriting frozen architecture documents.
* A frozen document may be reopened only through a documented decision — a new ADR that supersedes or amends part of it, or a new milestone that explicitly includes architecture revision in its scope.
* Freeze status is recorded in the journal (`docs/journal/`) when a milestone is declared complete.

This rule preserves repository maintainability as it grows: decisions are added as layers (new ADRs), not as edits that erode the historical record of what was decided.

---

## 5. Repository Consistency Rules

### 5.1 Internal Consistency

* Documentation shall remain internally consistent across all files.
* Cross-references between documents shall be valid and accurate.
* Terminology shall be consistent across the entire repository.
* Naming conventions shall be followed consistently.

### 5.2 Consistency Review Triggers

A repository consistency review shall be performed whenever:

* A new document category is introduced.
* An SRS chapter is added or modified.
* An ADR is created or updated.
* The governance framework is modified.
* The standing engineering responsibilities (11_Engineering_Responsibilities.md) or the Master Execution Prompt (12_Master_Execution_Prompt.md) are modified.
* A significant architectural change is made.
* Before any major release.

### 5.3 Consistency Violations

If a consistency violation is discovered:

1. Document the violation in the Engineering Report.
2. Determine the root cause.
3. Fix all affected files.
4. Update the journal (`docs/journal/`) with the resolution.

---

## 6. Repository Health Checks

Regular health checks shall verify:

* All cross-references are valid.
* No dead or orphaned files exist.
* Naming conventions are followed.
* The documentation hierarchy is respected.
* No contradictions exist between documents.
* Terminology is consistent.
* The Project Status accurately reflects the repository state.
* The Master Execution Prompt (12_Master_Execution_Prompt.md) references only valid governance documents and duplicates no operational steps.
* No standing responsibility (11_Engineering_Responsibilities.md) has pending, unaddressed violations.

Health check results shall be recorded in the journal ( `docs/journal/` ).

---

## 7. Branching Strategy

Until public collaboration begins, the project will follow a simplified workflow:

* **main** — Primary branch. All approved work lands here.
* Future branches may include:
  + `develop` — Integration branch for active work
  + `feature/*` — Feature-specific branches
  + `bugfix/*` — Bug fix branches
  + `release/*` — Release preparation branches

---

## 8. Continuous Improvement

* The repository governance rules shall be reviewed at each milestone.
* Suggested improvements shall be recorded in the journal (`docs/journal/`).
* Governance improvements shall be proposed through the ADR process if they are architecturally significant.

---

## 9. Relationship to Other Governance Documents

| Document | Relationship |
| ---------- | ----------- |
| 01_Project_Constitution.md | Governance rules must not contradict the Constitution. |
| 02_AI_Engineering_Contract.md | Contract grants change authority; this document defines repo rules. |
| 03_AI_Engineering_Standards.md | Standards define quality; Governance defines structure. |
| 06_Engineering_Report_Standard.md | The consistency review feeds into the Engineering Report. |
| 07_Review_Checklist.md | Consistency checks are part of the review process. |
| 11_Engineering_Responsibilities.md | RSP-002 through RSP-005 execute the repository rules defined here. |
| 12_Master_Execution_Prompt.md | Sessions that modify the repository are booted with this template. |

---

## 10. References

* 01_Project_Constitution.md
* 02_AI_Engineering_Contract.md
* 03_AI_Engineering_Standards.md
* 06_Engineering_Report_Standard.md
* 07_Review_Checklist.md
* 11_Engineering_Responsibilities.md
* 12_Master_Execution_Prompt.md
* ADR-001: Separation of Requirements, Architecture, and Implementation
