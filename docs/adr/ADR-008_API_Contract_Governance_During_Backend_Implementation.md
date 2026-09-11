# ADR-008: API Contract Governance During Backend Implementation

**Status:** Accepted

**Date:** 2026-09-04

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (eighth ADR). Ratifies and supersedes the standalone "API Design (Milestone 6)" plan recorded, as of 2026-08-07, in `docs/Timeline.md` (Milestone 12 forward note), `docs/Project_Status.md`, `docs/Baseline_Register.md` (API Baseline v1 row), `docs/Traceability_Index.md`, and `docs/READme.md`.

---

## Status

**Accepted.** Following the Independent Repository Audit recorded in `docs/journal/2026-09-04.md`, this ADR ratifies the decision that ScholarOS is **READY FOR BACKEND IMPLEMENTATION** and that API Design does not require a standalone, pre-implementation documentation milestone (previously planned as a `docs/api/` set mirroring the Database Design milestone). It governs how API contracts (SRS Chapter 9; `05_Backend_Architecture.md`) are produced, reviewed, and kept traceable from this point forward.

---

## Context

* Database Baseline v1 (`docs/database/01`–`08`) was frozen 2026-08-07. Its close-out (`08_Database_Design_Review_and_Readiness_Assessment.md` §2, §4) declared **"READY FOR API DESIGN,"** treating API Design as the next standalone milestone — consistent with the lifecycle table in ADR-001 (`API Design | Architecture | API docs`).
* `docs/srs/09_API_Requirements.md` §3 explicitly delegates concrete API shape to a later phase: *"The architecture phase may combine, split, or reorganize these domains as needed... What is required is that each listed capability be available through some interface — not that each domain corresponds to a distinct service, endpoint group, or implementation module."* DC-001 (§4.2) makes the same delegation for storage-interface retrieval criteria.
* ADR-002 already selected **FastAPI + Pydantic v2** as the backend framework. This stack's defining characteristic is that typed request/response models are written as implementation code, and the API contract (an OpenAPI schema) is mechanically derived from that code rather than authored as a separate upstream artifact — a **code-first** API development model, as opposed to the **contract-first** model that motivates a standalone pre-implementation API specification.
* An Independent Repository Audit (`docs/journal/2026-09-04.md`) found that producing a separate `docs/api/` document set before any backend code exists would mean hand-authoring a contract that FastAPI regenerates automatically from real Pydantic models the moment implementation begins — introducing document/code drift risk without reducing implementation risk, since no second team or external consumer currently exists to justify a contract-first artifact produced ahead of code.
* This is a live, triggered decision (the Milestone 5 → Milestone 6 transition), not a speculative pre-milestone decision of the kind `ADR-007` §"Future Considerations" item 4 reserved and deferred (frontend technology selection, multi-tenant isolation, workflow-engine trigger, agent execution architecture, embedding provider routing). That reserve list is illustrative of candidate topics bound to their own future milestones; it is not exhaustive or exclusive, and it does not govern this differently-triggered topic.

---

## Problem

ScholarOS needs a decision, made once and recorded durably, on:

1. Whether "API Design" remains a discrete, gated documentation milestone (as Database Design was) before backend implementation may begin.
2. If not, how API contracts are still produced with enough rigor to satisfy API-042 (*"API contracts shall be defined before implementation and shall not be determined by implementation convenience"*) and remain traceable to SRS Chapter 9, the architecture set, the ADR set, and the database baseline.
3. Where the line falls between routine engineering authority over endpoint/schema shape and architecturally significant API decisions that still require ADR governance.

---

## Decision

1. **No standalone API Design milestone.** `docs/api/` is not populated with a static, pre-implementation document set. The "API Baseline v1" milestone previously planned in `docs/Baseline_Register.md` is superseded by this ADR and will not be produced as originally scoped.
2. **API contracts are defined progressively, as code, during backend implementation.** Each domain's Pydantic request/response models and FastAPI route definitions are the authoritative contract artifact for that capability, written before or alongside the route's business logic — satisfying API-042's contract-before-convenience intent through implementation discipline and code review rather than a separate document-review gate.
3. **FastAPI's generated OpenAPI schema is the living "API docs" artifact** referenced by ADR-001's lifecycle table, satisfying API-041 (technology-independent API description) without a hand-maintained duplicate that could drift from the real contract.
4. **Every API contract remains traceable.** Each domain's Pydantic model/route set must cite, in its implementation documentation, the SRS API-### capability it realizes, the architecture domain it belongs to (`05_Backend_Architecture.md`), and the database entity or entities it serves (`docs/database/04`, `05`).
5. **Architecturally significant API decisions still require ADR governance.** A new ADR is required before: introducing a second external-facing protocol or transport; changing the authentication/authorization model at the service boundary; adopting a versioning scheme that breaks existing contracts; or any decision that would alter the component/service boundaries defined in `05_Backend_Architecture.md` and ADR-003. Routine decisions — endpoint paths, request/response field naming, status-code choices, pagination shape, per-domain error detail — remain ordinary engineering authority, reviewable at L1/L2 per `07_Review_Checklist.md`, and do not require a new ADR.
6. **API Baseline v1 is redefined.** It will be recorded as part of **Implementation Baseline v1** at the first implementation milestone's close-out, not as its own separate frozen baseline.

---

## Rationale

1. **SRS Chapter 9 already made the necessary delegation.** The SRS's own authors classified API domain decomposition, protocol, and serialization as architecture/implementation-phase decisions (§3, DC-001). Treating that delegation as requiring yet another document before it can be exercised would contradict the SRS's own stated intent.
2. **The chosen stack is code-first by design.** ADR-002 selected FastAPI specifically because typed Python models double as both implementation and machine-readable contract. Producing a separate hand-written contract ahead of that code works against the stack's own value proposition rather than with it.
3. **No external consumer justifies contract-first discipline yet.** Contract-first API development earns its cost when independent teams build against a contract in parallel, or when external/public consumers cannot see the implementation. ScholarOS's MVP has one implementer and no external API consumer (frontend implementation is deferred; see `decision_01.md`).
4. **Governance is preserved, not removed.** This ADR does not eliminate API governance — it relocates the review gate from a document-review milestone to code review (L1/L2) for routine decisions, and explicitly preserves ADR-level review for architecturally significant ones (Decision item 5), consistent with ADR-001's separation-of-concerns rule.

---

## Alternatives Considered

### Alternative 1: Proceed with Milestone 6 as originally planned (an 8-document `docs/api/` set mirroring Database Design)

**Rejected because:** SRS Ch9 §3 and DC-001 already delegate the necessary decisions to the architecture/implementation phase; ADR-002's code-first framework choice makes a hand-written contract document immediately redundant with, and at risk of drifting from, the generated OpenAPI schema; no second team or external consumer exists yet to justify a contract produced ahead of code.

### Alternative 2: No API governance at all — leave all contract decisions to unreviewed engineer discretion

**Rejected because:** violates API-042 (contract-first mandate) and AIR-040 to AIR-042 (provider-abstraction consistency); would allow architecturally significant decisions (e.g., the authentication model) to be made silently without ADR review, contradicting ADR-001.

### Alternative 3: A short standalone "API Conventions" document produced before implementation begins

**Considered as a middle path; not adopted as a required gate.** SRS Ch9 already states the capability inventory and ADR-002 already fixes the framework; the remaining conventions (URL prefix, error envelope) are thin enough to record inside the first implementation session's engineering report rather than gating implementation on a new document. This ADR does not forbid an engineer from writing such a note — it only removes it as a prerequisite.

---

## Consequences

### Positive

1. Backend implementation can begin immediately; no additional documentation milestone stands between the frozen Database Baseline v1 and code.
2. No risk of a hand-written contract document drifting from the real, generated schema.
3. Keeps the project aligned with the code-first stack it already chose in ADR-002.
4. API governance is preserved for the decisions that matter (Decision item 5) rather than applied uniformly to routine ones.

### Negative

1. No static, human-reviewable API document exists before code is written; reviewers must read Pydantic models and route code to review contracts, rather than a design document.
2. Slightly less separation between architecture-level and implementation-level artifacts than the Database Design milestone had.

### Neutral

1. `docs/api/` remains a valid, reserved location for architecturally significant API documentation (for example, a future public/external API for institutional integration, per SRS Chapter 11 Phase 6) if and when that need arises. It is not deleted — only not populated as a prerequisite milestone now.

---

## Repository Impact

Supersedes the "API Design (Milestone 6)" plan recorded in `docs/Timeline.md` (Milestone 12 forward note), `docs/Project_Status.md`, `docs/Baseline_Register.md`, `docs/Traceability_Index.md`, and `docs/READme.md`. Those repository-state artifacts are synchronized separately per RSP-005 (see `docs/journal/2026-09-04.md`, Session 2). `docs/api/` remains an empty, reserved directory per `04_Repository_Governance.md` §2, to be populated only if a future architecturally significant API artifact is needed.

---

## AI Engineering Implications

AI engineers implementing backend capabilities must write Pydantic models and route definitions with the same rigor expected of a reviewed design artifact (per `02_AI_Engineering_Contract.md` §7), and must escalate to a new ADR — not decide silently — whenever a contract decision falls into the "architecturally significant" list in Decision item 5.

---

## Compliance Rules

Verified via `07_Review_Checklist.md` (L1/L2 code review covers routine contract decisions; L3 architectural review is required only for the Decision-item-5 escalation list) and `05_Definition_of_Done.md` §2.3 (Architecture Alignment) and §2.6 (Documentation — the generated OpenAPI schema satisfies the documentation requirement for public interfaces). Violations of the escalation rule are handled per `04_Repository_Governance.md` §5.3.

---

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-001 (Separation of Requirements, Architecture, and Implementation) | Accepted | Classifies API Design under the Architecture concern; this ADR clarifies how that concern is realized for ScholarOS's stack and scale without contradicting the separation rule. |
| ADR-002 (Technology Stack and Provider Abstraction) | Accepted | The FastAPI + Pydantic v2 code-first stack is the direct enabler of this decision. |
| ADR-003 (Service Organization — Modular Monolith) | Accepted | Domain/service boundaries are the trigger for the Decision-item-5 escalation to a new ADR. |
| ADR-010 (Authentication Boundary — Single-User Session Model) | Accepted | The authentication-model escalation this ADR's Decision item 5 requires — ADR-010 is that decision, not a silent code choice. |
| ADR-007 (Deployment Strategy) | Accepted | Establishes the ADR-discipline precedent this ADR follows: record a decision when its trigger arrives, not before. |

---

## Future Considerations

1. If ScholarOS reaches the institutional/multi-tenant stage (SRS Chapter 11, Phase 6) and needs a public, versioned, externally consumed API, a dedicated `docs/api/` specification (OpenAPI-derived and published) should be produced at that trigger. This ADR does not forbid it — it only removes it as an MVP prerequisite.
2. Candidate topics reserved in `ADR-007` §"Future Considerations" item 4 (frontend technology selection, multi-tenant isolation, workflow-engine trigger, agent execution architecture, embedding provider routing) remain unaffected by this ADR and will be recorded as ADR-009 and onward, in trigger order, as each is reached.

---

## References

* `docs/journal/2026-09-04.md` — Independent Repository Audit and ratification session
* SRS Chapter 9 — API-001 to API-043, DC-001
* `05_Backend_Architecture.md` — Service Boundary Layer, Domain Service Layer
* ADR-001 — Separation of Requirements, Architecture, and Implementation
* ADR-002 — Technology Stack and Provider Abstraction
* ADR-003 — Service Organization — Modular Monolith
* ADR-007 — Deployment Strategy
* `docs/database/08_Database_Design_Review_and_Readiness_Assessment.md` §21 — Database Handoff Report for Backend Engineers
