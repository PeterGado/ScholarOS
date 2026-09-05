# ADR-001: Separation of Requirements, Architecture, and Implementation

**Status:** Accepted (Foundational)

**Date:** 2026-07-29

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (first ADR)

---

## Status

**Accepted.** This ADR is the foundational architectural decision of ScholarOS. It establishes the permanent engineering rule that requirements, architecture, and implementation shall remain distinct concerns throughout the lifetime of the project.

This ADR is referenced by:

* The Project Constitution (01_Project_Constitution.md), Section 8
* All subsequent governance documents (02–12)
* All SRS chapters (01–11)
* The Contributing Guide (Contributing.md)
* The Documentation Index (READme.md)

No future ADR may contradict this ADR. Amendments to this ADR require constitutional-level review per the amendment process defined in 01_Project_Constitution.md, Section 9.

---

## Context

ScholarOS has completed the specification phase. All eleven chapters of the Software Requirements Specification (SRS) have been defined. The project is now preparing to transition from requirements specification into architecture design and, subsequently, into implementation.

### Specification Phase Complete

During the specification phase, the repository maintained a clear separation of concerns:

* The SRS defined **what** the system must do.
* The Vision and product overview defined **why**.
* No implementation code existed.

### Governance Framework Established

The Engineering Governance Framework (docs/governance/01–12) defines the project's governance hierarchy, engineering standards, and documentation conventions. The framework explicitly recognizes the separation of concerns in multiple documents:

| Document | Section | Relationship to Separation |
|----------|---------|---------------------------|
| 01_Project_Constitution.md | §5 (Documentation Hierarchy), §6 (Development Lifecycle), §8 (Separation of Concerns) | Establishes the three-concern model as constitutional principle |
| 02_AI_Engineering_Contract.md | §10 (Documentation Principles) | Requires clear distinction between requirements, architecture, and implementation |
| 03_AI_Engineering_Standards.md | §5 (Architecture Governance), §6 (Implementation Governance) | Enforces separation in engineering workflow |
| 04_Repository_Governance.md | §2 (Directory Structure) | Defines where each concern's documents reside |
| 09_Documentation_Standards.md | §2 (Documentation Principles), §6.2 (ADR Standards) | Requires clear concern distinction and defines ADR structure |

### Development Lifecycle

The approved development lifecycle (01_Project_Constitution.md, §6; Contributing.md) establishes the following traceability chain:

```md
Vision
↓
Software Requirements Specification (SRS)
↓
Architecture
↓
Database Design
↓
API Design
↓
Implementation
↓
Testing
↓
Documentation Review
```

Each arrow in this chain crosses a concern boundary. The separation rule governs how those boundaries are maintained.

### The Risk of Conflation

As implementation work begins, there is a natural risk that these concerns may become conflated:

* Requirements may be reinterpreted to fit implementation convenience.
* Architecture decisions may be incorrectly recorded as requirements.
* Implementation details may drift into specification documents.

Without explicit governance preventing these patterns, the repository's long-term clarity, maintainability, and traceability will degrade.

---

## Problem

ScholarOS requires a clear engineering governance rule that:

1. **Prevents requirements** from being modified to match implementation choices.
2. **Prevents implementation details** from being introduced into the SRS.
3. **Establishes architecture** as the bridge between requirements and code.
4. **Ensures that every contributor** — human or AI — understands which documents govern which kind of engineering decision.

Without this rule, the following specific problems are likely to occur:

### 1. Specification Drift

Requirements become polluted with implementation detail, making them harder to validate, maintain, and trace. The SRS loses its authority as an implementation-agnostic reference.

### 2. Architecture Invisibility

Architectural decisions are embedded in code rather than documented independently, making them invisible to reviewers, future contributors, and AI assistants. The rationale behind design choices is lost.

### 3. Traceability Loss

The chain from Vision to code becomes untraceable when documents mix different concerns. A requirement cannot be reliably traced to an architectural component, nor an architectural decision to its implementation.

### 4. Contradictory Documentation

SRS chapters, architecture documents, and source code begin to contradict one another because the boundary between them is undefined. Without clear ownership of each concern, no single document can be trusted as authoritative.

### 5. AI Misalignment

AI assistants cannot reliably distinguish between prescriptive requirements, design guidance, and implementation notes when these concerns are mixed. This leads to inconsistent contributions, contradictory interpretations, and reduced engineering quality.

### 6. Maintenance Debt

When a single document contains requirements, design decisions, and implementation hints, changing any one concern requires understanding and modifying multiple unrelated aspects. This coupling increases maintenance cost and reduces the reliability of each document as a source of truth.

---

## Decision

ScholarOS shall maintain a strict separation among three engineering concerns: **Product Requirements**, **System Architecture**, and **Technical Implementation**.

### Product Requirements

The Software Requirements Specification (SRS) defines **what** the system must do.

* The SRS is the authoritative definition of required system behavior.
* The SRS shall remain implementation-agnostic. It shall not prescribe programming languages, frameworks, database engines, AI providers, code structure, or deployment infrastructure.
* The SRS may describe functional outcomes, quality attributes, data concepts, user workflows, and interface contracts without specifying how those outcomes are realized in software.
* No feature may be implemented without a corresponding approved requirement in the SRS.
* The SRS shall not be modified solely to accommodate implementation convenience.
* Requirement identifiers (FR, NFR, AIR, DR, WR, API, MVP, RDM, DC) shall be used consistently per SRS Chapter 1, Section 7.

The SRS is owned by the Product Owner (per 09_Documentation_Standards.md, §5.1).

### System Architecture

Architecture documents define **how the system is organized** to satisfy the requirements.

* Architecture documentation resides in `docs/architecture/` and any supporting subdirectories (`docs/database/`,    `docs/api/`, etc.).
* Architecture documents describe system organization, component boundaries, data flow, service interaction, deployment topology, and technology decisions.
* Architecture may reference specific technologies, frameworks, or patterns where those choices are architecturally significant and cannot be deferred to implementation.
* Architecture decisions are governed by Architecture Decision Records (ADRs) in `docs/adr/`.
* Architecture documents shall remain implementation-aware but not implementation-prescriptive. They define the design constraints within which implementation occurs.

Component-level design decisions — including backend service organization, frontend component boundaries, interface contracts between layers, and data flow between subsystems — belong in architecture documentation. The boundary between architecture and implementation is the line at which a design decision ceases to constrain the system's structure and begins to constrain how individual modules are written.

Architecture documents are owned by the Lead Engineer (per 09_Documentation_Standards.md, §5.1). Changes that affect architecture require ADR documentation if architecturally significant.

### Technical Implementation

Implementation defines **how the architecture is realized in code**.

* Implementation consists of source code, configuration files, migration scripts, tests, and technical documentation (e.g., inline comments, README files within modules).
* Implementation must conform to the architecture and satisfy the requirements.
* Implementation details that do not affect architecture or requirements belong exclusively in code and technical documentation.
* No implementation detail shall be promoted into the SRS or architecture documentation unless it represents an architecturally significant constraint.
* Implementation shall not redefine requirements (per 01_Project_Constitution.md, §5).
* Implementation shall not bypass architecture (per 03_AI_Engineering_Standards.md, §5).
* Implementation shall not introduce undocumented functionality.

### Development Lifecycle Integration

The three concerns map to the approved development lifecycle as follows:

| Lifecycle Stage | Concern | Document Type |
|----------------|---------|---------------|
| Vision | Product Identity | Vision Document |
| SRS | Requirements | SRS Chapters (01–11) |
| Architecture | System Organization | Architecture docs, ADRs |
| Database Design | Architecture | Database docs |
| API Design | Architecture | API docs |
| Implementation | Code | Source code, tests |
| Testing | Verification | Test suites |
| Documentation Review | All | Cross-document review |

---

## Rationale

### 1. Requirements Must Remain Stable to Preserve Project Direction

The SRS represents the product owner's intent and the approved project vision. If requirements are modified to match implementation convenience, the product begins to serve the implementation rather than the user need. Keeping requirements implementation-agnostic protects the product owner's intent and ensures that implementation remains accountable to requirements — not the reverse.

**Governance reference:** 01_Project_Constitution.md, §5 (Documentation Hierarchy: Source Code shall never redefine requirements), §10 (Constitutional principle of traceability).

### 2. Architecture Exists Because Requirements Alone Do Not Determine Design

Many valid architectural designs can satisfy the same set of requirements. Architecture documentation captures the specific organizational decisions that were made and why. Without explicit architecture documentation, these decisions are either lost or implicitly encoded in source code, making them invisible to future contributors and difficult to revisit.

**Governance reference:** 01_Project_Constitution.md, §6 (Development Lifecycle places Architecture between SRS and Database Design).

### 3. Mixing Concerns Creates Maintenance Debt

When a single document contains requirements, design decisions, and implementation hints, it becomes difficult to change any one concern without affecting the others. Requirements changes require understanding which parts of the document are truly requirements. Architecture changes require disentangling design from specification. This coupling increases maintenance cost and reduces the reliability of each document as a source of truth.

**Governance reference:** NFR-013 (Maintainability), NFR-014 (Traceability), NFR-015 (Modularity).

### 4. Separation Supports Traceability

The approved Vision defines the traceability chain as:

```md
Vision
↓
SRS
↓
Architecture
↓
Implementation
↓
Testing
↓
Documentation
```

Each arrow represents a distinct concern boundary. Preserving separation at each stage ensures that traceability remains unambiguous: a requirement can be traced to an architectural component, which can be traced to an implementation module, which can be traced to a test. When concerns are mixed, traceability becomes ambiguous.

**Governance reference:** 01_Project_Constitution.md, §7 (Requirement Traceability), Contributing.md (Requirement Traceability), SRS Chapter 1, §11 (Requirement Traceability).

### 5. AI-Assisted Engineering Requires Clear Boundaries

AI assistants rely on precise documentation to produce consistent, non-contradictory work. When requirements, architecture, and implementation are mixed in the same documents, AI contributors cannot reliably determine which statements are prescriptive requirements, which are design guidance, and which are implementation notes.

Separation of concerns makes the documentation machine-readable in the engineering sense: each document type has a known purpose, a known level of authority, and known relationships to other document types. This enables AI contributors to interpret each document according to its defined role and detect contradictions across concern boundaries.

**Governance reference:** 02_AI_Engineering_Contract.md, §7 (Engineering Workflow), §10 (Documentation Principles); 09_Documentation_Standards.md, §2 (Documentation Principles).

### 6. Repository Governance Requires Clear Concern Boundaries

The repository governance rules (04_Repository_Governance.md) define where each type of document resides, naming conventions, and cross-reference policies. These rules can only be enforced when the boundaries between document types are clearly defined. The separation rule provides the foundation for all repository organization decisions.

---

## Alternatives Considered

### Alternative 1: Single Specification Document

A single document containing requirements, architecture, and implementation notes was considered and rejected.

**Rejected because:**

* Contradicts the approved Vision's traceability chain (Vision → SRS → Architecture → Implementation → Testing → Documentation).
* Creates unavoidable coupling between concerns, making it impossible to change one layer independently of the others.
* Reduces the reliability of the document as a requirements reference, since readers cannot readily distinguish between what the system must do and how it was implemented.
* Cannot be reliably interpreted by AI assistants, who would be unable to distinguish prescriptive rules from informational content.
* Violates 01_Project_Constitution.md, §6 (Development Lifecycle) and §7 (Requirement Traceability).

### Alternative 2: Requirements with Embedded Architecture

Under this model, architecture decisions would be recorded as sections within the SRS rather than in separate documents.

**Rejected because:**

* The SRS is explicitly described as implementation-agnostic in SRS Chapter 1, Section 1: *"This document is intentionally implementation-agnostic. It defines what the system must accomplish rather than prescribing how individual components should be implemented."*
* Embedding architecture decisions would violate this constraint and blur the boundary between required behavior and design choice.
* Architecture belongs in dedicated documents and ADRs where design rationale can be fully explored without being constrained by SRS format conventions.
* Would create ambiguity about which sections are requirements (binding) and which are design guidance (mutable).

### Alternative 3: Architecture-Free Implementation

Under this model, implementation would proceed directly from requirements without an intervening architecture documentation layer.

**Rejected because:**

* Contradicts the approved development lifecycle documented in 01_Project_Constitution.md, §6 and Contributing.md (Vision → SRS → Architecture → Database Design → API Design → Implementation).
* Eliminates the documented traceability path, making architectural decisions invisible, undocumented, and unreviewable.
* Violates 03_AI_Engineering_Standards.md, §5.1 (Architecture decisions shall be documented before implementation begins).
* Creates long-term maintenance debt as undocumented architectural assumptions become implicit in code.

### Alternative 4: Implementation-Driven Requirements

Under this model, requirements would be refined and updated based on implementation feedback as part of normal development, allowing implementation convenience to inform requirement changes.

**Rejected because:**

* Violates the constitutional principle that "Source Code shall never redefine requirements" (01_Project_Constitution.md, §5).
* Undermines the SRS's authority as a stable reference point for the product vision.
* Creates a feedback loop where implementation convenience drives scope rather than user need.
* Contradicts 02_AI_Engineering_Contract.md, §13 (Prohibited Behavior): "Promote implementation details into requirements."

---

## Consequences

### Positive

1. **Clear authority:** Every contributor understands which documents govern requirements, which govern architecture, and which govern implementation. This is reinforced by the documentation hierarchy in 01_Project_Constitution.md, §5.

2. **Traceable evolution:** Changes can be traced from requirement to architecture to code without ambiguity, satisfying the traceability requirements in SRS Chapter 1, §11 and 01_Project_Constitution.md, §7.

3. **Implementation freedom:** Architects and engineers can make implementation choices within the architectural boundary without needing to modify requirements.

4. **Stable SRS:** The SRS remains a stable reference point throughout development, protecting the product vision from implementation-driven scope changes.

5. **Auditable ADRs:** Architectural decisions are captured in ADRs, providing a permanent record of why the system was designed the way it was.

6. **AI alignment:** AI contributors can reliably interpret each document type according to its defined role in the engineering hierarchy (02_AI_Engineering_Contract.md, §10).

7. **Repository integrity:** Documentation remains internally consistent because each concern has a clear home with defined ownership (04_Repository_Governance.md, §2).

8. **Governance enforcement:** The separation rule can be verified during reviews (07_Review_Checklist.md) and is part of the Definition of Done (05_Definition_of_Done.md, §2.8).

### Negative

1. **Documentation overhead:** Maintaining three distinct documentation layers requires discipline and periodic review.

2. **Coordination cost:** Architecture changes that affect requirements or implementation boundaries require explicit cross-document updates.

3. **Learning curve:** Contributors must understand the separation model before making changes.

4. **Upfront effort:** Architecture documentation must be produced before implementation can begin, potentially slowing initial velocity.

5. **Boundary ambiguity:** In some cases, it may be unclear whether a decision is architectural or implementation-level, requiring judgment calls.

### Neutral

1. **Architecture as gating mechanism:** Implementation cannot proceed without approved architecture, which may surface design issues earlier.

2. **Documentation as deliverable:** Documentation is treated as part of the product (01_Project_Constitution.md, Principle 9), so documentation overhead is not considered waste.

### Mitigations

| Risk | Mitigation |
|------|-----------|
| Documentation overhead | Justified by maintainability requirements NFR-013, NFR-014. The Project Status and journal ( `docs/journal/` ) track documentation synchronization tasks (NFR-035). |
| Coordination cost | Cross-document consistency checks are part of the Definition of Done (05_Definition_of_Done.md, §2.7) and Review Checklist (07_Review_Checklist.md, §3.2). |
| Learning curve | The README, Contributing Guide, and governance framework all document the hierarchy and separation model. |
| Boundary ambiguity | Architecture documents shall include clear scope statements. Disputes about boundary placement shall be resolved by the Lead Engineer and recorded in the journal ( `docs/journal/` ). |

---

## Repository Impact

The separation decision governs how the repository is organized. The mapping of concerns to directories (requirements in `docs/srs/` , architecture in `docs/architecture/` and `docs/adr/` , implementation in code directories) is defined by **04_Repository_Governance.md, §2 (Directory Structure)**.

Cross-reference rules between concerns, file modification policies that respect the separation, and consistency review triggers are all governed by **04_Repository_Governance.md, §4 (File Modification Policies)** and **§5 (Repository Consistency Rules)**.

---

## AI Engineering Implications

AI Software Engineers must interpret each document type according to its concern: SRS chapters are binding requirements, architecture documents and ADRs are binding design constraints, source code is implementation. When contradictions arise across concern boundaries, the document hierarchy in **01_Project_Constitution.md, §5** governs.

The AI engineering workflow — including repository review, dependency analysis, consistency checks, and report production — is defined in **02_AI_Engineering_Contract.md, §7 (Engineering Workflow)** and executed through the standing engineering responsibilities in **11_Engineering_Responsibilities.md** (RSP-001 to RSP-007). Prompt construction practices that respect the separation of concerns are governed by **10_Prompting_Guidelines.md**, and self-executing sessions are booted with the **12_Master_Execution_Prompt.md**.

---

## Compliance Rules

Separation compliance is verified through the standard review and completion processes:

* **07_Review_Checklist.md** — §3.2 (Consistency) and §4.2 (Architecture Alignment) define how concern-separation violations are detected during review.
* **05_Definition_of_Done.md** — §2.2 (Requirements Alignment), §2.3 (Architecture Alignment), and §2.8 (No Contradictions) define the completion criteria that ensure separation is maintained.

No additional compliance rules beyond those defined in the governance framework are required. If a separation violation is discovered, it shall be handled per **04_Repository_Governance.md, §5.3 (Consistency Violations)**.

---

## Related ADRs

This ADR is the first and foundational ADR of ScholarOS. It establishes the governance pattern that all future ADRs shall follow.

This ADR also clarifies that documentation-only repository hardening work is permitted without creating database design, API design, implementation, testing, deployment, or infrastructure artifacts. Such work remains within the governance and documentation concern boundary and must preserve the frozen milestone discipline.

| ADR | Status | Relationship |
|-----|--------|-------------|
| ADR-001 (this document) | Accepted | Foundational. Defines the separation rule that all future ADRs must respect. |
| ADR-002 (Technology Stack and Provider Abstraction) | Accepted | Technology decisions recorded within the architectural concern boundary defined here. |
| ADR-003 (Service Organization — Modular Monolith) | Accepted | Module organization respecting the separation of concerns and traceability chain. |
| ADR-004 (Storage and Memory Strategy) | Accepted | Storage decisions behind the data access layer boundary. |
| ADR-005 (Retrieval and Search Strategy) | Accepted | Retrieval decisions within the architecture's retrieval contract. |
| ADR-006 (Async Processing and Event Coordination) | Accepted | Pipeline coordination without introducing implementation requirements. |
| ADR-007 (Deployment Strategy) | Accepted | Deployment decisions within the architecture's deployment assumptions. |
| ADR-008 (API Contract Governance During Backend Implementation) | Accepted | Clarifies how the API Design lifecycle stage (Development Lifecycle Integration table, above) is realized for ScholarOS's code-first stack: API contracts are produced progressively during implementation rather than as a standalone pre-implementation document set, while architecturally significant API decisions remain subject to ADR governance. |
| ADR-009 (Agent and Project Domain Model Introduction) | Accepted | Corrects the frozen Database and Architecture Baselines: introduces Agent as the user's permanent workspace, narrows Project to raw input material, and renames the capability-registry entities from Agent/Agent Capability to Capability/Capability Entry to resolve a naming collision. |

All future ADRs must:

1. State clearly which concern(s) they address.
2. Reference the SRS requirements they support (traceability to requirements).
3. Not introduce implementation details.
4. Not contradict the separation rule established in this ADR.

---

## Future Considerations

1. **Architecture documentation convention:** A future ADR (or update to 09_Documentation_Standards.md) should define the standard structure and content requirements for architecture documents in `docs/architecture/`.

2. **SRS refinement governance:** As implementation reveals ambiguities in the SRS, a defined process should exist for proposing SRS amendments without violating the separation rule. This process should be documented in a future governance document or ADR.

3. **Boundary arbitration:** A documented process for resolving disputes about whether a decision belongs in requirements, architecture, or implementation should be established. The Project Constitution (§5) and this ADR provide the framework, but an arbitration procedure would reduce ambiguity.

4. **Automated consistency checks:** As the repository grows, automated validation tools could verify that requirements, architecture documents, and implementation remain consistent and that no concern has leaked across boundaries.

5. **ADR template evolution:** As more ADRs are created, the standard ADR template should be reviewed and refined to capture lessons learned from earlier ADRs.

---

## References

### Governance Framework

* 01_Project_Constitution.md — §5 (Documentation Hierarchy), §6 (Development Lifecycle), §7 (Requirement Traceability), §8 (Separation of Concerns)
* 02_AI_Engineering_Contract.md — §7 (Engineering Workflow), §10 (Documentation Principles), §13 (Prohibited Behavior)
* 03_AI_Engineering_Standards.md — §5 (Architecture Governance), §6 (Implementation Governance), §7 (Traceability Standards)
* 04_Repository_Governance.md — §2 (Directory Structure), §4 (File Modification Policies), §5 (Repository Consistency Rules)
* 05_Definition_of_Done.md — §2.2 (Requirements Alignment), §2.3 (Architecture Alignment), §2.8 (No Contradictions)
* 07_Review_Checklist.md — §3.2 (Consistency), §4.2 (Architecture Alignment)
* 09_Documentation_Standards.md — §2 (Documentation Principles), §6.2 (ADR Standards), §8 (Prohibited Documentation Practices)
* 10_Prompting_Guidelines.md — Prompt construction practices
* 11_Engineering_Responsibilities.md — Standing responsibilities (RSP-001 to RSP-007)
* 12_Master_Execution_Prompt.md — Self-executing session template

### Vision Document

* Vision Document v1.0 — §11 (Requirement Traceability), §12 (Design Philosophy)

### SRS

* SRS Chapter 1 — §1 (Purpose: implementation-agnostic), §7 (Document Conventions), §11 (Requirement Traceability)
* SRS Chapter 5 — NFR-013 (Maintainability), NFR-014 (Traceability), NFR-015 (Modularity), NFR-035 (Documentation)
* SRS Chapter 6 — AIR-061 (Traceability), AIR-062 (Documentation traceability)
* SRS Chapter 7 — §9 (Traceability to ADR-001)
* SRS Chapter 8 — §8 (Traceability to ADR-001)
* SRS Chapter 9 — §7 (Traceability to ADR-001)
* SRS Chapter 10 — §9 (Traceability to ADR-001)
* SRS Chapter 11 — §9 (Traceability to ADR-001)

### Project Documentation

* Contributing.md — Development Philosophy, Source of Truth, Requirement Traceability
* READme.md — Documentation Hierarchy, Development Principles
* decision_01.md — Backend-First Decision (pre-governance legacy record)
