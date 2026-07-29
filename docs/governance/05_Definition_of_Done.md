# Definition of Done

**Document:** 05_Definition_of_Done.md

**Governance Framework:** Engineering Governance Framework v1.0

**Status:** Active

**Date:** 2026-07-29

**Authority:** Fifth, after Repository Governance (04).

---

## 1. Purpose

This document defines the mandatory completion criteria that every engineering task in ScholarOS must satisfy before it can be considered complete.

No task — whether documentation, architecture, implementation, or governance — is finished until all applicable criteria in this definition have been met.

---

## 2. The Definition of Done

A task is complete only when **all** of the following conditions are true:

### 2.1 Requested Work

- [ ] The explicitly requested work has been completed.
- [ ] No undocumented features or functionality have been introduced.
- [ ] The work does not contradict the Project Constitution, Vision, or approved SRS.

### 2.2 Requirements Alignment

- [ ] The implementation satisfies the relevant approved requirements.
- [ ] Every implemented feature maps to an approved requirement.
- [ ] No requirement has been modified without documented justification.

### 2.3 Architecture Alignment

- [ ] The implementation conforms to the approved architecture.
- [ ] If architecture deviations were necessary, they are documented in an ADR or the Engineering Report.
- [ ] Temporary workarounds are documented with a resolution plan.

### 2.4 Implementation Quality

- [ ] Code follows the standards defined in 03_AI_Engineering_Standards.md.
- [ ] Code is modular, testable, and maintainable.
- [ ] Provider-specific logic is abstracted behind interfaces.
- [ ] No hardcoded secrets or environment-specific values exist.

### 2.5 Testing

- [ ] Tests exist for the new or modified functionality.
- [ ] All existing tests continue to pass.
- [ ] Test coverage meets the thresholds defined in 03_AI_Engineering_Standards.md.
- [ ] No flaky tests have been introduced.

### 2.6 Documentation

- [ ] All new public APIs, functions, classes, and modules are documented.
- [ ] Documentation follows the conventions in 09_Documentation_Standards.md.
- [ ] README files are updated where the change affects module understanding.

### 2.7 Repository Consistency

- [ ] All cross-references to and from modified files are valid.
- [ ] Terminology is consistent with existing documentation.
- [ ] Naming conventions (04_Repository_Governance.md) are followed.
- [ ] The Project Status has been reviewed and updated where necessary.

### 2.8 No Contradictions

- [ ] No contradictions exist with the Project Constitution, Vision, or approved SRS.
- [ ] No contradictions exist within the governance framework.
- [ ] No contradictions exist between related documentation files.

### 2.9 Engineering Report

- [ ] An Engineering Report conforming to 06_Engineering_Report_Standard.md has been produced.
- [ ] The report documents all changes, justifications, and affected files.
- [ ] Risks and technical debt are documented.

### 2.10 Journal

- [ ] The Journal has been updated with a summary of the completed work.
- [ ] Key decisions, lessons learned, and outstanding items are recorded.

---

## 3. Task-Specific Criteria

Some tasks may have additional completion criteria beyond the standard DoD:

| Task Type | Additional Criteria |
|-----------|-------------------|
| SRS Chapter | Approved by architectural review. No implementation details. |
| ADR | Accepted status. Alternatives documented. Rationale clear. |
| Architecture Document | Traceable to SRS requirements. ADR references where decisions are recorded. |
| Implementation | All tests passing. Code reviewed. No linting errors. |
| Governance Document | Internal consistency verified. Cross-references validated. |
| Bug Fix | Root cause identified. Regression test added. |

---

## 4. DoD Violations

If a task is submitted without satisfying the Definition of Done:

1. The incomplete criteria shall be identified and communicated.
2. The contributor shall address the gaps before the task is accepted.
3. Repeated violations shall be documented in the Journal and may result in workflow adjustments.

---

## 5. Relationship to Other Governance Documents

| Document | Relationship |
|----------|-------------|
| 02_AI_Engineering_Contract.md | Contract references the DoD as a completeness requirement. |
| 03_AI_Engineering_Standards.md | DoD incorporates quality standards from this document. |
| 04_Repository_Governance.md | DoD incorporates repository rules from this document. |
| 06_Engineering_Report_Standard.md | DoD requires compliance with the report standard. |
| 07_Review_Checklist.md | DoD criteria are verified during the review process. |
| 09_Documentation_Standards.md | DoD requires compliance with documentation conventions. |

---

## 6. References

- 02_AI_Engineering_Contract.md — Section 13 (Definition of Done)
- 03_AI_Engineering_Standards.md — Testing Standards
- 04_Repository_Governance.md — Repository Consistency Rules
- 06_Engineering_Report_Standard.md
- 07_Review_Checklist.md
- 09_Documentation_Standards.md
