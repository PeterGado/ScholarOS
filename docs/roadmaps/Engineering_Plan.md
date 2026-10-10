# Engineering Plan

**Document:** Engineering_Plan.md

**Status:** Active

**Date:** 2026-10-10

---

## 1. Purpose

This document is a forward-looking engineering plan: what is actually outstanding, grounded in [`docs/Project_Status.md`](../Project_Status.md)'s recorded current state, the repository's own flagged risks and open items, and the directional phases already recorded in [`docs/srs/11_Future_Roadmap.md`](../srs/11_Future_Roadmap.md). It is new content — `docs/roadmaps/` previously held no files.

Per [`09_Documentation_Standards.md`](../governance/09_Documentation_Standards.md), this plan cross-references rather than restates its sources. Every item below cites the specific document (and, where applicable, section or risk-table row) it is grounded in. Items are organized by horizon — **near-term** (the next few weeks), **medium-term** (the next one to two quarters), and **longer-term** (the SRS's own post-MVP phases) — not by priority within a horizon.

This plan does not itself authorize any of the work it describes. Per `docs/Project_Status.md`'s own "Immediate Next Steps" item 10, no next milestone is automatically implied; starting any item below still requires the same explicit authorization every prior milestone in this repository has required.

---

## 2. Near-Term (Next Few Weeks)

### 2.1 Land the in-progress Queue Health Monitor

As of this writing, `backend/app/workers/health.py` (a new `QueueHealthMonitor` and a shared `check_queue_health` helper), the corresponding edit to `backend/app/api/routes/health.py`, the wiring in `backend/app/main.py`'s lifespan, and new unit/integration tests are present in the working tree but **not yet committed**. The code's own docstring (dated 2026-10-10) frames this as closing a specific, previously-reported gap: the 2026-09-30 "stuck on Thinking" outage, where the web server kept answering `/health` while the Work Item executor had silently stopped making progress. This is the most immediate, concrete outstanding item — finish review, run the full suite, and commit it.

**Grounded in:** current git working-tree state (uncommitted files) and the dated docstrings inside `backend/app/workers/health.py` and `backend/app/main.py` themselves.

### 2.2 Correct the stale Draft/Review crash-window Risk entry

`docs/Project_Status.md`'s Risks table still carries an entry — "Async draft generation (Project Writing Stage 6) has a crash-window gap... `GenerateDraftVersionUseCase` commits but before the Work Item success marker commits..." — that describes a use case belonging to the Draft/Review pipeline [ADR-012](../adr/ADR-012_Chat_Memory_Model_Replaces_Draft_Review_Pipeline.md) formally removed. This entry was not updated when ADR-012 was written and is now misleading to a reader who has not also read ADR-012. The more general form of the same concern (a crashed Work Item of any kind) is already mitigated by `WorkItemRepository.requeue_stale_running`, per `docs/Project_Status.md`'s "Immediate Next Steps" item 3 — but the stale Risk-table row itself still needs a correction pass, in the same spirit as the opportunistic-correction discipline ADR-012 itself establishes.

**Grounded in:** direct contradiction between `docs/Project_Status.md`'s Risks table and ADR-012's Decision/Repository Impact sections (found during this plan's own research pass).

### 2.3 Complete the Draft/Review reference cleanup ADR-012 deliberately deferred

ADR-012's Decision item 6 and its "Future Considerations" section both explicitly flag that `02_Domain_Model.md`, `03_Conceptual_Data_Model.md`, and `05_Constraints_and_Integrity.md` still contain inline Draft/Review references the correction pass did not reach, with the precise list left in `docs/database/08_Database_Design_Review_and_Readiness_Assessment.md` §25. This is documentation debt with an already-written follow-up list — a good candidate for an "opportunistic" pass per ADR-012's own AI Engineering Implications.

**Grounded in:** ADR-012, Decision item 6 and Future Considerations; `08_Database_Design_Review_and_Readiness_Assessment.md` §25 (referenced, not duplicated here).

### 2.4 Close the human (non-AI) review of Database Baseline v1

`docs/Project_Status.md`'s Risks table lists "No formal human (non-AI) review of Database Baseline v1 yet" as open, and "Immediate Next Steps" item 8 confirms prep materials are already written (`docs/Database_Human_Review_Materials.md`) but the review itself "needs the project owner, not something an AI session can complete." This is a scheduling/ownership item, not an engineering task — it is listed here because it remains the single most-cited open item in the project's own status record.

**Grounded in:** `docs/Project_Status.md`, Risks table and "Immediate Next Steps" item 8.

### 2.5 Two small, explicitly non-blocking cleanups

- Document `format`'s accepted values above the implementation layer — flagged as still open in `docs/Project_Status.md`'s "Immediate Next Steps" item 9 (originally surfaced as an open item back in Stage 3 of Milestone 6).
- The pre-existing `agent`/`document`/`knowledge` modules' `Enum` columns store each Python enum member's `.name`, not its documented `.value` — flagged as harmless today (nothing reads the raw column outside the ORM) in "Immediate Next Steps" item 6, left open "for whenever the project owner wants them addressed."

**Grounded in:** `docs/Project_Status.md`, "Immediate Next Steps" items 6 and 9.

---

## 3. Medium-Term (Next One to Two Quarters)

### 3.1 Move off a single-machine architecture — statelessness and multi-server capability

The project owner has directly flagged, separately from this plan's source documents, wanting the application made stateless and able to run across multiple servers rather than a single machine. This is not yet recorded as a planned item anywhere else in the repository as of this writing, so it is recorded here for the first time, grounded in that direct instruction rather than in a pre-existing document. It connects to two things the repository *does* already document:

- The 2026-09-30 outage that motivated Section 2.1's Queue Health Monitor is a direct symptom of single-machine risk: one process running the web server and the Work Item executor together means a stuck executor degrades the whole deployment with no redundancy. `QueueHealthMonitor`'s own docstring names the residual gap plainly: "If the whole process dies, nothing inside it can report that — genuine external uptime monitoring... is still the only way to catch that case, and remains a real, separate gap." A multi-server design is the structural fix section 2.1 only detects around.
- `docs/Project_Status.md`'s Risks table previously flagged SQLite's single-writer ceiling as reachable within a single user's single session (not only at a hypothetical future multi-user stage), mitigated with transaction demarcation, WAL mode, and best-effort writes, but noted as needing either a serialized-write strategy or the Postgres migration "ADR-004 already names" for full elimination. The Postgres/Neon cutover has since happened (`docs/Project_Status.md`'s 2026-10-09 dated note), which likely resolves the original SQLite-specific concern — but that resolution has not been explicitly confirmed against this specific risk entry, and moving to multiple application servers reopens the general question of concurrent-write and session-consistency behavior under Postgres with multiple backend processes, which has not yet been exercised.

This is the largest architectural item in this plan. It should start with an ADR, per ADR-012's own stated lesson ("any future removal of a previously-frozen entity should get an ADR before implementation, not after") and per the project's standing discipline that architecturally significant changes require one before implementation — this item is exactly that scale of change to the deployment architecture.

**Grounded in:** direct project-owner instruction (not yet recorded elsewhere in the repository); `backend/app/workers/health.py`'s own docstring naming the residual single-process gap; `docs/Project_Status.md`'s Risks table entry on SQLite's single-writer ceiling and its own note that full elimination needs either a serialized-write strategy or the Postgres migration.

### 3.2 External uptime monitoring for `/health/queue`

`QueueHealthMonitor`'s docstring is explicit that its in-process self-check "can only ever observe 'the process is alive but the queue isn't moving'" — it cannot detect the process dying outright, and genuine external polling of `/health/queue` "remains a real, separate gap," deliberately not wired into Fly's own machine health check (reasoned through in the same docstring: an unhealthy queue does not mean a restart would help). Standing up that external monitor is a natural, smaller companion to Section 3.1, and does not require the larger multi-server redesign to be useful on its own.

**Grounded in:** `backend/app/workers/health.py`, `QueueHealthMonitor` class docstring.

### 3.3 Revisit Work Item retry idempotency as redundancy increases

`WorkItemRepository.requeue_stale_running` (per `docs/Project_Status.md`'s "Immediate Next Steps" item 3) recovers any Work Item left stuck `RUNNING` by a crashed prior process, as a general, kind-agnostic worker concern. This is sufficient for a single executor process. If Section 3.1's multi-server work introduces multiple concurrent executor processes, the retry/idempotency guarantees that currently rely on there being exactly one executor should be re-examined before that change ships — this is called out explicitly so it is not silently assumed to still hold.

**Grounded in:** `docs/Project_Status.md`, "Immediate Next Steps" item 3; reasoned dependency on Section 3.1 above.

### 3.4 Retrieval quality: fusion-weight tuning and reranking

`docs/Project_Status.md`'s Risks table records two retrieval-quality items as deliberately deferred once ADR-005's hybrid (lexical + semantic) retrieval was fully realized on 2026-09-18: per-retrieval-context fusion-weight tuning (ADR-005 Future Considerations #3) and reranking (ADR-005 Decision 4). Both were deferred because "only one real retrieval context exists" at the time — revisit once there is enough real usage to tune against.

**Grounded in:** `docs/Project_Status.md`, Risks table (the resolved hybrid-retrieval entry's own trailing note).

### 3.5 Decide the fate of the 6 manual-only e2e specs

Per `docs/Project_Status.md`'s 2026-10-09 dated note, CI gained a hermetic Playwright `e2e` job covering 2 of the 8 specs under `frontend/e2e/` against a real backend; "the other 6 need a real AI provider and stay manual-only." Deciding whether and how to bring those into CI (a sandboxed/mocked AI provider key, a scheduled rather than per-PR run, or an accepted permanent manual-only status) is a concrete, scoped medium-term item.

**Grounded in:** `docs/Project_Status.md`, 2026-10-09 dated update note.

---

## 4. Longer-Term (Post-MVP Roadmap)

[`docs/srs/11_Future_Roadmap.md`](../srs/11_Future_Roadmap.md) already records the project's longer-range direction as six post-MVP phases, explicitly as "intended direction, not committed delivery" (§7) subject to the standard SRS amendment and architectural review process before any item is implemented (RDM-008). This plan does not restate that chapter's content; it only notes where the current, actually-shipped state already overlaps it, so the roadmap is read against reality rather than against the MVP baseline it was originally written against:

- **Phase 4 (Collaborative Research)** lists "Security and authentication architecture must be established for multi-user support" as a dependency. Multi-user self-service registration, Google OIDC sign-in, email verification, and password reset are now live (per ADR-011 and `docs/Project_Status.md`'s 2026-10-09 note) — meaning Phase 4's stated authentication dependency is substantially further along than `11_Future_Roadmap.md`'s original MVP-era framing assumed. Phase 4's own remaining capabilities (supervisor review workflows, co-author collaboration, role-based access, shared knowledge bases) remain undelivered and still require their own SRS amendment and ADR before implementation, per RDM-008/RDM-010.
- **Phase 2 (Expanded Drafting)**, as written, assumes the Draft/Review pipeline's vocabulary (full-chapter generation building on draft structuring). Any future work toward this phase should be re-scoped against the real chat/memory model (per ADR-012) before being treated as actionable, rather than assumed to extend a pipeline that no longer exists.
- **Phases 3, 5, 6, and 7** (Advanced Knowledge Management, Extended Research Lifecycle, Institutional/Commercial Readiness, Advanced Intelligence) remain unstarted, exactly as `11_Future_Roadmap.md` describes them. They are not restated here; see that chapter directly.

No item in this section is treated as authorized or scheduled — per RDM-008, each would need its own SRS amendment and architectural review before implementation, independent of this plan.

---

## 5. Summary Table

| Horizon | Item | Primary Source |
| ------- | ---- | --------------- |
| Near-term | Land the uncommitted Queue Health Monitor | Working-tree state; `backend/app/workers/health.py` |
| Near-term | Correct the stale Draft/Review Risk-table entry | `docs/Project_Status.md` Risks table vs. ADR-012 |
| Near-term | Finish the ADR-012-deferred `02`/`03`/`05` reference cleanup | ADR-012 Decision item 6; `08` §25 |
| Near-term | Close the human L3 review of Database Baseline v1 | `docs/Project_Status.md`, "Immediate Next Steps" item 8 |
| Near-term | Document `format`'s accepted values; fix Enum `.name`/`.value` debt | `docs/Project_Status.md`, items 9 and 6 |
| Medium-term | Stateless, multi-server architecture | Direct project-owner instruction; `backend/app/workers/health.py` docstring |
| Medium-term | External uptime monitoring for `/health/queue` | `backend/app/workers/health.py`, `QueueHealthMonitor` docstring |
| Medium-term | Re-examine Work Item retry idempotency under multiple executors | `docs/Project_Status.md` item 3; dependency on multi-server work |
| Medium-term | Retrieval fusion-weight tuning and reranking | `docs/Project_Status.md` Risks table (ADR-005 deferred items) |
| Medium-term | Decide the fate of the 6 manual-only e2e specs | `docs/Project_Status.md`, 2026-10-09 note |
| Longer-term | Post-MVP Phases 2–7 | `docs/srs/11_Future_Roadmap.md` |

---

## 6. References

- [`docs/Project_Status.md`](../Project_Status.md) — the current-state record this plan's near- and medium-term sections are grounded in.
- [`docs/srs/11_Future_Roadmap.md`](../srs/11_Future_Roadmap.md) — the longer-term phases referenced in Section 4.
- [`docs/adr/ADR-012_Chat_Memory_Model_Replaces_Draft_Review_Pipeline.md`](../adr/ADR-012_Chat_Memory_Model_Replaces_Draft_Review_Pipeline.md) — source for Sections 2.2, 2.3, and 4's Phase 2 note.
- [`docs/database/08_Database_Design_Review_and_Readiness_Assessment.md`](../database/08_Database_Design_Review_and_Readiness_Assessment.md) §25 — the specific follow-up list referenced in Section 2.3.
- [`docs/Database_Human_Review_Materials.md`](../Database_Human_Review_Materials.md) — referenced in Section 2.4.
- `backend/app/workers/health.py`, `backend/app/main.py` — source for Sections 2.1, 3.1, and 3.2.
- [`docs/User_Flow_Diagrams.md`](../User_Flow_Diagrams.md) — companion document showing the current, as-implemented flows this plan's near-term items maintain.
