# ADR-005: Retrieval and Search Strategy

**Status:** Accepted

**Date:** 2026-08-06

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (fifth ADR)

---

## Status

**Accepted.** This ADR records ScholarOS's retrieval and search strategy: **hybrid retrieval** over knowledge chunks — lexical (keyword) search combined with semantic (vector) search, fused and optionally reranked — behind the retrieval contract of 04_AI_Architecture.md §16.

---

## Context

Retrieval is the product's core differentiator: ScholarOS must find the *right* knowledge chunk for a task from a growing project corpus, with evidence traceability (AIR-046 to AIR-048). 04 §16 defines the retrieval strategy architecturally (chunk-based, evidence-linked); this ADR decides *how* retrieval matches and ranks candidates.

Governing requirements:

- Retrieval quality over growing corpora: AIR-022 to AIR-027, AIR-067, AIR-068.
- Evidence grounding: every retrieved item traces to source documents (AIR-046 to AIR-048, DR-006, DR-008, DR-018).
- Performance within the MVP envelope (API-038, API-039).
- Provider agnosticism applies to embeddings as to generation (AIR-040 to AIR-042; ADR-002 gateway pattern).

## Problem

Lexical search alone misses semantically similar phrasing (a student's question rarely matches document wording). Pure vector search alone misses exact terms, identifiers, and quotations that matter in academic work, and suffers from embedding-model biases. Both together — hybrid retrieval — is the industry-standard answer (RAG practice), but it must be specified: what is indexed, what is searched, how results fuse, and how evidence links survive the process.

## Decision

1. **Chunk-level hybrid retrieval.** Every query is executed as: (a) lexical search over the chunk index, and (b) semantic search over chunk embeddings, with results fused into a single ranked candidate set.
2. **Fusion by reciprocal rank fusion (RRF)** — a weighted merge of the two rankings — with the fusion weights configurable per retrieval context (04 §16 retrieval contexts).
3. **Evidence links are first-class.** Every candidate chunk carries its source-document links (04 §18); retrieval never returns content without its evidence path, and candidate sets are filtered by project scope before ranking.
4. **Reranking is a deferred capability.** Cross-encoder reranking is a post-MVP enhancement (SRS Chapter 11, Phase 7 Advanced Intelligence); the fusion contract is designed so reranking replaces the fused ranking without changing the retrieval interface.
5. **Embeddings flow through the provider gateway** (ADR-002): embedding models are configuration-selected, and embedding-version changes trigger re-indexing through the knowledge processing pipeline (04 §7, §9).

## Rationale

1. **Why hybrid:** academic retrieval is bimodal — the user asks in prose (semantic match) but quotes exact passages, terms, and citations (lexical match). Lexical search provides precision on exact terms and identifiers; semantic search provides recall on paraphrase and concept. This is the standard finding in IR research (e.g., BM25 + dense retrieval hybrid baselines consistently beat either alone in retrieval benchmarks) and the dominant pattern in production RAG systems.
2. **Why RRF:** reciprocal rank fusion is a parameter-light, well-understood fusion method (rank-based, not score-based, so it is robust to incomparable lexical/semantic scores). It avoids tuning score normalization between heterogeneous retrieval systems — exactly the situation here (lexical scores and cosine similarity are not comparable).
3. **Why chunk-level, not document-level:** the knowledge chunk is the retrieval unit by architecture (04 §9; DR-007 to DR-009); document-level retrieval would reintroduce the context-assembly problem chunks solve. Chunks are small enough for precise evidence linking and context window assembly (04 §17).
4. **Why evidence links are non-negotiable:** AIR-046 to AIR-048 require that generated support be grounded; a retrieval pipeline that loses source provenance would break the citation and evidence flow (04 §18) and the traceability chain (ADR-001).
5. **Why defer reranking:** cross-encoder reranking adds inference cost and a second model dependency; the MVP quality envelope (API-038) does not require it, and the contract keeps it addable. This follows the correctness-vs-completeness principle of the Vision.

## Alternatives Considered

### Alternative 1: Pure vector search

**Rejected because:** exact-term and quotation retrieval is unreliable with embeddings alone; hallucination risk rises when the wrong-but-semantically-similar chunk is retrieved; academic work demands exact-match reliability (AIR-067, AIR-068).

### Alternative 2: Pure lexical (BM25-style) search

**Rejected because:** paraphrase and conceptual retrieval fail; the product's understanding layer (04 §7) produces interpretation that lexical search cannot surface for differently-worded questions.

### Alternative 3: Graph-based knowledge retrieval only

**Rejected because:** knowledge graphs excel at relationship traversal but are poor at lexical and semantic similarity; the architecture's knowledge structure (03 §3.3) is not a graph database, and a graph-first strategy would require a different data model. Graph traversal can be layered on later for Phase 3/6 capabilities (KnowledgeGraph, SRS Chapter 11).

### Alternative 4: LLM-based retrieval (generate the answer, then verify)

**Rejected because:** retrieval must be a deterministic, testable component (03 §3) that the review pipeline can audit; generative retrieval blurs evidence grounding and is less testable.

## Consequences

### Positive

1. Precision of lexical search + recall of semantic search; stronger evidence grounding (AIR-046 to AIR-048).
2. Robust fusion without score-normalization tuning.
3. Testable retrieval component (deterministic ranking for a given index) — satisfies independent testability (01 §5).
4. Provider-agnostic embeddings through the gateway (ADR-002).

### Negative

1. Two indexes to maintain (lexical + vector) — the knowledge processing pipeline (04 §7) owns synchronization, and consistency is eventual (07 §3.3).
2. Fusion weights need empirical tuning per retrieval context — a small ongoing cost, tracked in the journal.
3. Indexing latency on document ingestion (mitigated by async processing, ADR-006).

### Neutral

1. Retrieval quality is measurable (recall@k on a golden query set); a small evaluation corpus should be created during implementation to detect regressions.

## Repository Impact

No repository-structure change. Retrieval evaluation fixtures will be created during implementation per **04_Repository_Governance.md, §2–§3**.

## AI Engineering Implications

AI engineers implement retrieval behind the retrieval contract of **04_AI_Architecture.md §16**, per **02_AI_Engineering_Contract.md, §7** and the standing responsibilities (**11_Engineering_Responsibilities.md**). Retrieval is a deterministic component: it must be testable without network access (03 §3.3).

## Compliance Rules

Verified through **07_Review_Checklist.md** (testability, architecture alignment) and **05_Definition_of_Done.md** (§2.5 Testing). Evidence-link integrity defects follow **04_Repository_Governance.md, §5.3**.

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-002 (Technology Stack) | Accepted | Embeddings flow through the provider gateway. |
| ADR-004 (Storage and Memory Strategy) | Accepted | The vector index is the retrieval engine. |
| ADR-006 (Async Processing and Event Coordination) | Accepted | Index updates run asynchronously. |

## Future Considerations

1. **Reranking (cross-encoder)** at Phase 7 — the fusion contract is the extension point.
2. **Graph-enhanced retrieval** for KnowledgeGraph capabilities (SRS Chapter 11, Phase 3/6).
3. **Per-context fusion tuning:** retrieval contexts (04 §16) may warrant per-context weights; record empirical results in the journal before changing the default.

## References

- 04_AI_Architecture.md — §7 (Knowledge Processing Pipeline), §9 (Knowledge Chunking), §16 (Retrieval Strategy), §17 (Context Window Management), §18 (Citation and Evidence Flow)
- 07_Operational_Architecture.md — §3 (Storage Strategy), §5.3 (Scaling Levers)
- SRS Chapter 6 — AIR-022 to AIR-027, AIR-040 to AIR-042, AIR-046 to AIR-048, AIR-067, AIR-068
- SRS Chapter 9 — API-038, API-039
- ADR-001 — Separation of Requirements, Architecture, and Implementation
