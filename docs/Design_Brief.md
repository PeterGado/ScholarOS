# Design Brief

**Document:** Design_Brief.md

**Status:** Active

**Date:** 2026-10-10

---

## 1. Purpose

This brief describes the design language ScholarOS already uses — in product copy, visual system, and UI pattern — grounded in the shipped frontend code, not in aspiration. It synthesizes product-level tone and principles from the [Vision Document](vision/Vision.md) with what is actually implemented in `frontend/src`. For functional requirements, see the [Product Requirements Document](Product_Requirements_Document.md); for implementation detail, read the referenced source files directly.

---

## 2. Brand Identity

**Name:** ScholarOS. **Tagline:** "Research. Reason. Write." (Vision §0; repeated verbatim on the [landing page](../frontend/src/pages/LandingPage.tsx)).

**One-line positioning**, from the landing hero copy itself:

> "An intelligent research operating system for academic writing... Upload your sources and style, and ScholarOS grounds every draft in them, so the writing stays provably yours."

**Voice**, from the same page and `index.html`'s meta description: direct, concrete, confidence without hype. It describes what the system does ("reads your research documents and writing style," "real citations grounded in the evidence you actually uploaded") rather than making unverifiable superlative claims. The closing line on the landing page states the product's relationship to the user plainly: *"ScholarOS doesn't replace the researcher — it amplifies your thinking and cuts the repetitive work, while keeping the writing genuinely yours."* This is a direct restatement of Vision §2 ("amplify their thinking, reduce repetitive work") in product copy, not a separate claim.

---

## 3. Target User and Mental Model

Per [Vision §9](vision/Vision.md#9-target-users) and SRS Chapter 2 §6: professional academic writers, undergraduate/master's/doctoral students, and independent researchers, in a personal (not institutional) research context.

**Mental model the UI assumes:** one Agent, one project, one knowledge base. ADR-009's one-Agent-per-user model is not just a backend constraint — it shapes navigation: there is no project picker or workspace switcher anywhere in the shipped frontend, because there is exactly one workspace to be in. The user's mental model is "my Agent," not "a project among several." The chat input placeholder is literal about this: *"Message your Agent Workspace..."* (`ChatDetailPage.tsx`).

The product is explicitly **not** a general chatbot in the user's mental model, even though its primary interaction surface is chat (see §6). The distinguishing idea, carried through copy and UI alike, is **groundedness**: every answer and draft is traceable to documents the user themselves uploaded, with visible evidence (search results, DOI verification badges, citation completeness) rather than an opaque black box.

**Gap:** no user personas, journey maps, or usability research exist anywhere in the repository. This section describes the user the product's copy and structure *imply*, not a researched persona set — treat accordingly.

---

## 4. Core Design Principles

Synthesized from the Vision Document's product philosophy and the patterns actually implemented in the frontend:

1. **Grounded, not generic.** Every feature-level claim on the landing page pairs a capability with evidence of groundedness ("grounded retrieval," "evidence pulled in at the right moment," DOI verification badges on `DocumentsPage`). This operationalizes Vision §6.2 (Evidence Before Opinion) as a visible UI property, not just a backend guarantee.
2. **Understand before generate, reflected in product structure.** The frontend's own navigation groups — Documents, Writing Style, Memory, before Chat — mirror the Vision's "Understand First, Write Second" sequence (Vision §5) at the level of information architecture, not just backend processing order.
3. **The researcher stays in control.** No content auto-publishes. Documents must finish processing before becoming part of the knowledge base; failed items get an explicit Retry action rather than silent disappearance; a failed chat reply surfaces an error with a Retry button instead of hanging indefinitely (`ChatDetailPage.tsx`). This operationalizes Vision §6.6 (Human Oversight).
4. **Calm, utilitarian minimalism.** The UI is built from a small, consistent shadcn-style component set (`Button`, `Card`, `Badge`, `Alert`, `Skeleton`, `EmptyState`) with no decorative chrome. The landing page's only illustrative graphic is a CSS-only abstract composition of three layered panels — explicitly not a product screenshot or stock photo (see the code comment in `LandingPage.tsx`).
5. **Transparent system state, never silent failure.** Document processing exposes real states (`pending` / `processing` / `processed` / `failed`) as visible badges; a chat reply in flight shows a `ThinkingIndicator` and survives page reloads by resuming from its real backend status rather than guessing from a timeout. Every mutation that can fail renders its own error state with a recovery action.
6. **Accessibility and reduced-motion as defaults, not an afterthought.** Every color pair in `index.css` is annotated with its actual measured WCAG contrast ratio (not just an OKLCH lightness assumption); `prefers-reduced-motion` is explicitly honored; form labels were audited and fixed for screen-reader association (see the dated audit comments in `DocumentsPage.tsx` and `index.css`, 2026-10-09).

---

## 5. Visual Language

**Color system** — "Deep Navy + Warm Ivory + Teal," defined in `frontend/src/index.css`, computed via sRGB → OKLab → OKLCH (not approximated) with per-pair contrast checked against real WCAG math:

| Role | Light value | Use |
|---|---|---|
| Background | `#FAFAF7` Warm Ivory | Page background |
| Foreground | `#172033` Ink | Primary text (15.6:1 on background) |
| Primary | `#172554` Deep Navy | Primary actions, sidebar chrome |
| Accent | `#0F766E` Scholarly Teal | Reserved specifically for "AI actions/highlights" per the code's own comment |
| Secondary | `#CCFBF1` Soft Teal | Secondary surfaces |
| Destructive / Success / Warning | Red `#B91C1C` / Green `#15803D` / Amber `#B45309` | Semantic status only |

Every token has a dark-mode counterpart in the same file, independently contrast-checked rather than mechanically inverted — several dark-mode status colors deliberately switch to dark-ink text instead of white because white fails AA against the brightened tone.

**Typography:** Geist Variable (`@fontsource-variable/geist`), sans-serif throughout; no separate display or serif face.

**Shape:** a three-step radius scale, applied consistently and without exception per the code's own comment — controls use `rounded-lg` (10px), containers use `rounded-xl` (14px), pills use `rounded-full`.

**Components:** a shadcn/ui-derived primitive set (Tailwind CSS v4) — `Button`, `Card`, `Input`, `Textarea`, `Badge`, `Alert`, `Skeleton`, `EmptyState` — used uniformly across pages rather than page-specific one-off styling.

---

## 6. UI Patterns in Practice

- **Chat as the primary writing surface** (`ChatDetailPage.tsx`): full-width alternating message rows styled after familiar AI-chat products (the code's own comment names Claude/ChatGPT as the reference pattern), an auto-growing input pinned to the bottom, Enter to send. Reply completion is observed by polling the reply's real backend Work Item status rather than a fixed timeout, and an in-flight reply survives a reload.
- **Documents as a staged workflow, not a flat file list** (`DocumentsPage.tsx`): uploaded documents appear in a pending/processing queue with visible status badges and a Retry action on failure; once processed, a document moves to a separate read-only "Processed documents" section and becomes searchable, communicating that it is now part of the knowledge base rather than a manageable file.
- **Landing page structure**: header (logo + theme toggle + auth actions) → hero (tagline, headline, value-prop copy, CTA, abstract graphic) → three-column feature grid → one-line product-philosophy statement → footer (Privacy/Terms). No pricing, testimonials, or social proof sections exist — consistent with this being a personal-MVP-stage product, not a marketing site for a commercial launch.

---

## 7. Tone and Copy Voice

Copy throughout favors concrete, falsifiable statements over marketing abstraction: "not just a pile of PDFs," "provably yours," "real, grounded citations." The product explicitly declines to call itself an AI chatbot in its own framing (Vision §8) even though chat is its primary interface — copy consistently frames the chat surface as "your Agent," grounded in your sources, rather than as a general-purpose assistant.

---

## 8. What This Brief Does Not Cover

- **No standalone design-system document, brand guideline, or Figma file exists in the repository.** This brief is derived entirely from `frontend/src/index.css`, the component library, and page-level code — there is no separate design spec to cross-reference for additional detail beyond what is cited above.
- **No user research, personas, or usability testing documentation exists.** §3's target-user description is inferred from the Vision Document's stated target users and the UI's own structure, not from research.
- **No formal accessibility audit report exists as a standalone document** — the accessibility fixes cited in §4 are known only from inline code comments dated to specific audit passes (e.g., 2026-10-09), not from a published audit artifact.

---

## 9. References

- [Vision Document](vision/Vision.md) — product philosophy, principles, target users
- [Product Requirements Document](Product_Requirements_Document.md) — functional scope and current state
- `frontend/src/pages/LandingPage.tsx` — value-proposition copy and page structure
- `frontend/src/pages/ChatDetailPage.tsx` — primary chat interaction pattern
- `frontend/src/pages/DocumentsPage.tsx` — document workflow and status pattern
- `frontend/src/index.css` — color system, typography, radius scale, accessibility defaults
- `frontend/index.html` — meta description and social-share copy
