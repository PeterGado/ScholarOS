# Project Writing — Implementation Plan

**Status:** Implementation in progress — Stages 2-4 complete; Stage 5 is next. All six open decisions in §19 were resolved by explicit user approval on 2026-09-12 — see §19 for the recorded decisions.

**Date:** 2026-09-12 (approved 2026-09-12)

**Author:** Lead AI Software Engineer

**Scope:** Architecture reconnaissance, product reconciliation, and staged implementation plan for the Project Writing milestone. This document does not implement anything.

---

## 1. Executive Summary

Project Writing turns the already-validated Slice 2 backend (upload → process → understand → retrieve) into a system that produces evidence-grounded, style-aware, project-specific draft writing. The central finding of this reconnaissance is that **the hard design work is mostly already done**: the frozen Database Baseline v1 (Milestone 5, 2026-08-07) already fully specifies `Draft` , `Draft Version` , `Review` , `Review Decision` , `Writing Profile` , `Profile Characteristic` , `Memory Record` , `Conversation` , `Message` , and four evidence/provenance link entities ( `Draft Evidence Link` , `Memory Provenance Link` , `Message Context Link` , `Profile Characteristic Source` ) — none implemented in code yet, all specified with complete attributes, keys, lifecycles, and invariants. Project Writing's job is to **realize** these entities (the same relationship Slice 2 had to `Knowledge Element` / `Knowledge Chunk` / `Session` / `Work Item` before it existed), not invent a new domain model from scratch.

Two genuine gaps were found and are reported, not silently resolved (§19): (1) Backend Architecture has no named "Writing Service" domain — Draft creation sits in an architectural blind spot between the AI Service Layer (generates, doesn't own data) and the Review Service (evaluates, doesn't create); (2) there is no frozen home for "similar-project" material that is retrievable but must never be mistaken for evidence — every existing knowledge-shaped entity either commits it to the evidence system ( `Knowledge Element` / `Knowledge Chunk` ) or doesn't fit at all ( `Memory Record` ). Writing style has no such gap: `Writing Profile` / `Profile Characteristic` already provide a structurally separate, evidence-incapable home for it.

The recommended smallest coherent architecture: build a new `modules/writing/` service (additive, no ADR needed) that persists Draft/Draft Version/Review through the already-frozen schema; reuse the existing Provider Abstraction, Work Item/outbox, and Stage 8 retrieval exactly as they exist today; ship MVP writing generation using **research knowledge + writing style + project topic** as inputs, with **similar-project material explicitly deferred** until its one open schema question (§19) is resolved.

---

## 2. Product Model

Confirmed unchanged and preserved throughout this plan — nothing here contradicts it:

```
User (exactly one, ADR-010)
  → Agent (exactly one, ADR-009) — the persistent project-writing workspace
      → Project (exactly one, permanent) — identity, topic, raw source material
      → Knowledge Element / Knowledge Chunk (Slice 2) — scoped to Agent
      → Writing Profile / Profile Characteristic (frozen, unbuilt) — scoped to Agent
      → Memory Record (frozen, unbuilt) — scoped to Agent
      → Draft / Draft Version / Review / Review Decision (frozen, unbuilt) — scoped to Agent
```

**Agent = Project Workspace** is not a new claim this plan introduces — it is ADR-009's own decision, already implemented and tested (Stages 6-9 of Slice 2 verified Agent-scoping end to end). Every entity this plan touches carries `agent_id` , directly or transitively, exactly as invariant 1 ( `05_Constraints_and_Integrity.md` §Agent scoping) already requires. The one-Agent-per-user, one-Project-per-Agent-permanent pairing is unchanged; nothing in this plan proposes multiple projects, multiple agents, or repointing.

---

## 3. Current Backend Capabilities (what already exists and is reused unchanged)

| Capability | Status | Reused as-is |
|---|---|---|
| Agent/Project creation, ownership chain | Built, tested (Slice 1, Stage 6) | `AgentRepository` , `ProjectRepository` , Document→Project→Agent resolution pattern |
| Authentication (session, bearer token) | Built, tested (Milestone 7) | `get_current_user_id` , agent resolved from authenticated identity, never from client |
| Document upload, mechanical extraction/chunking | Built, tested (Stages 1, 4) | `UploadResearchDocumentUseCase` , `ProcessDocumentUseCase` , `TextChunkCandidate` |
| Semantic classification → Knowledge Element/Chunk/Evidence Link | Built, tested (Stage 5) | `ExtractDocumentKnowledgeUseCase` , `classify_chunk` |
| Embedding + vector index | Built, tested (Stage 7) | `ChunkEmbedding` , `KnowledgeChunkEmbeddingRepository` , `rank_by_similarity` |
| Async Work Item / outbox executor | Built, tested (Stage 6) | `WorkItemRepository` , `process_one_work_item` , `WorkItemExecutorLoop` |
| Agent-scoped vector retrieval | Built, tested (Stage 8) | `SearchKnowledgeUseCase` — **vector-only, not hybrid (§9)** |
| AI Provider gateway (2 concrete providers) | Built, tested (Stage 3, corrected Stage 9) | `TextGenerationProvider` , `EmbeddingProvider` , `create_provider(settings)` |
| Real-provider validation | Done (Stage 9) | Real Gemini account, full upload→search loop proven |

Nothing above needs to change for Project Writing to begin. This is the load-bearing fact behind "smallest coherent architecture."

---

## 4. Architecture Reconciliation

Mapping the frozen architecture onto the proposed writing system, section by section of `05_Backend_Architecture.md` :

* **§4.1 Domain Inventory** lists `Review` ("Draft evaluation, approval state, revision records") but **no domain for Draft creation itself**. `Author Profile` is listed as a domain but has no dedicated numbered service section anywhere in the document (the closest is AI Architecture's Author Profile Integration, §9, and Backend Architecture §22.2's composition list, which names "Author Profile" as one of the services composed by the Agent Service without ever giving it its own `§X Author Profile Service` write-up).
* **§7 AI Service Layer** explicitly disclaims data ownership: "The AI service layer consumes domain data through the data access layer; it does not own project, document, or draft data" (§7.3). Its Structure table (§7.2) lists "Drafting" as a capability referencing AI Architecture §20, but that is a *capability*, not a *service boundary* — it says nothing about who persists a `Draft` row.
* **§14 Review Service** owns evaluating drafts, not creating them: "Support user review of drafts... Record revision requests and approval decisions... Preserve review state and version history" — every responsibility is about a draft that already exists.
* **§22.2 Agent Service** lists what it composes: "the Knowledge, Memory, Conversation, Author Profile, Review, and Configuration services" — **Draft/Writing is conspicuously absent from this list**, even though `Draft`/`Draft Version` are fully specified frozen entities under the Agent's own ownership (`04_Logical_Data_Model.md` §3.15/§3.16).

**This is a real architectural gap** (reported formally in §19), not a contradiction requiring a fix to an existing frozen decision — no existing text is wrong, something is simply missing. **Recommendation:** introduce a new peer domain, **Writing Service** ( `modules/writing/` ), realizing exactly the Draft/Draft Version data domain already frozen, mirroring precisely how `modules/knowledge/` realizes the already-frozen Knowledge Element/Knowledge Chunk domain. This requires **no ADR** — no frozen decision is being changed, no schema is being altered, no ownership chain is being redrawn; it is the same category of gap-filling Slice 2 performed for `Session` / `Work Item` (ADR-010's own precedent: "an entity architecturally implied but never fully realized... formally specified and realized"). The only housekeeping this implies is appending a new `§23 Writing Service` section to `05_Backend_Architecture.md` when implementation actually begins (append-don't-renumber, per `04_Repository_Governance.md` §4.4) — **not done in this stage**, per the explicit instruction not to modify frozen documents now.

ADRs reconciled:

| ADR | Relevance | Verdict |
|---|---|---|
| ADR-001 (Separation) | Requirements/architecture/implementation stay separated | No conflict |
| ADR-002 (Provider Abstraction) | `TextGenerationProvider` is reused unmodified (§10) | No conflict |
| ADR-003 (Modular Monolith) | `modules/writing/` is a new bounded context, same pattern as `modules/knowledge/` | No conflict |
| ADR-004 (Storage) | No new storage category; structured core only | No conflict |
| ADR-005 (Retrieval) | Vector-only implementation still open (§9) — reconciled, not resolved, here | **Open, reported** |
| ADR-006 (Async/Outbox) | Work Item/executor reused for generation (§11) | No conflict |
| ADR-007 (Deployment) | Single-node MVP unaffected | No conflict |
| ADR-008 (API Governance) | New API surface defined progressively as code (§14), no new ADR needed unless an architecturally significant decision emerges | No conflict |
| ADR-009 (Agent/Project) | Agent = Project Workspace preserved exactly | No conflict |
| ADR-010 (Auth) | Every new route requires the existing `get_current_user_id` | No conflict |

---

## 5. Domain Model — Reconciling Research / Similar-Project / Style / Knowledge / Memory / Writing Task / Draft / Evidence

This section answers §4/§5 of the brief directly: **these are not one knowledge system with metadata tags — they are three structurally distinct systems, two of which already exist in the frozen model, one of which has a real, unresolved gap.**

### A. Research knowledge — reuse unchanged

`Research Document → Knowledge Element → Knowledge Chunk → Chunk Evidence Link` (Slice 2, built). This *is* the evidence system: `Draft Evidence Link.target_type` only accepts `knowledge_chunk` or `research_document` ( `04_Logical_Data_Model.md` §4.2) — nothing else can ever be cited as evidence, by construction. No changes needed.

### B. Writing-style material — already has a safe, separate home

`Writing Profile` (§3.11) + `Profile Characteristic` (§3.12) + `Profile Characteristic Source` (§4.5, provenance to the samples that informed a characteristic) are fully frozen and **structurally incapable of being cited as evidence** — `Draft Evidence Link` 's exclusive-arc target list does not include Writing Profile or Profile Characteristic at all. Style cannot leak into the evidence chain even by accident; the schema itself prevents the exact confusion §5. C warns about. **Gap:** the ingestion pipeline (style document → Profile Characteristic) does not exist in code yet — this is new work (§13, Stage 3 below), not new design.

### C. Similar-project material — the genuine, unresolved gap

No frozen entity fits. `Knowledge Element` / `Knowledge Chunk` would make it evidence-eligible (wrong — it is not the user's own research). `Memory Record` 's `record_type` enum ( `objective / hypothesis / method / decision / terminology / guidance / other` ) does not describe "structural/organizational reference material" and its `content` field is sized for a decision statement, not a reference document's worth of structural patterns. There is no third option in the frozen model. **This is reported as an open decision in §19, not resolved here.** Recommendation: **defer similar-project ingestion from MVP Project Writing** rather than force it into a wrong-fitting entity or add a schema correction under time pressure. Writing generation ships using research knowledge + style + topic; similar-project material becomes its own later stage once the schema question is deliberately decided (most likely resolution sketched in §19: an additive `source_category` on a *new, non-evidence-eligible* structure — not a correction to `Knowledge Element` , to avoid ever making it evidence-eligible by construction).

### D. Memory — already frozen, reused

`Memory Record` (§3.8) is the "Agent learns over time" mechanism already specified: `record_type` , `content` , `rationale` , `status` (current/superseded), `superseded_record_id` chain. `Memory Provenance Link` (§4.3) already traces a memory record to what produced it — including `draft_version_id` and `review_decision_id` as valid sources, meaning **the frozen model already anticipated that approved writing decisions can become project memory**. No new entity needed; see §8 for behavior.

### E. Writing Task / Draft / Evidence — already frozen, reused

See §8. `Draft` is the writing task; `Draft Version` is the immutable per-generation/per-revision output; `Review` / `Review Decision` are the approval mechanism; `Draft Evidence Link` is the citation mechanism. No new parallel entities.

---

## 6. Context Model

What can enter a writing generation's context, and how it is assembled — concretized against Slice 2's real building blocks, realizing the already-frozen `04_AI_Architecture.md` §6 Context Assembly Pipeline:

```
Draft/Draft Version generation request
        │
        ├── Project.topic (permanent, from Project Service — already exists)
        ├── User instructions for this generation (NEW — no frozen field holds this today, §19)
        ├── Research knowledge: SearchKnowledgeUseCase(query=derived from topic+instructions) 
        │     → ranked Knowledge Chunks, each with Chunk Evidence Link → Research Document
        ├── Writing style: active Writing Profile's Profile Characteristics for this Agent
        ├── Relevant Memory Records (current status only, agent-scoped)
        └── (deferred) Similar-project context — not in MVP, see §5.C
                │
                ▼
        Context Assembly (pure function, no I/O — mirrors ProcessDocumentUseCase's own purity)
                │
                ▼
        Prompt construction (single string, same pattern as Stage 5's classify_chunk prompt)
                │
                ▼
        TextGenerationProvider.generate(prompt) — existing, unmodified
                │
                ▼
        New Draft Version (content = response) + Draft Evidence Links (one per Knowledge Chunk used)
```

Addressing each required point explicitly:

* **Retrieval ordering / source prioritization:** research knowledge ranked by `rank_by_similarity` (Stage 7, unchanged); style characteristics included wholesale (the Writing Profile is small — a handful of `Profile Characteristic` rows, per DR-010 to DR-012 — not a ranked retrieval problem); memory included by agent-scope + `status=current` filter (mirrors the `status=CURRENT` filter Stage 8 already added for Knowledge Chunk).
* **Context limits / truncation:** `04_AI_Architecture.md` §17 (Context Window Management) already governs this: "Fit the most relevant context... Prioritize task-relevant... over peripheral... When the full relevant context exceeds capacity, prioritization and summarization decisions remain explainable." For MVP: cap the number of retrieved chunks (reuse `top_k`, already implemented) and truncate deterministically (never mid-sentence) if the assembled prompt exceeds a configured character budget — an implementation-level default, not a frozen requirement.
* **Evidence selection:** every Knowledge Chunk actually included in the prompt gets a `Draft Evidence Link` recorded against the resulting Draft Version — provenance is what was *used*, not merely what was *available* (matches DR-018/AIR-027's "annotation connecting a Draft Version to the Knowledge Chunks... that support it").
* **Duplicate/conflicting context:** out of scope for MVP synthesis logic — the LLM is given the ranked, deduplicated (by `chunk_id`) evidence set and is instructed (via prompt, not new architecture) to note disagreement rather than silently pick a side; a dedicated "conflict resolution" capability is a Future Roadmap item (`04_AI_Architecture.md` §21 Reflection Loop territory), not MVP.
* **Citation generation:** represented via `Draft Evidence Link` rows, not inline citation-formatting text — "Citation awareness, not citation management" is the frozen invariant (`05_Constraints_and_Integrity.md` line 202); automated citation formatting is explicitly out of MVP scope (SRS Ch10 §4).
* **Unsupported claims / insufficient evidence:** per AIR-046/AIR-048, when retrieval returns too few or no relevant chunks for the requested target, the Writing Service must not silently generate ungrounded content — see §10.
* **Style / similar-project influence:** style characteristics are included as *style signals only* in the prompt, explicitly labeled as such (never presented to the LLM as factual content); similar-project influence is deferred (§5. C).
* **User instructions overriding retrieved context:** user instructions are passed as the primary framing of the prompt (matching AIR-028: "construct task-specific prompts from the current project context, not solely from a single user instruction string" — instructions shape the request, they do not replace context).
* **Project-topic constraints:** `Project.topic` is always included and is immutable per Agent (already enforced — `Project.topic`/`agent_id` are immutable after creation,  `05_Constraints_and_Integrity.md` §5); no writing request can implicitly redefine it.

---

## 7. Research / Similar-Project / Style Separation

Already answered structurally in §5. Summary table:

| | Research | Style | Similar-project |
|---|---|---|---|
| Frozen entity | Knowledge Element/Chunk | Writing Profile/Profile Characteristic | **None — gap** |
| Evidence-eligible? | Yes (by design) | No (by design — schema excludes it) | N/A (deferred) |
| Retrieval mechanism | Vector search (Stage 8) | Direct fetch (small set, agent-scoped) | Deferred |
| MVP status | Reused as-is | New ingestion pipeline needed | Deferred to a later stage |

---

## 8. Memory Model

Four distinct concepts, mapped to frozen entities, answering §7's core question precisely:

| Concept | Frozen entity | What's allowed to enter it |
|---|---|---|
| **Permanent Agent configuration** | `Agent` , `Project.topic` (immutable) | Set once at Agent creation; never inferred, never auto-updated |
| **Project knowledge** | `Knowledge Element` / `Knowledge Chunk` | Derived from research documents via the AI provider (Stage 5) — already user-initiated (user uploads the document) |
| **Writing preferences** | `Writing Profile` / `Profile Characteristic` | Derived from user-supplied style samples (new pipeline, §13) — user-initiated |
| **Task history** | `Draft` / `Draft Version` / `Review` / `Review Decision` | Every writing request and its outcomes — system-recorded, not "memory" in the AI sense |
| **Actual Agent memory** | `Memory Record` | See below |

**What is allowed to be learned automatically, and what requires explicit user confirmation** — this is not a new design decision; it is already frozen and definitive: *"Memory is populated through user input and system-derived context; the system shall not infer memory elements without user awareness"* ( `04_AI_Architecture.md` §22.3, MVP-011). Concretely for Project Writing: an approved `Review Decision` (the user explicitly approving a draft) is a legitimate trigger for a new `Memory Record` (traced via `Memory Provenance Link.source_type = review_decision` ) — the user's own approval action *is* the required awareness/confirmation. A draft being merely *generated* (not yet reviewed) must never, by itself, create a Memory Record — that would be inference without user awareness, a direct violation of MVP-011.

**Cross-user learning** — the vision-level idea of the system "learning from other users" is **out of scope for this plan and for the MVP entirely**, not because of a new judgment call but because the MVP has exactly one possible user account (ADR-010: single pre-provisioned account) — there is no second user's data to learn from or leak to. `10_MVP_scope.md` 's Out-of-Scope table already excludes "Multi-user collaboration" and "Cross-project knowledge management" outright. **None of options 1-5 in the brief's §7 is chosen** — the question does not yet apply and building any mechanism for it now would be scope creep the current architecture doesn't need and can't safely support (there is no per-user data partition to test isolation against). Revisit only if/when multi-user is ever authorized as its own milestone.

---

## 9. Retrieval Architecture (ADR-005 discrepancy — answered as required)

**Question A — Can Project Writing reasonably begin using the existing vector retrieval?** **Yes.** `SearchKnowledgeUseCase` already returns agent-scoped, evidence-linked, ranked chunks — exactly the shape Context Assembly (§6) needs. Vector-only retrieval is a quality ceiling, not a functional blocker: it will miss some exact-term/quotation matches ADR-005's lexical half would catch, but nothing about *building* the writing system requires hybrid retrieval to exist first.

**Question B — Does writing require hybrid retrieval before implementation?** **No.** Writing consumes whatever `SearchKnowledgeUseCase` returns through the same interface regardless of its internal ranking method; hybrid fusion is an internal improvement to that method, invisible to every caller.

**Question C — Should ADR-005 hybrid retrieval become a prerequisite stage?** **Recommendation: no**, but this is a reported decision point, not a unilateral call (see §19) — the project owner already deferred this exact question at the end of Stage 9. This plan does not re-decide it; it only confirms that Project Writing does not *technically* require it to be resolved first.

**Question D — Can the writing architecture be retrieval-neutral so hybrid retrieval can be added without redesign?** **Yes, already true.** The Writing Service will depend on `SearchKnowledgeUseCase` 's public interface ( `execute(user_id, query, top_k) -> list[SearchResult]` ), never on `rank_by_similarity` or the vector index directly. When/if hybrid fusion is added inside `SearchKnowledgeUseCase` , the Writing Service needs zero changes — the same seam that already isolates Stage 8's callers from its internals.

---

## 10. AI Provider Architecture

* **Is `TextGenerationProvider` sufficient?** **Yes.** `generate(prompt: str) -> str` already carried Stage 5's structured-JSON classification via prompt design alone, with no protocol change. Draft generation is the same shape: one assembled prompt in, one text response out. No new provider capability is required for MVP.
* **Structured output?** Not needed as a protocol feature. If citation markers or section structure are wanted in a specific format, request it via the prompt (as Stage 5 already does for `element_type`/`label`/`description`), parsed the same way `semantic_classification.py` parses classification responses — a new `draft_response_parsing.py`-style module, not a provider change.
* **Streaming?** Not needed for MVP. Draft generation completes as one Work Item execution (§11); no user-facing token-by-token display exists yet (no frontend). Flagged as a legitimate future capability, not built now.
* **Sync or async?** Async, via the existing Work Item mechanism — see §11.
* **Provider failure handling:** identical to Stage 5/7 — `ProviderRequestError`/`ProviderConfigurationError` (already exist, already mapped to HTTP 502/503 since Stage 8) propagate through the same Work Item retry/failure path already proven (bounded retry,  `Draft`/`Draft Version` simply do not get created on failure — no partial state, mirroring `ExtractDocumentKnowledgeUseCase`'s atomicity).
* **Should prompts be persisted?** **Recommendation: no**, for MVP — the assembled prompt is reconstructable from `Draft Evidence Link`s + the Writing Profile + `Project.topic` + the user's instructions (if persisted, §19), so persisting the raw prompt text would duplicate already-traceable data and bloat storage with retrieved content verbatim. Flagged as an implementation default, not a frozen requirement either way.
* **Should model/version metadata be persisted?** **DECIDED (§19.6): yes, cheaply** — recorded via the Work Item's own `payload_reference` (already free-text), not a new column on the frozen `Draft Version` entity.

**General AI knowledge (§10 of the brief):** the frozen requirements already lean firmly toward evidence-first: AIR-043 ("shall not fabricate... claims... not supported by the project context"), AIR-046 ("reduce likelihood of unsupported claims by requiring evidence-grounded reasoning before draft support is produced"), and `04_AI_Architecture.md` §11.2 ("Research Intelligence does not supplement project knowledge with external sources unless explicitly configured"). **DECIDED (§19.5):** general pretrained knowledge is usable only for non-factual scaffolding (transitions, phrasing, structure) and must never be the sole basis for a factual claim; retrieved project knowledge (via `SearchKnowledgeUseCase` ) is the primary and default grounding source; when retrieval returns insufficient evidence for a requested section, the system must say so explicitly (AIR-048) rather than silently filling the gap with unlabeled pretrained content. This policy is now binding for Stage 4/5 prompt construction.

---

## 11. Generation Architecture

**Recommendation: asynchronous, via the existing Work Item/outbox mechanism — the same pattern proven in Stages 5-7, not a new mechanism.**

```
POST /writing/drafts/{id}/generate (or similar, §14)
        ↓
create/locate Draft, enqueue Work Item
   (kind=pipeline_stage, payload_reference="generate_draft_version:<draft_id>")
        ↓
202 Accepted, same request/response shape philosophy as document upload
        ↓
Executor claims the Work Item (existing `process_one_work_item`-style dispatch,
   extended with one new payload-reference case)
        ↓
Context Assembly (§6) → TextGenerationProvider.generate() → new Draft Version + Draft Evidence Links
        ↓
Draft.status transitions (drafting → in_review, per the already-frozen state machine)
```

Why not synchronous: draft generation latency is materially longer than Stage 5's one-sentence classification (a full section of writing, not a label), and the Work Item mechanism already solves exactly this class of problem (latency, retry, atomicity, crash-durability) — reusing it costs one new `payload_reference` case, not a new subsystem. Idempotency: mirrors Stage 5's own pattern — a Work Item for a given generation request is keyed the same idempotent way uploads already are; a completed generation is detected and not silently re-run (exact mechanism is an implementation detail for Stage 5 below, not a new architectural concept).

---

## 12. Evidence / Citation Architecture

Fully traceable through already-frozen structures — no new citation system:

```
Research Document
      ↓ (Chunk Evidence Link, frozen)
Knowledge Chunk
      ↓ (Draft Evidence Link, frozen — target_type=knowledge_chunk)
Draft Version
```

* **Can a claim be traced to knowledge, and knowledge to a source document?** Yes — this chain already exists and is exactly what Stage 5-8 built and tested.
* **Can the draft preserve that provenance?** Yes, via `Draft Evidence Link`, created per Draft Version (never edited in place — `05_Constraints_and_Integrity.md` line 200: "annotations are never edited in place").
* **Citation representation:** structured link rows, not formatted citation text (matches "citation awareness, not citation management").
* **No supporting evidence found:** the Writing Service must surface this rather than generate ungrounded content — concretely, if retrieval returns zero relevant chunks for a request,  `Draft` generation should fail informatively (a new, narrowly-scoped domain exception, not a silent empty draft) rather than let the LLM invent unsupported claims.
* **Evidence-only generation mode:** a reasonable future `WritingTask`-level setting, not required for MVP — flagged in §19 as an open, not-yet-decided refinement.

---

## 13. Data Model Changes

**Zero changes to the frozen Logical Data Model are proposed.** Every entity below is already fully specified (cited section numbers refer to `04_Logical_Data_Model.md` ); "new" here means "not yet realized in code, " exactly Slice 2's own starting position with `Knowledge Element` / `Session` / `Work Item` .

| Entity | §  | Owner (agent_id path) | New code needed |
|---|---|---|---|
| `Draft` | §3.15 | `agent_id` direct | ORM model, domain entity, repository |
| `Draft Version` | §3.16 | via `draft_id` → Draft | ORM model, domain entity, repository |
| `Review` | §3.17 | via `draft_version_id` | ORM model, domain entity, repository |
| `Review Decision` | §3.18 | via `review_id` ; `decided_by` → User | ORM model, domain entity, repository |
| `Draft Evidence Link` | §4.2 | via `draft_version_id` | ORM model, domain entity, repository |
| `Writing Profile` | §3.11 | `agent_id` + `user_id` direct | ORM model, domain entity, repository |
| `Profile Characteristic` | §3.12 | via `profile_id` | ORM model, domain entity, repository |
| `Profile Characteristic Source` | §4.5 | via `profile_id` / `characteristic_id` | ORM model, domain entity, repository |
| `Memory Record` | §3.8 | `agent_id` direct | ORM model, domain entity, repository |
| `Memory Provenance Link` | §4.3 | via `record_id` | ORM model, domain entity, repository |
| `Conversation` | §3.9 | `agent_id` direct | ORM model, domain entity, repository — realized to carry per-Draft instructions (§19.3) |
| `Message` | §3.10 | via `conversation_id` | ORM model, domain entity, repository — first Message of a Draft's Conversation holds the user's writing instructions |
| `Message Context Link` | §4.4 | via `message_id` , `draft_version_id` | ORM model, domain entity, repository — links the instruction Message to the Draft Version it produced |

Every ownership question the brief asks is already answered by the frozen schema (§13 of the brief): Agent ID is required and direct on `Draft` / `Writing Profile` / `Memory Record` / `Conversation` ; Project ID is never duplicated onto these (the Agent already transitively owns its one Project — duplicating would violate "no duplicate ownership columns without a reason, " which the brief itself warns against); User ID appears only where actor-accountability is required ( `Review Decision.decided_by` , `Writing Profile.user_id` — the sample provider). Deletion behavior, timestamps, versioning, and uniqueness are all already specified per-entity in §3/§4 and cross-checked against the lifecycle table ( `05_Constraints_and_Integrity.md` §"State Transitions") — reproduced in full in §5/§8 above.

**Former field-level gap — RESOLVED (§19.3):** per-request writing instructions are not a new field on `Draft` / `Draft Version` . They are stored as the first `Message` of a Draft-scoped `Conversation` , linked to the resulting `Draft Version` via the already-frozen `Message Context Link` . This adds no column to any frozen entity; it only requires a Draft to reference (or lazily create) one `Conversation` , which Stage 2 must wire.

---

## 14. API Surface (conceptual — not implemented)

Every endpoint requires `get_current_user_id` (existing dependency) and resolves the Agent server-side, exactly as `/agents` and `/knowledge/search` already do — no endpoint accepts `agent_id` from the client.

| Method | Path | Purpose | Sync/Async | MVP? |
|---|---|---|---|---|
| `POST` | `/writing/drafts` | Create a Draft (writing task) for the caller's Agent | Sync | MVP |
| `POST` | `/writing/drafts/{draft_id}/generate` | Enqueue generation of the next Draft Version | Async (202 + Work Item) | MVP |
| `GET` | `/writing/drafts/{draft_id}` | Fetch a Draft with its current status | Sync | MVP |
| `GET` | `/writing/drafts/{draft_id}/versions` | List Draft Versions (history, immutable) | Sync | MVP |
| `GET` | `/writing/drafts/{draft_id}/versions/{version_id}` | Fetch one version + its evidence links | Sync | MVP |
| `POST` | `/writing/drafts/{draft_id}/versions/{version_id}/reviews` | Open a Review with a decision (approve/request-revisions/reject) | Sync | MVP |
| `POST` | `/writing/style-profile/documents` | Upload a writing-style sample (enqueues style-extraction Work Item) | Async | MVP |
| `GET` | `/writing/style-profile` | Fetch the Agent's active Writing Profile + characteristics | Sync | MVP |

**Deliberately not proposed for MVP:** a "revise" endpoint distinct from `generate` (a revision is just another `generate` call against the same Draft with new instructions, producing the next Draft Version — no separate concept needed, avoiding the brief's own warning against inventing parallel entities); similar-project document endpoints (deferred, §5. C); any endpoint exposing raw prompts, embeddings, or Work Item internals (matches Stage 8's "no raw vectors" precedent).

Every response error case mirrors existing precedent exactly: 401 (no session), 404 (no Agent yet / Draft not found or not owned — indistinguishable, same non-enumeration principle as Stage 6/8), 422 (validation), 502/503 (provider failure, already mapped since Stage 8-9).

---

## 15. Security / Ownership

No new isolation mechanism is needed — the existing pattern (resolve Agent from authenticated `user_id` , filter every query by `agent_id` , never accept `agent_id` from the client) already proven for documents (Stage 6) and knowledge search (Stage 8, including an explicit cross-agent authorization test) extends directly to every new entity in §13: `Draft` , `Draft Version` (via its Draft), `Review` / `Review Decision` (via the Draft Version chain), `Writing Profile` / `Profile Characteristic` (agent-scoped directly), `Memory Record` (agent-scoped directly). `05_Constraints_and_Integrity.md` 's own invariant already states this generally: "No cross-Agent references in the MVP... retrieval is filtered by Agent scope before ranking" — this plan does not weaken or reinterpret that, it applies it to five more entities the same way.

---

## 16. Frontend Contract (backend capabilities only — no UI design)

The eventual frontend will need, at minimum: a way to create/view a Draft and its topic context; a way to trigger generation and poll/observe its async status (mirrors how document processing status is already polled); a way to view Draft Version history with evidence references visible per version; a way to submit a Review decision; a way to upload writing-style samples and view the resulting Writing Profile; visibility into "insufficient evidence" states (§10) so the user understands why a section wasn't generated. Similar-project document upload is explicitly not part of this contract yet (§5. C).

---

## 17. Testing Strategy

Same standard as Slice 2, no exceptions:

* **Unit:** context-assembly pure functions, prompt construction, response parsing (mirrors `semantic_classification.py`'s test style exactly) — no DB, no network.
* **Integration:** real SQLite + real filesystem — Draft/Draft Version/Review persistence, evidence-link correctness, Writing Profile persistence, Memory Record supersession, agent-scoping (including an explicit cross-agent test, mirroring Stage 8's).
* **E2E:** real HTTP, isolated per-test database/storage, fake provider — full create-draft → generate → review loop over separate requests (mirrors Stage 6/8's discipline exactly).
* **Real-provider validation:** reserved for the final validation stage of this milestone, using the already-configured Gemini free-tier key, deliberately tiny (one short generation, not a full chapter) — never required for the automated suite, never a real key in source/tests/docs, per the standing discipline this whole project has followed since Milestone 7.

---

## 18. Implementation Stages

Derived from the architecture above, not copied from the brief's example — each stage is independently reviewable and gated on explicit authorization, matching every prior Slice 2 stage's discipline.

### Stage 2 — Writing Domain & Persistence

**Objective:** realize `Draft` , `Draft Version` , `Review` , `Review Decision` , `Draft Evidence Link` , plus `Conversation` / `Message` / `Message Context Link` wired to a Draft (§19.3, for per-request instructions) exactly as frozen; no generation, no API yet.
**Files:** `app/modules/writing/{domain,infrastructure}/*` (new module, mirrors `modules/knowledge/` ).
**New entities:** the eight above (§13).
**New APIs:** none.
**Dependencies:** none beyond existing repositories.
**Tests:** unit (domain entities/lifecycle rules) + integration (real SQLite, ownership, immutability, evidence-link exclusive-arc rule, instruction-Message-to-Draft-Version linkage).
**Acceptance:** a Draft can be created, versioned, reviewed, and evidence-linked entirely through the application/infrastructure layers, with zero HTTP surface, and a Draft's writing instructions are persisted and retrievable via its Conversation.
**Non-goals:** no LLM call, no context assembly, no routes.

### Stage 3 — Writing-Style Ingestion

**Objective:** realize `Writing Profile` , `Profile Characteristic` , `Profile Characteristic Source` ; build the style-document → characteristic extraction pipeline (mirrors Stage 4-5's mechanical-then-semantic split).
**Files:** `app/modules/writing/{domain,application,infrastructure}/*` (style sub-area).
**New entities:** the three style entities (§13).
**New APIs:** none yet (internal use case only, tested directly — mirrors how `ProcessDocumentUseCase` was built before any route existed).
**Dependencies:** existing `ContentStore` , `TextGenerationProvider` .
**Tests:** unit + integration, mirroring Stage 4/5's test shape exactly.
**Acceptance:** a style document produces real, persisted `Profile Characteristic` rows, never mistaken for evidence (verified by asserting `Draft Evidence Link` 's target types never include them).
**Non-goals:** no similar-project handling, no API.

### Stage 4 — Context Assembly — Complete

**Objective:** implemented the pure Context Assembly function (§6) — topic + explicit writing instructions + retrieved knowledge + style + memory → one assembled prompt, applying the general-AI-knowledge policy (§19.5). No provider call, persistence, route, or background work was introduced.
**Files:** `app/modules/writing/domain/context_assembly.py` , plus `InvalidContextAssemblyInputError` in `app/modules/writing/domain/exceptions.py` .
**Implementation boundary:** assembly accepts already-resolved value objects rather than performing repository access. This keeps the function deterministic and leaves retrieval, Conversation/Message loading, and provider orchestration to later application stages.
**Behavior:** preserves input evidence ordering, removes duplicate or blank chunks, applies a maximum evidence count, includes source metadata, labels style signals as guidance rather than facts, includes current memory, and truncates deterministically within a character budget with sentence-boundary preference.
**Tests:** 7 focused unit tests covering determinism, evidence deduplication, limits, style/memory inclusion, truncation, and invalid input; full suite remained green at 441 tests.
**Acceptance:** complete — the function returns both the assembled prompt and the exact evidence value objects selected for later evidence-linking.
**Non-goals:** no LLM call, persistence, HTTP route, retrieval invocation, or Work Item integration.

### Stage 5 — Generation Gateway & Writing Service — Complete

**Objective:** wire Context Assembly → `TextGenerationProvider.generate()` → new Draft Version + Draft Evidence Links, as a directly-callable use case.
**Files:** `app/modules/writing/application/use_cases.py` ( `GenerateDraftVersionUseCase` ); `app/modules/writing/domain/exceptions.py` (empty-output and insufficient-evidence errors).
**Boundary:** the caller supplies already-resolved `ContextAssemblyInput` ; Stage 5 does not perform repository retrieval, Conversation/Message loading, HTTP handling, or background execution. This resolves the current repository gap without silently inventing the still-unimplemented Conversation/Message subsystem.
**Behavior:** validates the Draft exists, rejects generation without selected evidence, calls only the injected `TextGenerationProvider` , creates the next immutable `DraftVersion` with `CreatedBy.SYSTEM` , creates one `DraftEvidenceLink` per selected Knowledge Chunk, and commits the complete result through the existing `UnitOfWork` .
**Tests:** unit tests use fake repositories/provider for success, evidence mapping, version increments, empty output, no-evidence rejection, and rollback signaling; integration tests use real SQLite and separate-session verification for success and provider-failure atomicity.
**Acceptance:** complete — successful generation persists a real evidence-linked Draft Version; provider or persistence failure leaves no committed generated result.
**Non-goals:** no async wiring, Work Items, HTTP routes, frontend, schema changes, or real-provider test calls.

### Stage 6 — Async Generation — Audited Complete

**Objective:** wire Stage 5's use case into the existing Work Item/executor without creating a second queue or worker mechanism.
**Files:** `app/workers/executor.py`, `app/workers/payloads.py`, plus Stage 6 worker integration tests.
**Work Item contract:** `kind=pipeline_stage`; `payload_reference` is `generate_draft_version:<compact JSON>` containing the server-created `draft_id`, request ID, and serialized resolved `ContextAssemblyInput`; `idempotency_key` is `generate_draft_version:<request_id>`. The existing 512-character payload limit is enforced; oversized contexts are rejected.
**Identity:** enqueue requires the authenticated `user_id` and verifies Draft → Agent → User ownership. The executor trusts only persisted Work Items and does not accept client identity fields.
**Execution:** the executor parses the payload and invokes `GenerateDraftVersionUseCase`; it does not duplicate generation or persistence logic. Stage 5 commits DraftVersion plus DraftEvidenceLink rows atomically before the Work Item is marked succeeded.
**Retry:** provider or generation failures use the existing bounded Work Item retry policy: attempts 1-2 requeue, attempt 3 becomes terminal `failed`; success records `succeeded` and `completed_at`.
**Tests:** real SQLite worker tests prove queued/claimed execution, DraftVersion/evidence persistence, persisted success and terminal-failure states, retry behavior, no partial generation persistence, and unchanged document-worker behavior. Full suite: 455 passed.
**Acceptance:** verified for the implemented flow and retry semantics. Known limitation: if the process crashes after Stage 5 commits but before the Work Item success marker commits, a retry can create another DraftVersion; the current frozen schema has no generation-request reference to close that crash window. Resolving that would require a later authorized schema/design decision.
**Non-goals:** no HTTP API, frontend, new queue, new Work Item kind, or provider abstraction.

### Stage 7 — API

**Objective:** expose the endpoints in §14 as thin routes over the now-complete Writing Service.
**Files:** `app/modules/writing/interface/*` , `app/api/router.py` , `app/core/dependencies.py` .
**New entities:** none.
**New APIs:** all of §14.
**Dependencies:** Stages 2-6.
**Tests:** e2e (real HTTP, fake provider, separate requests — mirrors Stage 6/8's e2e discipline, including an explicit cross-agent authorization test for every new endpoint).
**Acceptance:** the full create → generate → review loop works over real HTTP.
**Non-goals:** no frontend.

### Stage 8 — Full Validation

**Objective:** full regression, fresh-environment real-HTTP exercise of the entire Project Writing loop, and — deliberately tiny — one real-provider generation, mirroring Stage 9 of Slice 2 exactly.
**Files:** none (validation only).
**Acceptance:** the complete path — Agent → topic → style samples → research documents → knowledge → **writing request → context assembly → real generation → evidence-linked draft → review** — proven end to end, once with fakes (automated suite) and once with the real, already-configured provider (manual, tiny, never a paid requirement).
**Non-goals:** no new functionality; report-only if defects are found, exactly the discipline Stage 9 of Slice 2 already established.

---

## 19. Risks and Open Decisions — RESOLVED 2026-09-12 by explicit user approval

All six items below were open at the end of Stage 1 review and have since been decided. Recorded here as decisions, not left as recommendations, so Stage 2 can proceed against a settled plan.

1. **Writing Service domain.** ~~No "Writing Service" domain exists in `05_Backend_Architecture.md`.~~ **DECIDED: Approved.** `modules/writing/` is authorized as a new, additive Writing Service domain, no ADR required (§4). A `§23 Writing Service` section should be appended to `05_Backend_Architecture.md` when Stage 7 (API) makes the boundary concrete — append-don't-renumber, per existing governance.
2. **Similar-project material.** ~~No frozen home that keeps it retrievable without making it evidence-eligible~~ (§5.C). **DECIDED: Deferred from MVP.** No new entity is invented at this stage. Similar-project ingestion remains an explicit non-goal through Stage 8 (§18); its eventual schema (if built) must not reuse or extend `Knowledge Element`/`Knowledge Chunk`, to preserve the evidence-eligibility guarantee.
3. **Per-request writing instructions.** ~~No field exists on `Draft`/`Draft Version`~~ (§13). **DECIDED: Option (b).** Instructions are stored as the first `Message` of a Draft-scoped `Conversation` (via `Message Context Link`, already frozen — §4.4), not as a new column. No correction ADR. Stage 2 must include wiring a Draft to its Conversation (see §13 update below) and Stage 4 (Context Assembly) must read the instruction from that Message rather than from a new field.
4. **ADR-005 hybrid retrieval.** **DECIDED: Left open.** Vector-only retrieval is explicitly accepted as sufficient for Writing MVP (§9, Questions A/B/D already established this is safe — the Writing Service is retrieval-neutral). No prerequisite stage is inserted. This does not resolve ADR-005 itself; it only confirms Writing does not block on it.
5. **General AI knowledge policy.** **DECIDED: Approved as proposed.** General pretrained knowledge may be used only where explicitly permitted by frozen requirements (non-factual scaffolding — transitions, phrasing, structure), never as the sole basis for a factual claim. Retrieved project knowledge (Knowledge Chunk via `SearchKnowledgeUseCase`) remains the primary and default grounding source for all factual content. This policy is now binding for Stage 4/5 prompt construction, not merely a recommendation.
6. **Model/version metadata.** **DECIDED: Approved as proposed.** Recorded via the Work Item's `payload_reference`, not a new `Draft Version` column. No schema change.

---

## 20. Recommended Order

Stage 2 → Stage 3 → Stage 4 → Stage 5 → Stage 6 → Stage 7 → Stage 8, exactly as numbered in §18 — each stage is a strict prerequisite for the next (persistence before context assembly, context assembly before generation, generation before async wiring, async wiring before API, API before end-to-end validation). Stages 2-6 are implemented; Stage 6 has been audited against its engineering prompt. Stage 7 is the next implementation target. All six items in §19 are resolved (2026-09-12); the crash-window generation idempotency limitation is recorded above rather than silently redesigned.

---

## Required Reviews (performed before declaring this stage complete)

**Senior Backend Engineer:** Every proposed use case ( `GenerateDraftVersionUseCase` , style extraction) mirrors an already-shipped, already-tested pattern ( `ExtractDocumentKnowledgeUseCase` , `ProcessDocumentUseCase` ) — feasibility is proven by precedent, not speculation. Transaction boundaries: identical atomicity discipline (gather-then-persist, `UnitOfWork` commit/rollback) as every prior use case. No new abstraction was proposed without a working analog already in the codebase.

**Principal Software Architect:** Dependency direction preserved — `modules/writing/` depends on `modules/knowledge/` 's public use case ( `SearchKnowledgeUseCase` ) and `app/ai/providers/base.py` , never on internals, exactly the existing cross-module pattern ( `modules/document` → `modules/agent` / `modules/project` ). No ADR conflict was silently resolved — the two live conflicts (ADR-005, similar-project schema) are reported, not fixed. The one identified gap (no Writing Service section) was classified correctly as additive, not corrective, and no ADR was proposed for it.

**Data Architect:** Every entity in §13 is a citation to an already-frozen table, not an invention. Ownership chain re-verified against `04_Logical_Data_Model.md` directly, not from memory. The one real field-level gap (instructions) was reported, not patched.

**AI/Knowledge Systems Engineer:** Retrieval reused unmodified and shown to be interface-neutral to the ADR-005 discrepancy. Evidence grounding traced through the actual existing link entities, not a new citation model. Style kept structurally separate by the schema itself, not by a new business rule. Similar-project handling correctly identified as unsolved rather than forced into a wrong-shaped entity. Provider boundary unchanged; no new capability requested without a concrete reason (§10's requirement).

**Security Reviewer:** Every new entity's isolation story is "the same pattern already proven, applied to one more table" — no new isolation mechanism was invented, which is itself the correct answer (a new mechanism would be an unreviewed risk; reusing the tested one is not).

**Independent Reviewer:** Re-read this plan assuming the above reasoning could be wrong. Checked specifically for: entities invented where a frozen one already existed (none found — the opposite risk, under-inventing, was actively watched for and resolved by re-reading `04_Logical_Data_Model.md` directly rather than from memory); a "WritingTask" entity duplicating `Draft` (explicitly rejected in §14); unnecessary complexity (no event sourcing, no new message queue, no new database, no new provider capability — every "no" in §23 of the brief is satisfied); missing decisions (the six items in §19 are the complete list of what remains genuinely open after this reconnaissance).
