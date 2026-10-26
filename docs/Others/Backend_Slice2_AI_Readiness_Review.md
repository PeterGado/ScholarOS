# Backend Slice 2 — Architecture/Implementation Readiness Review

**Status:** Complete (review only — no code written, no ADR drafted)

**Date:** 2026-09-11

**Author:** Lead AI Software Engineer

**Trigger:** Milestone 7 (Real Authentication Boundary) reached Stage 6 complete. The project owner requested a readiness review of the intelligence capability ("upload → process → understand → retrieve") against the now-authenticated backend, before authorizing any Slice 2 implementation stage.

**Scope:** This is a review, not an implementation plan. It answers the project owner's specific questions against the frozen baseline (Architecture 01–07, Database 01–08, ADR-001 to ADR-010, SRS Chapters 6–7) and the current `backend/` code, and ends with a verdict on whether new governance artifacts (ADR, baseline correction) are required before implementation can begin.

---

## 1. What exactly happens when a user uploads a research document, today?

Per Milestone 6/Stage 1-6 implementation, exactly this and nothing more: `POST /projects/{project_id}/documents` (now authenticated and ownership-checked, Stage 6) validates the request, writes the file bytes to the content-addressed filesystem object store (ADR-004 §Decision 4), and persists a `Research Document` row with `processing_status = pending`. **`processing_status` never transitions** — no code anywhere reads or advances it. This matches `05_Backend_Architecture.md` §10.1's own scope: the Document Service is explicitly CRUD-only ("register, metadata, status, list, remove... no AI Service Layer or Provider Abstraction dependency" — `Backend_Implementation_Plan.md` §2). Document Service's own responsibility list ends at "provide source material to the knowledge processing pipeline" (§10.1) — that pipeline does not exist yet.

## 2. What happens with a writing-style document?

Nothing — it cannot currently be uploaded at all. Per `Backend_Implementation_Plan.md` §2, three upload categories exist in the frozen model: Research Document (Project-scoped, evidence), reference/similar documents (Agent-scoped, via Knowledge Service), and writing-style documents (Agent-scoped, via Author Profile). Only Research Document upload was built in Slice 1. Writing-style ingestion has its own module (`modules/author_profile/`, not yet scaffolded), its own entities (Writing Profile, Profile Characteristic), and its own derivation pipeline — architecturally and physically distinct from Research Document → Knowledge.

## 3. What does "processing" mean?

Per `04_AI_Architecture.md` §7 (Knowledge Processing Pipeline), "processing" a document means running it through six stages: material acceptance → **conceptual extraction** (deriving concepts, themes, methods, claims — an AI provider call) → relationship recognition → relevance classification → structuring → evidence linkage. It is not text extraction or file parsing in isolation — it is the transformation of a document into interpreted **Knowledge Elements**, each still linked back to its source document (evidence linkage, DR-008).

## 4. Where does extracted text live?

**Nowhere, as a named artifact — this is a real, unaddressed gap.** The frozen Logical Data Model has no "extracted plain text" field: `Research Document.content_reference` points at the original file in the object store (ADR-004); `Knowledge Element.description` and `Knowledge Chunk.content` hold *interpreted* content, not raw extracted text. Nothing in the frozen baseline mandates persisting an intermediate raw-text artifact — this is legitimately an implementation-level decision, not a specified requirement. It should be resolved explicitly during Slice 2 planning (most likely: extract text in-memory during the pipeline run, re-reading from the object store each time re-processing is needed — cheap at MVP scale and consistent with "the vector index is rebuildable from the structured core; it is never a source of truth," `06_Physical_Design_Strategy.md` §7).

## 5. What gets chunked?

**Knowledge, not raw text.** `04_AI_Architecture.md` §9.1 is explicit: "Chunks are units of interpreted knowledge, not raw text fragments." The Logical Data Model confirms this structurally: `Knowledge Chunk.element_id` is a **not-null** foreign key to `Knowledge Element` (`04_Logical_Data_Model.md` §3.7) — a chunk cannot exist without first deriving from an already-extracted, already-interpreted Knowledge Element. This has a real implementation consequence: Slice 2 cannot be "extract text, run a text-splitter, embed the splits" (the common naive RAG pattern) — it must first produce Knowledge Elements from the document (an AI call), and only then chunk *those*.

## 6. What gets embedded?

`Knowledge Chunk.content` (interpreted chunk content) is what gets embedded, per ADR-005 Decision 5 ("Embeddings flow through the provider gateway") and the Logical Data Model's own note on §3.7 ("the chunk's embedding... is persisted in the vector index, keyed by `chunk_id`... it is not an attribute of this logical entity in the structured core").

## 7. Where are embeddings stored?

The **vector index** storage category (ADR-004 Decision 3), never the structured core as a chunk attribute — confirmed again in `06_Physical_Design_Strategy.md` §7 ("Embeddings are derived data... stored in the vector index, never in the structured core as attributes of the chunk entity"). ADR-004 leaves the *concrete mechanism* open: "e.g., a SQLite-adjacent vector extension or an in-process vector index" — this is an implementation choice Slice 2 must make explicitly, not a frozen requirement. Migration path is a dedicated vector store (e.g. pgvector) later; the embedded index is explicitly rebuildable and never a source of truth.

## 8. How are research knowledge and writing style distinguished?

They are architecturally separate domains with separate pipelines, never overlapping:

| | Research Knowledge | Writing Style |
|---|---|---|
| Source | Research Document (Project-scoped) | writing-style sample document (Agent-scoped) |
| Entities | Knowledge Element, Knowledge Chunk | Writing Profile, Profile Characteristic |
| Content | Interpreted concepts/claims, evidence-linked | Stylistic signals: `characteristic_type` enum (structure / vocabulary / transitions / explanation / citation) with a `confidence` value — never raw prose |
| Consumed by | Retrieval Strategy (evidence, factual grounding) | Writing Pipeline (style alignment only, at generation time) |
| Retrievable as evidence? | Yes — every chunk carries a Chunk Evidence Link | No — a profile is never returned as "evidence" for a claim |

## 9. How does retrieval know which knowledge has authority?

**It doesn't, and the frozen baseline doesn't specify that it should — this is worth naming explicitly rather than assuming.** ADR-005's hybrid retrieval ranks by relevance (lexical + semantic fusion via RRF), scoped to the Agent, with every result carrying its evidence link (traceability, not trust-weighting). AIR-067/AIR-068 distinguish "supported evidence" from "inferred interpretation" from "unresolved uncertainty" — that is an epistemic-confidence distinction about a given piece of content, not a cross-source authority ranking (e.g., "this document is more authoritative than that one"). If the intent behind this question is "can one uploaded document outrank another," there is currently no mechanism for that, and none is required by any approved document — it should not be invented now; if it becomes a real need, it is a retrieval-strategy extension requiring its own review against ADR-005, not a silent addition.

## 10. When does the AI provider get called?

Exactly twice in the minimal loop, both behind the Provider Abstraction gateway (ADR-002 Decision 3, never called directly from domain/application code):

1. **Conceptual extraction** — one call per document (or per reasonable text window) to derive Knowledge Elements.
2. **Embedding** — one call per Knowledge Chunk to produce its retrieval vector.

A third, smaller call is needed at **query time**: embedding the incoming search query text before vector search runs. Retrieval itself (the search/ranking step) does not call the AI provider — it is a deterministic, testable component by design (ADR-005 §AI Engineering Implications: "Retrieval is a deterministic component: it must be testable without network access").

## 11. What is synchronous vs asynchronous?

| Synchronous (interactive path) | Asynchronous (background path) |
|---|---|
| Document upload (register, store bytes, write row, enqueue work item) | Conceptual extraction (provider call) |
| Retrieval query (lexical + vector search + RRF fusion) | Chunking, embedding, index update |
| Query embedding (single, fast provider call) | Any retry/backoff on provider failure |

This split is not a Slice 2 invention — it is ADR-006 Decision 1, verbatim: "Interactive requests return quickly; long-running work is dispatched to a background execution context." Retrieval stays synchronous because it must be conversationally responsive (API-038/API-039) and depends only on an already-built index — it does not itself trigger any long-running pipeline.

## 12. How does ADR-006's outbox/event model enter the implementation, concretely?

1. The document-upload use case, in the **same transaction** that persists the `Research Document` row, also inserts a **Work Item** row (e.g., `type=process_document`, `payload={document_id}`, `status=queued`). One commit, both writes — solving the dual-write problem ADR-006 names explicitly.
2. An in-process background executor (the simplest correct realization: an `asyncio` loop or a polling worker reading the Work Item table — no external broker, per ADR-006 Decision 3/4) picks up queued items, runs the pipeline (extract → chunk → embed → index), and updates `processing_status` plus the Work Item's own status (`succeeded`/`failed`, with bounded retry per ADR-006 Decision 5).
3. Domain events (`document_ingested`, `knowledge_updated`, `index_updated`) drive the handoff between pipeline stages, exactly as ADR-006 Decision 2 names them.

`Backend_Implementation_Plan.md` §6 already anticipated this exact module: `app/workers/work_items.py`, recorded as a forward note when Slice 1 was scoped, specifically so Slice 1's scaffolding would not need reshaping to accommodate it.

## 13. What should be implemented in Slice 2?

The smallest set that makes every architectural boundary in questions 1–12 real, not simulated:

1. `app/ai/providers/` — the Provider Abstraction gateway (ADR-002), with **one** concrete provider wired behind it, configuration-selected.
2. A **Work Item / outbox** ORM realization of the already-specified §3.20 entity, plus a minimal in-process executor (ADR-006) — one `kind` value (e.g., `process_document`) is enough to prove the pattern; it does not need a general-purpose scheduler.
3. `modules/knowledge/` — Knowledge Element and Knowledge Chunk domain/application/infrastructure layers, realizing the **already fully-specified** Logical Data Model entities (§3.5–§3.7) and the Chunk Evidence Link junction (§18 note).
4. A minimal extraction step: one provider call per document producing a small set of Knowledge Elements (a handful of concepts/claims is sufficient to prove the loop — exhaustive extraction quality is explicitly not an MVP requirement, per MVP-005's own limitation clause).
5. A minimal chunking step: one Knowledge Chunk per Knowledge Element is a legitimate MVP-scale simplification (nothing in the frozen model forbids 1:1; sophisticated multi-element chunk composition can come later without a schema change).
6. Embedding + a minimal vector index realization — a plain table of `(chunk_id, vector_blob)` with brute-force cosine similarity in Python is a legitimate, explicitly-permitted MVP realization of ADR-004's "in-process vector index" — no exotic infrastructure needed for one user's corpus.
7. One retrieval endpoint implementing ADR-005's hybrid retrieval at minimum real fidelity: lexical search (SQLite `LIKE`/FTS5 is sufficient) + vector search, fused by RRF, returning ranked chunks with their evidence link back to the source document.

## 14. What should remain deferred?

Writing Profile / author-style ingestion; Memory Record building and integration; Conversation Intelligence; the Context Assembly Pipeline; the Writing Pipeline (draft generation); the Review Pipeline; formal Capability Registry/Orchestration and the Planning Layer; cross-encoder reranking (explicitly deferred by ADR-005 itself, Phase 7); sophisticated multi-element chunk composition; any cross-source "authority" ranking (see Q9); production-grade text-extraction-format handling beyond common academic formats (MVP-003's own scope).

## 15. Which existing database entities are sufficient, as-is?

**Correction (recorded, not silently fixed):** the first version of this review incorrectly stated that the Work Item entity was missing from the Logical Data Model. A full read of `04_Logical_Data_Model.md` §2.2 and §3.20, `05_Constraints_and_Integrity.md` (lifecycle table, invariant 10 "Outbox discipline," §18 duplicate prevention), and `06_Physical_Design_Strategy.md` shows this was wrong — Work Item is already fully specified, in more detail than this review's own draft attempt at it. The error came from relying on an earlier, partial grep of §2.2's "core entities" sentence (which by design does not include Work Item — it belongs to the separate "system entities" family named one line later) instead of reading the full document before concluding a gap existed. Corrected below.

**Research Document** (already implemented, Stage 1, no change needed) and, unimplemented but **fully specified and requiring no schema change**:

* **Knowledge Element** (§3.5), **Knowledge Chunk** (§3.6/§3.7), and **Chunk Evidence Link** (§18 note) — the Research Document ↔ Knowledge Chunk evidence junction.
* **Work Item** (§3.20, "Work Item (Durable Outbox)") — already carries `work_item_id`, `kind` (`pipeline_stage` / `domain_event`), `state` (`queued` / `running` / `succeeded` / `failed`), `payload_reference`, `idempotency_key` (candidate key), `attempts`, `last_error`, `created_at`, `executed_at`, `completed_at`. Its lifecycle, retry rule (`failed → queued`, bounded), and duplicate-prevention rule (idempotency key, at-most-once) are already written into `05_Constraints_and_Integrity.md`, and its durability/backup/recovery posture is already written into `06_Physical_Design_Strategy.md`.

This is the same situation ADR-010 found with `Session`, extended to four entities, not one: all pre-specified at Milestone 5, none implemented, all ready to realize exactly as written.

## 16. Which new entities are actually required?

**None.** Every entity the Knowledge Processing Pipeline needs — Knowledge Element, Knowledge Chunk, Chunk Evidence Link, and Work Item — is already fully specified in the frozen Database Baseline v1. There is no Logical Data Model gap.

## 17. Do we need an ADR before implementing anything?

**No.** With the Q15/16 correction above, the only things Slice 2 must still pin down are two configuration-level realization choices that ADR-002 and ADR-004 explicitly delegated to implementation:

* **First concrete AI provider** — ADR-002 already states "Provider implementations... are selected by configuration, never by business logic." Naming one is ordinary configuration, not a new architectural decision.
* **Vector index mechanism** — ADR-004 Decision 3 already says "e.g., a SQLite-adjacent vector extension or an in-process vector index," explicitly leaving the concrete choice to implementation.

Neither trips ADR-008 item 5's escalation criteria (authentication model, versioning scheme, protocol, service-boundary change). This is exactly the same category of decision Milestone 7 Stage 1 made without a new ADR — choosing SHA-256 over bcrypt for session-token hashing was recorded in `Authentication_Implementation_Plan.md` as "a physical-realization detail, not a new ADR," not escalated. The same treatment applies here: both choices belong in a **Slice 2 Implementation Plan** (mirroring `Authentication_Implementation_Plan.md`'s own structure), not in a new ADR.

## 18. What is the smallest vertical slice that lets you personally test the first real ScholarOS intelligence capability?

Upload a research document → an async Work Item fires → the pipeline calls the AI provider once to extract a handful of Knowledge Elements from the document → derives one Knowledge Chunk per Element → calls the AI provider (or a local embedding call) to embed each chunk → stores the vector in a minimal in-process vector table → one retrieval endpoint takes a text query, embeds it, runs lexical + vector search, fuses by RRF, and returns ranked chunks each carrying its evidence link back to the source document.

This single loop exercises every architectural boundary named in this review — Provider Abstraction, the async/outbox model, the Knowledge Service, and the Retrieval Strategy — at real (not simulated) fidelity, and is personally testable with exactly one upload and one search call over real HTTP, mirroring how every prior milestone in this project was verified.

---

## Recommended Staging (mirrors Milestone 6/7's stage-gated discipline; not yet authorized)

| Stage | Content |
|---|---|
| 1 | Draft a Slice 2 Implementation Plan (first provider choice, vector-index mechanism, file impact matrix, staging), mirroring `Authentication_Implementation_Plan.md`'s structure. No ADR required (§17). |
| 2 | Work Item / outbox ORM realization (of the already-specified §3.20 entity) + minimal in-process executor |
| 3 | `app/ai/providers/` gateway with one concrete provider wired |
| 4 | `modules/knowledge/` — Knowledge Element, Knowledge Chunk, Chunk Evidence Link |
| 5 | Extraction pipeline (document → elements), dispatched through the Work Item executor |
| 6 | Embedding + minimal vector index realization |
| 7 | Hybrid retrieval endpoint (lexical + vector + RRF) |
| 8 | End-to-end real-HTTP verification (upload → process → retrieve, over separate requests) + governance sync |

## Verdict

**READINESS REVIEW COMPLETE — RECOMMEND DRAFTING A SLICE 2 IMPLEMENTATION PLAN. NO NEW ADR IS REQUIRED.**

An earlier version of this review incorrectly concluded that a Work Item entity was missing from the frozen Database Baseline v1 and recommended drafting ADR-011 on that basis. That conclusion was wrong (§15/§16, corrected above) and the drafted ADR-011 was deleted before this review was finalized — it was never committed. Every entity Slice 2 needs is already fully specified in the frozen baseline; only two configuration-level realization choices remain, and they belong in an implementation plan, not an ADR.

No code, ADR, or implementation plan has been written or committed as part of this review.
