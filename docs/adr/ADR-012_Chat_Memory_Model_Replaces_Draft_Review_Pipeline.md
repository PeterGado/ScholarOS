# ADR-012: Chat/Memory Model Replaces the Draft/Review Pipeline

**Status:** Accepted (retroactively — see Context)

**Date:** 2026-10-09 (written); the decision itself was made and implemented earlier, in an uncommitted working session between 2026-09-16 and 2026-09-18, with no contemporaneous record

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** Database Baseline v1's `Draft`, `Draft Version`, `Review`, and `Review Decision` entities (`04_Logical_Data_Model.md` §3.15–§3.18) and the `Draft Evidence Link` link entity (§4.2), in full. `Conversation` and `Message` (§3.9, §3.10) are unaffected by this ADR — they were already specified in the frozen model and are not newly introduced by it; what changes is their role, from a secondary channel into the primary writing-generation mechanism the removed entities used to serve.

---

## Status

**Accepted, written retroactively.** The product decision this ADR records was made and fully implemented before this document existed — `Draft`, `Draft Version`, `Review`, and `Review Decision` were built against the frozen Database Baseline v1, then removed entirely in a later, uncommitted working session, with the chat/memory model (`Conversation`/`Message`, rolling summarization, automatic memory extraction) taking over as the real writing-generation mechanism. The removal was first written down anywhere on 2026-09-18, as a "pivot note" in `docs/Frontend_Implementation_Plan.md` and an entry in `docs/Project_Status.md` — not as a decision record, but as a fact the frontend milestone's own status needed to state honestly. `docs/Database_Human_Review_Materials.md` §3.2 later flagged the absence of a formal correction as the single most significant unresolved governance gap in the repository and handed the decision of whether to close it to a human reviewer. This ADR is that correction, written after the fact because no one wrote it at the time.

---

## Context

The frozen Database Baseline v1 (Milestone 5 close-out, 2026-08-07) specified a Draft/Review pipeline: a `Draft` accumulates `Draft Version`s through writing and revision cycles; each version can be evaluated by a `Review`, producing exactly one `Review Decision` (approved / revisions requested / rejected); evidence supporting a version is recorded via `Draft Evidence Link`. This modeled academic writing as a formal, versioned, human-approved artifact pipeline — consistent with the product's original framing of ScholarOS as a tool that produces reviewable drafts.

The Project Writing milestone (Stages 1–8, completed and committed 2026-09-16) built this pipeline exactly as specified, with no deviation from the frozen model. It worked, was tested (524/524 tests passing at that milestone's close), and was validated against a real Gemini provider.

Separately — in a working session that was never committed incrementally and so left no journal entry — the product itself changed shape. `Draft`, `Draft Version`, `Review`, and `Review Decision` were removed; `Conversation` and `Message`, already specified in the frozen model (§3.9–§3.10) but not yet serving as the primary writing mechanism, took over that role instead: a user writes by chatting with their Agent, replies are generated asynchronously per message, and `Memory Record` (automatic extraction from conversation content, replacing `Review Decision` as a memory-provenance source) carries forward the persistent context the old evidence-link chain used to. The backend's own code is unambiguous that this was a deliberate, total removal, not a partial refactor — `GenerateConversationReplyUseCase`'s class docstring states plainly that "the Drafts/Review pipeline... was removed entirely," and three other files (`backend/app/modules/writing/domain/entities.py`, `enums.py`, `memory_extraction.py`, `infrastructure/models.py`) independently confirm the same fact from different angles (removed enum values, a removed memory-trigger source, removed polymorphic-link target types).

No ADR, journal entry, or `08` correction section was ever written for this. `docs/Database_Human_Review_Materials.md` §3.2, prepared 2026-09-18 for a human baseline review, explicitly declined to decide whether a *removal* of five previously-frozen entities warranted the same governance weight ADR-009 was given for an *addition*, and left that decision to the project owner. The project owner has since confirmed it does.

---

## Problem

How should this five-entity removal — made without a decision record, implemented, shipped, and now relied upon by every part of the product built since — be formally reconciled with the frozen Database Baseline v1, so that:

1. The baseline accurately reflects what the system actually is, not what it was at Milestone 5 close-out;
2. The decision's real rationale is captured once, authoritatively, rather than left to be inferred from code comments and absence;
3. The correction follows the same governance discipline ADR-009 and ADR-010 already established (`04_Repository_Governance.md` §4.4): frozen documents are corrected, not rewritten, with the correction itself recorded as a numbered addition to `08`.

---

## Decision

1. **`Draft`, `Draft Version`, `Review`, and `Review Decision` are removed from the Database Baseline**, and `Draft Evidence Link` is removed with them. No successor entity directly replaces any of the four core entities — their responsibilities are absorbed by entities the baseline already specified: `Conversation`/`Message` for the writing surface itself, and `Memory Record` for the persistent context `Review Decision` used to feed.

2. **The motivating reason is that a conversational interface is a better fit for AI-assisted writing than a formal Draft → Review → Decision state machine.** The removed pipeline modeled writing as a sequence of discrete, versioned artifacts passing through an explicit approval gate — a shape borrowed from traditional document-review workflows. That shape adds process the product's actual single-researcher, iterative use case never needed: there is no separate reviewer role, no approval gate distinct from the same person continuing to write, and no real reason to force every revision through a named "review" step rather than simply continuing the conversation. Chat is both the natural interaction model users already bring to AI writing tools and a closer match to how research writing actually happens — iteratively, conversationally, without a formal sign-off between drafts.

3. **`Conversation`/`Message` were not newly designed for this — they generalize.** Both were already specified in the frozen model (§3.9–§3.10) as a secondary channel (e.g., user notes, clarifying exchanges) alongside the Draft/Review pipeline. This decision promotes them to the primary writing-generation mechanism; it does not introduce a new entity requiring its own schema-design review the way ADR-009's `Agent` did.

4. **Evidence grounding is preserved through a different mechanism, not dropped.** The removed pipeline's evidence-closure invariant (05 §19 invariant 2: every retrievable claim traces to source material) is now satisfied through `Message Context Link` (already specified, polymorphic, the same exclusive-arc pattern `Draft Evidence Link` used) rather than `Draft Evidence Link` specifically. The underlying product requirement — AI-generated writing must be traceable to real source material, never asserted ungrounded — is unchanged; only the entity carrying it changed.

5. **This correction updates the Database Baseline's entity and domain counts.** Removing four core entities and one link entity changes `04_Logical_Data_Model.md` §16's summary figures (twenty-six logical entities → twenty-one; twenty-one core/system → seventeen; five link entities → four) and `02_Domain_Model.md`'s domain inventory (thirteen domains → eleven, removing Draft and Review). Unlike ADR-010's correction, this is not a narrower change than ADR-009's — if anything it is larger in surface area, since Draft/Review references were woven through invariants, state tables, and relationship matrices across `02`, `03`, `04`, and `05`, not confined to a small number of self-contained sections.

6. **Scope of this correction pass.** This ADR, together with `08` §25, is the authoritative record of the decision and is fully accurate as of the date above. The high-value structural corrections — the entity/link definitions themselves (`04` §3.15–§3.18, §4.2), the summary counts (`04` §16), and the domain inventory (`02`) — are corrected in place by this same change. The remaining inline references to Draft/Review scattered through `02`'s domain narratives, `03`'s relationship catalogue, and `05`'s invariants, state tables, and candidate-key lists are **not** exhaustively corrected by this pass — see `08` §25's own "Documents corrected" section for the precise, honest accounting of what was and wasn't touched, and the open follow-up this leaves.

---

## Rationale

* **The product decision is sound on its own merits, independent of how late it was recorded.** A conversational writing surface is a better match for this product's actual single-researcher use case than a formal review-gate model borrowed from a different kind of workflow — see Decision item 2.
* **Writing this retroactively is strictly better than leaving it unrecorded.** The alternative — closing `Database_Human_Review_Materials.md` §3.2 as "no action" — would leave the single largest gap between the frozen baseline and the real system permanently undocumented, with the only trace of the decision being inferences from code comments.
* **Reusing already-specified entities (`Conversation`/`Message`/`Memory Record`/`Message Context Link`) rather than designing new ones kept the actual implementation change small**, even though the correction's documentation surface area is large — the same "additive, reuses what's proven" discipline ADR-011 applied to registration.

---

## Alternatives Considered

### Alternative 1: Treat the removal as already adequately recorded by the pivot note and Project_Status.md entry

**Rejected because:** both are status artifacts, not decision records — neither carries a rationale, neither is cross-referenced from the Database Baseline the way `04_Repository_Governance.md` §4.4 requires for an architecturally significant correction, and neither would be found by someone navigating the documentation hierarchy from `docs/READme.md` the way an ADR and a `08` correction section would be.

### Alternative 2: Reintroduce a Draft/Review layer on top of the chat model to restore baseline conformance

**Rejected because:** the chat/memory model is the real, working, validated product — proposing to add back a pipeline the product owner deliberately removed, in order to avoid writing a correction document, would be optimizing for baseline conformance over product reality, exactly backwards from what the baseline is supposed to serve.

### Alternative 3: A full, exhaustive line-by-line correction of every Draft/Review reference across `02`–`05` in this same pass

**Rejected for now because:** the actual reference surface (invariants, state tables, relationship matrices, candidate-key lists, tombstone-policy lists) is large enough that attempting it in one uninterrupted pass risked rushing dense formal prose and introducing new inconsistencies — a worse outcome than an honestly-scoped partial correction with a clearly flagged follow-up. See Decision item 6 and `08` §25.

---

## Consequences

### Positive

* The single largest flagged governance gap in the repository (`Database_Human_Review_Materials.md` §3.2) is closed.
* The Database Baseline's entity/domain counts are accurate again.
* Future readers encountering `Draft`/`Review` in `02`–`05`'s remaining uncorrected prose have an ADR and a `08` §25 section to find, rather than silence.

### Negative

* `02`, `03`, and `05` still contain inline Draft/Review references this pass did not reach (see Decision item 6) — a reader relying on those specific lines without also reading this ADR and `08` §25 could still be misled until the follow-up pass happens.
* As with ADR-011's email verification/password reset, this correction documents a decision after its consequences were already live in production — a process gap worth naming directly: **the project's own discipline (ADR before implementation) was not followed for this change**, and this ADR is a repair, not prevention.

### Neutral

* No code change results from this ADR — the chat/memory model has been in production since the original uncommitted session; this is a documentation-only correction.

---

## Repository Impact

* `docs/database/04_Logical_Data_Model.md`: `Draft` (§3.15), `Draft Version` (§3.16), `Review` (§3.17), `Review Decision` (§3.18), and `Draft Evidence Link` (§4.2) marked removed in place (section numbers preserved for cross-reference stability, not renumbered); §16 summary counts corrected.
* `docs/database/02_Domain_Model.md`: domain inventory corrected (Draft, Review removed; count thirteen → eleven).
* `docs/database/08_Database_Design_Review_and_Readiness_Assessment.md`: new §25 correction section, following §23/§24's own pattern.
* `docs/database/03_Conceptual_Data_Model.md`, `05_Constraints_and_Integrity.md`: reviewed; not exhaustively corrected in this pass (see Decision item 6, `08` §25).
* `docs/Baseline_Register.md`, `docs/READme.md`, `docs/Project_Status.md`: cross-reference additions for ADR-012.

---

## AI Engineering Implications

* No application code changes as a result of this ADR — `app/modules/writing/` already reflects the chat/memory model; this ADR documents what is already true of the running system.
* Any future work touching `02`, `03`, or `05`'s remaining uncorrected Draft/Review prose should complete that correction opportunistically rather than treating the partial state as permanent — see `08` §25's flagged follow-up.
* Any future removal of a previously-frozen entity should get an ADR *before* implementation, not after — this ADR's own existence is the counterexample to follow away from, not toward.

---

## Compliance Rules

* No code may reference `Draft`, `Draft Version`, `Review`, or `Review Decision` as live concepts going forward — they exist only as historical record in `08` §25 and this ADR.
* Evidence-grounding for AI-generated content continues to be enforced through `Message Context Link`, not reintroduced as a separate mechanism.

---

## Related ADRs

| ADR | Relationship |
|---|---|
| ADR-005 (Retrieval and Search Strategy) | The evidence-grounding invariant this ADR's Decision item 4 relies on is unchanged in substance, only in which entity carries it. |
| ADR-009 (Agent and Project Domain Model Introduction) | The precedent this ADR follows for a post-freeze correction's governance shape (ADR + `08` numbered correction section). |
| ADR-010 (Authentication Boundary — Single-User Session Model) | A second precedent for the same correction shape, narrower in scope than this one. |
| ADR-011 (Self-Service Registration and Multi-User Access) | Establishes the same "additive, reuses what's proven, no ADR required for every subsequent feature built the same shape" discipline this ADR's own Rationale cites for password reset/email verification. |

---

## Future Considerations

* **Complete the correction of `02`, `03`, and `05`'s remaining inline Draft/Review references**, opportunistically or as a dedicated pass — see `08` §25 for the specific list of what remains.
* **A process gap, not a design gap:** this ADR exists because a significant product decision was implemented without one. Future sessions making an architecturally significant change — especially a *removal* from a frozen baseline — should write the ADR before or during implementation, not months later during an unrelated review.

---

## References

* `docs/Database_Human_Review_Materials.md` §3.2 — the review that surfaced this gap and handed the decision to the project owner.
* `docs/Frontend_Implementation_Plan.md` — the original, informal "pivot note" (2026-09-18), the first written trace of this decision.
* `docs/adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md`, `docs/adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md` — the precedent this ADR's correction shape follows.
* `backend/app/modules/writing/application/chat.py` (`GenerateConversationReplyUseCase`'s docstring) — the plainest code-level statement that the removal happened.
