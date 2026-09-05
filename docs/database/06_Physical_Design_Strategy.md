# Physical Design Strategy

**Document:** 06_Physical_Design_Strategy.md

**Status:** Active

**Date:** 2026-08-07

**Milestone:** Milestone 5 — Database Design

**Revision:** 1

---

## 1. Purpose

This document defines the **physical design strategy** of ScholarOS: how the logical model of [04_Logical_Data_Model.md](04_Logical_Data_Model.md) and the integrity contract of [05_Constraints_and_Integrity.md](05_Constraints_and_Integrity.md) are organized for persistence — at the level of storage categories, persistence philosophy, and lifecycle mapping. It answers the question *"How will the logical model be realized across storage, without becoming implementation?"*

It is the sixth layer of the database design document set ([01_Database_Overview.md](01_Database_Overview.md) §12). Document 04 defined the logical structure; this document maps that structure onto the approved storage categories of [07_Operational_Architecture.md](../architecture/07_Operational_Architecture.md) §3 and aligns with the governing ADRs (ADR-004, ADR-005, ADR-006, ADR-007).

This document is a **strategy**, not an implementation:

* It maps logical entities to storage **categories** — never to engines, schemas, or physical layouts.
* It does **not** write SQL, choose engine features, design indexes, or write migrations (01 §12.3; ADR-004).
* Storage engines, schema realization, index inventory, and migration scripts belong to the implementation milestone, bounded by this strategy and by the ADR decisions it references.

**Authoritative Source Rule:** per [01 §12.2](01_Database_Overview.md), this document treats Documents 01–05 as authoritative, extends the design, and does not duplicate their content. Mapping decisions here are refinements of 07 §3 and ADR-004/005/006 — never new storage decisions.

---

## 2. Governing Decisions (Referenced, Not Restated)

The physical strategy operates within decisions already recorded:

* **Storage categories** — structured core, vector index, object store, working cache (07 §3.2). These are architectural and binding.
* **Engine decisions and migration paths** — SQLite structured core for the MVP with PostgreSQL migration path; embedded vector index with dedicated vector store path; local object store with S3-compatible path; in-process cache with shared-cache path (ADR-004). This document does not re-decide them.
* **Retrieval contract** — chunk-level hybrid retrieval with first-class evidence links; embeddings flow through the provider gateway; embedding-version changes trigger re-indexing (ADR-005).
* **Async and outbox** — durable work items and events in the structured core; idempotent, retryable processing (ADR-006).
* **Deployment envelope** — local-first, single-node for the MVP; managed deployment later (ADR-007).

Any genuinely new storage decision that is architecturally significant must be recorded in a new ADR — never slipped into this document (01 §11.3).

---

## 3. Storage Organization

The storage categories of 07 §3.2 organize the logical model as follows. The mapping expresses *which information belongs in which category*; it does not define physical layout:

| Storage category (07 §3.2) | Logical content | Access pattern | Consistency model |
|---|---|---|---|
| **Structured core** | All relational entities and links: User, Session, Agent, Project, Research Document (metadata + content reference), Knowledge Element, Knowledge Element Relationship, Knowledge Chunk (metadata + content), Memory Record, Conversation, Message, Writing Profile, Profile Characteristic, Capability, Capability Entry, Draft, Draft Version, Review, Review Decision, Configuration Item, Work Item, and all five link entities *(Agent added; Capability/Capability Entry renamed from Agent/Agent Capability — ADR-009)* | Transactional create/read/update; relational queries; state transitions | Strong (07 §3.3) |
| **Vector index** | Knowledge Chunk embeddings and retrieval indexes, keyed by `chunk_id` (ADR-005) | Similarity search during retrieval | Eventual; rebuilt/updated asynchronously (ADR-005, ADR-006) |
| **Object store** | Source document content payloads, exports, large artifacts | Write-once, read-anytime; blob access | Immutable or versioned; strong on metadata, content-addressed (07 §3.2) |
| **Working cache** | Assembled context, interim pipeline results, conversation working state | Ephemeral, high-frequency | Loose; loss recoverable from the structured core (07 §3.2) |

**Mapping principle (class-by-access-pattern):** data is placed by its access pattern and consistency requirement, not by domain convenience (07 §3.1). Transactional, relational, strongly consistent data lives in the structured core; retrieval-oriented derived data lives in the vector index; large immutable payloads live in the object store; ephemeral state lives in the working cache.

---

## 4. Persistence Strategy

* **One realization boundary.** All categories are realized behind the data access layer (API-032, API-033; 05 §16); domain logic and services never touch storage engines directly (ADR-004 §AI Engineering Implications).
* **Per-module data ownership.** Each bounded context (03 §7; 05 §4) owns its data; cross-context persistence flows through the orchestration layer and the data access layer (ADR-003).
* **Strong-then-eventual.** State that requires ordering or exclusivity — project lifecycle, draft versioning, review state, memory updates, the outbox — is strongly consistent in the structured core; derived artifacts (retrieval indexes, summaries) are eventually consistent (07 §3.3; ADR-006).
* **Durability of intent.** Work Items and events are durably recorded before execution (outbox, ADR-006), so intent survives restart regardless of engine.
* **Exportability.** User-owned domains remain retrievable and exportable at project level (03 §4; 07 §3.1).

---

## 5. Large Document Handling

* Source document **content payloads** are stored in the **object store** category; the structured core retains document **metadata and a content reference** (`content_reference`, 04 §3.4).
* Payloads are **content-addressed** (immutable, versioned) per the object-store profile of 07 §3.2 — the same source content is stored once and referenced, never duplicated per project or per chunk.
* Large documents are processed **asynchronously** through the pipeline (ingestion → knowledge processing → chunking → indexing, 04 §7/§9; ADR-006), so ingestion never blocks the interactive path (ADR-006 §Decision 1).
* Exports are materialized as object-store artifacts; user ownership guarantees exportability (03 §4; 07 §3.4).
* The structured core never stores full document bodies; it stores what is needed for governance, retrieval coordination, and state.

---

## 6. Knowledge Chunk Storage

* Chunk **content and metadata** live in the **structured core** — chunks are the transactional retrieval unit (DR-007 to DR-009; ADR-005) and must support strong referential integrity with documents, elements, and drafts.
* Chunk **embeddings** live in the **vector index**, keyed by `chunk_id` (04 §3.7 note; ADR-005) — the split keeps similarity search out of the transactional store.
* Superseded chunks remain in the structured core with retained traceability (07 §3.3, §3.4); the vector index is updated asynchronously and may lag (eventual consistency, ADR-006).
* Re-chunking is a pipeline-coordinated activity: new chunks supersede old ones through the knowledge pipeline, and index updates follow as events (ADR-005 §Decision 5; ADR-006).

---

## 7. Embedding Storage Strategy

* Embeddings are **derived data** of the retrieval strategy (ADR-005): stored in the **vector index**, never in the structured core as attributes of the chunk entity (04 §3.7).
* **Keying:** embeddings are keyed by `chunk_id`; the retrieval contract resolves chunk identity before similarity (ADR-005).
* **Versioning:** embedding-model changes require re-indexing of affected chunks; embeddings are derived data, so retention rules apply to them as derived artifacts (ADR-004 §Future Consideration 2; DR-023 to DR-025).
* **Recoverability:** the vector index is rebuildable from the structured core; it is never a source of truth (07 §3.2 recovery assumption).
* **Consistency:** index updates are eventually consistent and may lag the structured core; the UI surfaces status states rather than hiding the lag (ADR-006 §Consequences).

---

## 8. Version Storage Strategy

* Versioned content — Draft Versions, superseded Knowledge Elements/Chunks, superseded Memory Records, Configuration Item history — is stored in the **structured core** as **immutable, append-only records** (04 §11; DR-014, DR-017).
* Versioning is expressed by the **logical model's chain semantics** (successor references, monotonic ordering), not by engine-specific versioning features (04 §11).
* The "current" state is derivable from the chain (§5 of 04 mapping; 04 §8) — no duplicated current-state storage.
* Conversations are **compacted**, not versioned (03 §3.6; 04 §11): summarization produces a continuity record in the structured core; raw message history may be summarized per retention policy.

---

## 9. Audit Storage Strategy

* Audit-bearing records — Review Decisions, evidence links, Configuration Item history, immutable version content — live in the **structured core** as append-only records (04 §12).
* **Immutability is the audit mechanism:** no separate audit log is needed for records whose history is the record itself (04 §12).
* Actor traceability (`created_by`, `changed_by`, `decided_by`) is stored with the record (04 §8, §12; AIR-054, DR-021).
* Work Items retain failure context in the structured core for observability and post-incident review (API-040; NFR-027 to NFR-028).
* Audit data is included in backups and point-in-time recovery (07 §3.5) — audit is recoverable, never incidental.

---

## 10. Retention Strategy

Retention follows 07 §3.4 and the data lifecycle (DR-023 to DR-025):

| Domain | Retention posture |
|---|---|
| Research Documents | Retained as evidence for the life of the project or until explicitly removed (05 §10; WR-004 to WR-006) |
| Knowledge Elements and Chunks | Superseded versions retain traceability; eligible for controlled removal only per lifecycle rules (DR-007 to DR-009, DR-023 to DR-025) |
| Memory Records | Retained with supersession chronology; first-class domain (ADR-004) |
| Conversations | Retained as continuity record; may be summarized and linked to memory rather than stored verbatim indefinitely (03 §3.6) |
| Drafts and Reviews | Version history preserved (DR-016 to DR-019) |
| Exports | User-owned, exportable at project level (03 §4) |
| Derived artifacts (embeddings, indexes) | Subject to the same lifecycle rules as their source; rebuildable (ADR-004, ADR-005) |

Retention windows and scheduling parameters are implementation/operational decisions (refined with 07 §3.4 assumptions), not design decisions.

---

## 11. Archival Strategy

* Archival is the **controlled preservation** of data that has left active use, per SRS Ch7 §4.4: archived data remains recoverable for future reference.
* Archival applies to **user-visible, tombstoned entities** (Project, Research Document, Conversation, Writing Profile, Draft — 04 §10) after their active life; history-bearing records are never archived away from traceability (supersession and audit remain in the structured core).
* Archival is **explicit and governed**: hard deletion is deferred to the archival/deletion policy (SRS Ch7 §4.4) and never implicit (04 §10).
* Exports and archived payloads are object-store artifacts; archive metadata is retained in the structured core so archived data remains discoverable and restorable.
* Archival mechanics (schedule, format, location) are operational decisions for later milestones; this document fixes the strategy.

---

## 12. Backup Assumptions

* **Structured core:** automated, scheduled backups with point-in-time recovery (07 §3.5; NFR-033 to NFR-034).
* **Object store:** backed up (07 §3.5); content-addressed payloads make backup and deduplication straightforward.
* **Vector index:** rebuildable from the structured core; not backed up as a source of truth (07 §3.2).
* **Working cache:** never backed up; loss is recoverable from the structured core (07 §3.2).
* **Outbox durability:** pending Work Items survive restart through the durable outbox — the backup posture for in-flight work (ADR-006; 07 §3.5).
* Assumptions, not over-engineered guarantees: no multi-region replication, no zero-downtime failover, no cross-region DR in the MVP (07 §3.5; ADR-007).

---

## 13. Recovery Assumptions

* Point-in-time recovery of the structured core restores transactional state; supersession and audit records are restored with it.
* Derived artifacts (vector index, working cache) are rebuilt from the restored structured core; the retrieval contract is unaffected by rebuild timing (ADR-005, ADR-006).
* In-flight work is recovered via the durable outbox: queued Work Items resume; idempotency keys prevent duplicate execution (ADR-006).
* Recovery never produces dangling references; referential integrity is re-validated as part of recovery (DR-028; 05 §16).
* RPO/RTO values are operational parameters to be set at implementation and re-validated when the structured core migrates to PostgreSQL (ADR-004 §Future Consideration 3).

---

## 14. Expected Growth

The MVP envelope (ADR-004, ADR-007) is a single researcher, single project at a time, personal research scale (SRS Ch10 §2). Growth expectations, in order of appearance:

* **Project and document volume** grows with the researcher's corpus; documents scale in the object store, metadata in the structured core.
* **Knowledge and chunk volume** grows with ingestion; the vector index grows with chunks (ADR-005).
* **Conversation and memory volume** grows with sessions; compaction bounds raw history (03 §3.6).
* **Index volume triggers** the dedicated vector store migration when a single project's chunk corpus or query concurrency exceeds the embedded envelope (ADR-004, ADR-005).
* **Concurrency triggers** the PostgreSQL migration when multi-user stages begin (07 §5 stage 2; ADR-004).
* **Deployment growth** moves the object store and cache to managed services when the cloud stage begins (ADR-004, ADR-007).

Growth is absorbed by the levers of 07 §5.3 (async processing, modular boundaries, stateless API tier, index partitioning, persistence swap) — none of which changes the logical model.

---

## 15. Partitioning Philosophy

* **By agent/tenant, never by domain.** When volume demands partitioning, retrieval indexes partition by Agent/tenant — matching the isolation model (05 §13, §15) and the retrieval contract (ADR-005 §Decision 3). *(Renamed from "by project/tenant" by ADR-009, reflecting Agent as the MVP tenant boundary.)* Partitioning never changes the retrieval or persistence contract (07 §5.3 lever 4).
* **Deferred until volume demands.** No partitioning in the MVP envelope; partitioning is an additive, deployment-level change (ADR-004, ADR-007).
* **Logical model neutrality.** Partitioning is a physical concern; the logical model contains no partition assumptions (01 §9.4).

---

## 16. Indexing Philosophy

* **Indexes serve documented patterns, not the reverse.** The physical index inventory is an implementation artifact selected to serve the documented access patterns: project-scoped retrieval, referential-integrity lookups, evidence-chain navigation, version ordering, and configuration lookup (04 §7 candidate keys).
* **No index design here.** Per 01 §12.3 and ADR-004, the index inventory, structure, and tuning belong to the implementation milestone — this document states the philosophy and the patterns, not the indexes.
* **Two indexes, one contract.** The lexical and semantic retrieval indexes (ADR-005) are implementation artifacts of the vector-index category; their synchronization is pipeline-owned (04 §7 of the AI architecture; ADR-005, ADR-006).
* **Candidate keys imply uniqueness enforcement** at realization (04 §7); the physical form is an implementation choice.

---

## 17. Caching Philosophy

* **The working cache is never a source of truth.** Assembled context, interim pipeline results, and conversation working state may be cached; loss is always recoverable from the structured core (07 §3.2).
* **Memory is not a cache.** Project memory is a first-class persisted domain in the structured core, never a cache or a reconstruction from logs (ADR-004 §Decision 6).
* **Cache invalidation follows events.** Pipeline completion and state transitions invalidate affected cache entries through the event model (ADR-006); stale cache entries are a recoverable inconsistency, never a correctness failure.
* **No premature caching.** Caching decisions beyond the working-cache category are deferred to implementation and driven by measured access patterns (API-038, API-039 envelope).

---

## 18. Future Scalability Path

The evolution path is fixed by 07 §5 and the ADR set; this document adds the persistence-strategy view:

* **What is invariant:** storage categories, the data access layer boundary, the logical model, evidence and memory architecture, provider abstraction, separation of concerns (07 §5.2).
* **What changes per stage:** the concrete implementations behind each category (ADR-004 engines and migration paths), process packaging, managed persistence, index partitioning, tenancy isolation (07 §5.1, §5.3).
* **Persistence swap is the mechanism:** the data access layer (API-032, API-033) turns engine migration into a configuration- and data-layer change, not a redesign (ADR-004).
* **Multi-tenancy is additive:** tenancy isolation decisions will be recorded in a future ADR at the stage that requires them (ADR-004 §Future Consideration 1; 07 §5).

---

## 19. Performance Considerations

Design-level performance posture (no physical tuning):

* **Interactive path stays light.** Long-running work is async (ADR-006); the interactive path touches only the structured core's strongly consistent state.
* **Retrieval latency envelope.** Retrieval operates over the vector index with project-scoped filtering before ranking (ADR-005); the envelope is defined by API-038 to API-039.
* **Strong-consistency hotspots.** Draft versioning, review state, memory updates, and the outbox are the ordering-critical operations (07 §3.3); their access patterns are transactional and small.
* **Large payloads never cross the relational path.** Document bodies move through the object store; the structured core handles references, not bulk content (§5).
* **Derived lag is surfaced, not hidden.** Eventual consistency of indexes is acknowledged in status states (ADR-006 §Consequences); the design never pretends derived state is synchronously current.

---

## 20. Storage Lifecycle

The storage lifecycle maps the data lifecycle of SRS Ch7 §4 (ingestion → storage/persistence → retrieval → archival/deletion) onto the categories:

```md
Ingestion        →  object store (payload) + structured core (metadata, intake state)
Knowledge processing → structured core (elements, chunks, links) → vector index (embeddings, async)
Retrieval        →  vector index (similarity) + structured core (evidence, context assembly)
Drafting/Review  →  structured core (versions, reviews, decisions, evidence links)
Continuity       →  structured core (memory, conversation records)
Archival/Deletion→  object store (archive/exports) + structured core (tombstones; governed hard delete)
```

Provenance is preserved across the lifecycle (DR-024); every stage retains the evidence-to-output chain (ADR-001).

---

## 21. Traceability

This document is traceable to the approved baseline as follows:

* **SRS Chapter 7** — lifecycle stages (DR-023 to DR-025), provenance (DR-024), removal (DR-025), relationships (DR-026 to DR-028).
* **SRS Chapter 9** — persistence boundary (API-032, API-033), diagnostics (API-040).
* **SRS Chapter 5** — responsiveness (API-038/039 envelope; NFR-001), integrity (NFR-004), observability (NFR-027 to NFR-028), configuration (NFR-031 to NFR-032), recovery (NFR-033 to NFR-034).
* **Architecture 07** — storage categories and principles (§3.1–§3.2), consistency (§3.3), retention (§3.4), backup assumptions (§3.5), scalability evolution (§5).
* **Architecture 04** — memory (§8), chunking (§9), retrieval (§16), evidence flow (§18). **Architecture 05** — data access layer (§16), authentication/isolation (§15).
* **ADR-004** — storage engines, memory persistence, migration paths; **ADR-005** — chunk retrieval, evidence links, embedding versioning; **ADR-006** — outbox, idempotency, async; **ADR-007** — deployment envelope.
* **Database Overview (01)** — design boundaries (§9.4, §11.3, §12.3); **Domain Model (02)** — vocabulary; **Conceptual Data Model (03)** — ownership (§4 of 03) and lifecycle; **Logical Data Model (04)** — entities, links, content references, storage note (§2.3, §3.7, §5 of 04); **Constraints and Integrity (05)** — retention and recovery obligations (§15–§16 of 05).
* **ADR-009** — adds Agent to the structured-core entity list; renames the partitioning boundary from project/tenant to agent/tenant.

---

## 22. Summary

This document defines the physical design strategy of ScholarOS: a class-by-access-pattern mapping of the logical model onto the four approved storage categories (structured core, vector index, object store, working cache), a persistence strategy built on the data access layer and per-module ownership, and strategies for large documents, chunks, embeddings, versioning, audit, retention, archival, backup, recovery, growth, partitioning, indexing, caching, and scalability. It remains a strategy: technology-neutral, ADR-aligned, and free of SQL, index design, and migrations.

The next document, [07_Database_Validation_and_Quality_Assurance.md](07_Database_Validation_and_Quality_Assurance.md), defines how this design — and the whole database baseline — will be validated before implementation.
