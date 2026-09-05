# Review Checklist

**Document:** 07_Review_Checklist.md

**Governance Framework:** Engineering Governance Framework v2.0

**Status:** Active

**Date:** 2026-07-29

**Authority:** Seventh, after the Engineering Report Standard (06).

---

## 1. Purpose

This document defines the mandatory review and validation process for all engineering contributions to ScholarOS.

Review is required before any significant change is accepted into the repository. The level of review depends on the type and impact of the change.

---

## 2. Review Levels

| Level | Required For | Reviewer | Depth |
|-------|-------------|----------|-------|
| L1 — Self Review | All changes | Contributor | The contributor verifies completeness and consistency |
| L2 — Peer Review | Feature implementations, architecture changes, ADRs | Another AI or human engineer | Full review against all criteria |
| L3 — Architectural Review | SRS changes, ADRs, governance changes, breaking changes | Lead Engineer | Full review plus architectural impact assessment |

---

## 3. Pre-Review Checklist (Self Review)

Before submitting any change for review, the contributor must verify:

### 3.1 Completeness

- [ ] The requested work is complete.
- [ ] No partially finished or placeholder code exists.
- [ ] All TODO comments are resolved or documented.

### 3.2 Consistency

- [ ] The change does not contradict the Project Constitution, Vision, or SRS.
- [ ] Terminology matches existing documentation.
- [ ] Cross-references are valid.
- [ ] Naming conventions are followed.

### 3.3 Quality

- [ ] Code follows the standards in 03_AI_Engineering_Standards.md.
- [ ] Tests exist and pass.
- [ ] Documentation is updated.
- [ ] No dead code, commented-out code, or debugging artifacts exist.

### 3.4 Governance Compliance

- [ ] The Definition of Done (05) criteria are met.
- [ ] An Engineering Report (06) has been produced.
- [ ] The journal (`docs/journal/`) has been updated.
- [ ] The standing engineering responsibilities (11) applicable to the task were executed and their outputs (dependency analysis, consistency validation, documentation synchronization, reporting) are documented.

---

## 4. Review Criteria (Peer and Architectural Review)

### 4.1 Correctness

- [ ] Does the implementation satisfy the approved requirements?
- [ ] Are edge cases handled?
- [ ] Are error conditions handled gracefully?
- [ ] Is the behavior deterministic for the same inputs?

### 4.2 Architecture Alignment

- [ ] Does the implementation conform to the approved architecture?
- [ ] Are architectural deviations documented and justified?
- [ ] Are component boundaries respected?
- [ ] Is provider abstraction maintained?

### 4.3 Maintainability

- [ ] Is the code readable and self-documenting?
- [ ] Are modules loosely coupled?
- [ ] Are interfaces clear and minimal?
- [ ] Would a future contributor understand the design?

### 4.4 Testability

- [ ] Are tests present for the new functionality?
- [ ] Are tests deterministic and independent?
- [ ] Can the component be tested in isolation?
- [ ] Are test quality standards met?

### 4.5 Documentation

- [ ] Is new functionality documented?
- [ ] Are public APIs documented?
- [ ] Are cross-references valid?
- [ ] Does the documentation follow 09_Documentation_Standards.md?

### 4.6 Security

- [ ] Are secrets properly handled?
- [ ] Is input validation performed at boundaries?
- [ ] Are there any introduced vulnerabilities?

### 4.7 Risk Assessment

- [ ] What risks does this change introduce?
- [ ] Are risks documented in the Engineering Report?
- [ ] Are mitigations in place for identified risks?
- [ ] Is there technical debt being introduced?

---

## 5. Validation Process

### 5.1 Automated Validation

Before review, automated validation must pass:

- [ ] All tests pass.
- [ ] No linting errors exist.
- [ ] Type checking passes (where applicable).
- [ ] Build succeeds.

### 5.2 Manual Validation

During review, the reviewer must verify:

- [ ] The implementation matches the requirements.
- [ ] The implementation matches the architecture.
- [ ] No undocumented functionality exists.
- [ ] The Definition of Done is satisfied.
- [ ] The Engineering Report is accurate.

### 5.3 Post-Review Validation

After review and before acceptance:

- [ ] All review comments are addressed.
- [ ] Changes are re-tested if the review required modifications.
- [ ] The Engineering Report is updated to reflect review outcomes.

---

## 6. Approval Criteria

A change is approved when:

1. All applicable review criteria are satisfied.
2. All issues identified during review are resolved.
3. Validation passes.
4. The Definition of Done is satisfied.
5. The Engineering Report is complete and accurate.

---

## 7. Relationship to Other Governance Documents

| Document | Relationship |
|----------|-------------|
| 03_AI_Engineering_Standards.md | Review criteria include quality standards from this document. |
| 05_Definition_of_Done.md | Review verifies that DoD criteria are met. |
| 06_Engineering_Report_Standard.md | Review validates the Engineering Report. |
| 08_AI_Roles_and_Responsibilities.md | Different AI roles perform different review levels. |
| 11_Engineering_Responsibilities.md | Review verifies that the responsibility outputs (RSP-004 through RSP-006) are complete. |

---

## 8. References

- 03_AI_Engineering_Standards.md
- 05_Definition_of_Done.md
- 06_Engineering_Report_Standard.md
- 08_AI_Roles_and_Responsibilities.md
- 11_Engineering_Responsibilities.md
