# Documentation Standards

**Document:** 09_Documentation_Standards.md

**Governance Framework:** Engineering Governance Framework v1.0

**Status:** Active

**Date:** 2026-07-29

**Authority:** Ninth, after AI Roles and Responsibilities (08).

---

## 1. Purpose

This document defines the formatting, structure, cross-referencing, and maintenance standards for all documentation within the ScholarOS repository.

All documentation, regardless of type or author, must conform to these standards.

---

## 2. Documentation Principles

- Documentation is treated as part of the product.
- Every implementation should leave the repository in a more understandable state than before.
- Avoid duplicated information. Prefer cross-references to duplication.
- Distinguish clearly between requirements, architecture, and implementation (per ADR-001).
- Use professional technical language.
- Be concise and unambiguous.

---

## 3. File Formatting Standards

### 3.1 Markdown

- All documentation files shall use Markdown (`.md`).
- Use ATX-style headers (`##`, `###`, etc.) with a space after the `#`.
- Use `---` horizontal rules to separate major document sections.
- Use tables for structured data where appropriate.
- Use fenced code blocks with language identifiers for code examples.

### 3.2 Naming and Metadata

Every document shall begin with a document header:

```md
# Document Title

**Document:** file_name.md

**Status:** [Draft | Active | Superseded]

**Date:** YYYY-MM-DD
```

Governance documents shall also include:

```md
**Governance Framework:** Engineering Governance Framework v1.0

**Authority:** [Position in hierarchy]
```

### 3.3 Section Structure

- Use `##` for top-level sections.
- Use `###` for subsections.
- Use `####` for sub-subsections (rarely needed).
- Each section should have a clear, descriptive heading.
- Avoid overly nested structures (prefer flatter hierarchies).

---

## 4. Cross-Referencing Standards

### 4.1 Internal Cross-References

- Cross-reference related documents using relative paths: `[description](path/to/file.md)`.
- When referencing a specific section, include the section name or number.
- When referencing a specific requirement, use its identifier: `FR-021`, `AIR-014`, `NFR-013`.
- When referencing an ADR, use its full title and number: `ADR-001: Separation of Requirements, Architecture, and Implementation`.

### 4.2 Cross-Reference Validation

- All cross-references must be validated when the target document is modified.
- Broken cross-references must be fixed immediately upon discovery.
- Cross-reference validation shall be part of the review process (07_Review_Checklist.md).

### 4.3 Avoiding Circular References

- Documentation should avoid circular cross-references where possible.
- If circular references are unavoidable, ensure they do not create logical contradictions.

---

## 5. Documentation Ownership

### 5.1 Ownership Model

- **SRS:** Owned by the Product Owner. Changes require architectural review.
- **Governance Framework:** Owned by the Lead Engineer. Changes require constitutional consistency check.
- **Architecture Documents:** Owned by the Lead Engineer. Changes require ADR if architecturally significant.
- **ADRs:** Owned by the project. Once accepted, they are permanent records.
- **Implementation Documentation:** Owned by the implementing engineer.

### 5.2 Documentation Maintenance

- Documentation is a living artifact. It shall be updated when requirements, architecture, or implementation change.
- Outdated documentation is considered technical debt.
- Documentation maintenance shall be tracked in the Journal.

---

## 6. Document Type Standards

### 6.1 SRS Chapters

- Must remain implementation-agnostic (per ADR-001).
- Must use requirement identifiers (FR, NFR, AIR, DR, WR, API).
- Must be traceable to the Vision Document.
- Each requirement shall have a unique identifier.

### 6.2 ADRs

- Must follow the structure defined in the existing ADR template (see ADR-001).
- Required sections: Title, Status, Date, Context, Problem Statement, Decision, Rationale, Consequences, Alternatives Considered, Future Considerations, References.
- Must be numbered sequentially (ADR-001, ADR-002, etc.).

### 6.3 Governance Documents

- Must include document header, purpose, and relationship table to other governance documents.
- Must be numbered sequentially (01_, 02_, etc.).
- Must cross-reference related governance documents.

### 6.4 README Files

- The root `docs/README.md` serves as the documentation index.
- Module-level README files shall explain purpose, setup, and usage.
- README files shall be updated when the documentation structure changes.

---

## 7. Language and Tone

- Use professional, technical language.
- Be concise. Prefer precise language over elaborate explanations.
- Use active voice where appropriate.
- Define acronyms on first use.
- Use consistent terminology across all documents.

---

## 8. Prohibited Documentation Practices

- Do not duplicate information already present in another document. Cross-reference instead.
- Do not include implementation details in requirements documents.
- Do not include requirements in implementation documentation.
- Do not use ambiguous language (e.g., "should probably", "might want to").
- Do not leave placeholder content (TBD, TODO) without documenting why and when it will be addressed.

---

## 9. Documentation Review

- All documentation changes shall be reviewed before acceptance.
- Review shall verify consistency with related documents.
- Review shall verify cross-reference validity.
- Review shall verify compliance with these standards.

---

## 10. Relationship to Other Governance Documents

| Document | Relationship |
|----------|-------------|
| 02_AI_Engineering_Contract.md | Documentation principles are defined in the Contract. |
| 03_AI_Engineering_Standards.md | Documentation quality expectations are defined in Standards. |
| 04_Repository_Governance.md | Naming conventions and file organization are defined in Governance. |
| 07_Review_Checklist.md | Documentation review is part of the review process. |

---

## 11. References

- 02_AI_Engineering_Contract.md — Section 10 (Documentation Principles)
- 03_AI_Engineering_Standards.md — Section 4 (Documentation Standards)
- 04_Repository_Governance.md — Section 3 (Naming Conventions)
- 07_Review_Checklist.md
- ADR-001: Separation of Requirements, Architecture, and Implementation
