# Constraints and Integrity

**Document:** 05_Constraints_and_Integrity.md

**Status:** Active

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design

**Revision:** 1

---

## 1. Purpose

This document defines the **complete business-level integrity contract** of ScholarOS: every rule that protects the coherence, traceability, and correctness of persisted data. It answers the question *"What rules keep ScholarOS data valid at all times?"*

It is the fifth layer of the database design document set ([01_Database_Overview.md](01_Database_Overview.md) §12). Document 03 declared the business rules (§8 of 03); Document 04 established the structural constraints, nullability, integrity, and soft-delete strategies (§7–§10 of 04). This document refines those layers into the operational integrity contract: entity state-transition machines, a required/optional relationship inventory, concern-organized integrity rules, and the domain invariants that must always hold. It does not duplicate 03 or 04 — it references their decisions and adds the level of detail they intentionally deferred.

This document is **implementation-independent**:

* Every rule is stated as a business invariant, not as DDL.
* It does **not** produce SQL, CHECK constraints, triggers, or any realization artifact.
* Enforcement is realized through the data access layer (API-032, API-033) and the later API design and implementation milestones, per [01 §11.2](01_Database_Overview.md) and ADR-001.

**Authoritative Source Rule:** per [01 §12.2](01_Database_Overview.md), this document treats Documents 01–04 as authoritative, uses their vocabulary, extends the design, and does not duplicate their content.

---

## 2. Integrity Principles

The integrity contract is governed by the quality attributes of [01 §10](01_Database_Overview.md) — Integrity, Traceability, Consistency, Continuity, and Reviewability — operationalized as follows:

1. **Every rule is a business invariant.** A rule is expressed in the language of the product (projects, conversations, evidence, memory), never in engine vocabulary. Realization (SQL, constraints, application logic) is a later concern.
2. **Rules are declared once.** The same rule is never restated in multiple documents; later documents reference the section that owns it. This document owns the integrity contract; 03 §8 owns business rules; 04 §7–§10 own the structural form.
3. **Consistency is graded, not uniform.** Strong consistency applies where correctness depends on ordering or exclusivity (project lifecycle, message ordering, memory updates); eventual consistency is accepted for derived artifacts (retrieval indexes, summaries) per 07 §3.3 and ADR-006. *(Previously "draft versioning, review state" — ADR-012, see `08` §25.)*
4. **Enforcement happens at boundaries.** Integrity is enforced at the data access layer and the API contract boundary (ADR-002, ADR-003), never scattered through domain logic.
5. **History is never rewritten.** Where a record must change meaningfully, the model uses immutability and supersession — never destructive update-in-place (DR-014, DR-017).

---

## 3. Business Constraints

The business rules of [03 §8](03_Conceptual_Data_Model.md) are authoritative. This section realizes each as an integrity obligation and adds the rule-level constraints that bind every domain:

| Business rule (03 §8) | Integrity obligation | Governing reference |
|---|---|---|
| 1. Understand before generate | A reply is generated only after context assembly has completed for that target; generation implies a sufficient context record exists. *(Previously stated in terms of Draft states — ADR-012, see `08` §25.)* | AIR-031; 04 §20.1 |
| 2. Evidence before assertion | Every Knowledge Element and Knowledge Chunk is reachable from source material through evidence links; content without an evidence path is not retrievable as supported. *(Draft Version carried this too before ADR-012.)* | AIR-024, AIR-027, AIR-046 to AIR-048; ADR-005; DR-008, DR-018 |
| 3. Artifact distinction | Raw input (Messages), interpreted knowledge (Elements/Chunks), and stored memory (Memory Records) remain distinguishable at all times. *(Approved output, previously "Draft Versions," has no successor category since ADR-012.)* | AIR-006; 04 §2.2 entity families |
| 4. Memory is user-aware | Memory Records are populated only through user input or approved outcomes; the system never infers memory without user awareness. | MVP-011; 04 §8.2; DR-013 |
| ~~5. Review is user-owned~~ | **REMOVED by ADR-012** (2026-10-09, see `08` §25) — no successor rule. | — |
| 6. Supersession retains history | A superseded record remains traceable; its chain is never rewritten. | DR-014; 04 §7, §9, §11 |
| 7. Evidence is retained | Research Documents are retained for the life of the project or until explicitly removed; removal preserves the integrity of referencing data. | 07 §3.4; 05 §10; DR-025 |
| 8. Conversation outcomes require approval | Conversation content is a continuity record; it becomes memory only when approved and entered with user awareness. | 03 §3.6; AIR-006; MVP-011 |
| 9. Single-user scoping in the MVP | All project data is scoped to a single authenticated user in the MVP; tenancy decisions are deferred. | SRS Ch10; WR-038; 07 §5 |
| 10. One Agent per user in the MVP | A user owns exactly one Agent; additional Agents per user are a deferred, monetization-gated capability, not an MVP requirement. | ADR-009 |

**Rule-level constraints (additional, structural):**

* **Project-scoping.** Every project-scoped record carries a reference to exactly one Project, and no reference may cross project boundaries (§13).
* **No orphaned data.** No record may reference a non-existent record (DR-028) and no record may exist solely to satisfy a reference that has no business meaning.
* **Single ownership of identity.** Identifiers are system-assigned and never reused (04 §7).
* **No derived truth.** State that can be derived from other state is never stored as an independent source of truth (04 §8; §7 below).

---

## 4. Referential Integrity Principles

Document 04 §9 defines referential integrity at the structural level. The principles governing it:

* **Every reference is valid.** A reference must resolve to an existing, non-tombstoned record within the same project boundary (DR-028; §13).
* **Evidence links are immutable and non-cascading.** Chunk Evidence Links (and, before ADR-012 removed it, Draft Evidence Links) are never modified after creation and are never cascade-deleted; removing an evidence target (soft or hard) does not remove the links that reference it, preserving the audit record (ADR-005; 07 §3.4).
* **Composition cascades only where ownership is exclusive.** Messages are removed with their Conversation, and only under the documented retention/deletion policy (03 §5; 04 §9). *(Draft Versions were removed with their Draft the same way, before ADR-012 — see `08` §25.)* Every other reference is **restrict**: the referenced record may not be removed while referenced.
* **Deletion preserves integrity.** Soft-deleting a record retains its identity and its links; remaining data never points into the void (DR-025).
* **One boundary.** All referential integrity is realized behind the data access layer (API-032, API-033); no component may bypass it.

---

## 5. Lifecycle Constraints and Entity State Transitions

Each entity's status is an enumerated value from its logical definition (04 §3). The following transitions are the only permitted ones; any other transition is a design violation:

| Entity | States (04) | Permitted transitions | Immutable after |
|---|---|---|---|
| User | active / suspended | active → suspended; suspended → active | — (account identity never removed) |
| Session | started (open) / ended | open → ended | session_token; start time |
| Agent | active / archived | active → archived | agent_id; user_id (ADR-009) |
| Project | active / closed / archived | active → closed; active → archived; closed → archived | project_id; topic; agent_id (ADR-009) |
| Research Document | pending / processing / processed / failed | pending → processing; processing → processed; processing → failed; failed → processing (retry) | ingested_at; content reference |
| Knowledge Element | current / superseded | current → superseded (only forward) | content; created_by |
| Knowledge Element Relationship | — (immutable link) | — | created once; never modified |
| Knowledge Chunk | current / superseded | current → superseded (only forward) | content; element derivation |
| Memory Record | current / superseded | current → superseded (only forward) | content; created_by |
| Conversation | active / summarized / retained | active → summarized; active → retained; summarized → retained | started_at |
| Message | — | — | sequence; direction; content |
| Writing Profile | active / inactive | active → inactive; inactive → active | created_at |
| Profile Characteristic | — | — | signal; characteristic_type |
| Capability | registered / active / retired | registered → active; active → retired; registered → retired | name |
| Capability Entry | enabled / disabled | enabled → disabled; disabled → enabled | capability_name |
| ~~Draft~~ | ~~drafting / in_review / approved / superseded~~ | **REMOVED by ADR-012** (2026-10-09, see `08` §25) | — |
| ~~Draft Version~~ | — | **REMOVED by ADR-012** alongside Draft | — |
| ~~Review~~ | ~~open / decided~~ | **REMOVED by ADR-012** — no successor | — |
| ~~Review Decision~~ | — | **REMOVED by ADR-012** alongside Review | — |
| Configuration Item | active / historical | active → historical (when a newer version is created) | config_key; changed_by |
| Work Item | queued / running / succeeded / failed | queued → running; running → succeeded; running → failed; failed → queued (bounded retry) | idempotency_key |
| Evidence/context link entities | — (immutable) | — | target reference; created_by |

**Table corrected by ADR-009:** Agent added; Capability/Capability Entry renamed from Agent/Agent Capability. **Further corrected by ADR-012 (2026-10-09, see `08` §25):** Draft, Draft Version, Review, Review Decision rows removed (rows preserved, not deleted, for cross-reference stability).

**Lifecycle rules:**

* Transitions are forward-only for history-bearing entities (Knowledge Element, Knowledge Chunk, Memory Record): once superseded, a record is read-only (04 §9, §11).
* A Research Document in `failed` processing state is retained for diagnostics; retry re-enters `processing`.
* Supersession writes are atomic: creating a record that supersedes an earlier one updates the new record's predecessor reference and the predecessor's status in the same logical transaction (04 §9).
* A Session ends when `ended_at` is set; no state change occurs after that.

---

## 6. Required and Optional Relationships

Relationships are classified into three integrity categories, consistent with the nullability principles of [04 §8](04_Logical_Data_Model.md):

**Mandatory (the reference must always be present):**

| Child | Mandatory reference |
|---|---|
| Session | user_id |
| Agent | user_id *(added — ADR-009)* |
| Project | agent_id *(renamed from `user_id` — ADR-009)* |
| Research Document | project_id |
| Knowledge Element | agent_id *(renamed from `project_id` — ADR-009)* |
| Knowledge Chunk | agent_id, element_id *(renamed from `project_id` — ADR-009)* |
| Memory Record | agent_id *(renamed from `project_id` — ADR-009)* |
| Conversation | agent_id *(renamed from `project_id` — ADR-009)* |
| Message | conversation_id |
| Writing Profile | agent_id, user_id *(renamed from `project_id` — ADR-009)* |
| Profile Characteristic | profile_id |
| Capability Entry | capability_id *(renamed from Agent Capability/`agent_id` — ADR-009)* |
| Chunk Evidence Link | chunk_id, document_id |
| Knowledge Element Relationship | element_from_id, element_to_id |
| Profile Characteristic Source | characteristic_id, document_id |
| Configuration Item | (scope-owner references are conditional — see below) |

*Rows removed by ADR-012 (2026-10-09, see `08` §25): Draft (agent_id), Draft Version (draft_id), Review (draft_version_id), Review Decision (review_id, decided_by).*

**Conditional (structural members — exactly one is set, per the exclusive arc):**

| Link entity | Condition |
|---|---|
| Memory Provenance Link | exactly one of conversation_id / element_id / document_id, consistent with source_type *(review_decision_id was also a valid source before ADR-012 removed Review Decision — see `08` §25)* |
| Message Context Link | exactly one of document_id / element_id / chunk_id / memory_record_id, consistent with target_type *(draft_version_id was also a valid target before ADR-012)* |
| Configuration Item | agent_id set iff scope = agent; user_id set iff scope = user *(renamed from `project_id`/scope = project — ADR-009)* |

*Row removed by ADR-012: Draft Evidence Link (exactly one of chunk_id / document_id, consistent with target_type).*

**Optional (null only when genuinely absent):**

| Entity | Optional references |
|---|---|
| Project | — |
| Research Document | author, source (unknown origin) |
| Knowledge Element | superseded_element_id, superseded_at (absent while current) |
| Memory Record | superseded_record_id, superseded_at (absent while current) |
| Conversation | summarized_at (absent until summarized) |
| Message | origin (absent for user messages) |
| Work Item | executed_at, completed_at, last_error (state-dependent) |
| Session | ended_at, last_active_at (state-dependent) |
| User | display_name |

Optional references are never placeholders: null means "genuinely absent or not yet occurred", never "unknown placeholder" (04 §8).

**Actor references** (`created_by`, `changed_by`, `decided_by`) are not domain relationships; they are mandatory where the baseline requires actor traceability (AIR-054, DR-021; 04 §8, §12).

---

## 7. Version Integrity

* ~~**Draft Versions — immutable chains.**~~ **REMOVED by ADR-012** (2026-10-09, see `08` §25) — Message content within a Conversation is immutable per-message (04 §10), the successor concept, but is not versioned the way Draft Version was; there is no chain to maintain integrity over.
* **Memory Records — supersession chains.** Evolving decisions create a new record that references its predecessor via `superseded_record_id`; chronology and history are retained (DR-014; 04 §8.2, §11).
* **Knowledge Elements and Chunks — supersession with retained history.** New evidence creates a successor; the superseded record remains traceable (07 §3.3; AIR-065). Re-chunking is coordinated by the knowledge pipeline (ADR-005, ADR-006).
* **Configuration Items — versioned on change.** Every change appends a new version; exactly one version is active per (scope, owner, key) (DR-021).
* **Conversations — compaction, not versioning.** Conversations may be summarized and linked to memory rather than versioned (03 §3.6).
* **Not versioned:** User, Session, Project, Agent, Capability, Capability Entry, Work Item — these are state machines, not versioned content (04 §11). *(Capability/Capability Entry renamed, and Agent added, by ADR-009.)*

**Chain rules:** supersession chains are monotonic and acyclic; at most one record may reference a given record as its predecessor (one active successor per record, 04 §7); a superseded record becomes read-only (04 §9).

---

## 8. Citation Integrity

Citation and evidence integrity is the product's traceability backbone (ADR-001, ADR-005):

* **Every retrievable claim carries an evidence path.** Knowledge Elements and Knowledge Chunks must be reachable from source material through evidence links; retrieval never returns content without its evidence path (AIR-046 to AIR-048; ADR-005 §Decision 3). *(Draft Versions carried this too before ADR-012 removed Draft — see `08` §25.)*
* **Evidence links are immutable and append-only.** Chunk Evidence Links are never modified, never cascade-deleted, and never rewritten when a target is superseded (04 §9). *(Draft Evidence Links were governed by the same rule before ADR-012.)*
* ~~**Draft annotations are preserved per version.**~~ **REMOVED by ADR-012** — evidence annotations are now carried by Message Context Link per message, not per draft version; there is no per-version annotation set to preserve.
* ~~**Evidence targets respect Agent/Project isolation.** A Draft Evidence Link may target only chunks and documents within the same Agent~~ — **superseded by ADR-012**: evidence targets now respect Agent/Project isolation via Message Context Link instead, same underlying rule, different carrying entity.
* **Citation awareness, not citation management.** The MVP supports evidence awareness in AI-generated writing (previously "drafts," per ADR-012); automated citation management is explicitly out of MVP scope (SRS Ch10 §4) and remains a roadmap item (SRS Ch11).

---

## 9. Knowledge Graph Integrity

The semantic relationships among Knowledge Elements (04 §3.6) are governed by:

* **Same-Agent scope.** Both endpoints of a Knowledge Element Relationship belong to the same Agent (§13). *(Renamed from "same project" by ADR-009.)*
* **No self-relationships.** `element_from_id` and `element_to_id` must differ.
* **No duplicate statements.** The candidate key `(element_from_id, element_to_id, relationship_type)` prevents repeated relationship declarations (04 §7).
* **Typed and documented.** `relationship_type` is drawn from the documented set (hierarchy / association / dependency); no free-form relationship kinds.
* **Acyclic hierarchy.** Relationships of type `hierarchy` must not form cycles; `association` and `dependency` are cycle-tolerant but must not create contradictory pairs (A depends on B and B depends on A is permitted only where semantically valid; contradiction is a data-quality defect, not a constraint violation).
* **Derivation consistency.** A Knowledge Chunk's `element_id` must reference an element of the same Agent; superseding an element does not orphan its chunks — the pipeline re-links or supersedes them (ADR-005, ADR-006).
* **Relationship entities are immutable.** A relationship statement is created once and never edited; corrections create a new statement (with the old one retained or the pair reconciled by the pipeline).

---

## 10. Capability Ownership Rules

**Renamed from "Agent Ownership Rules" by ADR-009.** This section governs the capability registry (Capability/Capability Entry), not the new Agent workspace entity — see §22 for Agent-specific rules.

* **The registry is system-managed.** Capabilities and their entries are architecture-level capability inventory (03 §3.8; 04 §14); users do not mutate the registry directly.
* **Composition.** A Capability Entry exists only within its Capability; removing the Capability removes its entries (03 §3.8 composition; 04 §9 restrict rules apply to external references).
* **Configuration-governed enablement.** Capability entry sets are enabled and disabled through Configuration Items (AIR-055 to AIR-057); enablement changes are reviewable and auditable.
* **Controlled extension.** New capabilities enter through the controlled extension path (AIR-058 to AIR-060); the registry reflects configuration-approved sets.
* **Named uniqueness.** Capability names and per-capability entry names are unique (candidate keys, 04 §7); no shadowed or duplicated capability registrations.

---

## 11. Memory Consistency

* **User awareness is a precondition.** Memory Records are populated through user input or approved system-derived context; the system never infers memory without user awareness (MVP-011; DR-013).
* **Agent-scoped.** Every Memory Record belongs to exactly one Agent; memory never leaks across Agents (§13). *(Renamed from "Project-scoped" by ADR-009.)*
* **First-class persistence.** Memory is a persisted domain in the structured core, never reconstructed from conversation logs (ADR-004 §Decision 6).
* **Monotonic supersession.** Evolving decisions supersede earlier records; the chain is never rewritten (DR-014; 04 §9, §11).
* **Provenance is recorded.** Memory Provenance Links trace each record to the activities and artifacts that produced it (DR-015; 04 §4.3).
* **Reflection never overrides awareness.** The reflection loop refines understanding without altering memory without user awareness (04 §22; MVP-011 limitation).

---

## 12. Conversation Integrity

* **Ordering.** Messages are strictly ordered per conversation; sequences are monotonic and immutable once assigned (04 §7 candidate key; 04 §9).
* **Scoping.** Every Conversation belongs to exactly one Agent; Messages belong to exactly one Conversation (composition, 03 §6). *(Renamed from "project" by ADR-009.)*
* **Reference integrity.** Message Context Links may reference only artifacts of the same Agent (§13); links are immutable.
* **Continuity record, not memory.** Conversation content is a continuity record; it enters memory only when approved and entered with user awareness (03 §3.6; MVP-011; AIR-006).
* **Compaction preserves continuity.** Summarization compacts history without destroying the record; the Conversation remains the anchor for its messages (§5 transitions).

---

## 13. Agent and Project Isolation

**Extended by ADR-009.** Isolation now has two nested boundaries: the Agent (the true MVP tenant boundary — one per user) and its one, permanent Project (raw materials only). Because the Agent–Project pairing is 1:1 and permanent, the two boundaries always coincide for a given user; the distinction below exists to state precisely which entities carry which scoping key.

* **Agent-scoping is structural for derived/accumulated data.** Knowledge, Knowledge Chunk, Memory, Conversation, Message, Writing Profile, and their link entities carry an Agent identity — directly or transitively — and every reference stays within that Agent (renamed from "Project-scoping" by ADR-009). *(Draft, Draft Version, Review, Review Decision carried this too before ADR-012 removed all four — see `08` §25.)*
* **Project-scoping is structural for raw materials.** Research Document carries a Project identity. Because a Project belongs to exactly one Agent, permanently, a Research Document is transitively reachable from exactly one Agent — evidence links between an Agent-scoped Knowledge Chunk and a Project-scoped Research Document (e.g., Chunk Evidence Link) are valid precisely when the document's Project is the chunk's Agent's own Project.
* **No cross-Agent references in the MVP.** A Conversation belonging to one Agent may not be evidence-linked (via Message Context Link) to a chunk belonging to a different Agent; retrieval is filtered by Agent scope before ranking (ADR-005 §Decision 3, read as Agent-scope filtering after ADR-009). *(Previously stated in terms of Draft — ADR-012.)*
* **Single-user MVP boundary.** All data is scoped to a single authenticated user, through that user's one Agent, per deployment (SRS Ch10 §2; WR-038; MVP-001; ADR-009); the isolation model is designed so multi-user tenancy and multi-Agent-per-user are additive changes (07 §5; ADR-009 Future Considerations; future ADR).
* **Isolation is enforced at the data access layer.** Agent-scoped and Project-scoped access control is part of the persistence contract (API-032, API-033; 05 §15, §16); no component may read or write across Agents outside that boundary.

---

## 14. Audit Consistency

* **Actor traceability is never null where required.** `created_by`, `changed_by`, and `decided_by` are recorded wherever the baseline demands actor accountability (AIR-054; DR-021; 04 §8, §12).
* **Append-only records.** Evidence links, Configuration Item history, and all version content are append-only; the audit trail is the entity history itself (04 §12). *(Review Decisions were append-only too before ADR-012 removed Review Decision — see `08` §25.)*
* **No silent modification.** Mutable entities expose change timing (`updated_at`) where it matters; there is no path that modifies a record without a traceable change record (04 §12).
* **Observability linkage.** Work Items retain failure context for diagnostics and post-incident review (API-040; NFR-027 to NFR-028).
* **Audit survives deletion.** Soft-deleted records retain their audit fields; hard deletion is deferred to the archival policy (SRS Ch7 §4.4; 04 §10).

---

## 15. Soft Delete Behaviour

* **Tombstoned entities (user-visible, removable):** Agent, Project, Research Document, Conversation, Writing Profile. These carry `deleted_at`; active queries and API responses exclude tombstones (04 §10). *(Agent added by ADR-009; Draft was also tombstoned before ADR-012 removed it — see `08` §25.)*
* **Never tombstoned (history-bearing):** Memory Record, Knowledge Element, Knowledge Chunk, Profile Characteristic, and all link entities — these are superseded or retained, never deleted (DR-014, DR-017, DR-019; 07 §3.3–§3.4). *(Draft Version, Review, Review Decision were never tombstoned either, before ADR-012.)*
* **Removal is explicit.** Document removal is an explicit user action (05 §10; DR-025); tombstoning preserves identity and the evidence chain.
* **Cascade semantics.** Tombstoning a Project tombstones its user-visible contents per the documented retention policy; history-bearing records are preserved for the retention window.
* **Hard delete is deferred and governed** by the archival/deletion policy (SRS Ch7 §4.4; refined in [06_Physical_Design_Strategy.md](06_Physical_Design_Strategy.md)); it is never implicit.
* **Rationale.** Tombstones satisfy three obligations simultaneously: user ownership and exportability (03 §4), recoverability (07 §3.5), and preservation of the evidence-to-output chain (ADR-001).

---

## 16. Recovery Expectations

The integrity contract assumes the recovery posture of 07 §3.5 and ADR-006:

* **Durability of in-flight work.** Work Items are durably recorded before execution (outbox); a process restart never loses queued work, and idempotency keys guarantee at-most-once processing (ADR-006).
* **Backup assumptions.** Automated, scheduled backups of the structured core and object store; point-in-time recovery for the structured core (07 §3.5; NFR-033 to NFR-034).
* **Recoverability of derived state.** Retrieval indexes (vector index) are rebuildable from the structured core; embedding-model changes trigger re-indexing (ADR-005). Working-cache loss is recoverable from the structured core (07 §3.2).
* **Consistency on recovery.** Strong consistency applies where ordering and exclusivity matter; eventual consistency of derived artifacts is acceptable (07 §3.3).
* **Integrity bar.** No silent data corruption (NFR-004); recovery never produces dangling references (DR-028).

---

## 17. Data Validation Principles

* **Boundary validation.** Data is validated at the API contract boundary and the data access layer (ADR-002; API-032, API-033); domain logic never trusts unvalidated input.
* **Enumerated state.** All state fields use documented enumerated values; free-form state strings are prohibited (04 §13).
* **Unknown vs. not-applicable.** Nullability distinguishes "genuinely unknown" from "not applicable"; this distinction is preserved through API payloads (04 §8).
* **No silent alteration.** Source material accuracy is preserved during processing (DR-029); content is never silently truncated (DR-030).
* **Content validation at ingestion.** Document format families are validated at intake; processing failures are recorded, never swallowed (§5 transitions).
* **Derived values are not stored redundantly.** Any stored status is a projection of the chain it represents (04 §8).
* **Credential non-exposure (ADR-010).** `User.password_hash` is never included in an API response, log entry, or diagnostic output; it is a credential, not project data or knowledge (AIR-006's raw/interpreted/output distinction).

---

## 18. Duplicate Prevention

* **Candidate keys are the primary mechanism** (04 §7): username, session_token, evidence links `(chunk_id, document_id)`, relationship statements `(element_from_id, element_to_id, relationship_type)`, message ordering `(conversation_id, sequence)`, registry names, configuration history keys, and Work Item idempotency keys. *(Version ordering `(draft_id, version_number)` and single-decision-per-review were also candidate-key mechanisms before ADR-012 removed Draft Version and Review — see `08` §25.)*
* **At-most-once processing.** Work Items carry an `idempotency_key`; duplicate events are detected and discarded (ADR-006).
* **No duplicate evidence statements.** The same evidence link may not be declared twice for the same chunk–document pair.
* ~~**No duplicate annotations.** A Draft Version may not carry two identical evidence annotations.~~ **REMOVED by ADR-012** — the equivalent rule now applies to Message Context Link annotations instead, already covered by the "no duplicate evidence statements" rule above.
* **Re-ingestion.** Re-ingesting the same source material is either detected by the pipeline or recorded as a new intake; silent duplication of documents is a data-quality defect to be surfaced, not absorbed (DR-031).

---

## 19. Domain Invariants

The following statements must hold **at all times** for every valid state of ScholarOS data. They are the acceptance language of the design and the basis for the validation checks of [07_Database_Validation_and_Quality_Assurance.md](07_Database_Validation_and_Quality_Assurance.md):

1. **Agent scoping.** Every Agent-scoped record (Knowledge, Memory, Conversation, Writing Profile, and their links) belongs to exactly one Agent, and every reference it carries resolves within that Agent. *(Renamed from "Project scoping" by ADR-009; see invariant 14 for Project-scoped Research Document. Draft and Review were also Agent-scoped before ADR-012 removed both — see `08` §25.)*
2. **Evidence closure.** Every Knowledge Element and Knowledge Chunk is connected to source material through an unbroken chain of evidence links. *(Draft Version was too, before ADR-012.)*
3. **Chain monotonicity.** Supersession chains are monotonic and acyclic; a superseded record is read-only and never rewritten; at most one record references a given record as its predecessor.
4. **Immutability.** Message content, Memory Record content, Knowledge Element content, and all link entities are immutable after creation. *(Draft Version content and Review Decisions were immutable too, before ADR-012 removed both.)*
5. **Ordering integrity.** Message sequences are monotonic and immutable within their parent. *(Draft Version numbers were too, before ADR-012.)*
6. **Configuration singularity.** Exactly one Configuration Item version is active per (scope, owner, key).
7. ~~**Review singularity.** At most one Review is open per Draft Version, and each Review produces at most one decision.~~ **REMOVED by ADR-012** (2026-10-09, see `08` §25) — no successor invariant; number preserved, not reused, for cross-reference stability.
8. **Profile singularity (MVP).** At most one Writing Profile is active per Agent. *(Renamed from "per project" by ADR-009.)*
9. **Knowledge graph validity.** Knowledge Element Relationships reference same-Agent elements, never self, never duplicate, and hierarchy relationships are acyclic. *(Renamed from "same-project" by ADR-009.)*
10. **Outbox discipline.** A Work Item is durably recorded before the state change it represents is acknowledged, and is executed at most once.
11. **Memory awareness.** No Memory Record exists that the user did not establish or approve.
12. **Evidence retention.** Removing a Research Document preserves its evidence links and the integrity of referencing data.
13. **Referential integrity.** No reference points to a missing record, and no active query or API response ever exposes a tombstoned record.
14. **Project scoping (raw materials).** Every Research Document belongs to exactly one Project, and every Project belongs to exactly one Agent, permanently — Research Document is transitively, unambiguously scoped to exactly one Agent. *(Added by ADR-009.)*
15. **Agent singularity (MVP).** Every User owns exactly one Agent, and every Agent owns exactly one Project for its entire life; neither pairing may be repointed. *(Added by ADR-009.)*

---

## 20. Traceability

This document is traceable to the approved baseline as follows:

* **SRS Chapter 7** — lifecycle (DR-002, DR-023 to DR-025), relationships and referential integrity (DR-026 to DR-028), quality (DR-029 to DR-033), constraints (DR-035, DC-002, DC-003), provenance (DR-012, DR-015, DR-018), memory decision history (DR-014), configuration (DR-020 to DR-022). *(DR-017 "versioning" and DR-019 "review state" traced to Draft Version and Review specifically; both are historical-only requirement mappings since ADR-012 removed both entities — see `08` §25. The SRS document itself is not corrected by this pass.)*
* **SRS Chapter 6** — evidence grounding (AIR-024, AIR-027, AIR-046 to AIR-048), memory (AIR-019 to AIR-021, AIR-065 to AIR-066), artifact distinction (AIR-006), context sufficiency (AIR-031), configuration governance (AIR-055 to AIR-057), extension (AIR-058 to AIR-060). *(AIR-003/AIR-037 to AIR-039/AIR-054 "review audit" and AIR-035 "version awareness" are historical-only mappings for the same reason as DR-017/DR-019 above.)*
* **SRS Chapter 10** — MVP scope (MVP-001, MVP-007 to MVP-008, MVP-011 to MVP-012, MVP-018 to MVP-022).
* **SRS Chapter 5** — integrity (NFR-004), observability (NFR-027 to NFR-028), configuration (NFR-031 to NFR-032), recovery (NFR-033 to NFR-034).
* **Architecture 03** — ownership model (§4), lifecycle (§5). **Architecture 05** — removal policy (§10), authentication and isolation (§15), data access layer (§16), configuration (§17). **Architecture 07** — consistency (§3.3), retention (§3.4), backup assumptions (§3.5), scalability evolution (§5).
* **ADR-004** — memory as a first-class domain; **ADR-005** — evidence links and project-scoped retrieval; **ADR-006** — durable outbox and idempotency; **ADR-002/ADR-003** — boundary enforcement.
* **Database Overview (01)** — quality attributes (§10) and separation of concerns (§11); **Domain Model (02)** — vocabulary (§6 of 02); **Conceptual Data Model (03)** — business rules (§8 of 03); **Logical Data Model (04)** — constraints, nullability, integrity, and soft delete (§7–§10 of 04).
* **ADR-009** — introduces Agent scoping and the Agent/Project isolation model (§13), renames Agent Ownership Rules to Capability Ownership Rules (§10), adds business rule 10 and domain invariants 14–15.
* **ADR-010** — adds the credential non-exposure rule (§17) for `User.password_hash`, realizing the Authentication Boundary via the already-specified Session entity and its existing lifecycle transitions (§5).

---

## 21. Summary

This document, as corrected by ADR-009, defines the business-level integrity contract of ScholarOS: ten business rules realized as integrity obligations, four referential-integrity principles, per-entity state-transition machines, a required/optional relationship inventory, and concern-organized rules covering versioning, citation, knowledge-graph, capability ownership, memory, conversation, Agent/Project isolation, audit, soft delete, recovery, validation, and duplicate prevention. It closes with the fifteen domain invariants that must always hold.

All rules are business-level and implementation-independent; realization is deferred to the data access layer and API design (ADR-001). The next document, [06_Physical_Design_Strategy.md](06_Physical_Design_Strategy.md), maps the logical model and this integrity contract onto the approved storage categories.
