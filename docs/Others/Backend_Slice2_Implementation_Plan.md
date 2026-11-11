# Backend Slice 2 — Knowledge Processing Pipeline Implementation Plan

**Status:** Complete (planning only — no code written)

**Date:** 2026-09-11

**Author:** Lead AI Software Engineer

**Authorizing review:** `docs/Backend_Slice2_AI_Readiness_Review.md` — verdict: no new ADR required; every entity Slice 2 needs is already specified in the frozen Database Baseline v1.

**Governing documents (unchanged by this plan):** ADR-002 (Provider Abstraction), ADR-004 (Storage and Memory Strategy), ADR-005 (Retrieval and Search Strategy), ADR-006 (Async Processing and Event Coordination), `04_AI_Architecture.md` §7/§9/§16, `04_Logical_Data_Model.md` §3.5–§3.7/§3.20/§18.

This plan mirrors `Authentication_Implementation_Plan.md`'s structure and discipline: it does not implement anything; it determines exactly what to build, in what order, against what already-approved decisions, and flags (rather than silently resolves) every choice the frozen baseline deliberately left open.

---

## 1. Current-State Findings

* `POST /projects/{project_id}/documents` (Stage 1, authenticated and ownership-checked as of Milestone 7 Stage 6) registers a Research Document and writes content to the object store. `processing_status` is set to `pending` and never advances — confirmed via `git grep` and direct reading of `UploadResearchDocumentUseCase`; no code anywhere reads or transitions it.
* `app/ai/`, `app/workers/`, and `app/modules/knowledge/` do not exist. No provider SDK or HTTP client for AI calls is installed.
* `Knowledge Element`, `Knowledge Chunk`, `Chunk Evidence Link`, and `Work Item` are fully specified in the frozen Logical Data Model (§3.5, §3.6/§3.7, §18 note, §3.20 respectively) but have no ORM realization, no domain entities, and are absent from `init_db()`'s registered metadata.
* `Agent`, `Project`, `Document` modules and the Authentication Boundary are complete, tested (164/164), and require no change for Slice 2 beyond what is noted in §10.
* No vector index table, no embedding storage, no retrieval endpoint of any kind exists.

## 2. Architecture Interpretation

Everything Slice 2 needs architecturally is already decided:

* **How AI providers are called:** ADR-002's provider-agnostic gateway. Not reopened.
* **How retrieval ranks candidates:** ADR-005's chunk-level hybrid retrieval (lexical + semantic, RRF fusion). Not reopened.
* **How long-running work is scheduled:** ADR-006's async/outbox model. Not reopened.
* **Where data lives:** ADR-004's storage-category mapping (structured core, vector index). Not reopened.

What is genuinely left to this plan, because ADR-002 and ADR-004 explicitly delegated it: **which concrete provider** realizes the gateway first, and **which concrete mechanism** realizes the "in-process vector index." Both are configuration-level choices, not architecture — recorded here per the readiness review's §17 finding, exactly as Milestone 7 Stage 1 recorded SHA-256-over-bcrypt as a physical-realization detail rather than escalating it.

## 3. Knowledge Processing Pipeline Design

```
POST /projects/{id}/documents  (synchronous, existing + one addition)
        │
        ├─ existing: validate, store bytes, persist Research Document row
        └─ new: enqueue Work Item (kind=pipeline_stage, payload_reference="process_document:<document_id>")
                — same transaction/commit as the document row (outbox discipline, invariant 10)
        ↓
   [returns 201 to the client — unchanged response shape/timing]

In-process executor (asynchronous, background)
        ↓
   Work Item picked up (state: queued → running)
        ↓
   ProcessDocumentUseCase.execute(document_id)
        │
        ├─ 1. Read document content from the object store
        ├─ 2. Provider call: extract Knowledge Elements (concepts/claims) from the content
        ├─ 3. Persist Knowledge Elements (agent_id resolved via document → project → agent)
        ├─ 4. Derive one Knowledge Chunk per Element (content = element.description)
        ├─ 5. Persist Knowledge Chunks + Chunk Evidence Links (chunk ↔ source document)
        ├─ 6. Provider call: embed each chunk's content
        ├─ 7. Persist embeddings to the vector index table
        └─ 8. Update Research Document.processing_status → processed (or failed, with last_error)
        ↓
   Work Item state: running → succeeded (or failed, bounded retry per ADR-006 Decision 5)

GET /knowledge/search?q=...  (synchronous, new)
        ↓
   Resolve caller's Agent (get_current_user_id → Agent.get_by_user_id)
        ↓
   Embed the query text (one provider call)
        ↓
   Lexical search (SQLite) + vector search (brute-force cosine) over the Agent's chunks
        ↓
   RRF fusion → ranked chunks, each with its Chunk Evidence Link → source document
```

**Recommendation (flagged, not silently decided — see §19 item 1):** Slice 2 implements steps 2–7 as one continuous run inside a single Work Item's execution, rather than as separate Work Items chained by discrete `document_ingested`/`knowledge_updated`/`index_updated` events. ADR-006 Decision 2 names those events as the coordination mechanism; collapsing them into one execution is a scope simplification for the minimal slice, not a contradiction — each step remains independently identifiable in code and log output, and splitting them into separate Work Items later is additive (new `payload_reference` stage names, or use of the existing `domain_event` kind value), not a redesign.

## 4. Provider Abstraction Realization

**Interface** (`app/ai/providers/base.py`):

```python
class TextGenerationProvider(Protocol):
    def generate(self, prompt: str) -> str: ...

class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...
```

**First concrete provider:** an OpenAI-compatible Chat Completions + Embeddings API (`app/ai/providers/openai_compatible.py`), selected via configuration (`Settings.ai_provider`, `ai_api_key`, `ai_model`, `ai_embedding_model` — following the exact pattern `auth_username`/`auth_password_hash` already established). No provider SDK is installed; the concrete implementation calls the HTTP API directly (see §13) behind the interface above, so swapping providers later means writing one new file, not touching `modules/knowledge/`.

**Correction (Stage 9 validation, 2026-09-11):** the real-provider validation used a Google Gemini account, initially routed through the OpenAI-compatible shim against Gemini's own OpenAI-compatibility layer. This worked, but required live discovery of Gemini-specific model names and surfaced avoidable friction; the project owner directed a switch to Google's native `google-genai` SDK instead. Added `app/ai/providers/google_genai.py` (`GoogleGenAIProvider`, implementing the same `TextGenerationProvider`/`EmbeddingProvider` protocols) and `app/ai/providers/factory.py` (`create_provider(settings)`, dispatching on `Settings.ai_provider`). **`google_genai` is now the default provider** (`Settings.ai_provider`, `ai_model="gemini-3.6-flash"`, `ai_embedding_model="gemini-embedding-001"`); `openai_compatible` remains available and selectable the same way — the gateway pattern itself (ADR-002) is unchanged, only the "first concrete provider" recorded here is corrected. No `modules/knowledge/` code changed as a result, confirming the abstraction held exactly as designed.

## 5. Work Item / Outbox Realization

ORM model (`app/workers/models.py`) realizing `04_Logical_Data_Model.md` §3.20 exactly — no attribute changes:

**Correction (caught before implementation, not after):** an earlier draft of this section modeled `kind` as an open-ended value (`process_document`). Re-reading `04_Logical_Data_Model.md` §3.20 shows `kind` is fixed to exactly two values — `pipeline_stage` / `domain_event` — with the *specific* unit of work identified by `payload_reference`, not by `kind`. Corrected below; Slice 2 uses `kind = pipeline_stage` for every item it enqueues (it introduces no domain-event dispatch), and encodes the specific stage and target in `payload_reference` as a single structured string (`"process_document:<document_id>"`) — no schema invention, no new enum members.

| Column | Type | Notes |
|---|---|---|
| work_item_id | Integer PK | |
| kind | Enum (`pipeline_stage` / `domain_event`) | Slice 2 uses `pipeline_stage` exclusively |
| state | Enum (`queued` / `running` / `succeeded` / `failed`) | |
| payload_reference | String | `"process_document:<document_id>"` — the specific stage + target |
| idempotency_key | String, unique | Prevents duplicate enqueue/execution of the same document |
| attempts | Integer | Starts at 0 |
| last_error | Text, nullable | Failure context only — never a credential or secret |
| created_at | DateTime | |
| executed_at | DateTime, nullable | |
| completed_at | DateTime, nullable | |

Repository (`app/workers/repository.py`): `enqueue(kind, payload_reference, idempotency_key)`, `claim_next_queued()` (atomically transitions one `queued` row to `running`), `mark_succeeded(item)`, `mark_failed(item, error)` (increments `attempts`, returns to `queued` if under the bound, else `failed`).

**Executor:** an `asyncio` background task started in `main.py`'s `lifespan`, polling `claim_next_queued()` on a short interval (recommendation, §19 item 2) — no new process, no broker, consistent with ADR-006 Decision 3/4 exactly as it already anticipates for the MVP.

## 6. Vector Index Realization

New table (`app/modules/knowledge/infrastructure/vector_models.py`): `knowledge_chunk_embeddings(chunk_id PK/FK → knowledge_chunks, embedding_vector Text, embedding_model_version String, created_at DateTime)`. `embedding_vector` is stored as a JSON-encoded list of floats (recommendation, §19 item 3) — simplest, dependency-free, and human-inspectable; migration to a packed binary format or a native vector extension is a storage-detail change only, per ADR-004's own migration path.

Similarity search: brute-force cosine similarity computed in Python over the calling Agent's chunk rows only (never cross-agent — same scoping discipline as Stage 6's document-ownership check). No new dependency required (§13).

## 7. Knowledge Module Design

```text
backend/app/modules/knowledge/
├── domain/
│   ├── entities.py        # KnowledgeElement, KnowledgeChunk (dataclasses, §3.5/§3.7)
│   ├── enums.py            # ElementType, ElementStatus, CreatedBy
│   ├── exceptions.py        # KnowledgeDomainError and subclasses
│   └── repositories.py       # KnowledgeElementRepository, KnowledgeChunkRepository (ABC)
├── application/
│   ├── use_cases.py           # ProcessDocumentUseCase, SearchKnowledgeUseCase
│   └── retrieval.py             # hybrid search: lexical + vector + RRF fusion (pure function, no I/O)
├── infrastructure/
│   ├── models.py                # SQLAlchemy: KnowledgeElement, KnowledgeChunk, ChunkEvidenceLink
│   ├── vector_models.py           # KnowledgeChunkEmbedding (§6)
│   └── repositories.py             # SqlAlchemy* realizations
└── interface/
    ├── schemas.py                   # SearchResultResponse, etc.
    └── routes.py                     # GET /knowledge/search
```

This mirrors the existing `modules/agent/`, `modules/project/`, `modules/document/` layering exactly — no new architectural pattern.

**Correction (Stage 4 completion, 2026-09-11):** the original draft above assumed `ProcessDocumentUseCase` would call the AI provider to derive real Knowledge Elements directly. A Stage 4 reconciliation (triggered by the Stage 4 engineering prompt's own instruction not to call the provider merely because the gateway exists) found a genuine conflict: `KnowledgeChunk.element_id` is a not-null FK, and every `Knowledge Element` type (concept/theme/method/claim/relationship) means semantic interpretation everywhere it is defined (`02_Domain_Model.md` §4, `02_System_Components.md` §3.3, `04_AI_Architecture.md` §7) — there is no enum value for "raw, uninterpreted excerpt." Manufacturing a placeholder Knowledge Element to satisfy the FK would persist a semantically false record. Resolved (with explicit sign-off): Stage 4 produces a new, deliberately transient value object, `TextChunkCandidate` (`app/modules/knowledge/domain/entities.py`), and does **not** persist `KnowledgeElement`, `KnowledgeChunk`, or `ChunkEvidenceLink` at all. Real semantic extraction (the actual AI provider call) and persistence of those three entities moves to Stage 5, renamed **Semantic Extraction & Persistence**, consuming Stage 4's `TextChunkCandidate` list as input. The staging table in §18 is corrected accordingly (one additional stage; final stage renumbered 9). No ADR is implicated — no frozen entity's shape changed, and ADR-002/ADR-006 are unaffected; this is a sequencing correction within Slice 2's own stages.

## 8. Authorization / Ownership (Retrieval Endpoint)

`GET /knowledge/search` depends on `get_current_user_id` (Stage 6's existing dependency, unchanged) and resolves the caller's Agent internally — the client never supplies `agent_id`. Every chunk repository query filters by the resolved `agent_id`, mirroring the exact ownership-scoping principle Stage 6 established for document upload (§15 security review). Since MVP is single-user, cross-agent leakage cannot currently be demonstrated end-to-end, but the query is written scoped regardless — the application must not depend on the single-user restriction as its security mechanism (the same standing principle Stage 6 was given for document ownership).

## 9. API Contract

```
GET /knowledge/search?q=<text>

200 OK
{
  "results": [
    {
      "chunk_id": 1,
      "content": "...",
      "summary": "...",
      "score": 0.83,
      "evidence": [{"document_id": 42, "title": "Baseline survey"}]
    }
  ]
}

401 — missing/invalid session (existing InvalidSessionError handling, unchanged)
404 — caller has no Agent yet (mirrors existing patterns; do not silently return an empty result set for "no Agent," since that is a different condition than "no matches")
422 — missing/empty q parameter
```

No new endpoint accepts a document upload or provider credential — the only new surface is this one read-only search endpoint.

## 10. Module / Package Placement

```text
backend/app/ai/
├── __init__.py
└── providers/
    ├── __init__.py
    ├── base.py              # TextGenerationProvider, EmbeddingProvider protocols
    └── openai_compatible.py  # concrete realization (§4)

backend/app/workers/
├── __init__.py
├── models.py       # Work Item ORM (§5)
├── repository.py    # WorkItemRepository (§5)
└── executor.py        # polling background task (§5)

backend/app/modules/knowledge/   # (§7)
```

**Changes elsewhere:**

| Location | Change |
|---|---|
| `app/core/config.py` | Add `ai_provider`, `ai_api_key`, `ai_model`, `ai_embedding_model` settings fields. |
| `app/core/dependencies.py` | Add providers for `WorkItemRepository`, the knowledge repositories, `ProcessDocumentUseCase`, `SearchKnowledgeUseCase` — mirroring the existing provider pattern exactly. |
| `app/api/router.py` | Add `from app.modules.knowledge.interface import routes as knowledge_routes` + `include_router`. |
| `app/database/session.py` | `init_db()` gains imports of `app.workers.models` and `app.modules.knowledge.infrastructure.models`/`vector_models` so they register on `Base.metadata`. |
| `app/modules/document/application/use_cases.py` | `UploadResearchDocumentUseCase` gains a `WorkItemRepository` dependency and enqueues a `process_document` Work Item inside its existing `UnitOfWork` transaction. |
| `main.py` | `lifespan` starts the executor background task (§5) alongside existing startup steps; stops it on shutdown. |
| `app/modules/agent/*`, `app/modules/project/*` | **No change.** |
| `pyproject.toml` | Add `httpx` if not already present (transitively via FastAPI's test client — confirm at Stage 3, not now). |

## 11. Dependency Direction

```
API (routes) → Application (use cases) → Domain (entities)
Application (ProcessDocumentUseCase) → app/ai/providers (interface only) → Infrastructure (concrete provider)
Application (ProcessDocumentUseCase) → Infrastructure (knowledge repositories, work item repository)
```

Explicitly verified clean against every prohibited arrow:
* **Domain → FastAPI / provider SDK / SQLAlchemy:** none — `KnowledgeElement`/`KnowledgeChunk` remain framework-free dataclasses, exactly like every other domain entity in this codebase.
* **Application → HTTP client / provider-specific request format:** none — `ProcessDocumentUseCase` depends only on the `TextGenerationProvider`/`EmbeddingProvider` protocols (§4), never on `httpx` or a provider's request/response shape directly.

## 12. File Impact Matrix

| File | Category | Why |
|---|---|---|
| `app/ai/providers/*` (3 files) | **Create** | Provider Abstraction gateway (§4). |
| `app/workers/*` (3 files) | **Create** | Work Item realization + executor (§5). |
| `app/modules/knowledge/*` (10 files) | **Create** | Knowledge module (§7). |
| `app/core/config.py` | **Modify** | Add AI provider settings. |
| `app/core/dependencies.py` | **Modify** | New providers, per §10 table. |
| `app/api/router.py` | **Modify** | Register the new search route. |
| `app/database/session.py` | **Modify** | Register new ORM metadata. |
| `app/modules/document/application/use_cases.py` | **Modify** | Add Work Item enqueue (§10). |
| `main.py` | **Modify** | Start/stop the executor. |
| `app/modules/agent/*`, `app/modules/project/*` | **No change** | Confirmed zero impact. |
| `tests/unit/`, `tests/integration/`, `tests/e2e/` (existing files) | **No change** | Unaffected by this addition — no existing route or use case signature changes except the one noted above, which existing document-upload tests do not assert against internals of. |
| New `tests/unit/test_knowledge_*.py`, `test_workers_*.py`, `test_ai_providers_*.py`; `tests/integration/test_knowledge_*.py`, `test_workers_*.py`; `tests/e2e/test_knowledge_search_api.py` | **Create** | Per §14. |

## 13. Dependency / Package Analysis

* **HTTP client for the provider call:** `httpx` (recommendation, §19 item 4) — already a transitive dependency via `starlette`'s test client; promoting it to a direct dependency for the provider implementation avoids adding a heavier provider SDK.
* **Cosine similarity:** pure Python (`sum`/`math.sqrt` over lists), **no `numpy` dependency** (recommendation, §19 item 5) — the MVP corpus size (a few thousand chunks at most, single user) does not justify a new numerical dependency; revisit only if a measured performance problem appears.
* **No new database engine or extension** — the vector index is a plain table in the existing SQLite database (§6).
* Not installed or modified in `pyproject.toml` during this planning stage.

## 14. Testing Strategy

**Unit** (no DB, no network):
* `TextGenerationProvider`/`EmbeddingProvider` protocol conformance via a `FakeProvider` test double — **no automated test may call a real AI provider** (§15).
* Cosine similarity function: known-vector test cases (identical vectors → 1.0, orthogonal → 0.0).
* RRF fusion function: known lexical/semantic rank inputs → expected fused order.
* Knowledge domain entities: construction/validation rules.

**Integration** (real SQLite, `FakeProvider` injected):
* `WorkItemRepository`: enqueue, claim-next-queued (atomicity — two claims never return the same row), mark-succeeded/failed, bounded-retry transition.
* Knowledge repositories: create/get Knowledge Element, Knowledge Chunk, Chunk Evidence Link against real persistence.
* `ProcessDocumentUseCase` end-to-end against a `FakeProvider`: document → elements → chunks → evidence links → embeddings persisted → `processing_status` transitions to `processed`.
* Failure path: `FakeProvider` raises → Work Item transitions to `failed` (or retries within bound) → `processing_status` transitions to `failed` with `last_error` populated — document row and object-store content are untouched (no partial corruption).

**E2E** (real HTTP, `FakeProvider` dependency-overridden — same pattern Stage 5/6 used for `get_content_store`):
* Upload → executor drains the queue → `GET /knowledge/search?q=...` returns the expected chunk with its evidence link back to the uploaded document, over **separate HTTP requests**, matching the discipline that caught the Stage 5 commit bug.
* Search with no matching content → empty result set, not an error.
* Search before processing completes → empty result set (no partial/uncommitted chunks ever returned) — an explicit test, since eventual consistency (ADR-006 Consequences) means this is a real, expected state, not a bug.
* Cross-agent scoping: a second provisioned user's chunks never appear in the first user's search results (mirrors Stage 6's cross-owner ownership test).

## 15. Security Review (planned checks, to run at Stage 8)

* `ai_api_key` never logged, never included in `last_error`, never returned in any API response.
* No provider SDK or raw HTTP client import in `modules/knowledge/domain` or `application`.
* Search results never cross agent boundaries (§8, §14).
* **Flagged, not solved here:** prompt injection via document content (a document's own text becomes part of the extraction prompt) is not addressed by any current ADR or requirement. This is a known, real category of risk for any LLM-based extraction pipeline; recording it here as an explicit open item for a future review rather than silently ignoring it or inventing an unreviewed mitigation now.

## 16. PostgreSQL Compatibility

All new tables (Work Item, Knowledge Element, Knowledge Chunk, Chunk Evidence Link, the vector-index table) are defined through SQLAlchemy behind the existing data access layer, using no SQLite-specific types or syntax — consistent with ADR-004's stated migration path. The brute-force-cosine vector search is pure Python operating on rows fetched via the ORM, so it is engine-agnostic; the eventual dedicated-vector-store migration (ADR-004 §Future Considerations) replaces only the vector-index infrastructure module, not the retrieval contract or the domain layer.

## 17. Traceability

* Knowledge processing: AIR-007 to AIR-012, MVP-005, MVP-006, DR-007 to DR-009.
* Retrieval: AIR-022 to AIR-027, AIR-067, AIR-068, MVP-007, MVP-008, ADR-005.
* Async/outbox: AIR-063, AIR-064, NFR-001 to NFR-006, ADR-006.
* Provider abstraction: AIR-040 to AIR-042, ADR-002.
* Architecture: `05_Backend_Architecture.md` §7 (AI Service Layer), §8 (Knowledge Service), §6 (Internal Orchestration).

## 18. Implementation Staging Proposal

| Stage | Objective | Key files | Tests | Gate |
|---|---|---|---|---|
| **1 — Planning** | This document. | — | — | Explicit authorization to begin Stage 2 |
| **2 — Knowledge & Outbox Scaffolding** | Package skeletons; Work Item + Knowledge Element/Chunk/Evidence Link ORM models registered in `init_db()`. No behavior yet. | `app/workers/models.py`, `app/modules/knowledge/infrastructure/models.py`, `session.py` | Boot smoke test only | App still boots, `/health` still 200, schema creates cleanly |
| **3 — Provider Gateway** | Interface + one concrete provider, configuration-wired. | `app/ai/providers/*`, `config.py` | Unit: `FakeProvider` + real-provider unit test against a stubbed HTTP layer | Gateway callable in isolation, no domain coupling |
| **4 — Mechanical Extraction & Chunking** *(corrected scope, complete)* | `ProcessDocumentUseCase` (document → extracted text → normalized text → `TextChunkCandidate[]`). No provider call, no persistence — deterministic only. Called directly in tests. | `modules/knowledge/domain/{entities,text_extraction,text_normalization,chunking,exceptions}.py`, `application/use_cases.py` | Unit (extraction/normalization/chunking) + integration against real SQLite + real filesystem | Deterministic, traceable, transient chunks produced from a real uploaded document; no Knowledge Element/Chunk/Evidence Link rows created |
| **5 — Semantic Extraction & Persistence** *(renamed; provider call moves here)* | Consumes Stage 4's `TextChunkCandidate[]`; calls the AI provider to derive real `KnowledgeElement`/`KnowledgeChunk`/`ChunkEvidenceLink` rows. | `modules/knowledge/infrastructure/repositories.py`, `application/use_cases.py` (extended) | Unit + integration against `FakeProvider` and real SQLite | Pipeline produces correct, persisted, evidence-linked, genuinely-interpreted knowledge |
| **6 — Async Dispatch** | Work Item enqueue on upload; executor drains the queue and runs Stages 4+5 as one execution; `processing_status` transitions. | `document/application/use_cases.py`, `app/workers/*`, `main.py` | Integration: enqueue→claim→execute→status transition, including the failure/retry path | Upload triggers real (test-provider) processing over separate requests |
| **7 — Embedding & Vector Index** | Embedding call per chunk; vector index table; cosine similarity function. | `modules/knowledge/infrastructure/vector_models.py`, `application/retrieval.py` | Unit: cosine correctness; integration: embeddings persisted | Chunks are embedded and retrievable by similarity |
| **8 — Hybrid Retrieval Endpoint** | `GET /knowledge/search`; lexical+vector+RRF fusion; evidence in response. | `modules/knowledge/interface/*`, `application/retrieval.py` | Unit: RRF fusion; API tests for all documented status codes | Search returns correct, evidence-linked, agent-scoped results |
| **9 — Testing & Final Validation** | Full regression; fresh-environment real-HTTP exercise (upload → process → retrieve, over separate requests); security review; governance sync. | test suite, `Project_Status.md`, journal | Full suite green | Slice 2 complete |

Each stage stops for explicit authorization before the next begins, per the established discipline — this plan does not authorize auto-progression.

## 19. Risks and Unresolved Decisions

These are recommendations, not blocking questions — flagged explicitly rather than silently decided, per this project's standing discipline:

1. **Pipeline coordination granularity** (§3) — one Work Item runs extract→chunk→embed→index as a single execution, rather than discrete events per ADR-006 Decision 2's example list. Recommended as an MVP simplification; splitting into finer-grained events later is additive.
2. **Executor mechanism** (§5) — an `asyncio` polling task inside the existing process, not a separate worker process. Recommended for MVP simplicity; consistent with ADR-006 Decision 3/4's own stated extraction path when it's eventually needed.
3. **Embedding storage encoding** (§6) — JSON-encoded float list, not packed binary. Recommended for simplicity and inspectability at MVP corpus scale; a storage-format change only if it ever matters.
4. **HTTP client choice** (§13) — `httpx`, not a provider SDK. Recommended to keep the gateway thin and provider-swap costs low.
5. **No `numpy` dependency** (§13) — pure-Python cosine similarity. Recommended to avoid a new dependency before there is a measured need.
6. **Real-provider verification strategy for Stage 8 — resolved.** Confirmed 2026-09-11: Stage 8's real-HTTP verification uses a real API key against a real AI provider, proving the full loop end-to-end (not a stub), consistent with how every prior milestone's final stage exercised the real, fully-wired system. The key is supplied at Stage 8, sourced the same way `AUTH_PASSWORD_HASH` was — via configuration, never hard-coded, never committed, never logged.

**Already resolved, recorded here for completeness, not open:** the ADR question itself (no new ADR required, per the readiness review §17); which entities are needed (none new, per readiness review §16).

## 20. Final Readiness Verdict

**READY FOR STAGE 2**

The plan is complete and internally consistent. Every entity it depends on is already specified in the frozen Database Baseline v1 (readiness review §15/§16); no ADR is required (§17 there, restated in §2 here). The six flagged items in §19 are recommendations with stated rationale, not invented assumptions — none blocks starting Stage 2's scaffolding; items 1–5 matter starting Stage 3–7, and item 6 matters only at Stage 8, leaving time to confirm without stalling.
