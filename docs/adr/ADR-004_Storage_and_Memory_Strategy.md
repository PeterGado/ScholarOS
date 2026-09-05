# ADR-004: Storage and Memory Strategy

**Status:** Accepted

**Date:** 2026-08-06

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (fourth ADR)

---

## Status

**Accepted.** This ADR selects the persistence engines and persistence model for the ScholarOS MVP, mapped to the storage categories of 07_Operational_Architecture.md §3, and records how the project memory architecture (04 §8) is persisted.

---

## Context

03_Data_Architecture.md defines the conceptual domains; 07_Operational_Architecture.md §3 defines storage categories (structured core, vector index, object store, working cache). This ADR decides the *engines* behind those categories for the MVP and the migration path that keeps the data access layer stable (05 §16, API-032, API-033).

Governing requirements:

- Data integrity and no silent corruption (NFR-003 to NFR-006 — NFR-004 specifically).
- Data domains with relationships and traceability (DR-001 to DR-025).
- Persistence behind a stable boundary (API-032, API-033).
- Memory persists across sessions and scales with project volume (AIR-019 to AIR-021, AIR-065, AIR-066, WR-013 to WR-015, MVP-011, MVP-012, DR-013 to DR-015).
- Retrieval over knowledge chunks and embeddings (AIR-022 to AIR-027; ADR-005).

## Problem

The MVP must persist heterogeneous data — strongly consistent relational state, vector embeddings for retrieval, immutable source documents, and ephemeral working state — without either (a) forcing one engine to serve all patterns poorly, or (b) adopting a distributed multi-engine architecture the MVP cannot operate. The choice must also be migration-friendly: from a single-node personal deployment (ADR-007) to a managed cloud deployment, and eventually to multi-tenant stages (07 §5).

## Decision

1. **Structured core — SQLite for the MVP**, accessed only through the data access layer (05 §16). SQLite provides a single-file, zero-operator relational engine with ACID transactions, which matches the MVP's strong-consistency needs (§3.3 of 07) and the single-node deployment model (ADR-007).
2. **Migration path — PostgreSQL.** The data access layer contract (API-032, API-033) and the ORM abstraction (ADR-002) are designed so the structured core can move to PostgreSQL when concurrent writers, multi-user access, or managed hosting demands (07 §5 stages 2+) exceed SQLite. This is a configuration- and data-layer change, not an architecture change.
3. **Vector index — embedded vector index for the MVP** (e.g., a SQLite-adjacent vector extension or an in-process vector index), owned by the retrieval strategy (04 §16; ADR-005). Migration path: a dedicated vector store (e.g., pgvector on PostgreSQL) when index volume or concurrent query load requires it.
4. **Object store — local filesystem for the MVP** for source documents and exports, behind the object-store boundary. Migration path: S3-compatible object storage when deployment moves to the cloud (ADR-007).
5. **Working cache — in-process cache for the MVP** for assembled context and interim pipeline state; loss recoverable from the structured core (07 §3.2). Migration path: a shared cache service if multi-process deployment (ADR-006 workers) requires it.
6. **Memory persistence.** Project memory (04 §8) is persisted in the structured core as project-scoped records with version and traceability (DR-013 to DR-015, DR-023 to DR-025); memory is a first-class data domain, never reconstructed from conversation logs.

## Rationale

1. **Why SQLite first:** it is the canonical "single-writer relational engine with zero operations" choice — used by default in Django and Rails development, and in production for single-writer workloads by many small services. It satisfies ACID integrity (NFR-004), requires no server, and matches the single-node, single-operator deployment (07 §4). PostgreSQL remains the target for growth; the boundary-first design (API-032, API-033) makes this a documented migration, not a rewrite.
2. **Why not a server database immediately:** running PostgreSQL (or a cloud DB) from day one adds operations burden (provisioning, backups, connection management) that the MVP's single-writer reality does not need, per the deployment assumptions of 07 §4.
3. **Why memory is a persisted domain, not a cache:** the memory architecture (04 §8) is the product's continuity mechanism (AIR-065, AIR-066). Treating it as a cache would make project understanding lossy and contradict the Persistence principle (01 §5). Persisting memory as project-scoped, versioned records in the structured core keeps it queryable, traceable, and exportable (user ownership, 03 §4).
4. **Why an embedded vector index now:** the MVP's retrieval volume is a single project's chunks; an embedded index removes an operator-managed dependency while preserving the retrieval contract (ADR-005). The dedicated vector store is deferred until volume or concurrency demands it (07 §5.3 lever 4).

## Alternatives Considered

### Alternative 1: PostgreSQL from day one

**Rejected because:** operations burden exceeds MVP needs; conflicts with the single-node, zero-operator deployment assumption (07 §4, ADR-007); the data access layer makes the later migration low-risk, so there is no architectural advantage to paying the cost early.

### Alternative 2: Single NoSQL/document store for everything

**Rejected because:** strong consistency and relational traceability (DR domains, 03 §3 relationships) are required for project state, drafts, and reviews; a document store would push consistency logic into application code, risking NFR-004 and the integrity bar of 07 §3.3.

### Alternative 3: Memory as reconstructed context (log replay)

**Rejected because:** contradicts AIR-065, AIR-066 and the Persistence principle; replay is lossy and slow; memory must be a queryable domain (04 §8), not a derivation.

### Alternative 4: Separate dedicated vector database (e.g., managed vector DB) in MVP

**Rejected because:** adds an external dependency and cost for a single-user retrieval workload; the embedded index satisfies MVP requirements (API-038, API-039) and the migration path preserves the choice.

## Consequences

### Positive

1. Zero-operator MVP storage; fast iteration.
2. ACID integrity for project state (NFR-004).
3. Migration paths are contractual (data access layer), not rewrites.
4. Memory persists as a first-class domain (AIR-065, AIR-066).

### Negative

1. SQLite's write concurrency limit is a known ceiling; acceptable until multi-user stages (07 §5 stage 2) trigger the PostgreSQL migration.
2. Embedded vector index does not scale horizontally; acceptable within the MVP envelope (API-038, API-039).
3. Two migration triggers (relational + vector) must be managed deliberately; both are documented in 07 §5.3.

### Neutral

1. Storage engines are invisible above the data access layer; the architecture set (03, 07) describes categories, not engines, preserving ADR-001 separation.

## Repository Impact

No documentation-structure change. Database design documentation (`docs/database/`) will be created against the data access layer and this ADR per **04_Repository_Governance.md, §2**.

## AI Engineering Implications

AI engineers implement persistence exclusively through the data access layer per **02_AI_Engineering_Contract.md, §7** and the standing responsibilities (**11_Engineering_Responsibilities.md**). Direct engine access from domain logic is an architectural violation (**07_Review_Checklist.md**, §4.2).

## Compliance Rules

Verified via **07_Review_Checklist.md** (architecture alignment, data-access discipline) and **05_Definition_of_Done.md** (§2.4 provider/abstraction quality). Storage integrity defects follow **04_Repository_Governance.md, §5.3**.

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-002 (Technology Stack) | Accepted | Provides the ORM and framework; this ADR selects engines. |
| ADR-005 (Retrieval and Search Strategy) | Accepted | The vector index serves the retrieval contract. |
| ADR-007 (Deployment Strategy) | Accepted | Storage engines match the single-node deployment model. |

## Future Considerations

1. **Multi-tenancy storage:** at SaaS stage (07 §5 stage 5), per-tenant data isolation decisions will be recorded in a future ADR; the data access layer is the enforcement point.
2. **Embedding versioning:** embedding model changes (ADR-005) require re-indexing strategy; retention rules (DR-023 to DR-025) apply to embeddings as derived data.
3. **Backup automation:** RPO/RTO assumptions (07 §3.5) should be re-validated when the structured core migrates to PostgreSQL.

## References

- 03_Data_Architecture.md — §3 (Major Data Domains), §4 (Data Ownership Model)
- 04_AI_Architecture.md — §8 (Memory Architecture)
- 05_Backend_Architecture.md — §16 (Infrastructure Boundary)
- 07_Operational_Architecture.md — §3 (Storage Strategy), §5 (Scalability Evolution)
- SRS Chapter 7 — DR-001 to DR-025
- SRS Chapter 6 — AIR-019 to AIR-021, AIR-065, AIR-066
- SRS Chapter 5 — NFR-003 to NFR-006, NFR-023, NFR-024, NFR-027, NFR-028
- SRS Chapter 9 — API-032, API-033
- ADR-001 — Separation of Requirements, Architecture, and Implementation
