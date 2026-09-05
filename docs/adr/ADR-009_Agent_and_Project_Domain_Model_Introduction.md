# ADR-009: Agent and Project Domain Model Introduction

**Status:** Accepted

**Date:** 2026-09-04

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (ninth ADR). Records an architecturally significant correction to the frozen **Database Baseline v1** (`docs/database/01`–`08`) and the frozen **Architecture Baseline v1** (`docs/architecture/01`–`07`), per `04_Repository_Governance.md` §4.4 ("architecturally significant change requires a new ADR or a new milestone that explicitly includes database revision in its scope"). This ADR is that new ADR.

---

## Status

**Accepted.** Following product clarification from the project owner, this ADR introduces **Agent** as a new top-level domain entity, narrows the scope of the existing **Project** entity to nest inside it, and renames the existing capability-registry entities (previously named `Agent` / `Agent Capability`) to **Capability** / **Capability Entry** to free the name. It governs the correction of Database Baseline v1 and Architecture Baseline v1 that follows this ADR.

---

## Context

The product's actual user-facing model, clarified directly by the project owner, is:

1. A user creates an **Agent** by providing a research/thesis topic, similar-project reference documents, and writing-style documents.
2. The Agent becomes the user's permanent, specialized research workspace — it never changes topic and is never replaced.
3. **MVP constraint:** one user → one Agent (strictly 1:1). Additional Agents per user are a future, monetization-gated capability (paid/premium tiers) — not an MVP requirement, and not built now.
4. The Agent's knowledge consists of: the project/topic material, uploaded reference documents, writing-style knowledge, accumulated system/AI knowledge, and preserved memory — i.e., everything the system learns and remembers over the Agent's lifetime.
5. **Project**, in the project owner's model, is the narrower concept: the specific research undertaking's raw material — its topic and the source documents supplied for it. An Agent owns exactly one Project, permanently; the Project is never swapped or replaced under the same Agent.

This does not match the frozen baseline as written. Three independent frozen documents — `docs/database/02_Domain_Model.md` §4.8, `docs/architecture/04_AI_Architecture.md` §14, and `docs/architecture/05_Backend_Architecture.md` §4.1/§13 — already define **"Agent"** as *"the catalog of intelligence capabilities"*: a system-managed registry of what the AI can do (knowledge processing, retrieval, drafting, review, coordination), not a user-owned workspace. `ADR-003` additionally names "Agent" as one of the modular monolith's seven hard module boundaries, in that same capability-registry sense.

Meanwhile, the frozen `Project` entity (`docs/database/04_Logical_Data_Model.md` §3.3) already owns everything the project owner described as belonging to the new "Agent" concept: `topic`, and (via relationships) Research Document, Knowledge, Knowledge Chunk, Memory Record, Conversation, Writing Profile, Draft, and Review.

This is a genuine naming collision, not a cosmetic one, and it was surfaced and resolved through a structured clarification process (recorded in `docs/journal/2026-09-04.md`) before this ADR was written, consistent with `ADR-007`'s stated discipline: *"record a decision when its trigger arrives, not before."* The trigger arrived when Stage 1 implementation planning required a real answer to "where does the workspace concept live."

---

## Problem

ScholarOS needs a data model that:

1. Introduces the user's permanent, specialized workspace (**Agent**) as a real, distinct entity — not a renaming of Project, and not a second thing confusingly sharing Project's name.
2. Preserves **Project** as a real, separate, nested entity representing the raw input material (topic + Research Documents) that an Agent is built around.
3. Frees the name "Agent" from its existing meaning (the capability registry) without losing that registry's function, by renaming it to something that doesn't collide.
4. Records the one-Agent-per-user MVP constraint as an explicit, testable invariant — not an implicit assumption.
5. Does all of this as an **additive, traceable correction** to the frozen baselines, not a silent rewrite — per `04_Repository_Governance.md` §4.4 and the correction discipline already used elsewhere in this repository (e.g., the five review findings resolved in `04_Logical_Data_Model.md` during Milestone 5, and the SRS-header housekeeping item recorded in `Baseline_Register.md`).

---

## Decision

1. **Agent is a new top-level entity.** Agent is owned by exactly one User (1:1 for MVP; multi-Agent-per-user is a documented future capability gated by monetization policy, not built now) and owns exactly one Project (1:1, permanent — the pairing never changes for the life of the Agent).
2. **Agent absorbs everything currently scoped to Project except the raw input material.** Knowledge, Knowledge Chunk, Memory Record, Conversation (+ Message), Writing Profile (+ Profile Characteristic), Draft (+ Draft Version), and Review (+ Review Decision) move from being scoped to `project_id` to being scoped to `agent_id`.
3. **Project's scope narrows to identity, topic, lifecycle, and raw source material.** Project retains: its identifier, `topic` (the single source of truth for the Agent's specialization — Agent does not carry its own copy), lifecycle status, and ownership of Research Document. Project no longer owns Knowledge, Memory, Conversation, Writing Profile, Draft, or Review.
4. **The existing capability-registry entities are renamed to free the name.** `Agent` → `Capability`; `Agent Capability` → `Capability Entry`. Their meaning, behavior, and every requirement/architecture reference to "the catalog of intelligence capabilities" is unchanged — only the name changes, throughout the Database Baseline, the Architecture Baseline, and ADR-003's module-boundary list.
5. **The one-Agent-per-user rule is a new domain invariant**, enforced at the application/data-access layer (a uniqueness constraint on `Agent.user_id` for the MVP), not merely assumed. It is recorded as an MVP-scope constraint (comparable to other `MVP-###` limits in SRS Chapter 10), not a permanent architectural ceiling — the future multi-Agent capability is a documented, deferred extension, additive to this model.
6. **This is realized as a correction, not a rewrite,** per `04_Repository_Governance.md` §4.4: existing document numbering, section anchors, and cross-references are preserved wherever possible; new content is added (new domain/entity sections) rather than renumbering existing ones; renamed content is relabeled in place.

---

## Rationale

1. **The collision was real, not stylistic.** Three frozen documents and one frozen ADR independently define "Agent" as the capability registry. Reusing the name for the workspace concept without renaming the registry would have produced two incompatible meanings for the same word inside one bounded context — the exact failure mode `ADR-001`'s separation-of-concerns rule and `ADR-003`'s module-boundary discipline exist to prevent.
2. **Project already modeled almost everything the project owner described as "Agent."** Rather than inventing new entities from nothing, this ADR reuses the fully-specified, already-reviewed `Project` aggregate and its dependents, and inserts one new ownership layer above it. This is the minimum structural change that satisfies the product clarification.
3. **Keeping Project separate (rather than renaming it to Agent) was an explicit product decision**, not an architectural default: the project owner distinguished "the documents and topic" (Project) from "the accumulated intelligence built around them" (Agent) as two things worth naming separately, most likely because a future capability (documented here as deferred, not built) may let a paid Agent's underlying Project material evolve or be supplemented while the Agent's accumulated memory and voice persist. Modeling them as two entities now, rather than conflating them, keeps that future path additive instead of requiring a later split.
4. **Renaming the registry to "Capability" costs nothing semantically.** Every existing requirement (AIR-058 to AIR-060) and architecture section (`04_AI_Architecture.md` §14) already describes the registry in capability terms ("catalog of intelligence capabilities," "capability entries," "capability selection") — "Capability" is the term the documents were already using descriptively; only the entity's formal name changes.
5. **A uniqueness constraint, not a schema redesign, enforces one-Agent-per-user.** The MVP constraint is expressed as `Agent.user_id` being a candidate key (at most one Agent per User), which is additive to the existing model, consistent with the Database Baseline's own stated design property (`08` §11: *"the logical model is structured so each deferred decision is additive, not a redesign"*).

---

## Alternatives Considered

### Alternative 1: Rename Project to Agent; no second entity

**Rejected because:** the project owner explicitly distinguished "the documents and topic" from "the accumulated intelligence built on top of them" as two separate things worth keeping separate, particularly given the deferred future capability of an Agent's Project material evolving independently of its accumulated memory/voice. A single renamed entity would have to be split back into two later, at higher cost.

### Alternative 2: Treat "Agent" as a pure UI/product label over Project, with no backend or database change

**Rejected because:** the project owner's description of Agent's scope (owning Draft, Review, and Writing Profile in addition to Knowledge/Memory/Conversation) and the explicit 1:1-then-monetization-gated-N cardinality are real, testable structural properties — not presentation choices. A UI-only label would leave the one-Agent-per-user rule unenforced and the future multi-Agent capability unmodeled.

### Alternative 3: Leave the capability registry named "Agent" and give the new workspace concept a different name (e.g., "Workspace")

**Considered, not adopted:** the project owner's own vocabulary consistently uses "Agent" for the workspace concept, and renaming the *newer, less-embedded* registry concept (introduced in the AI Architecture, not yet implemented in any code) is lower-cost than working against the project owner's established terminology going forward, provided the registry's rename ("Capability") is itself accurate and non-disruptive — which it is, per Rationale 4.

---

## Consequences

### Positive

1. The product's real user-facing model (Agent as permanent workspace) now has an accurate, unambiguous home in the frozen baseline, resolving an ambiguity that would otherwise have been decided ad hoc during implementation.
2. The capability registry keeps its function under a name ("Capability") that no longer collides with anything.
3. The one-Agent-per-user MVP rule is now an explicit, enforceable invariant rather than an implicit assumption never written down.
4. The correction is additive: existing entities (Project and its remaining dependents, the renamed Capability registry) keep their attributes, keys, and most of their relationships — only their ownership scope and name change.

### Negative

1. Every FK currently pointing at `project_id` on Knowledge Element, Knowledge Chunk, Memory Record, Conversation, Writing Profile, and Draft must be re-pointed to `agent_id` — a real, non-trivial correction across the Logical Data Model, Constraints and Integrity document, and the traceability sections of both.
2. This is the first time Database Baseline v1 has been reopened for an architecturally significant change since its freeze (2026-08-07) — the Baseline Register must record this honestly as a revision, not pretend the baseline was never touched.
3. `Configuration Item`'s `project` scope value is renamed to `agent` scope, since project-level configuration nested under an Agent is more naturally agent-scoped (project no longer owns Knowledge/Memory/Drafting, the primary consumers of workflow configuration).

### Neutral

1. No storage-engine, retrieval-strategy, async-processing, or deployment decision changes — ADR-002, ADR-004, ADR-005, ADR-006, and ADR-007 are unaffected by this correction; Agent and its dependents live in the same structured-core storage category as everything else (07 §3.2).

---

## Repository Impact

This ADR authorizes and governs corrections to:

* **Database Baseline v1:** `docs/database/02_Domain_Model.md`, `03_Conceptual_Data_Model.md`, `04_Logical_Data_Model.md`, `05_Constraints_and_Integrity.md`, `06_Physical_Design_Strategy.md` (mapping table only), and an addendum to `08_Database_Design_Review_and_Readiness_Assessment.md`.
* **Architecture Baseline v1:** `docs/architecture/02_System_Components.md`, `03_Data_Architecture.md`, `04_AI_Architecture.md`, `05_Backend_Architecture.md` (terminology corrections; no layering or component-count change).
* **ADR-003:** a cross-reference correction only (its module-boundary list renames "Agent" to "Capability" and gains "Agent" as a new module boundary); its substantive modular-monolith decision is unchanged.
* **Requirements Baseline v1:** SRS Chapter 7 (Data Requirements) and Chapter 10 (MVP Scope) gain the Agent concept and the one-Agent-per-user constraint.
* **`docs/Baseline_Register.md`:** records this reopening against Database Baseline v1 and Architecture Baseline v1, per the register's own "Reading Guide."

All corrections preserve existing section numbering and cross-reference anchors wherever possible; new content is appended rather than inserted mid-document, to avoid invalidating existing citations elsewhere in the repository.

---

## AI Engineering Implications

Any future session implementing backend code must build against `agent_id` as the scoping key for Knowledge, Memory, Conversation, Writing Profile, Draft, and Review, and against `project_id` only for Research Document. The renamed `Capability`/`Capability Entry` entities must be used in all new code; no new code may introduce `Agent`/`Agent Capability` in the capability-registry sense.

---

## Compliance Rules

Verified through the standard processes: `07_Review_Checklist.md` (L3 architectural review, required for database/architecture-affecting changes) and `05_Definition_of_Done.md` §2.3 (Architecture Alignment) and §2.8 (No Contradictions — this correction must leave no document contradicting another). The correction is recorded in the journal and the Baseline Register per `04_Repository_Governance.md` §4.4 and §5.3.

---

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-001 (Separation of Concerns) | Accepted | This correction stays within the Architecture concern (per ADR-001's Development Lifecycle Integration table: Database Design is an architecture concern); it does not touch implementation. |
| ADR-003 (Modular Monolith) | Accepted | Gains "Agent" as an eighth hard module boundary; its existing "Agent" boundary is renamed "Capability." The modular-monolith decision itself is unchanged. |
| ADR-004 (Storage and Memory Strategy) | Accepted | Unaffected — Agent and its dependents use the same structured-core storage category and the same memory-persistence decision (Decision 6). |
| ADR-005 (Retrieval and Search Strategy) | Accepted | Unaffected in mechanism; retrieval's project-scope filtering (ADR-005 §Decision 3) becomes agent-scope filtering, since Knowledge Chunk now scopes to `agent_id`. |
| ADR-008 (API Contract Governance) | Accepted | Unaffected — API contracts realizing this corrected model are still defined progressively during implementation, per ADR-008. |

---

## Future Considerations

1. **Multi-Agent-per-user (paid/premium tiers).** Deferred, monetization-gated. When triggered, the `Agent.user_id` uniqueness constraint is relaxed (an additive change, not a redesign), and a plan/entitlement model determines how many Agents a user may hold.
2. **Project replacement under an existing Agent.** Explicitly not modeled now (the pairing is permanent per this ADR's Decision 1) — if a future requirement allows an Agent's underlying Project to be superseded (e.g., a thesis topic pivot that preserves accumulated memory), that is a new ADR, not an assumption to build in now.
3. **Agent-level configuration scope.** The `Configuration Item` scope enum value renamed from `project` to `agent` in this correction; if project-specific configuration independent of the owning Agent is later needed, that is an additive future decision.

---

## References

* `docs/journal/2026-09-04.md` — the clarification process that produced this decision
* `docs/database/02_Domain_Model.md`, `04_Logical_Data_Model.md` — the entities corrected by this ADR
* `docs/architecture/04_AI_Architecture.md` §14, `05_Backend_Architecture.md` §4.1, §13 — the capability-registry sections renamed by this ADR
* ADR-001, ADR-003, ADR-004, ADR-005, ADR-008
* `04_Repository_Governance.md` §4.4 — the correction/reopening discipline this ADR follows
