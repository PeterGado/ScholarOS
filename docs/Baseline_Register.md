# Baseline Register

**Document:** Baseline_Register.md

**Status:** Active

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design (close-out)

**Authority:** This register records the freeze status of milestone baselines per 04_Repository_Governance.md §4.4. It is a repository state artifact (like Project_Status.md and Timeline.md), not a governance document; it does not create new rules — it records the baselines the governance framework already defines.

---

## 1. Purpose

The Baseline Register is the single record of **what is frozen, when it was frozen, and what it includes**. It exists so that any contributor — human or AI — can determine at a glance which artifact sets are authoritative-and-frozen versus active or planned, without reading the milestone history.

A baseline is the frozen artifact set of a completed milestone. Freezing follows 04_Repository_Governance.md §4.4: a frozen set is modified only for corrections (typos, broken references, factual errors, consistency fixes); architecturally significant change requires a new ADR or a new milestone that explicitly includes revision in its scope.

---

## 2. Register

| Baseline | Status | Includes | Frozen on | Change path |
|---|---|---|---|---|
| **Requirements Baseline v1** | Frozen | Vision + SRS 01–11 | 2026-07 (SRS completion) | New SRS revision requires architectural review (09 §5.1); scope changes require approval (MVP-028) |
| **Governance Baseline v2** | Frozen | Governance 01–12 | 2026-08-06 | Governance changes require constitutional consistency check (09 §5.1) |
| **Architecture Baseline v1** | Frozen (corrected 2026-09-04 by ADR-009) | Architecture 01–07 + ADR-001 to ADR-009 | 2026-08-06 (Milestone 4 close-out audit passed) | New ADRs only (04 §4.4); frozen documents are not rewritten |
| **Database Baseline v1** | **Frozen (corrected 2026-09-04 by ADR-009)** | Database 01–08 (`docs/database/`) | 2026-08-07 (Milestone 5 close-out) | Corrections only; significant change requires a new ADR or a revision milestone |
| **API Baseline v1** | **Superseded** (see §3) | Not produced as a standalone artifact set; API contracts are folded into Implementation Baseline v1 | 2026-09-04 (superseded) | See ADR-008 and `docs/journal/2026-09-04.md` |
| **Implementation Baseline v1** | Planned | Backend/frontend implementation artifacts, including the API contracts (Pydantic models / generated OpenAPI schema) produced progressively per ADR-008 | — | To be recorded when the implementation milestone freezes |

---

## 3. Note on Freeze Records

* **Architecture Baseline v1** and **Database Baseline v1** were frozen with formal close-out declarations recorded in the journal (Milestone 4 and Milestone 5 respectively).
* **Requirements Baseline v1** and **Governance Baseline v2** are declared frozen by this register on 2026-08-07: their artifact sets were completed and treated as authoritative by every subsequent milestone, as reflected in the milestone records (Timeline.md and the journal).
* **Known header inconsistency:** the SRS chapter files historically carry `**Status:** Draft` in their headers. This is pre-baseline metadata that predates the register; it does not affect the authority of the requirements (the SRS is the governing requirements baseline for all design and implementation work). Correction of these headers is recorded here as a housekeeping item for a future pass — it is a metadata correction, not a requirements change.
* **API Baseline v1 superseded:** the standalone API Design milestone previously planned here (an 8-document `docs/api/` set mirroring Database Design) was superseded on 2026-09-04 by **ADR-008 (API Contract Governance During Backend Implementation)**, following an Independent Repository Audit (`docs/journal/2026-09-04.md`). API contracts are now defined progressively during backend implementation as Pydantic/FastAPI code and will be recorded as part of **Implementation Baseline v1** at its close-out, not as a separate frozen baseline. This is a documented, ratified decision, not a silent removal — see ADR-008 for full rationale, alternatives considered, and the ongoing governance rule for architecturally significant API decisions.
* **Architecture Baseline v1 and Database Baseline v1 reopened for correction (2026-09-04):** per this register's own Reading Guide (§5) and `04_Repository_Governance.md` §4.4, **ADR-009 (Agent and Project Domain Model Introduction)** is the new ADR authorizing an architecturally significant correction to both baselines — introducing Agent as a new entity, narrowing Project's scope, and renaming the capability-registry entities from `Agent`/`Agent Capability` to `Capability`/`Capability Entry`. This is a **correction, not a re-freeze**: both baselines remain Frozen at their original freeze dates, with the correction recorded against them per the journal (`docs/journal/2026-09-04.md`) and ADR-009 itself. Corrected documents: `docs/database/02`–`06`, `08` (addendum, §23); `docs/architecture/02`, `03`, `04`, `05`; `docs/adr/ADR-003` (cross-reference only — its substantive decision is unchanged); `docs/adr/ADR-001` (cross-reference addition only).
* **Architecture Baseline v1 and Database Baseline v1 further corrected (2026-09-10):** **ADR-010 (Authentication Boundary — Single-User Session Model)** authorizes a further correction — adding `password_hash` to the `User` entity and a credential-non-exposure rule, and realizing the Authentication Boundary via the already-specified (previously unimplemented) Session entity rather than a new mechanism. Both baselines remain Frozen at their original freeze dates. Corrected documents: `docs/database/04` (§3.1, §15, §16), `docs/database/05` (§17, §20), `docs/database/08` (addendum, §24); `docs/architecture/05` (§15.4, §21); `docs/adr/ADR-002`, `ADR-004`, `ADR-008`, `ADR-009` (cross-reference additions only — substantive decisions unchanged). This is the second correction to these baselines, following ADR-009's precedent and the same correction discipline.

---

## 4. Maintenance Rules

1. A row is added or updated only when a milestone is declared complete and frozen (04 §4.4) and the declaration is recorded in the journal.
2. Corrections to a frozen baseline do not change the baseline version; the correction is recorded in the journal (04 §5.3).
3. If a baseline must be reopened, the decision, its authority (ADR or milestone scope), and the journal record are noted in the register.
4. The register is synchronized with Project_Status.md, Timeline.md, and the Traceability Index whenever a baseline status changes.
5. The register never defines new governance; it reflects the freeze discipline of 04 §4.4.

---

## 5. Reading Guide

* A **Frozen** baseline is authoritative for its artifact set; later work extends or references it, never rewrites it.
* A **Planned** baseline is not yet frozen; its artifacts will be created when its milestone begins and frozen at its close-out.
* Conflicts between baselines are resolved by the documentation hierarchy (01_Project_Constitution.md §5): Constitution → Governance → Vision → SRS → Architecture/ADRs → Database design → API design → Implementation.

---

## 6. Traceability

* 04_Repository_Governance.md — §4.4 (Frozen Milestones), §5.3 (Consistency Violations)
* 01_Project_Constitution.md — §5 (Documentation Hierarchy)
* 05_Definition_of_Done.md — §2.10 (Journal update), §2.7 (Repository Consistency)
* docs/Project_Status.md — current phase dashboard
* docs/Timeline.md — milestone history
* docs/Traceability_Index.md — navigation index
* docs/database/08_Database_Design_Review_and_Readiness_Assessment.md — Database Baseline v1 definition (§18 of 08)
