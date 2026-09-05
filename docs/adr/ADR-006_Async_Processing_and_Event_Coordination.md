# ADR-006: Async Processing and Event Coordination

**Status:** Accepted

**Date:** 2026-08-06

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (sixth ADR)

---

## Status

**Accepted.** This ADR records how ScholarOS executes long-running intelligence work: **asynchronous processing**, decoupled from interactive requests, coordinated through an event model, with an in-process queue for the MVP and a durable queue as the extraction path. It governs the orchestration of 05_Backend_Architecture.md §6 and the pipelines of 04_AI_Architecture.md.

---

## Context

The intelligence lifecycle (04 §5) contains long-running, multi-stage work: document ingestion → knowledge processing → chunking → indexing (04 §7, §9); context assembly (04 §6); drafting, review, and reflection pipelines (04 §19–§21). These pipelines can run for seconds to minutes and depend on external AI providers with variable latency (04 §23).

Governing requirements:

- Responsive interactive experience (API-038, API-039, NFR-001).
- Deterministic, auditable pipelines (AIR-063, AIR-064, NFR-004).
- Failure isolation: external provider failures must not cascade (NFR-003 to NFR-006; 04 §24).
- Scalability levers: async decoupling is the primary lever in 07 §5.3 and 05 §20.

## Problem

If long-running intelligence work runs synchronously inside interactive request handling, a single document ingestion or draft generation blocks the user, ties up request workers, and makes provider latency a direct user-experience failure. The architecture must define how work is scheduled, tracked, and reported without coupling the interactive tier to pipeline duration.

## Decision

1. **Async execution model.** Interactive requests return quickly; long-running work is dispatched to a background execution context and tracked as a unit of work with state (queued, running, succeeded, failed) surfaced through the API (API-035, API-040).
2. **Event-based coordination.** Pipelines emit and consume domain events (e.g., `document_ingested`, `knowledge_updated`, `index_updated`, `draft_generated`, `review_completed`). Events drive: pipeline chaining (04 §5 lifecycle stages), index synchronization (ADR-005), memory updates (04 §8), and failure handling (04 §24).
3. **In-process queue for the MVP.** The background executor runs in-process within the modular monolith (ADR-003), with a durable outbox pattern: events and work items are persisted in the structured core (ADR-004) before execution, so no work is lost on process restart (07 §3.5 recovery assumption).
4. **Durable queue as the extraction path.** When workers are extracted into separate processes (ADR-003 extraction, 07 §5.3 lever 1), the in-process queue is replaced by a durable message queue behind the same event contract — a deployment change, not a design change.
5. **Idempotency and retry.** Every event/work item is idempotent and retryable; failures are retried with bounded backoff and terminal failures surface through the review pipeline and observability (API-040).

## Rationale

1. **Why async now:** the architecture's own scalability principles (05 §20) name asynchronous processing as the mechanism that keeps long-running work off the interactive path. Doing it synchronously would contradict API-038 (responsive interaction) the moment ingestion exceeds a trivial size. The event model is the industry-standard way to coordinate multi-stage pipelines (the "outbox pattern" and event-driven orchestration used broadly across SaaS architectures) — it gives chaining, observability, and recovery for free.
2. **Why an outbox over a pure in-memory queue:** the MVP's single-node model (ADR-007) can survive process restarts only if pending work is durable. Persisting work items and events in the structured core before execution is the outbox pattern — the standard solution to the dual-write problem (state change + event must both persist atomically). It makes "crash during ingestion" recoverable without a message broker.
3. **Why events, not direct calls, between pipelines:** direct synchronous chaining would couple pipeline stages to each other's durations and failure modes; events decouple stages (each stage can be retried, skipped, or re-run independently), which is precisely what 04 §24 (Failure Handling) and the reflection loop (04 §21) require.
4. **Why defer a durable broker:** a broker (e.g., RabbitMQ/Kafka-style) is an operator-managed dependency with no MVP-scale benefit; the outbox + in-process executor satisfies the MVP envelope, and the event contract makes the later swap mechanical.

## Alternatives Considered

### Alternative 1: Fully synchronous execution

**Rejected because:** contradicts API-038/API-039; provider latency becomes user latency; long pipelines block workers; no failure isolation. Unacceptable beyond trivial workloads.

### Alternative 2: Durable message broker from day one

**Rejected because:** operational overhead (ADR-007 deployment assumptions) exceeds MVP need; the outbox pattern covers the single-node case; broker adoption is the extraction-path migration, not an MVP requirement.

### Alternative 3: State-machine orchestration engine (workflow engine)

**Rejected because:** a heavyweight orchestration dependency for a solo-developer MVP; the intelligence lifecycle is already defined (04 §5) and the event model implements it with less machinery. Revisit if pipeline branching complexity outgrows the event model (a future ADR trigger).

### Alternative 4: Cron/batch scheduling of all work

**Rejected because:** user-initiated work (ingest a document, generate a draft) must respond to interaction, not a schedule; batch-only would break the conversational workflow (WR-031, WR-034).

## Consequences

### Positive

1. Interactive requests stay responsive (API-038); long work is tracked and reported.
2. Crash-safe work through the durable outbox (07 §3.5).
3. Pipeline stages are independently retryable and observable (API-040).
4. The extraction path (broker) is a deployment swap, not a redesign.

### Negative

1. Eventual consistency for derived artifacts (indexes, summaries) — acceptable per 07 §3.3 but must be surfaced in the UI (06 §9 memory visualization, status states).
2. Event schema discipline required; events are contracts (09 Documentation Standards apply to their documentation).
3. Slight initial complexity (outbox, idempotency) for a solo developer.

### Neutral

1. The event model is invisible to the user except as status; it is an internal coordination mechanism.

## Repository Impact

No repository-structure change. Event contracts will be documented in API documentation per **04_Repository_Governance.md, §2** and **09_Documentation_Standards.md**.

## AI Engineering Implications

AI engineers implement pipelines as event-driven, idempotent units per **02_AI_Engineering_Contract.md, §7** and the standing responsibilities (**11_Engineering_Responsibilities.md**). Idempotency and failure handling are part of the Definition of Done (05 §2.4, §2.5).

## Compliance Rules

Verified via **07_Review_Checklist.md** (error handling, determinism) and **05_Definition_of_Done.md** (§2.5 Testing — retry/idempotency tests). Failure-handling defects follow **04_Repository_Governance.md, §5.3**.

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-003 (Modular Monolith) | Accepted | The in-process executor runs inside the monolith; extraction is coordinated here. |
| ADR-004 (Storage and Memory Strategy) | Accepted | The outbox persists in the structured core. |
| ADR-005 (Retrieval and Search Strategy) | Accepted | Index updates are async events. |
| ADR-007 (Deployment Strategy) | Accepted | Worker process topology is a deployment decision. |

## Future Considerations

1. **Workflow-engine trigger:** if pipeline branching (04 §12 Planning Layer) outgrows the event model, record a workflow-engine ADR.
2. **Event schema registry:** as events grow, a documented registry (per 09) prevents contract drift.
3. **Backpressure:** ingestion of very large corpora should define concurrency limits; record tuning results in the journal.

## References

- 04_AI_Architecture.md — §5 (AI Lifecycle), §7 (Knowledge Processing Pipeline), §19–§21 (Review, Writing, Reflection), §24 (Failure Handling)
- 05_Backend_Architecture.md — §6 (Internal Orchestration), §20 (Scalability Principles)
- 07_Operational_Architecture.md — §3.3 (Consistency and Integrity), §5.3 (Scaling Levers)
- SRS Chapter 5 — NFR-001 to NFR-008
- SRS Chapter 6 — AIR-063, AIR-064
- SRS Chapter 9 — API-035, API-038 to API-040
- ADR-001 — Separation of Requirements, Architecture, and Implementation
