# ScholarOS Documentation

**Version:** 1.0.0  
**Status:** Active  
**Last Updated:** 2026-07-29  
**Latest ADR:** ADR-001 — Separation of Requirements, Architecture, and Implementation
**Governance Framework:** Engineering Governance Framework v1.0 — Active

---

## Overview

Welcome to the official documentation for **ScholarOS**.

This documentation serves as the single source of truth for the design, development, implementation, and future evolution of ScholarOS.

All contributors—human or AI—must consult these documents before proposing, implementing, or modifying any feature.

---

## Documentation Hierarchy

If multiple documents appear to conflict, the following order of precedence shall apply:

1. Project Constitution
2. AI Engineering Contract
3. AI Engineering Standards
4. Repository Governance
5. Vision Document
6. Software Requirements Specification (SRS)
7. Architecture Documentation
8. Architecture Decision Records (ADR)
9. Source Code

Higher-level documents always take precedence over lower-level documents.

**Note:** Governance documents 05–14 (Definition of Done through Prompting Guidelines) sit between ADRs and Source Code in the full hierarchy. See `docs/governance/01_Project_Constitution.md` Section 5 for the complete, authoritative hierarchy.

---

## Reading Order

All contributors should review the documentation in the following order before beginning work.

### Phase 0 — Engineering Governance Framework (Read First)

```md
docs/governance/
```

| Document | Purpose |
|----------|---------|
| 01_Project_Constitution.md | Foundational project identity, philosophy, and governing principles. Highest authority. |
| 02_AI_Engineering_Contract.md | Binding contract for all AI Software Engineers. |
| 03_AI_Engineering_Standards.md | Quality and engineering standards. |
| 04_Repository_Governance.md | Repository structure, naming, and consistency rules. |
| 05_Definition_of_Done.md | Mandatory completion criteria for all tasks. |
| 06_Engineering_Report_Standard.md | Mandatory Engineering Report template. |
| 07_Review_Checklist.md | Review and validation process. |
| 08_AI_Roles_and_Responsibilities.md | Multi-AI collaboration framework. |
| 09_Documentation_Standards.md | Documentation formatting and conventions. |
| 10_Prompting_Guidelines.md | Prompt engineering standards. |

---

### Phase 1 — Product Vision

```md
docs/vision/
```

| Document | Purpose |
|----------|---------|
| Vision_v1.0.md | Defines why ScholarOS exists, the problem it solves, product philosophy, and long-term vision. |

---

### Phase 2 — Software Requirements Specification

```md
docs/srs/
```

| Document | Purpose |
|----------|---------|
| 01_Introduction.md | Defines the purpose, scope, terminology, and governance of the SRS. |
| 02_Product_Definition_and_Overview.md | Defines ScholarOS as a product, its users, objectives, and boundaries. |
| 03_Overall_System_Description.md | Describes the system from a high-level engineering perspective. |
| 04_Functional_Requirements.md | Defines what the system must do. |
| 05_Non_Functional_Requirements.md | Defines quality requirements such as performance, security, and scalability. |
| 06_AI_Requirements.md | Defines AI-specific behaviors and constraints. |
| 07_Data_Requirements.md | Defines the data model and information managed by ScholarOS. |
| 08_User_Workflows.md | Defines user interactions and workflows. |
| 09_API_Requirements.md | Defines system interfaces and service contracts. |
| 10_MVP_Scope.md | Defines the boundaries of the first release. |
| 11_Future_Roadmap.md | Defines planned future capabilities. |

---

### Phase 3 — Architecture

```md
docs/architecture/
```

Contains:

* System Architecture
* Component Architecture
* AI Pipeline
* Context Assembly Pipeline
* Deployment Architecture
* Sequence Diagrams
* Data Flow Diagrams

---

### Phase 4 — Database

```md
docs/database/
```

Contains:

* Entity Relationship Diagram (ERD)
* Database Schema
* Migration Strategy
* Indexing Strategy

---

### Phase 5 — API

```md
docs/api/
```

Contains:

* REST API Specification
* Internal Services
* Authentication
* Error Handling

---

### Phase 6 — AI Agents

```md
docs/agents/
```

Contains documentation for the intelligent subsystems that power ScholarOS.

Examples include:

* Knowledge Manager
* Author Profile Builder
* Context Builder
* Writing Engine
* Review Engine
* Citation Assistant
* Project Memory

---

### Phase 7 — Architecture Decision Records

```md
docs/adr/
```

Contains significant engineering decisions made throughout the project's lifecycle.

---

## Development Principles

All contributors should follow these principles.

* Documentation is the source of truth.
* Requirements precede implementation.
* Architecture precedes code.
* Every feature must map to an approved requirement.
* Components should remain modular.
* AI providers should remain replaceable.
* Human review is required before approving major documentation or code changes.

---

## AI Contributor Guidelines

AI assistants contributing to ScholarOS should:

1. Read the documentation before performing work.
2. Avoid contradicting approved documents.
3. Raise ambiguities rather than making assumptions.
4. Preserve consistency across documentation.
5. Recommend updates when requirements appear incomplete.
6. Clearly distinguish between requirements, design, and implementation.

---

## Current Project Status

Refer to the following file for the active development state:

```md
PROJECT_STATUS.md
```

This file identifies:

* Current milestone
* Current task
* Completed work
* Upcoming work

---

## Documentation Maintenance

Documentation is a living artifact.

Whenever a requirement, architecture decision, or implementation changes, the corresponding documentation should be reviewed and updated to maintain consistency across the project.

---

## Final Principle

ScholarOS follows one core engineering philosophy:

> **Understand First. Build Second.**

Every contributor—human or AI—should fully understand the approved documentation before proposing new designs or implementing code.
