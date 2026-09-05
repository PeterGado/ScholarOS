# Database Design Review and Readiness Assessment

**Document:** 08_Database_Design_Review_and_Readiness_Assessment.md

**Status:** Active — Milestone Close-Out

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design (COMPLETE AND FROZEN)

**Revision:** 1

---

## 1. Purpose

This document is the **authoritative close-out document for the ScholarOS Database Design milestone**. It reviews the completed design set (01–08), assesses readiness for the next milestone, declares the completion and freeze of the database baseline, defines Database Baseline v1, and hands the design to API design and backend implementation.

It answers the question *"Is the database design complete, correct, consistent, and ready — and what exactly is being handed off?"*

**Authoritative Source Rule:** per [01_Database_Overview.md](01_Database_Overview.md) §12.2, this document treats Documents 01–07 as authoritative and does not duplicate their content; it references their decisions and adds the close-out level of detail.

---

## 2. Executive Summary

Milestone 5 — Database Design is **complete and frozen as Database Baseline v1**.

The milestone produced a layered, implementation-independent database design document set (01–08) under the Authoritative Source Rule:

* **01** — the milestone constitution: why the database exists, its boundaries, and the rules that govern the design.
* **02** — the Domain Model: the business language of ScholarOS (twelve domains).
* **03** — the Conceptual Data Model: nineteen conceptual entities, their relationships, cardinalities, bounded contexts, and business rules.
* **04** — the Logical Data Model: twenty-five logical entities, attributes, candidate keys, references, normalization, integrity, and versioning/audit strategies.
* **05** — Constraints and Integrity: the business-level integrity contract — state transitions, required/optional relationships, and thirteen domain invariants.
* **06** — Physical Design Strategy: the mapping of the logical model onto the four approved storage categories and the persistence, retention, archival, backup, recovery, and growth strategies.
* **07** — Database Validation and Quality Assurance: how the design is validated — review process, quality gates, acceptance criteria, and the defect catalog.
* **08** — this document: the review, readiness assessment, freeze declaration, and handoff.

The design is implementation-independent throughout: no SQL, DDL, migrations, index designs, engine selections, or ORM content. The frozen architecture (01–07) and ADR set (ADR-001 to ADR-007) were preserved untouched. All repository state artifacts are synchronized, and the milestone is declared complete and frozen per 04_Repository_Governance.md §4.4.

**Verdict: READY FOR API DESIGN.**

---

## 3. Database Architecture Summary

* **Domains (02):** Project, Research Document, Knowledge, Knowledge Chunk, Memory, Conversation, Writing Profile, Capability, Draft, Review, Configuration, User and Session, and Agent (thirteen domains as of ADR-009; see §23). Candidate concepts (Citations, Prompt Assets, Generated Responses, Version History, Capability Configurations, login Sessions) were validated out with rationale.
* **Conceptual model (03):** twenty entities as of ADR-009 (originally nineteen); ownership, containment, derivation, evidence, context, oversight, and configuration-governance relationships; composition vs. aggregation; one generalization (Traceable Record) and two subtypings; bounded contexts aligned to the backend domains.
* **Logical model (04):** twenty-six entities as of ADR-009 (originally twenty-five: twenty core/system, five link entities); surrogate identifiers; candidate keys; exclusive-arc link entities for polymorphic associations; 3NF baseline with documented deviations (EAV for configuration only, content references, explicit evidence links); soft-delete, versioning, audit, and naming strategies.
* **Integrity (05):** thirteen domain invariants; per-entity state-transition machines; required/conditional/optional relationship inventory; evidence-chain, knowledge-graph, memory, conversation, isolation, and audit rules.
* **Physical strategy (06):** class-by-access-pattern mapping onto the structured core, vector index, object store, and working cache; retention, archival, backup, recovery, growth, partitioning, indexing, caching, and scalability strategies — technology-neutral and ADR-aligned.

The design serves the product's core commitments: evidence-grounded research (evidence links are first-class), persistent project memory (a first-class domain, never reconstructed), author preservation (Writing Profile with provenance), human oversight (immutable Review Decisions), and continuity across sessions.

---

## 4. Readiness Assessment

| Dimension | Assessment |
|---|---|
| Design completeness | Complete — all eight layers produced, each extending its predecessors |
| Consistency | All cross-references verified; terminology stable; no contradictions with the frozen baseline |
| Traceability | All cited requirements, architecture sections, and ADRs verified; no invented references |
| Implementation independence | No SQL, DDL, migrations, indexes, engines, or ORM content in the set |
| Architecture conformance | Set is subordinate to the frozen architecture and ADR baseline; no reinterpretation |
| ADR conformance | Consistent with ADR-001 to ADR-007; no unrecorded storage decisions |
| Governance conformance | RSP-001 to RSP-007 executed; Engineering Reports and journal up to date; DoD satisfied |
| Backend readiness | A Senior Backend Engineer can begin physical schema design from 04–06 alone |
| API readiness | API design can begin from this document's handoff without database clarification |

**Verdict: READY FOR API DESIGN.** The database design milestone is complete and frozen.

---

## 5. Database Design Inventory

| Document | Title | Status |
|---|---|---|
| 01_Database_Overview.md | Database Overview (milestone constitution) | Active — Frozen (Database Baseline v1) |
| 02_Domain_Model.md | Domain Model | Active — Frozen (Database Baseline v1) |
| 03_Conceptual_Data_Model.md | Conceptual Data Model | Active — Frozen (Database Baseline v1) |
| 04_Logical_Data_Model.md | Logical Data Model | Active — Frozen (Database Baseline v1) |
| 05_Constraints_and_Integrity.md | Constraints and Integrity | Active — Frozen (Database Baseline v1) |
| 06_Physical_Design_Strategy.md | Physical Design Strategy | Active — Frozen (Database Baseline v1) |
| 07_Database_Validation_and_Quality_Assurance.md | Database Validation and Quality Assurance | Active — Frozen (Database Baseline v1) |
| 08_Database_Design_Review_and_Readiness_Assessment.md | Database Design Review and Readiness Assessment | Active — Frozen (Database Baseline v1) |

**Title confirmation:** Document titles 05–08 were confirmed on 2026-08-07 as listed above and recorded in the journal, per 01 §12.1 (titles may be adjusted without altering the layering). The layering itself — refinement (05, 06) then validation and close-out (07, 08) — is unchanged.

---

## 6. Traceability Summary

The design set preserves the chain Vision → SRS → Architecture → Database Design → (next) API Design → Implementation:

* **Vision** — continuity, evidence grounding, project memory, author preservation, human oversight.
* **SRS** — data domains and lifecycle (DR-001 to DR-035, DC-002, DC-003), AI persistence expectations (AIR-003 to AIR-068 ranges), workflows (WR-001 to WR-039 ranges), API boundary (API-001 to API-043), MVP scope (MVP-001 to MVP-028), quality attributes (NFR-001 to NFR-040).
* **Architecture** — conceptual domains and ownership (03), intelligence operating model (04), backend boundaries and data access layer (05), frontend expectations (06), storage/deployment/scalability (07).
* **ADRs** — ADR-001 (separation), ADR-002 (ORM abstraction), ADR-003 (modular monolith), ADR-004 (storage/memory), ADR-005 (retrieval/evidence), ADR-006 (async/outbox), ADR-007 (deployment).
* **Each database document** carries its own traceability section (01 §16, 02 §8, 03 §10, 04 §15, 05 §20, 06 §21, 07 §23, and this document).

Every citation was verified during validation (07 §6); no invented references exist in the set.

---

## 7. Architecture Alignment

* The design set is **subordinate to** the frozen architecture (01–07) and never reinterprets component boundaries, service responsibilities, storage categories, or operational assumptions (01 §6).
* The logical model is realizable behind the data access layer (API-032, API-033; 05 §16).
* The physical strategy maps onto the approved storage categories of 07 §3 without new storage decisions.
* The scalability invariants of 07 §5.2 (evidence grounding, memory architecture, provider abstraction, separation of concerns, human oversight) are preserved throughout.
* **No architecture deviations were introduced.** No architecture document or ADR was modified during this milestone.

---

## 8. ADR Alignment

| ADR | Alignment |
|---|---|
| ADR-001 | Design is an architecture concern; the design set contains no implementation artifacts; implementation must not redefine the model |
| ADR-002 | The logical model is expressible behind the ORM abstraction; validation occurs at the API boundary |
| ADR-003 | Per-module data ownership; cross-context references flow only through the data access layer |
| ADR-004 | Memory is a first-class persisted domain; storage categories and migration paths respected |
| ADR-005 | Chunk-level retrieval; evidence links first-class; embeddings keyed by chunk identity |
| ADR-006 | Durable outbox; idempotent, retryable work items; async coordination |
| ADR-007 | MVP deployment envelope respected; managed deployment path preserved |

No new storage or architectural decision was introduced by the design set; any future decision (e.g., multi-tenant isolation) requires a new ADR (01 §11.3; ADR-004 §Future Consideration 1).

---

## 9. Governance Alignment

* **Definition of Done (05):** requested work complete; requirements and architecture alignment verified; no undocumented functionality; Engineering Reports produced; journal updated; RSP-001 to RSP-007 executed and recorded.
* **Engineering Reports (06):** every milestone session produced a conforming report embedded in the journal.
* **Review process (07):** L1/L2/L3 and multi-pass role reviews executed; findings resolved before freeze.
* **Repository governance (04):** naming conventions followed; consistency rules applied; freeze recorded per §4.4.
* **Documentation standards (09):** headers, cross-references, no duplication, no placeholders.
* **Baseline Register:** Database Baseline v1 recorded in [../Baseline_Register.md](../Baseline_Register.md) as Frozen.

---

## 10. Outstanding Technical Debt

Debt accepted at milestone close-out, with its governing decision and the trigger for retirement:

| Debt | Accepted decision | Retirement trigger |
|---|---|---|
| SQLite write-concurrency ceiling | ADR-004 (single-writer MVP) | Multi-user stage (07 §5 stage 2) → PostgreSQL migration |
| Embedded vector index ceiling | ADR-004/ADR-005 | Chunk corpus or query concurrency exceeds the embedded envelope |
| EAV pattern for Configuration Item | 04 §6 deviation 1 | If configuration demands typed, queryable structure |
| Transitive document→element provenance (via chunk evidence chain) | 04 §5 mapping note | If direct element-to-document provenance becomes a requirement (recorded in the journal) |
| Embedded-index eventual consistency | ADR-006 | Surfaced via status states; no retirement needed |
| No automated citation management | SRS Ch10 out of scope | SRS Ch11 roadmap phase |

---

## 11. Deferred Decisions

Decisions intentionally deferred, each with the trigger that will resolve it:

| Decision | Deferred to | Trigger |
|---|---|---|
| Multi-tenant data isolation | Future ADR | SaaS stage (07 §5 stage 5) |
| Draft version branching | Future database/API refinement | A requirement for parallel draft variants |
| Cross-encoder reranking | Retrieval enhancement (SRS Ch11 Phase 7) | Retrieval quality requires it |
| Index inventory and partitioning layout | Implementation milestone | Schema realization begins |
| Retention windows and archival schedules | Implementation/operational design | Operations planning |
| RPO/RTO values | Implementation | Backup automation setup |
| Hard-delete mechanics | Archival policy (SRS Ch7 §4.4) | Archival stage |
| Knowledge-graph traversal/graph store | Future stage (KnowledgeGraph, SRS Ch11) | Cross-project knowledge |

Deferral is a deliberate design property: the logical model is structured so each deferred decision is additive, not a redesign (07 §5; ADR-004).

---

## 12. Future Database Evolution

* **Immediate next milestone (6 — API Design):** consumes this document's handoff (§21) to define contracts over the logical model.
* **Post-MVP stages (07 §5):** the storage categories persist; the concrete implementations migrate per ADR-004 (SQLite → PostgreSQL; embedded → dedicated vector store; local → S3-compatible object store; in-process → shared cache).
* **Tenancy:** workspace → organization → enterprise → infrastructure-level isolation, each an additive change behind the data access layer, each requiring a new ADR.
* **KnowledgeGraph capabilities:** cross-project knowledge (SRS Ch11) will extend the knowledge model; the design's explicit relationship entities (04 §3.6) provide the extension point.

---

## 13. Known Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Supersession direction change (resolved in 04) could be misread by a future reader | Implemented chain semantics could diverge from the document | Recorded in the journal and 05 §7; 05 §19 invariant 3 is the enforcement language |
| Forward references to 05–08 in frozen documents | Stale titles | Titles confirmed in this document §5 and the journal |
| No formal human L3 review yet | Milestone-level assurance rests on recorded AI review passes | A human architectural review is recommended before API design begins (07 §4) |
| SQLite→PostgreSQL migration is a documented, not executed, path | Migration friction at stage 2 | Data access layer (API-032/033) and ORM abstraction (ADR-002) bound the change |
| Retrieval quality unproven without empirical tuning | RAG quality risk | Golden query evaluation set during implementation (ADR-005) |

---

## 14. Recommendations

1. **Begin Milestone 6 (API Design)** using the handoff contract in §21; SRS Chapter 9 and 05_Backend_Architecture.md are the governing inputs.
2. **Conduct a human architectural review** of the database baseline (L3, 07_Review_Checklist.md) before or during early API design.
3. **Enforce the database baseline at implementation:** physical schema, indexes, and migrations must be traceable to 04–06; any divergence is a consistency violation (04 §5.3).
4. **Retire technical debt deliberately** at the triggers in §10, via new ADRs where architecturally significant.
5. **Maintain the Baseline Register** (§18) as future baselines (API Design, Implementation) are frozen.

---

## 15. Lessons Learned

* **Layered design is self-validating.** Cross-checking each layer against its predecessor caught real defects (supersession direction, soft-delete mismatch, entity classification) that any single-pass review missed.
* **Freeze discipline pays.** Recording decisions as layers (this set) rather than edits preserves the historical record and makes future change explicit.
* **State artifacts lag content.** Synchronizing Project Status, Timeline, journal, and indexes is part of the deliverable, not an afterthought (RSP-005).
* **Implementation independence is enforceable.** The design set contains no SQL or DDL because the boundary was checked at every gate (ADR-001; 07 §7).
* **Deferral is a design property, not procrastination.** Every deferred decision in §11 names its trigger, keeping the MVP lean without blocking the roadmap.

---

## 16. Milestone Completion Declaration

**Milestone 5 — Database Design is declared COMPLETE and FROZEN as Database Baseline v1 on 2026-08-07.**

The design set (01–08) satisfies the acceptance criteria of 07 §17; the Definition of Done (05) is met; the Engineering Reports and journal record the session history; and the repository state artifacts are synchronized. This declaration is recorded in the journal per 04 §4.4.

---

## 17. Freeze Declaration

Per 04_Repository_Governance.md §4.4, the **Database Design artifact set** (`docs/database/01` through `docs/database/08`) is **frozen**:

* The set shall not be modified except for **corrections**: typos, broken references, factual errors, and consistency fixes required by the review process.
* Architecturally significant change requires a **new ADR** or a new milestone that explicitly includes database revision in its scope.
* Freeze status is recorded in the journal and in the Baseline Register.
* Future milestone artifacts (e.g., `docs/api/`) are new documents, not edits to frozen ones.

---

## 18. Database Baseline v1 Definition

**Database Baseline v1** is the frozen set of database design documents produced by Milestone 5, recorded in the [Baseline Register](../Baseline_Register.md):

| Baseline | Status | Includes |
|---|---|---|
| Database Baseline v1 | **Frozen** (2026-08-07) | Database 01–08 (`docs/database/`) |

The baseline is the authoritative source for all database structure, constraints, lifecycle, and storage-philosophy decisions. Later milestones build on it; they do not redefine it.

---

## 19. Documents Included in the Baseline

* `docs/database/01_Database_Overview.md` — constitution
* `docs/database/02_Domain_Model.md` — business language
* `docs/database/03_Conceptual_Data_Model.md` — conceptual relationships
* `docs/database/04_Logical_Data_Model.md` — logical structure
* `docs/database/05_Constraints_and_Integrity.md` — integrity contract
* `docs/database/06_Physical_Design_Strategy.md` — physical strategy
* `docs/database/07_Database_Validation_and_Quality_Assurance.md` — validation apparatus
* `docs/database/08_Database_Design_Review_and_Readiness_Assessment.md` — close-out (this document)

---

## 20. Success Criteria for Milestone 6 (API Design)

Milestone 6 (API Design) may begin and will be considered well-founded when it:

1. Defines service contracts over the logical model of 04 (payloads reflect entities, identifiers, and relationships; API-041 to API-043).
2. Maps service boundaries to the bounded contexts of 03 §7 and the backend domains of 05 §4.
3. Respects the data access layer boundary (API-032, API-033) as the only persistence realization path.
4. Consumes the structural semantics of 04–05: draft versioning and review state, supersession chains, evidence links, configuration versioning, soft-delete semantics.
5. Exposes state transitions per 05 §5 (e.g., draft lifecycle, review decisions) without inventing new states.
6. Follows the naming conventions of 04 §13 in endpoint and payload vocabulary.
7. Preserves implementation independence (ADR-001): API contracts are defined before implementation and not determined by implementation convenience (API-042).
8. Reuses the handoff contract (§21) without requiring database clarification.

---

## 21. Database Handoff Report for Backend Engineers

The following is the operative contract that backend engineers will implement against. It summarizes — it does not replace — the referenced documents.

**What backend engineers will build against:**

1. **The logical model (04).** Twenty-five logical entities with surrogate identifiers, candidate keys, and references. Physical schema design begins from 04 §3–§5; naming conventions from 04 §13 are binding on schema and payloads.
2. **The integrity contract (05).** State transitions (05 §5), required/optional relationships (05 §6), and the thirteen domain invariants (05 §19) are the acceptance language for data-access behavior. Enforce at the data access layer and API boundary; never scatter through domain logic.
3. **The storage strategy (06).** Persist through the data access layer (API-032, API-033) only. Structured core: all relational state (SQLite for the MVP, PostgreSQL migration path — ADR-004). Vector index: chunk embeddings keyed by chunk identity (ADR-005). Object store: document content payloads and exports (content-addressed). Working cache: ephemeral, never a source of truth.
4. **The outbox (ADR-006; 04 §3.20).** Record Work Items durably in the same logical transaction as the state change they represent; process idempotently via `idempotency_key`.
5. **Evidence links (ADR-005; 04 §4.1–§4.2).** Immutable, append-only, non-cascading; retrieval and drafting must preserve the evidence path.
6. **Versioning and supersession (04 §11; 05 §7).** Draft Versions immutable with monotonic numbers; Memory and Knowledge supersession via predecessor references (the newer record references the record it supersedes); Configuration versioned with exactly one active per key.
7. **Soft delete (04 §10; 05 §15).** Tombstone Project, Research Document, Conversation, Writing Profile, Draft (`deleted_at`); exclude tombstones from active queries and API responses; never hard-delete history-bearing records.
8. **Isolation (05 §13).** All project-scoped references stay within the project; retrieval filters by project before ranking; the data access layer enforces the boundary.
9. **Engine migration path (ADR-004).** SQLite → PostgreSQL, embedded → dedicated vector store, local → S3-compatible object store are configuration- and data-layer changes behind the data access layer — never architecture changes.
10. **No shortcuts.** Schema, indexes, and migrations must be traceable to 04–06; implementation must not redefine the model (ADR-001; 04 §5.3).

---

## 22. Closing

The ScholarOS database design milestone is complete. The design set (01–08) is frozen as Database Baseline v1; the repository is synchronized; and the next milestone — API Design — can begin without requiring clarification of database structure, constraints, lifecycle, or storage philosophy, while fully preserving the separation of concerns established by ADR-001.

*Understand first. Build second.*

---

## 23. Post-Freeze Correction: ADR-009 (2026-09-04)

This section is appended after the original close-out (§1–§22, dated 2026-08-07) to record a subsequent, architecturally significant correction, per `04_Repository_Governance.md` §4.4. Sections 1–22 above are preserved as the historical record of the milestone's original close-out and are not rewritten; where later sections summarize entity/domain counts affected by this correction (§3, §5), those summaries were updated in place to remain accurate, with a pointer here for the full account. This does not reopen Milestone 6 (Backend Implementation, ratified 2026-09-04 per `docs/journal/2026-09-04.md`) — it corrects the database baseline that milestone builds against, before implementation code exists.

**What changed:** `ADR-009` introduced **Agent** as a new top-level entity — the user's permanent, specialized research workspace (1:1 with User in the MVP, 1:1 permanently with Project) — and narrowed **Project** to raw input material (identity, topic, Research Document ownership) nested inside its owning Agent. Knowledge, Knowledge Chunk, Memory Record, Conversation, Writing Profile, Draft, and Review moved from `project_id` scoping to `agent_id` scoping. The pre-existing capability-registry entities (previously named `Agent`/`Agent Capability`) were renamed to `Capability`/`Capability Entry` to free the name.

**Why:** a product clarification (recorded in `docs/journal/2026-09-04.md`) revealed that the frozen "Agent" entity (a system capability registry) collided with the project owner's actual user-facing "Agent" concept (a permanent workspace). The correction resolves the collision by renaming the registry and introducing the real workspace concept as a distinct, properly-scoped entity, reusing the already-reviewed Project aggregate rather than duplicating it.

**Documents corrected:** `02_Domain_Model.md`, `03_Conceptual_Data_Model.md`, `04_Logical_Data_Model.md`, `05_Constraints_and_Integrity.md`, `06_Physical_Design_Strategy.md` (mapping table and partitioning boundary only). `07_Database_Validation_and_Quality_Assurance.md` was reviewed and requires no substantive change — it defines the validation methodology, not entity-specific content.

**Updated readiness verdict:** the correction does not change the milestone's fundamental readiness — the design remains implementation-independent, internally consistent, and traceable. **Verdict: STILL READY FOR BACKEND IMPLEMENTATION**, now against the corrected model. A Senior Backend Engineer beginning physical schema design should build `agent_id` as the scoping key for Knowledge, Memory, Conversation, Writing Profile, Draft, and Review, and `project_id` only for Research Document, per the corrected `04_Logical_Data_Model.md` §3.3–§3.21.

**Outstanding technical debt and deferred decisions (§10–§11) are unaffected** by this correction, with one addition: multi-Agent-per-user (a monetization-gated future capability) joins §11's deferred-decisions list, deferred to a future ADR at the stage that requires it (`ADR-009` §Future Considerations).

**Governance record:** this correction is recorded in the journal (`docs/journal/2026-09-04.md`) and in `docs/Baseline_Register.md`, per `04_Repository_Governance.md` §4.4 and §5.3.
