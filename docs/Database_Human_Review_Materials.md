# Database Baseline v1 — Human Architectural Review: Preparation Materials

**Document:** Database_Human_Review_Materials.md

**Status:** Active — preparation materials for a review that has not yet happened

**Date:** 2026-09-18

**Prepared by:** AI engineering session, at the project owner's request, in place of performing the review itself

**Authority:** Not a governance document and not part of the frozen Database Baseline v1 (`docs/database/01`–`08`). It is scaffolding for the human L3 review those documents' own §13/§14 (in `08_Database_Design_Review_and_Readiness_Assessment.md`) have flagged as outstanding since 2026-08-07. It sits outside the frozen set deliberately — `08`'s own Freeze Declaration (§17) permits only corrections to the frozen set, and this is neither a correction nor architecturally significant on its own; it is a reading list and a checklist.

---

## 1. Why this document exists

Every AI-performed review pass on the database design has been recorded (`07_Database_Validation_and_Quality_Assurance.md`, `08`'s own §§4–9). What has never happened is a **human** L3 architectural review — `08` §13 names this as a known risk ("Milestone-level assurance rests on recorded AI review passes") and §14 recommends it explicitly, using the general review framework in `docs/governance/07_Review_Checklist.md` §2 (L3 — Architectural Review, reviewer: Lead Engineer).

This document does not perform that review. It cannot — an AI review pass, however careful, is exactly the thing already on record and exactly what a human review is meant to check independently. What follows is the material a reviewer needs to do it efficiently: what to read, what has genuinely changed since the baseline froze, and a checklist to work through.

---

## 2. What to actually read, in order

1. `docs/database/08_Database_Design_Review_and_Readiness_Assessment.md` — start here. It's the close-out document; §21 (Database Handoff Report) is the operative contract everything else was built against.
2. `docs/database/04_Logical_Data_Model.md` and `05_Constraints_and_Integrity.md` — the two documents implementation code is directly traceable to.
3. **Section 3 of this document (below)** — the concrete list of how the *actual, currently-running* schema has diverged from what `08` describes, and which divergences were never formally recorded the way ADR-009 and ADR-010 were (`08` §23, §24).
4. `docs/adr/ADR-004_Storage_and_Memory_Strategy.md` and `ADR-005_Retrieval_and_Search_Strategy.md` — both have been *realized* since baseline freeze (Postgres/Alembic/S3-compatible storage; hybrid retrieval), and both realizations found real gaps in the original design's assumptions (§3.4, §3.5 below).

You do not need to re-read `01`–`03`, `06`, `07` line by line unless something in §3 below sends you back to them — they haven't been implicated by anything found since freeze.

---

## 3. What has actually changed since the baseline froze (2026-08-07)

This is the part a design-document read-through won't surface on its own — everything here is a fact about the *implementation*, gathered across engineering sessions since. Organized by how formally each one was ever recorded.

### 3.1 Formally recorded corrections (already reviewed, already in `08`)

- **ADR-009** (2026-09-04): introduced `Agent` as a top-level entity, rescoped several entities from `project_id` to `agent_id`. Recorded in `08` §23.
- **ADR-010** (2026-09-10): added `User.password_hash`, realized the already-designed `Session` entity as `AuthSession`. Recorded in `08` §24.

These two are examples of the correct process working — nothing to review here beyond confirming you agree with them, which is itself in scope.

### 3.2 A significant divergence that was *never* formally recorded — the primary thing this review should decide

**The entire Draft / Review pipeline no longer exists in the implementation.** `Draft`, `Draft Version`, `Review`, `Review Decision`, and `Draft Evidence Link` — five entities the frozen Logical Data Model (`04` §3) still documents as core, and which `08` §21 (the handoff contract) explicitly names as what backend engineers would build against — were built, then removed in a later, previously uncommitted working session. The product replaced them with a persistent chat/memory model instead (`Conversation` → `Message`, which — importantly — *were* already specified in the frozen model, `04` §3.9, just not implemented until later; their realization is not the problem). The removal itself is recorded nowhere except:
- A docstring in `backend/app/modules/writing/application/chat.py` (`GenerateConversationReplyUseCase`'s class docstring), stating plainly that "the Drafts/Review pipeline... was removed entirely."
- This session's own updates to `docs/Frontend_Implementation_Plan.md` (a pivot note) and `docs/Project_Status.md`, written today (2026-09-18) specifically because nothing else documented it.
- No journal entry. No ADR. No correction section appended to `08` the way ADR-009 and ADR-010 got §23/§24.

**This is the one thing this review should make a real decision on, not just note:** does removing five previously-frozen entities warrant a formal baseline correction (an ADR, or a §25 appended to `08` mirroring §23/§24's own pattern), the same governance weight given to ADR-009 (which *added* an entity)? The project's own precedent (`04_Repository_Governance.md` §4.4, cited throughout `08`) says architecturally significant change requires exactly this. Whether an *removal* clears that bar the same way an addition did is a judgment call — this document takes no position on it, since that's precisely what a human reviewer's authority is for.

If the answer is yes, the mechanical work (an ADR documenting the product decision and its rationale, then a `08` §25 correction section) is small; the review's value is in deciding whether it's warranted, not in doing the writing.

### 3.3 Flagged, unfixed deviations already on record (not new, but worth confirming you agree with the disposition)

- **SQLAlchemy's `Enum` columns store the Python member's `.name`, not its `.value`**, in the `agent`, `document`, and `knowledge` modules — found during Project Writing Stage 2, fixed there (via `values_callable`) but left unfixed in the three pre-existing modules as an accepted, non-blocking deviation (nothing currently reads those columns outside the ORM). Still true as of today. Worth a second opinion on whether "accepted" should become "scheduled."
- **`DocumentPurpose` enum** (`RESEARCH` / `WRITING_STYLE_SAMPLE`) added to `Research Document` — not in the original frozen model, added to distinguish writing-style samples from research material after a real bug (samples polluting research-document listings) made the gap concrete. A legitimate, documented deviation (see `backend/app/modules/document/domain/enums.py`'s own docstring), not hidden — but never run past a human either.

### 3.4 New physical-layer realizations since freeze (ADR-004's own named migration path, now actually built)

- **PostgreSQL support**, via Alembic migrations, live-validated today (2026-09-18) against a real local Postgres 17 instance — schema-equivalent to SQLite, dialect-branched where SQLite and Postgres genuinely differ (see next bullet). Not yet cut over; the running app still defaults to SQLite.
- **A real dialect-compatibility bug found by this realization, now fixed:** `WritingProfile`'s "at most one active profile per Agent" invariant (`05` §19 invariant 8) was implemented as a partial unique index, but only ever configured for SQLite (`sqlite_where`, never `postgresql_where`). On Postgres it would have silently become a *full* unique index — enforcing "at most one profile ever," not "at most one *active* profile" — a real behavioral divergence between dialects that nothing but an actual Postgres run surfaced. This is worth reading as a data point on how much weight to put on "implementation-independent" design review alone (`08` §4 lists it as a strength) versus needing at least one real run against each target engine before trusting a cross-dialect invariant.
- **S3-compatible object storage**, realized behind the existing `ContentStore` port (`06`'s own storage-category abstraction) — no schema change, config-selected per `06` §21 item 9's own anticipated migration path.

### 3.5 New realization of ADR-005 (hybrid retrieval) — a genuine gap in the original design's own physical strategy

`ADR-005` decided hybrid (lexical + semantic) retrieval back at Milestone 4; the frozen `06_Physical_Design_Strategy.md` maps the *vector* index onto a storage category but says nothing about where a lexical index lives, because none existed at design time. Realizing it (2026-09-18) required inventing that placement: SQLite gets an FTS5 virtual table, Postgres gets a generated `tsvector` column + GIN index — both are real, working, but neither was anticipated by `06`, and `06` was never revised to say so (it wasn't required to — this is exactly the kind of "additive, not a redesign" evolution `07 §5`/`ADR-004` describe as fine at the physical layer). Worth a look at whether the physical design strategy should be formally amended to name this, or whether "the physical layer evolves without touching the frozen document" genuinely holds here the way `08` §12 assumes it will.

### 3.6 A smaller, unrelated housekeeping gap noticed in passing

`docs/Baseline_Register.md` §2's Database Baseline v1 row still only says "corrected 2026-09-04 by ADR-009" — it was never updated for the ADR-010 correction (`08` §24, dated 2026-09-10) either. A one-line fix, not a review item, but flagged here since it was noticed while preparing this document and nowhere else seemed like the right place to record it.

---

## 4. Review checklist

Adapted from `docs/governance/07_Review_Checklist.md` §4 (Peer and Architectural Review criteria) for the database baseline specifically. Not every line will apply equally — use judgment.

### 4.1 Correctness & Architecture Alignment
- [ ] Does §3.2's Draft/Review removal warrant a formal baseline correction (ADR + `08` §25)? — the primary decision this review exists to make.
- [ ] Do the thirteen domain invariants (`05` §19) still hold against the *current* implementation, given §3.2's removal? (At minimum, any invariant referencing Draft/Review/Draft Evidence Link needs re-reading against what's actually enforced now.)
- [ ] Is `agent_id` vs `project_id` scoping (ADR-009) applied consistently everywhere it should be, per `04` §3.3–§3.21?
- [ ] Does the evidence-link chain (`ADR-005`; `04` §4.1–§4.2) still hold end-to-end now that Draft Evidence Link is gone — is evidence traceability preserved through the chat/memory path the way it was through Drafts?

### 4.2 Consistency & Documentation
- [ ] Does `08`'s own content (§3, §5, §21) still describe the system accurately, given §3.2? A stale handoff contract is worse than none.
- [ ] Is the `.name`-vs-`.value` enum deviation (§3.3) still an acceptable "flagged, unfixed" state, or should it be scheduled?
- [ ] Should `06_Physical_Design_Strategy.md` be amended to name the lexical-index placement (§3.5), or is the existing "additive evolution, no redesign" framing sufficient?

### 4.3 Risk Assessment
- [ ] Does the SQLite→Postgres migration path (`ADR-004`, now partially executed) change the risk profile of anything in `08` §13's Known Risks table?
- [ ] Given the partial-index bug (§3.4), are there other cross-dialect invariants in `05` that haven't been run against a real second engine yet and should be spot-checked before any real cutover?

### 4.4 Governance Compliance
- [ ] Is the Baseline Register housekeeping gap (§3.6) worth a one-line fix now?
- [ ] Should this review's outcome itself be recorded as a new `08` correction section (§25), a journal entry, or both — per `04_Repository_Governance.md` §4.4's own recording requirements?

---

## 5. Recording the outcome

Whatever this review concludes, record it the way ADR-009 and ADR-010's corrections were recorded (`08` §23, §24 as the pattern to follow):

1. If a baseline correction is warranted (most likely for §3.2): a new ADR stating the product decision and its rationale, then a `08` §25 appended in the same style as §23/§24 (preserving §1–§24 as historical record, not rewriting them).
2. A journal entry (`docs/journal/`) recording the review happened, who did it, and what it concluded — matching every other milestone-level review in this project's history.
3. An update to `docs/Baseline_Register.md` if the correction changes the baseline's recorded status line.
4. This document (`Database_Human_Review_Materials.md`) can be deleted once the review is complete and recorded — it's scaffolding, not a permanent artifact.
