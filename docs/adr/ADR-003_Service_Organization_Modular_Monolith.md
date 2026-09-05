# ADR-003: Service Organization — Modular Monolith

**Status:** Accepted

**Date:** 2026-08-06

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (third ADR)

---

## Status

**Accepted.** This ADR decides how ScholarOS organizes its backend services: a **modular monolith** for the MVP, with explicitly extracted service boundaries that allow selective decomposition later. It governs the service responsibilities and boundaries of 05_Backend_Architecture.md.

---

## Context

05_Backend_Architecture.md defines logical service boundaries (Project, Document, Knowledge, Memory, Conversation, Capability, Review services) behind an orchestration layer. **Corrected by ADR-009 (2026-09-04):** the "Agent" service named here originally referred to the capability registry; it is renamed "Capability" and a new, distinct "Agent" service (the user's workspace, owning Project) is added as an eighth hard module boundary — see 05_Backend_Architecture.md §22. The question this ADR answers: in what *process topology* do those services run for the MVP and near-term evolution?

The governing requirements:

- Maintainability and modularity (NFR-013 to NFR-018).
- Independent testability of every major component (01 §5; 03 §3).
- Scalability envelope: NFR-001, NFR-002, NFR-007, NFR-008, API-038, API-039.
- A credible path to collaborative and institutional stages (07 §5; SRS Chapter 11, Phase 4 and Phase 6).

## Problem

Decomposing services into separate deployable processes (microservices) from day one would maximize independent scaling but introduce distributed-systems cost (network failure modes, distributed transactions, service discovery, observability complexity) that a solo-developer MVP cannot justify. A single monolith, however, risks losing the modular boundaries the architecture already defines — the classic failure mode where "it's a monolith" becomes "it's a big ball of mud" (Lehman's law of increasing complexity).

The decision must preserve the architecture's service boundaries while choosing the right deployment granularity for each stage.

## Decision

1. **Modular monolith.** All backend services run in a single deployable process for the MVP, organized as strictly separated modules that honor the boundaries of 05_Backend_Architecture.md §4 and §5.
2. **Boundaries are architectural, not cosmetic.** Cross-service communication happens through explicit module interfaces; a service may only be accessed through its public interface, never through internals. Internal modules may not import each other's persistence or internals (05 §18 Dependency Principles).
3. **Extraction-ready seams.** The orchestration layer (05 §6) treats services as callable units with defined contracts, so any service can be extracted into its own process later without interface changes.
4. **Shared persistence is a boundary, not a tie.** Modules share the data access layer but do not share each other's storage internals; per-module data ownership follows 03 §4 (Data Ownership Model).

## Rationale

1. **Why a monolith first:** a single deployable process gives the fastest feedback loop for a solo engineer, the simplest debugging, atomic deployments, and in-process calls (no network failures between services). This is the industry-standard starting point: Shopify and GitHub ran (and largely still run) modular monoliths at enormous scale before extracting services where evidence demanded it — the "monolith-first, extract-when-it-hurts" strategy.
2. **Why *modular*:** the boundaries are the asset. The architecture defines eight logical services (seven originally, plus Agent added by ADR-009) with distinct responsibilities and data ownership; encoding them as hard module boundaries from the start means the cost of future decomposition is interface design, not archaeology. This directly answers the "big ball of mud" risk.
3. **Why not microservices now:** distributed transactions, eventual consistency across service boundaries, and observability overhead would dominate a small team's effort without any current scaling demand (NFR-001, NFR-002 are personal-MVP envelopes). Microservices optimize for *team scaling and independent deployment*, neither of which the MVP needs.

## Alternatives Considered

### Alternative 1: Microservices from day one

**Rejected because:** operational and transaction complexity far exceeds the MVP's scaling demand; contradicts the MVP quality envelope (API-038, API-039) and the solo-developer delivery constraint; would multiply deployment and observability work (ADR-007 §4 assumptions).

### Alternative 2: Layered monolith without module boundaries

**Rejected because:** it discards the service architecture of 05; module boundaries would have to be re-created later at far higher cost (the extraction trap). Contradicts 05 §18 (Dependency Principles) and NFR-015 (modularity).

### Alternative 3: Serverless functions per service

**Rejected because:** imposes platform-specific contracts, complicates the long-running intelligence pipelines (ADR-006), and couples the architecture to a provider — contrary to provider agnosticism (AIR-040 to AIR-042) and 07 §4.

## Consequences

### Positive

1. Fastest possible MVP delivery with a single deployable process.
2. Architectural boundaries preserved, so the scalable stages of 07 §5 are reachable by extraction, not redesign.
3. Simple debugging, deployment, and testing (atomic unit; NFR-023 to NFR-026 testability).

### Negative

1. Scaling requires scaling the whole process until boundaries are extracted (bounded by NFR-007, NFR-008).
2. Module discipline must be enforced in review; weak boundaries degrade into coupling (07_Review_Checklist.md §4.3 Maintainability).
3. A single-process failure domain for the MVP — acceptable given single-node deployment (ADR-007).

### Neutral

1. The modular monolith is compatible with both async workers (ADR-006) and future extraction; the decision is a point on a spectrum, not a permanent topology.

## Repository Impact

Source organization follows **04_Repository_Governance.md, §2 and §3**: module directories mirror the logical services of 05 §5 under the implementation root. No change to documentation directories.

## AI Engineering Implications

AI engineers implement services as modules with explicit interfaces per **02_AI_Engineering_Contract.md, §7**, executing the standing responsibilities (**11_Engineering_Responsibilities.md**). Cross-module import violations are architectural defects and are caught at review (**07_Review_Checklist.md**).

## Compliance Rules

Verified through the standard processes: **07_Review_Checklist.md** (§4.3 Maintainability — module coupling), **05_Definition_of_Done.md** (§2.4 Implementation Quality), and dependency-principle checks per **04_Repository_Governance.md**.

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-001 (Separation of Concerns) | Accepted | Module boundaries must respect requirements/architecture/implementation separation. |
| ADR-002 (Technology Stack) | Accepted | The stack supports in-process module composition. |
| ADR-004 (Storage and Memory Strategy) | Accepted | Shared data access layer, per-module data ownership. |
| ADR-006 (Async Processing and Event Coordination) | Accepted | Workers may run in-process or as separate processes at extraction time. |
| ADR-009 (Agent and Project Domain Model Introduction) | Accepted | Renames the "Agent" module boundary to "Capability"; adds a new, distinct "Agent" module boundary (the user's workspace) as an eighth hard boundary. |

## Future Considerations

1. **Extraction criteria:** define evidence-based triggers for extracting a service (e.g., independent scaling demand, deployment cadence conflict, team ownership). This should be recorded when the first extraction is proposed.
2. **Distributed state:** if extraction occurs, per-module data ownership (03 §4) is the precondition that keeps extraction tractable.
3. **Event architecture maturity:** the async model (ADR-006) is the mechanism through which extracted services will eventually communicate.

## References

- 05_Backend_Architecture.md — §4 (Domain Boundaries), §5 (Service Responsibilities), §6 (Internal Orchestration), §18 (Dependency Principles), §20 (Scalability Principles)
- 07_Operational_Architecture.md — §4 (Deployment Assumptions), §5 (Scalability Evolution)
- SRS Chapter 5 — NFR-001, NFR-002, NFR-007, NFR-008, NFR-013 to NFR-018
- SRS Chapter 9 — API-038, API-039
- ADR-001 — Separation of Requirements, Architecture, and Implementation
