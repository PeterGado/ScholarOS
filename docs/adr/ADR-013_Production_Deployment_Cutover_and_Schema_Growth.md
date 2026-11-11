# ADR-013: Production Deployment Cutover and Schema Growth Beyond the Corrected Baseline

**Status:** Accepted (retroactively — see Context)

**Date:** 2026-10-10 (written); the deployment cutover and schema additions happened progressively between approximately 2026-09-21 and 2026-10-09, with no contemporaneous ADR for any of it

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** Nothing is removed. This ADR records the realization of migration paths ADR-004 and ADR-007 already named as acceptable, formally decides one thing neither ADR anticipated by name (Row-Level Security and a restricted application role), and records schema growth beyond what ADR-009/010/012's corrections already captured. ADR-004 and ADR-007's MVP-stage decisions and rationale remain historically accurate for the stage they described and are not rewritten.

---

## Status

**Accepted, written retroactively.** Every fact this ADR records is already true of the running production system, verified directly against `backend/fly.toml`, the Alembic migration history, and the live SQLAlchemy models while writing [`docs/Technical_Design_Document.md`](../Technical_Design_Document.md) and [`docs/Backend_Schema_Reference.md`](../Backend_Schema_Reference.md) (2026-10-10) — both of which surfaced this gap directly: neither ADR-004 nor ADR-007 had been updated to reflect the cloud cutover, and ADR-007's own Decision item 5 had explicitly reserved a "future ADR" for multi-tenant isolation decisions that was never written when Row-Level Security shipped. This ADR is that correction and that future ADR, written after the fact because no one wrote either at the time — the same pattern, and the same honesty about it, as ADR-012.

---

## Context

[ADR-004 (Storage and Memory Strategy)](ADR-004_Storage_and_Memory_Strategy.md) specified SQLite for the MVP and named PostgreSQL as the migration path "when concurrent writers, multi-user access, or managed hosting demands... exceed SQLite," explicitly calling this "a configuration- and data-layer change, not an architecture change" (Decision item 2). It separately named a dedicated vector store (pgvector on PostgreSQL) as the migration path for the embedded MVP vector index "when index volume or concurrent query load requires it" (Decision item 3).

[ADR-007 (Deployment Strategy)](ADR-007_Deployment_Strategy.md) specified local-first single-node deployment for the MVP, with containerization as the committed cloud path (Decision item 3) and "managed services" at the cloud stage (Decision item 4). Its Decision item 5 is explicit: *"Multi-tenant stage: platform isolation. SaaS-stage tenancy... introduces per-tenant isolation decisions that will be recorded in a future ADR."*

Both migrations anticipated by ADR-004 have since happened: production now runs on Neon-hosted PostgreSQL, and object storage already migrated to an S3-compatible backend (resolved and recorded 2026-09-18, per [`docs/Project_Status.md`](../Project_Status.md)'s Risks table — not re-decided here). The deployment topology anticipated by ADR-007 has also happened: the backend runs as a containerized service on Fly.io, the frontend is deployed to Vercel. None of this used to be recorded with the specific vendor names, nor was it corrected into either ADR.

Separately, and not anticipated by either ADR: the Postgres cutover brought Row-Level Security, enforced via a restricted, non-superuser application database role — exactly the shape of "per-tenant isolation decision" ADR-007 Decision item 5 said would get a future ADR. It never did, until now.

Separately again: the live schema has grown several tables and columns past what ADR-009, ADR-010, and ADR-012's corrections already recorded, with no ADR or baseline correction covering any of it — confirmed by direct inspection of `backend/app/**/infrastructure/models.py`, `backend/app/database/shared_models.py`, `backend/app/auth/models.py`, `backend/app/workers/models.py`, `backend/app/ai/models.py`, `backend/app/core/rate_limit_models.py`, and all 14 Alembic revisions, while writing [`docs/Backend_Schema_Reference.md`](../Backend_Schema_Reference.md).

---

## Problem

How should the real, already-live production deployment topology, the Row-Level Security mechanism it introduced, and the schema growth that accompanied it be formally reconciled with the frozen Architecture Baseline v1 and Database Baseline v1, so that:

1. The baselines accurately reflect what the system actually runs as, not the MVP stage either baseline described at freeze time;
2. Row-Level Security — a genuine, security-relevant architectural decision — gets the dedicated decision record ADR-007 Decision item 5 itself said it would need, rather than existing only as inline code comments and migration names;
3. The schema growth is formally acknowledged in one place rather than left to accumulate indefinitely across undocumented commits;
4. The correction follows the same governance discipline ADR-009, ADR-010, and ADR-012 already established (`04_Repository_Governance.md` §4.4): frozen baselines are corrected, not rewritten, with the correction recorded as a new ADR plus a numbered addition to the relevant `08`-series review document.

---

## Decision

1. **The structured core now runs on Neon-hosted PostgreSQL in production**, with SQLite retained for local development and tests. This is not a new decision — it is the realization of the migration path ADR-004 Decision item 2 already named and pre-authorized. SQLite's own operational limits (confirmed in real use, not hypothetically: see [`docs/Project_Status.md`](../Project_Status.md)'s dated note on the single-writer ceiling being reachable within a single user's own session) are exactly the condition ADR-004 said would trigger this migration.

2. **Production deployment topology is Fly.io (backend, containerized, a single machine) + Vercel (frontend) + Neon (PostgreSQL)**, recorded here by name for the first time. This realizes ADR-007 Decision item 4's "cloud stage: managed services" in the specific form actually chosen. The backend machine is deliberately kept at exactly one (`fly.toml`: `min_machines_running = 1`, `auto_stop_machines = "off"`) because the in-process Work Item executor (ADR-006) must keep polling continuously — this single-machine constraint is itself the subject of a separate, already-flagged future item (see Future Considerations).

3. **Row-Level Security, enforced via a restricted application database role, is adopted as the per-tenant data-isolation mechanism** — the decision ADR-007 Decision item 5 reserved for a future ADR. Specifically:
   - Every tenant-owned table carries a Postgres RLS policy whose `USING`/`WITH CHECK` condition walks that table's real foreign-key chain back to `agents.user_id`, resolved via a `app_current_user_id()` SQL function reading a per-transaction Postgres session variable that `app/database/session.py` sets from the already-resolved authenticated identity. An unset session variable resolves to `NULL`, and `column = NULL` is always false — every policy fails closed.
   - The running application connects as `scholaros_app`, a role created specifically for this purpose with `NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE` and CRUD-only grants — not the table-owner role Alembic migrations run as. `FORCE ROW LEVEL SECURITY` is additionally set on every protected table as defense against future role/ownership drift.
   - This is deliberately a **second, independent enforcement layer** on top of application-level ownership checks already in place (every Writing read/write use case verifies `agent.user_id == user_id` before touching data) — not a replacement for them.
   - Sixteen tables are protected; `users` (the ownership root), `sessions`/`password_reset_tokens`/`email_verification_tokens` (looked up by secret token hash before any `user_id` is known — RLS would create a chicken-and-egg problem on the first query of a request), `work_items` (no FK to anything), and `rate_limit_counters` (not user content) are deliberately excluded, each for the stated reason.
   - The background Work Item executor (ADR-006) connects through a separate, unrestricted engine, outside RLS — a considered tradeoff, not an oversight, recorded fully in [`docs/Technical_Design_Document.md`](../Technical_Design_Document.md) §10 item 4, including the real 2026-09-30 production outage this tradeoff's initial implementation caused before the dedicated worker engine existed.

4. **The vector index has not yet migrated to the dedicated vector store ADR-004 Decision item 3 named as its path.** Embeddings remain a JSON-encoded float list in an ordinary Postgres column (`knowledge_chunk_embeddings.embedding_vector`), with similarity computed in application code — functionally equivalent to the MVP's embedded-index decision, not yet the pgvector migration. This is recorded explicitly as **not done**, to prevent the Postgres cutover from being mistaken for the vector-store migration too.

5. **The following schema growth, beyond what ADR-009/010/012's corrections already cover, is formally acknowledged as additive evolution, not a redesign** (per [`08_Database_Design_Review_and_Readiness_Assessment.md`](../database/08_Database_Design_Review_and_Readiness_Assessment.md) §11's own "deferred decisions are additive, not a redesign" framing, already established for exactly this kind of growth):
   - `User` gained `email`, `email_verified`, and `google_subject` — the schema-level consequence of ADR-011's email-based registration, Google Sign-In, password reset, and email verification being built out beyond what ADR-011 itself described in detail.
   - `ResearchDocument` gained `publication_year`, `doi`, `doi_verification_status`, and `purpose` (distinguishing a research source from a writing-style sample).
   - Five new tables with no prior baseline entity: `writing_segments` (a named, reusable part of a project with its own saved writing instructions), `password_reset_tokens`, `email_verification_tokens`, `ai_usage_records` (a per-user AI usage ledger), and `rate_limit_counters` (the rate limiter's backing store, replacing an in-memory default so limits survive a redeploy).
   - None of these required a redesign of any frozen entity; all are additive columns or new, independent tables. Full current detail — not reproduced here — is in [`docs/Backend_Schema_Reference.md`](../Backend_Schema_Reference.md) §2–§3.

---

## Rationale

* **Items 1–2 are not really decisions being made here — they are decisions ADR-004 and ADR-007 already made, being recorded as realized.** This ADR's job for those items is closing the gap between "named as an acceptable future path" and "actually happened, with no record of when or how," not re-litigating whether to do them.
* **Row-Level Security deserves its own decision record on the merits, independent of how late it is**, because it is a genuine security-architecture choice — a second enforcement layer, a new restricted role, an explicit set of exclusions with reasons — exactly the kind of thing ADR-007 Decision item 5 itself predicted would need one.
* **Schema growth is recorded in aggregate, not as five separate ADRs**, following the same discipline ADR-011 and ADR-012 already established: an additive column or an independent new table, built in an existing module's already-proven shape, does not need its own architecturally-significant decision record — a periodic correction pass recording the accumulated growth is proportionate, a new ADR per column is not.
* **Writing this retroactively is strictly better than leaving ADR-007 Decision item 5's promise unfulfilled indefinitely** — the same reasoning ADR-012's own Rationale gives for itself.

---

## Alternatives Considered

### Alternative 1: Rely on `docs/Technical_Design_Document.md` and `docs/Backend_Schema_Reference.md` as the record, without a correcting ADR

**Rejected because:** both are synthesis references, explicitly scoped (per their own Purpose sections) as practical companions to the authoritative baselines, not as decision records themselves, and not discoverable from `docs/Baseline_Register.md`'s change-path column the way an ADR is. Same reasoning as ADR-012's own Alternative 1.

### Alternative 2: Write two separate ADRs — one for the deployment/RLS topic, one for schema growth

**Considered, rejected because:** both are symptoms of the same underlying gap (production reality left the frozen baselines behind, uncorrected, for the same stretch of uncommitted/unjournaled work this project's own journaling gap note already flags), and both are being corrected in the same pass for the same reason. Splitting them would fragment one coherent correction into two without a real boundary between them — RLS itself is as much a schema-level fact (policies, a new role, `FORCE ROW LEVEL SECURITY` migrations) as it is a deployment-level one.

### Alternative 3: Rewrite ADR-004 and ADR-007's Decision sections in place to describe the cloud stage as current

**Rejected because:** this project's own frozen-document discipline (`04_Repository_Governance.md` §4.4) is explicit that ADRs, once accepted, are permanent records — corrected via a new ADR and cross-reference, never rewritten. ADR-004 and ADR-007's MVP-stage text remains an accurate historical record of the MVP-stage decision; this ADR is the record of what happened next, exactly the same relationship ADR-009/010/012 have to the Database Baseline they correct.

---

## Consequences

### Positive

* ADR-007 Decision item 5's promised "future ADR" for multi-tenant/per-tenant isolation now exists.
* The production deployment topology (Fly.io/Vercel/Neon) and the RLS mechanism have a single, discoverable decision record, cross-referenced from the baselines they touch.
* Schema growth that had been silently accumulating across five tables and seven columns is now formally acknowledged in one place.

### Negative

* As with ADR-011 and ADR-012, this records decisions already live in production — the project's own discipline (ADR before implementation) was not followed for any of this, and this ADR is a repair, not prevention. This is the third ADR in this repository's history with that same shape.
* The pgvector migration ADR-004 named is still not done (Decision item 4) — recording that honestly here is a negative consequence of looking closely, not a new problem created by this ADR.

### Neutral

* No code change results from this ADR — every fact recorded here is already true of the running system, verified independently while writing the Technical Design Document and Backend Schema Reference.

---

## Repository Impact

* `docs/adr/ADR-004_Storage_and_Memory_Strategy.md`, `docs/adr/ADR-007_Deployment_Strategy.md`: cross-reference additions only, noting this ADR as the realization/multi-tenant-isolation record their own Decision items anticipated. Decision text not rewritten.
* `docs/Baseline_Register.md`: new correction line for Architecture Baseline v1, following the same pattern already used for its ADR-009/010 corrections and the Database Baseline's ADR-009/010/012 corrections.
* `docs/database/08_Database_Design_Review_and_Readiness_Assessment.md`: new addendum section recording the schema-growth portion of this correction, following the `§23`/`§24`/`§25` pattern.
* `docs/Technical_Design_Document.md`, `docs/Backend_Schema_Reference.md`: already correctly describe the current state independently verified against code; cross-referenced here as the detailed record, not duplicated.
* `docs/READme.md`, `docs/Project_Status.md`: cross-reference additions for ADR-013.

---

## AI Engineering Implications

* No application code changes result from this ADR.
* The stateless/multi-server architecture work already recorded as a medium-term item in [`docs/roadmaps/Engineering_Plan.md`](../roadmaps/Engineering_Plan.md) will change the single-machine fact Decision item 2 just recorded as current reality — that work should get its own ADR before implementation, not after, learning the lesson ADR-012's Future Considerations already states once.
* Any future schema addition of comparable scale (a new table, or several new columns on an existing entity) should be captured in the next periodic baseline-correction pass rather than left to accumulate indefinitely — the same discipline this ADR itself applies retroactively.

---

## Compliance Rules

* Production deployment-topology changes (provider, region, single- vs. multi-machine) should update this ADR's realization record or be recorded in a superseding ADR, not left implicit in `fly.toml` alone.
* Any future per-tenant isolation mechanism change (RLS policy shape, the restricted role's grants, which tables are protected) should be treated as touching this ADR's Decision item 3, not as a routine migration.

---

## Related ADRs

| ADR | Relationship |
|---|---|
| ADR-004 (Storage and Memory Strategy) | Decision items 1–2 here realize its Decision items 1–2; Decision item 4 here explicitly records its Decision item 3 (pgvector) as not yet done. |
| ADR-005 (Retrieval and Search Strategy) | The embedded vector index Decision item 4 describes is the same one ADR-005's hybrid retrieval already operates over; unaffected in substance. |
| ADR-006 (Async Processing and Event Coordination) | The single-machine constraint Decision item 2 records as current reality is a direct consequence of ADR-006's in-process executor design. |
| ADR-007 (Deployment Strategy) | Decision items 2–3 here realize its Decision items 3–4; Decision item 3 here is the "future ADR" its own Decision item 5 reserved. |
| ADR-009, ADR-010, ADR-012 | Precedent for this correction's governance shape (ADR + baseline correction, frozen documents not rewritten) and, for ADR-012 specifically, precedent for a retroactive ADR recording a decision already live before it was written down. |

---

## Future Considerations

* **The pgvector migration ADR-004 named remains open** — worth revisiting as the chunk corpus grows past what an application-computed cosine-similarity scan over a JSON column comfortably serves.
* **The single-machine constraint Decision item 2 records is the next thing expected to change** — stateless, multi-server operation is already the top medium-term item in `docs/roadmaps/Engineering_Plan.md`, and per this ADR's own AI Engineering Implications, that work should get its own ADR before implementation.
* **External uptime monitoring for `/health/queue`** (also recorded in the Engineering Plan) is a smaller, related gap: the in-process `QueueHealthMonitor` this project added alongside this ADR can only ever detect "alive but stuck," never "process died outright" — only genuine external polling closes that.

---

## References

* `docs/Technical_Design_Document.md` — the verified-against-code system reference this ADR's deployment/executor facts are drawn from.
* `docs/Backend_Schema_Reference.md` §2, §6, §7 — the verified-against-code schema-growth and RLS detail this ADR's Decision items 3 and 5 are drawn from.
* `docs/Project_Status.md` — the 2026-10-09 dated entry recording the cutover's completion, and the Risks table entry on SQLite's single-writer ceiling that motivated it.
* `docs/roadmaps/Engineering_Plan.md` — the forward-looking items this ADR's Future Considerations cross-reference.
* `backend/fly.toml`, `backend/alembic/versions/cff25673e0e3_add_row_level_security_policies.py`, `backend/alembic/versions/2e1d18abf226_create_scholaros_app_restricted_role.py`, `backend/alembic/versions/c65baaf64ccf_force_row_level_security.py` — the primary-source configuration and migrations this ADR's Decision items 2–3 describe.
