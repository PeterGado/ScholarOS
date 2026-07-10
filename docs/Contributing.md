# Contributing to ScholarOS

**Version:** 1.0.0  
**Status:** Active

---

## Purpose

This document defines the engineering workflow, contribution standards, and development principles for ScholarOS.

Its purpose is to ensure that all contributions—whether made by humans or AI assistants—remain consistent, traceable, maintainable, and aligned with the project's approved documentation.

---

## Development Philosophy

ScholarOS follows a documentation-first engineering methodology.

Every implementation must be supported by approved documentation.

The development lifecycle is:

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

No implementation should bypass this process.

---

## Source of Truth

The official source of truth is the project documentation.

If multiple documents conflict, the following order applies:

1. Vision Document
2. Software Requirements Specification
3. Architecture Documentation
4. Database Documentation
5. API Documentation
6. Architecture Decision Records (ADR)
7. Source Code

Code shall never redefine requirements.

---

## Contribution Workflow

Every contribution should follow this workflow.

1. Read the Documentation Index (`docs/README.md`).
2. Review the relevant approved documentation.
3. Identify the requirement(s) being implemented.
4. Raise ambiguities before making assumptions.
5. Produce the proposed change.
6. Perform self-review.
7. Submit for architectural review.
8. Merge after approval.

---

## Requirement Traceability

Every feature must map back to an approved requirement.

Example:

Requirement

```md
FR-021 — Document Upload

↓

Architecture

Document Processing Service

↓

Implementation

backend/app/services/document_service.py

↓

Tests

tests/test_document_upload.py
```

This traceability ensures that every feature has a documented purpose.

---

## Documentation Standards

Documentation should:

* be concise and unambiguous
* avoid duplication
* distinguish requirements from implementation
* remain consistent with earlier documents
* use professional technical language.

Major documentation changes should be reviewed before approval.

---

## Coding Standards

Code should be:

* modular
* readable
* well documented
* testable
* loosely coupled
* strongly typed where practical.

Business logic should remain separate from infrastructure code.

---

## AI Contributor Guidelines

AI assistants are treated as engineering contributors.

Before beginning work, an AI assistant should:

1. Read the project documentation.
2. Understand the current project status.
3. Identify the relevant requirements.
4. Explain uncertainties before implementation.
5. Avoid introducing undocumented functionality.
6. Recommend documentation updates when appropriate.

AI assistants should assist—not redefine—the project.

---

## Architecture Principles

ScholarOS is designed around several long-term architectural principles:

* Modular components
* Replaceable AI providers
* Backend-first development
* Clear separation of concerns
* Persistent project memory
* Context-aware generation
* Human oversight
* Scalable system design

Every contribution should reinforce these principles.

---

## Branching Strategy

Until public collaboration begins, the project will follow a simplified Git workflow.

Primary branch:

main

Future branches may include:

* develop
* feature/*
* bugfix/*
* release/*

---

## Commit Message Convention

Use clear and descriptive commit messages.

Examples:

docs: complete SRS Chapter 3

docs: update Vision v1.1

arch: define AI orchestration layer

feat: implement document ingestion

feat: add author profile service

fix: correct chunking pipeline

test: add integration tests for upload service

Avoid generic commit messages such as:

update

changes

fix

misc

---

## Pull Request Guidelines

Every pull request should explain:

* What changed.
* Why the change was necessary.
* Which requirement(s) it implements.
* Any architectural implications.

---

## Review Checklist

Before approving a contribution, verify:

* Documentation remains consistent.
* Requirements are satisfied.
* No undocumented functionality was introduced.
* Architecture remains modular.
* Code is maintainable.
* Tests exist where appropriate.

---

## Long-Term Goal

ScholarOS aims to become a maintainable, extensible research platform.

Every contribution should improve the quality, clarity, and longevity of the system.

Short-term convenience should never compromise long-term maintainability.

---

# Final Principle

Before changing the software, first understand the system.

> **Understand First. Build Second.**
