# Contributing to ScholarOS

**Version:** 2.0.0  
**Status:** Active  
**Last Updated:** 2026-07-29

---

## Purpose

This document defines the engineering workflow, contribution standards, and development principles for ScholarOS.

Its purpose is to ensure that all contributions—whether made by humans or AI assistants—remain consistent, traceable, maintainable, and aligned with the project's approved documentation.

**Note:** This document is part of a broader governance framework. All contributors shall also read the Engineering Governance Framework in `docs/governance/` (Phase 0 reading) before beginning work.

---

## Governance Framework

ScholarOS is governed by the **Engineering Governance Framework v1.0**, located at `docs/governance/`. The framework consists of 10 documents that define permanent engineering standards.

All contributors must read the governance documents in order before beginning work:

| Doc | Title | Purpose |
|-----|-------|---------|
| 01 | Project Constitution | Foundational project identity, philosophy, and principles |
| 02 | AI Engineering Contract | Binding obligations and workflow for AI engineers |
| 03 | AI Engineering Standards | Quality and engineering standards |
| 04 | Repository Governance | Repository structure, naming, and consistency rules |
| 05 | Definition of Done | Mandatory completion criteria |
| 06 | Engineering Report Standard | Engineering Report template |
| 07 | Review Checklist | Review and validation process |
| 08 | AI Roles and Responsibilities | Multi-AI collaboration |
| 09 | Documentation Standards | Documentation conventions |
| 10 | Prompting Guidelines | Prompt engineering standards |

---

## Development Philosophy

ScholarOS follows a documentation-first engineering methodology.

Every implementation must be supported by approved documentation.
The development lifecycle is:

```md
Vision
↓

Software Requirements Specification (SRS)
↓

Architecture
↓

Database Design
↓

API Design
↓

Implementation
↓

Testing
↓

Documentation Review
```

No implementation should bypass this process.

---

## Source of Truth

The official source of truth is the project documentation.

If multiple documents conflict, the following order applies:

1. Project Constitution
2. AI Engineering Contract
3. AI Engineering Standards
4. Repository Governance
5. Vision Document
6. Software Requirements Specification (SRS)
7. Architecture Documentation
8. Architecture Decision Records (ADR)
9. Source Code

**Note:** Governance documents 05–14 (Definition of Done through Prompting Guidelines) sit between ADRs and Source Code in the full hierarchy. See `01_Project_Constitution.md` Section 5 for the complete, authoritative hierarchy.

Code shall never redefine requirements.

---

## Contribution Workflow

Every contribution should follow this workflow.

1. Read the Documentation Index (`docs/README.md`).
2. Read the Engineering Governance Framework (`docs/governance/`, 01–10 in order).
3. Review the relevant approved documentation.
4. Identify the requirement(s) being implemented.
5. Raise ambiguities before making assumptions.
6. Produce the proposed change.
7. Perform self-review against 07_Review_Checklist.md.
8. Verify the Definition of Done (05).
9. Produce an Engineering Report conforming to 06_Engineering_Report_Standard.md.
10. Submit for architectural review.
11. Merge after approval.

---

## Requirement Traceability

Every feature must map back to an approved requirement.

Example:

Requirement

```md
FR-021 — Document Upload

↓

Architecture

Document Processing Service

↓

Implementation

backend/app/services/document_service.py

↓

Tests

tests/test_document_upload.py
```

This traceability ensures that every feature has a documented purpose.

---

## Documentation Standards

Documentation should:

* be concise and unambiguous
* avoid duplication
* distinguish requirements from implementation
* remain consistent with earlier documents
* use professional technical language.
* follow the conventions in 09_Documentation_Standards.md.

Major documentation changes should be reviewed before approval.

---

## Coding Standards

Code should:

* be modular, readable, well documented, testable, and loosely coupled.
* use strong typing where practical.
* keep business logic separate from infrastructure code.
* follow the detailed standards in 03_AI_Engineering_Standards.md.

---

## AI Contributor Guidelines

AI assistants are treated as engineering contributors and are bound by 02_AI_Engineering_Contract.md.

Before beginning work, an AI assistant should:

1. Read the Project Constitution (01).
2. Read the AI Engineering Contract (02).
3. Review the Engineering Standards (03) and Repository Governance (04).
4. Understand the current project status (`docs/Project_Status.md`).
5. Identify the relevant requirements.
6. Explain uncertainties before implementation.
7. Avoid introducing undocumented functionality.
8. Recommend documentation updates when appropriate.

AI assistants should assist—not redefine—the project.

---

## Architecture Principles

ScholarOS is designed around several long-term architectural principles:

* Modular components
* Replaceable AI providers
* Backend-first development
* Clear separation of concerns
* Persistent project memory
* Context-aware generation
* Human oversight
* Scalable system design

Every contribution should reinforce these principles.

---

## Branching Strategy

Until public collaboration begins, the project will follow a simplified Git workflow.

Primary branch:

main

Future branches may include:

* develop
* feature/*
* bugfix/*
* release/*

---

## Commit Message Convention

Use clear and descriptive commit messages following the conventional commits format:

- `docs:` — Documentation changes
- `arch:` — Architecture decisions or documentation
- `feat:` — New features
- `fix:` — Bug fixes
- `test:` — Test additions or changes
- `chore:` — Maintenance, configuration, tooling
- `governance:` — Governance framework changes
- `refactor:` — Code refactoring

Examples:

docs: complete SRS Chapter 3

arch: define AI orchestration layer

feat: implement document ingestion

governance: adopt Engineering Governance Framework v1.0

Avoid generic commit messages such as:

update

changes

fix

misc

---

## Pull Request Guidelines

Every pull request should explain:

* What changed.
* Why the change was necessary.
* Which requirement(s) it implements.
* Any architectural implications.

---

## Review Checklist

See 07_Review_Checklist.md for the complete review and validation process.

Before approving a contribution, verify:

* Documentation remains consistent.
* Requirements are satisfied.
* No undocumented functionality was introduced.
* Architecture remains modular.
* Code is maintainable and meets quality standards (03).
* Tests exist where appropriate and pass.
* The Definition of Done (05) is satisfied.
* An Engineering Report (06) has been produced.

---

## Long-Term Goal

ScholarOS aims to become a maintainable, extensible research platform.

Every contribution should improve the quality, clarity, and longevity of the system.

Short-term convenience should never compromise long-term maintainability.

---

# Final Principle

Before changing the software, first understand the system.

> **Understand First. Build Second.**

---

# References

- Engineering Governance Framework: `docs/governance/01` through `docs/governance/10`
- 01_Project_Constitution.md
- 02_AI_Engineering_Contract.md
- 05_Definition_of_Done.md
- 06_Engineering_Report_Standard.md
- 07_Review_Checklist.md
- 09_Documentation_Standards.md
- ADR-001: Separation of Requirements, Architecture, and Implementation
