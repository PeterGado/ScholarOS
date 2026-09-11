# Backend Slice 2 — Stage 5 Implementation Plan: Semantic Extraction & Persistence

**Status:** Complete (planning), validated, then implemented

**Date:** 2026-09-11

**Prerequisite:** Stage 4 complete — `ProcessDocumentUseCase` produces `list[TextChunkCandidate]`, transient, no knowledge persisted (see Stage 4 Completion Report).

## 1. Objective

Consume Stage 4's `TextChunkCandidate[]` and, via the AI provider gateway, produce genuinely-interpreted, persisted `KnowledgeElement` + `KnowledgeChunk` + `ChunkEvidenceLink` rows — realizing exactly the "conceptual extraction" step of the Knowledge Processing Pipeline (`04_AI_Architecture.md` §7 stage 2) that Stage 4 deliberately did not perform.

## 2. Reconciliation Against the Four Named Sources

**Database model (`04_Logical_Data_Model.md`):** §3.5 (Knowledge Element), §3.7 (Knowledge Chunk), §4.1 (Chunk Evidence Link) are already fully specified — Stage 2 already realized them as ORM models with no schema changes. Stage 5 does not need any new entity or attribute. Cardinality check: `KnowledgeChunk.element_id` is not-null but carries no stated multiplicity constraint beyond that — a 1:1 Element↔Chunk mapping (one classified concept per mechanical chunk) is permitted, not just a many-chunks-per-element pattern.

**AI Architecture (`04_AI_Architecture.md` §7):** stage 2 of the pipeline is "Conceptual extraction — the pipeline derives concepts, themes, methods, claims, and relationships from source material." Stage 5 realizes exactly this, and stage 6 ("Evidence linkage — every knowledge element retains traceability to its source material") — realized via `ChunkEvidenceLink`. Relationship recognition (stage 3) and relevance classification (stage 4) are **not** implemented — no `Knowledge Element Relationship` rows are created; this is an explicit, narrower slice of §7, not a full realization, consistent with "smallest testable vertical slice."

**ADRs:** ADR-002 (gateway) — reused exactly as built in Stage 3, no new provider code, `TextGenerationProvider.generate()` only. ADR-005 (retrieval) — not implicated yet (no retrieval endpoint exists); the evidence-link requirement it depends on is satisfied here. ADR-006 (async/outbox) — **not used in Stage 5**, confirmed deliberately: Work Item enqueue/dispatch remains Stage 6's responsibility per the corrected staging table; Stage 5 delivers the persistence-capable use case standalone, called directly (mirrors how Stage 4 was built before Stage 6 wires it into the outbox).

**Stage 4 artifacts:** `ProcessDocumentUseCase` is reused as a dependency (composition, not duplication) to obtain `TextChunkCandidate[]` — Stage 5 does not re-implement extraction/normalization/chunking. `TextChunkCandidate.document_id`/`sequence_number`/`text`/offsets flow directly into the new use case.

## 3. New Abstractions (justified, not invented for convenience)

* **Domain entities** (`app/modules/knowledge/domain/entities.py`, added alongside `TextChunkCandidate`): `KnowledgeElement`, `KnowledgeChunk`, `ChunkEvidenceLink` — dataclasses mirroring the ORM models exactly, following the same domain/infrastructure split every other module in this codebase already uses (e.g. `Project`, `Agent`).
* **Repository interfaces** (`app/modules/knowledge/domain/repositories.py`, new file): `KnowledgeElementRepository`, `KnowledgeChunkRepository`, `ChunkEvidenceLinkRepository` (ABCs), mirroring `ProjectRepository`/`AgentRepository`'s exact shape.
* **`ChunkEvidenceLinkRepository.exists_for_document(document_id) -> bool`** — the idempotency check (§5).
* **One new exception**, `SemanticExtractionError` (`app/modules/knowledge/domain/exceptions.py`): the provider's response could not be parsed into a valid `(element_type, label, description)` triple (malformed JSON, or `element_type` outside the frozen five-value enum). Never invents a business rule — an `element_type` the provider returns that isn't one of `concept`/`theme`/`method`/`claim`/`relationship` is rejected, not coerced.
* **`ExtractDocumentKnowledgeUseCase`** (`app/modules/knowledge/application/use_cases.py`, added alongside `ProcessDocumentUseCase`) — the actual Stage 5 orchestrator.

No Work Item interaction, no route, no new provider, no embedding call (that's Stage 7) — kept to exactly what Stage 5 needs.

## 4. Semantic Classification Design

One provider call per `TextChunkCandidate` (not one call for the whole document) — the natural continuation of Stage 4's per-chunk mechanical output, avoiding a separate "map many elements onto many chunks" reconciliation problem. Prompt asks for a strict JSON object:

```
Classify the following research excerpt as exactly one of: concept, theme, method, claim, relationship.
Respond with ONLY a JSON object: {"element_type": "...", "label": "...", "description": "..."}
- element_type: exactly one of concept, theme, method, claim, relationship
- label: a short name (a few words) summarizing the excerpt
- description: one or two sentences describing what the excerpt conveys

Excerpt:
"""
<chunk text>
"""
```

Response parsing strips optional markdown code fences, then `json.loads`; validates `element_type` against the frozen enum and `label` is non-empty. Any failure raises `SemanticExtractionError` — aborting before any persistence for that document (§5).

## 5. Idempotency

Unlike Stage 4 (pure functions, idempotent by construction), Stage 5 persists rows and calls a non-deterministic AI provider — naively reprocessing would create duplicate `KnowledgeElement`/`KnowledgeChunk` rows for the same source content. Resolution, using the frozen model's own invariants rather than inventing new ones: **before doing any provider call or persistence, check `ChunkEvidenceLinkRepository.exists_for_document(document_id)`.** If the document already has evidence links, it has already been semantically processed — the use case returns the existing persisted `KnowledgeChunk` rows for that document instead of reprocessing. This is the "detect an existing processing result" strategy, not "version/supersede" — supersession (`superseded_element_id`) is reserved for genuinely evolving understanding of an unchanged document, which is out of scope here (Research Document content is immutable once ingested, per `05_Constraints_and_Integrity.md` §5 — there is nothing that would legitimately trigger a new version of the same document's knowledge yet).

## 6. Atomicity

All provider calls for a document's chunks complete **before** any database write begins. If any chunk's classification fails, nothing is persisted for that document — no partially-classified document. Once all classifications succeed, all `KnowledgeElement`/`KnowledgeChunk`/`ChunkEvidenceLink` rows are written and committed together via the existing `UnitOfWork`, with rollback on any persistence-time exception — mirroring `CreateAgentWorkspaceUseCase`'s exact pattern (`try: ...; uow.commit() except: uow.rollback(); raise`).

## 7. Agent Scoping

`KnowledgeElement.agent_id`/`KnowledgeChunk.agent_id` are not-null — resolved via the same Document → Project → Agent chain Stage 6 already established for document-upload ownership checks (`project = projects.get_by_id(document.project_id)`, `agent = agents.get_by_id(project.agent_id)`), reusing `ProjectRepository`/`AgentRepository`, not duplicating that logic.

## 8. Testing Strategy

Unit: prompt/response parsing (valid JSON, code-fenced JSON, malformed JSON, invalid `element_type` value) using `FakeProvider`; idempotency check logic. Integration: real SQLite — a document with real Stage 4 output produces real, persisted, evidence-linked `KnowledgeElement`/`KnowledgeChunk` rows; reprocessing returns the same rows without duplicating; a provider failure partway through leaves zero rows persisted (rollback verified); agent scoping verified against real Agent/Project/Document rows. No automated test calls a real provider (`FakeProvider` throughout, per ADR-002/ADR-005's testability requirement, already established in Stage 3).

## 9. Validation Checklist (all confirmed before implementation began)

- [x] No new database entity — confirmed against `04_Logical_Data_Model.md` §3.5/§3.7/§4.1.
- [x] No provider re-implementation — confirmed against Stage 3's `app/ai/providers/`.
- [x] No Work Item / async wiring — confirmed against ADR-006 and the corrected 9-stage plan.
- [x] Stage 4's `ProcessDocumentUseCase`/`TextChunkCandidate` reused, not duplicated.
- [x] Idempotency and atomicity strategies use existing model invariants, not invented ones.
- [x] No ADR implicated — no frozen decision changes.
