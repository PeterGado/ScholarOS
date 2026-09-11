# ADR-002: Technology Stack and Provider Abstraction

**Status:** Accepted

**Date:** 2026-08-06

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (second ADR)

---

## Status

**Accepted.** This ADR selects the ScholarOS backend technology stack for the MVP and establishes the provider abstraction boundary. It is the decision that unblocks database design, API design, and implementation (Project_Status.md "Next Milestone").

---

## Context

The architecture set (01–07) is intentionally implementation-agnostic (ADR-001). Before database design, API design, and implementation can begin, the project must make its foundational technology decisions once, architecturally, with rationale — not implicitly during coding.

The governing requirements are:

- Provider agnosticism: the AI provider layer must be replaceable (AIR-040 to AIR-042).
- Externalized configuration: provider selection and keys are configuration, not code (AIR-055 to AIR-057, NFR-031, NFR-032).
- Maintainability and testability: the codebase must remain modular and independently testable (NFR-013 to NFR-018, NFR-023 to NFR-026).
- Backend-first delivery: the MVP ships the backend capability set first (SRS Chapter 10; `docs/decsion/decision_01.md`).

## Problem

Without an explicit technology baseline, database and API design cannot be finalized, and implementation would make ad-hoc technology choices that silently become architecture. The decision must balance: speed of development for a solo engineer, long-term maintainability, provider interchangeability, and a credible path to the SaaS stages of 07_Operational_Architecture.md §5.

## Decision

1. **Language and runtime.** Python 3.12+ with an async-capable web framework (**FastAPI**) and Pydantic v2 for typed, validated interfaces.
2. **Persistence access.** An ORM (SQLAlchemy 2.x) behind the data access layer boundary (05_Backend_Architecture.md §16, API-032, API-033). Persistence *engines* are decided in ADR-004.
3. **AI provider abstraction.** A **provider-agnostic gateway** in the AI service layer (05 §7) exposing capabilities — text generation, embeddings, structured output — behind interfaces. Provider implementations (e.g., OpenAI-compatible APIs) are selected by configuration, never by business logic. Business and domain layers must not import provider SDKs.
4. **Testing.** pytest as the test framework; test isolation per component (03_AI_Engineering_Standards.md §3).
5. **Out of scope.** Frontend framework selection and deployment topology are deferred: frontend architecture is defined logically (06), and deployment is decided in ADR-007. The MVP is backend-first.

## Rationale

1. **Python + FastAPI** because the project is research- and AI-oriented; Python has the deepest AI/ML ecosystem (provider SDKs, embedding tooling, NLP), and FastAPI's async model matches the asynchronous pipeline reality of the AI lifecycle (04 §5; ADR-006). Pydantic gives validated contracts at the API boundary, directly supporting API-041 (technology-independent API definitions) by keeping schema and validation declarative.
2. **ORM behind a boundary** because 05 §16 requires persistence isolation; the ORM provides a portable, typed data model while the data access layer preserves the option to swap engines (ADR-004) without touching domain logic.
3. **Gateway abstraction** is the industry-standard pattern for AI provider portability (the "LLM gateway" / "model router" pattern used by platforms such as LiteLLM, Portkey, and enterprise gateways). ScholarOS's requirement is stronger than most: AIR-040 requires the *platform* to remain replaceable with respect to providers, and the architecture must survive a provider being retired, rate-limited, or changed by the researcher. Selecting by configuration (AIR-055 to AIR-057) makes a provider swap a configuration change, not a code change.
4. **pytest** because it is the de facto standard, supports the deterministic, isolated tests required by 03 §3, and integrates with the architecture's component testability principle (01 §5).

## Alternatives Considered

### Alternative 1: TypeScript/Node.js backend

**Rejected because:** the AI ecosystem leverage is weaker for research-oriented NLP/embedding work; the async pipeline needs are equally served but the AI tooling gap is decisive for a solo-developer MVP; the SRS and architecture are language-neutral and this choice reduces AI-integration risk.

### Alternative 2: No web framework (pure async library)

**Rejected because:** the API layer must serve typed, documented, technology-independent contracts (API-041 to API-043); a framework with schema validation and OpenAPI generation directly supports contract-first delivery (API-042).

### Alternative 3: Tightly coupled provider integration (SDK calls in domain code)

**Rejected because:** it violates AIR-040 to AIR-042, 03_AI_Engineering_Standards.md §2.3 (Provider Abstraction), and 01_Architecture_Overview.md §5 (provider agnosticism). A provider outage or price change would then force code changes across the business layer.

### Alternative 4: Self-hosted models only (no external providers)

**Rejected because:** the MVP must move fast with bounded compute cost; self-hosting is a deployment consideration (ADR-007) and remains compatible with the gateway design — the gateway makes self-hosted and cloud models interchangeable behind the same interface.

## Consequences

### Positive

1. Provider swap becomes a configuration change (AIR-040, AIR-041 satisfied).
2. Typed contracts at every API boundary reduce validation drift (API-041, API-042).
3. The stack is mainstream, well-documented, and easy for future contributors to learn.
4. Async-first matches the pipeline architecture and the scalability levers of 07 §5.3.

### Negative

1. Python runtime performance is not the strongest; acceptable for the MVP's workloads (NFR-001, NFR-002 define the target envelope) and mitigable by async I/O and the asynchronous processing model (ADR-006).
2. Framework and ORM version churn requires dependency governance (03 §10 Compliance Standards).
3. Frontend technology remains undecided, which delays frontend implementation milestones — accepted per backend-first scope (SRS Chapter 10).

### Neutral

1. The gateway adds one indirection layer; its cost is justified by the replaceability requirement.
2. Technology choices are recorded here, not in the SRS or architecture documents, preserving ADR-001 separation.

## Repository Impact

No repository structural change. Implementation directories and naming follow **04_Repository_Governance.md, §2 and §3**. Source code for the backend will be created under the implementation root when implementation begins.

## AI Engineering Implications

AI engineers implement within the gateway and data access boundaries defined in **02_AI_Engineering_Contract.md, §7**, executing the standing responsibilities of **11_Engineering_Responsibilities.md** (RSP-001 to RSP-006). No AI engineer may import a provider SDK into domain layers — this is an architectural constraint, enforced at review per **07_Review_Checklist.md**.

## Compliance Rules

Compliance is verified through the standard review and completion processes: **07_Review_Checklist.md** (§4.2 Architecture Alignment, provider abstraction check) and **05_Definition_of_Done.md** (§2.4 Implementation Quality: provider-specific logic abstracted behind interfaces). Provider-abstraction violations are handled per **04_Repository_Governance.md, §5.3**.

## Related ADRs

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-001 (Separation of Concerns) | Accepted | This ADR records technology decisions that remain out of requirements and architecture documents. |
| ADR-004 (Storage and Memory Strategy) | Accepted | Persistence engines are decided there, behind the data access layer this ADR requires. |
| ADR-006 (Async Processing and Event Coordination) | Accepted | The async-first framework supports the pipeline decisions recorded there. |
| ADR-010 (Authentication Boundary — Single-User Session Model) | Accepted | Uses this ADR's stack (FastAPI/SQLAlchemy) unchanged; adds only a password-hashing library, no new stack element. |
| ADR-007 (Deployment Strategy) | Accepted | Deployment topology complements this stack decision. |

## Future Considerations

1. **Provider failover and routing** (multiple providers, cost-aware routing) is a post-MVP capability; the gateway interface must be designed so routing can be added without interface changes.
2. **Embedding provider selection** follows the same gateway pattern; embeddings are consumed through the retrieval strategy (ADR-005).
3. **Frontend technology selection** should be recorded in a future ADR when frontend implementation begins.

## References

- 01_Architecture_Overview.md — §5 (Architectural Principles)
- 04_AI_Architecture.md — §23 (Provider Abstraction)
- 05_Backend_Architecture.md — §7 (AI Service Layer), §16 (Infrastructure Boundary)
- 07_Operational_Architecture.md — §5 (Scalability Evolution)
- SRS Chapter 6 — AIR-040 to AIR-042, AIR-055 to AIR-057
- SRS Chapter 5 — NFR-013 to NFR-018, NFR-023 to NFR-026, NFR-031, NFR-032
- SRS Chapter 9 — API-032, API-033, API-041 to API-043
- ADR-001 — Separation of Requirements, Architecture, and Implementation
