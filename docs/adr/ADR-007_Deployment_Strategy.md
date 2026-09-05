# ADR-007: Deployment Strategy

**Status:** Accepted

**Date:** 2026-08-06

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (seventh ADR)

---

## Status

**Accepted.** This ADR records ScholarOS's deployment strategy: **local-first, single-node deployment for the MVP**, with a containerized cloud path and a documented evolution to managed and multi-tenant hosting. It governs the deployment assumptions of 07_Operational_Architecture.md §4.

---

## Context

07 §4 establishes the operational assumptions: backend-first personal MVP, single-node topology, development topology ≈ production topology, external AI provider egress, and minimal but present operations tooling. This ADR turns those assumptions into a concrete deployment decision and its evolution path.

Governing requirements:

- Observability and diagnostics (API-040).
- Configuration externalization (AIR-055 to AIR-057, NFR-031, NFR-032).
- Integrity and failure isolation (NFR-003 to NFR-006).
- Credible path to collaborative and institutional stages (07 §5; SRS Chapter 11 Phases 4–6).

## Problem

The deployment model shapes everything downstream: how the MVP is run, backed up, updated, and eventually hosted; how much operations burden the solo developer carries; and how the architecture migrates to cloud and multi-tenant stages without rework. Deploying "like an enterprise" from day one would drown the MVP in operations; deploying without a path would make later stages a rewrite.

## Decision

1. **MVP: local-first single-node deployment.** ScholarOS runs as a single backend process on the developer's machine (or a single small server), with local persistence (ADR-004) and local object storage. The frontend is served or connected locally (backend-first; 06 defines the client architecture).
2. **Automated setup and backup from the start.** Reproducible local setup (dependency and environment management) and automated scheduled backups with point-in-time recovery for the structured core (07 §3.5).
3. **Containerization is the cloud path.** The backend is packaged as a container image from the start, so the single-node model ports to any container host (VPS, managed container service) without changing the application.
4. **Cloud stage: managed services.** At the cloud stage, persistence moves to managed relational storage and object storage (ADR-004 migration paths), the async executor may become separate workers (ADR-006 extraction), and TLS termination and backups become platform-managed.
5. **Multi-tenant stage: platform isolation.** SaaS-stage tenancy (07 §5 stage 5) introduces per-tenant isolation decisions that will be recorded in a future ADR; the authentication boundary (05 §15) and data access layer are the enforcement points that keep this a later, contained decision.

## Rationale

1. **Why local-first:** the MVP's user is the researcher-developer; running the system locally gives the fastest iteration cycle, simplest debugging, and zero hosting cost, while preserving the production topology (07 §4.1). This is the pragmatic starting point for backend-first personal tools: local-first development with cloud-readiness, not cloud-first.
2. **Why containerization now, not later:** a container image is the cheapest possible insurance against environment drift and the standard unit of deployment; building it from the start costs days, not months, and eliminates the "works on my machine" class of problems (NFR-023 to NFR-026 maintainability). It is also the prerequisite for the cloud path with zero application changes.
3. **Why managed services at the cloud stage:** managed persistence and object storage remove operator burden (backups, replication) exactly when a real user's data is at stake; the data access layer (05 §16) makes the swap contractual (ADR-004).
4. **Why not cloud-first:** hosting, CI/CD, and managed services from day one add recurring cost and operations friction that a pre-release MVP does not justify, and they obscure the architecture behind infrastructure. The staged path keeps the architecture visible and testable first.

## Alternatives Considered

### Alternative 1: Cloud-first deployment (managed platform from day one)

**Rejected because:** recurring cost and operations burden before product validation; obscures the architecture; contradicts the personal-MVP stage and the deployment assumptions of 07 §4.1.

### Alternative 2: Desktop application (no server)

**Rejected because:** contradicts the backend-first architecture (05), the API contracts (API-041 to API-043), and the roadmap to collaborative research (SRS Chapter 11, Phase 4), which requires a server.

### Alternative 3: Serverless function deployment for the MVP

**Rejected because:** long-running intelligence pipelines (ADR-006) fit poorly in function time limits; provider lock-in contradicts AIR-040 to AIR-042; the modular monolith (ADR-003) is not a function-shaped topology.

### Alternative 4: No containerization, deploy from source

**Rejected because:** environment drift and setup cost rise sharply at the cloud stage; containerization from the start is cheaper than retrofitting.

## Consequences

### Positive

1. Fastest iteration cycle for the MVP; zero hosting cost.
2. Cloud path is application-transparent (container + managed services).
3. Backups and recovery are in place before real data exists.
4. Multi-tenant stage is a contained future decision, not a looming rewrite.

### Negative

1. Local-first means the MVP is not immediately shareable; sharing awaits the cloud stage (acceptable per backend-first MVP scope).
2. Containerization adds a small build step from the start.
3. The operator is the developer in the MVP; operational maturity (observability dashboards, alerting) is minimal by design (07 §4.3).

### Neutral

1. Deployment topology is invisible above the infrastructure boundary; the architecture set (07 §4) describes assumptions, and this ADR records the decision and path.

## Repository Impact

No documentation-structure change. Deployment and operations documentation (`docs/` operations notes, container definition files at implementation root) follow **04_Repository_Governance.md, §2–§3**.

## AI Engineering Implications

AI engineers implement with the deployment envelope in mind (single-node, containerized, external provider egress) per **02_AI_Engineering_Contract.md, §7** and the standing responsibilities (**11_Engineering_Responsibilities.md**). Secrets and configuration are externalized per AIR-055 to AIR-057; no environment-specific values are hardcoded (05 §17).

## Compliance Rules

Verified via **07_Review_Checklist.md** (configuration, security) and **05_Definition_of_Done.md** (§2.4: no hardcoded secrets or environment-specific values). Configuration violations follow **04_Repository_Governance.md, §5.3**.

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-002 (Technology Stack) | Accepted | The stack must run in the containerized single-node model. |
| ADR-003 (Modular Monolith) | Accepted | A single deployable process matches the MVP topology. |
| ADR-004 (Storage and Memory Strategy) | Accepted | Persistence engines match the deployment stage. |
| ADR-006 (Async Processing) | Accepted | Worker process topology is defined at the cloud stage. |

## Future Considerations

1. **Multi-tenant isolation ADR** — required at the SaaS stage (07 §5 stage 5); enforcement points are the auth boundary (05 §15) and data access layer.
2. **CI/CD** — a build pipeline is introduced at the cloud stage; the container image is the unit it deploys.
3. **Observability maturity** — dashboards and alerting are deferred to the cloud stage (API-040 defines the diagnostics baseline now).
4. **ADR-008 and beyond (numbering reserve).** No ADR-008 is required for Milestone 4. Deferred candidate topics, each bound to its triggering milestone: frontend technology selection (frontend implementation; ADR-002 item 3), multi-tenant isolation (SaaS stage; this ADR item 1), workflow-engine trigger (ADR-006 item 1), agent execution architecture (only if 04 §13–§14 prove insufficient during implementation), and embedding provider routing (ADR-002 item 1). Creating an ADR before its milestone triggers would record decisions without requirements — ADR discipline forbids it.

## References

- 05_Backend_Architecture.md — §15 (Authentication Boundary), §16 (Infrastructure Boundary), §17 (Configuration Management)
- 07_Operational_Architecture.md — §3 (Storage Strategy), §4 (Deployment Assumptions), §5 (Scalability Evolution)
- SRS Chapter 5 — NFR-003 to NFR-006, NFR-031 to NFR-034
- SRS Chapter 6 — AIR-040 to AIR-042, AIR-055 to AIR-057
- SRS Chapter 9 — API-036, API-037, API-040
- ADR-001 — Separation of Requirements, Architecture, and Implementation
