# Backend Schema Reference

**Document:** Backend_Schema_Reference.md

**Status:** Active

**Date:** 2026-10-10

---

## 1. Purpose and Relationship to the Database Baseline

**This document is a living companion to the frozen Database Baseline v1 (`docs/database/01`–`08`), not a replacement for it and not a new baseline revision.** It exists to give an engineer a practical, current view of the real database schema as implemented — table names, key columns, relationships, constraints, and indexes — verified directly against the live SQLAlchemy models (`backend/app/**/infrastructure/models.py`, `backend/app/database/shared_models.py`, `backend/app/auth/models.py`, `backend/app/workers/models.py`, `backend/app/ai/models.py`, `backend/app/core/rate_limit_models.py`) and the Alembic migration history (`backend/alembic/versions/`).

The Database Baseline v1 remains the authoritative source for *why* the model is shaped the way it is — domain rationale, normalization reasoning, nullability and integrity principles, versioning and audit strategy. See [04_Logical_Data_Model.md](database/04_Logical_Data_Model.md) for the full logical contract and [08_Database_Design_Review_and_Readiness_Assessment.md](database/08_Database_Design_Review_and_Readiness_Assessment.md) §23–§25 for the baseline's own correction record (ADR-009, ADR-010, ADR-012). This document does not reopen or correct that baseline; where the real schema has moved further than even those corrections record, it is noted here as current fact, with a pointer back to the baseline rather than a silent rewrite of it.

Per [09_Documentation_Standards.md](governance/09_Documentation_Standards.md) §2, this is a synthesis, not a reproduction: table definitions below are abbreviated to the columns that matter for understanding relationships and constraints, not a full column-by-column transcription.

---

## 2. What Has Moved Beyond the Corrected Baseline

Three ADR-driven corrections are already recorded against the Database Baseline (ADR-009: Agent/Project split, Capability rename; ADR-010: `User.password_hash`, Session; ADR-012: Draft/Review pipeline removed). Cross-checking those corrections against the live code confirms they are accurately realized — `agent_id` is the scoping key for Knowledge, Memory, Conversation, Writing Profile exactly as ADR-009 specifies, and no `Draft`/`Review`/`ReviewDecision`/`DraftEvidenceLink` table or model exists anywhere in `backend/app/`.

Beyond those three corrections, the live schema has grown further with **no corresponding ADR or baseline correction**, confirmed directly in the model files' own inline documentation (commit-dated comments) and the Alembic revision history:

* `ResearchDocument` gained `publication_year`, `doi`, `doi_verification_status`, and `purpose` (style-sample vs. research material) — none of these appear in [04_Logical_Data_Model.md](database/04_Logical_Data_Model.md) §3.4.
* `User` gained `email`, `email_verified`, and `google_subject` for Google Sign-In and email-based flows (ADR-011 named password reset/email verification/Google sign-in as deferred future work; they are now built, additively, in `app/auth/`, per [Project_Status.md](Project_Status.md)'s 2026-10-09 entry — but no ADR records the resulting schema changes).
* New tables with no baseline entity at all: `writing_segments` (a named part of a project with its own saved instructions, added 2026-10-02), `password_reset_tokens`, `email_verification_tokens`, `ai_usage_records` (a per-user AI usage ledger), `rate_limit_counters` (backing store for the rate limiter).
* `knowledge_chunk_embeddings` and the lexical index (`knowledge_chunk_fts` on SQLite; a generated `search_vector` column on Postgres) realize ADR-005's hybrid retrieval but are physical/index-layer additions beyond the logical model's scope, not additions requiring a baseline correction.

None of this is a defect — it is the normal, additive evolution [08_Database_Design_Review_and_Readiness_Assessment.md](database/08_Database_Design_Review_and_Readiness_Assessment.md) §11 anticipated ("deferred decisions... additive, not a redesign"). It is flagged here because a reader relying on the Database Baseline documents alone, even including their three recorded corrections, would not learn these fields and tables exist.

---

## 3. Entities by Domain

### 3.1 Identity and Authentication (`app/database/shared_models.py`, `app/auth/models.py`)

| Table | Key columns | Notes |
|---|---|---|
| `users` | `user_id` (PK), `username` (unique), `password_hash`, `email` (unique, nullable), `email_verified`, `google_subject` (unique, nullable), `status` | `password_hash` defaults to `""` for rows created without a credential (e.g. test fixtures); never a valid bcrypt hash. `email_verified` defaults `True` (safe default for every pre-existing/Google/admin row); `RegisterUserUseCase` is the one path that explicitly passes `False`. |
| `sessions` (ORM class `AuthSession`, per ADR-010 Decision item 6 to avoid colliding with `sqlalchemy.orm.Session`) | `session_id` (PK), `user_id` (FK → users), `token_hash` (unique), `started_at`, `last_active_at`, `ended_at` | No expiry column, by design (ADR-010 Decision item 2). Excluded from RLS (§6) — looked up by secret token hash before any `user_id` is known. |
| `password_reset_tokens` | `token_id` (PK), `user_id` (FK), `token_hash` (unique), `expires_at`, `used_at` | Added 2026-10-06; same pre-identity lookup reasoning as `sessions`; excluded from RLS. |
| `email_verification_tokens` | `token_id` (PK), `user_id` (FK), `token_hash` (unique), `expires_at`, `used_at` | Added 2026-10-06 (external security review); same RLS exclusion reasoning. |

### 3.2 Agent and Project (`app/modules/agent/infrastructure/models.py`, `app/modules/project/infrastructure/models.py`)

| Table | Key columns | Notes |
|---|---|---|
| `agents` | `agent_id` (PK), `user_id` (FK → users, **unique**), `status`, `deleted_at` | Unique `user_id` enforces one-Agent-per-user (ADR-009). |
| `projects` | `project_id` (PK), `agent_id` (FK → agents, **unique**), `title`, `topic`, `status`, `closed_at`, `deleted_at` | Unique `agent_id` enforces exactly one Project per Agent, permanently (ADR-009). |

### 3.3 Document (`app/modules/document/infrastructure/models.py`)

| Table | Key columns | Notes |
|---|---|---|
| `research_documents` | `document_id` (PK), `project_id` (FK → projects, indexed), `format` (plain string — see below), `content_reference`, `processing_status`, `purpose`, `publication_year`, `doi`, `doi_verification_status`, `deleted_at` | `format` is deliberately a plain string, not a fixed enum: no approved document defines its accepted values, and the model's own docstring refuses to invent one. `purpose` (research vs. writing-style sample) and the DOI fields are post-baseline additions (§2). An index on `project_id` was added 2026-09-21 after a real-traffic audit found every "list a project's documents" call scanning it unindexed. |

### 3.4 Knowledge (`app/modules/knowledge/infrastructure/models.py`, `vector_models.py`)

| Table | Key columns | Notes |
|---|---|---|
| `knowledge_elements` | `element_id` (PK), `agent_id` (FK → agents), `element_type`, `status`, `superseded_element_id` (self-FK) | Supersession chain per the baseline's monotonic-history rule. |
| `knowledge_chunks` | `chunk_id` (PK), `agent_id` (FK), `element_id` (FK → knowledge_elements), `status` | Composite index on `(agent_id, status)` added 2026-09-21 — the hottest missing index found in a real-traffic audit (every search and every chat reply filters on exactly this pair). |
| `chunk_evidence_links` | `link_id` (PK), `chunk_id` (FK), `document_id` (FK → research_documents); unique `(chunk_id, document_id)` | Immutable once created; an index on `document_id` alone was added 2026-09-21 (the composite unique constraint's leading column, `chunk_id`, already served `chunk_id`-only lookups via the btree-prefix rule, but not `document_id`-only ones). |
| `knowledge_chunk_embeddings` | `chunk_id` (PK, FK → knowledge_chunks), `embedding_vector` (JSON-encoded float list, stored as text), `embedding_model_version` | The MVP's "embedded vector index" realization (ADR-004 Decision 3) — see [Technical_Design_Document.md](Technical_Design_Document.md) §10 item 2 for how this differs from ADR-004's longer-term pgvector-migration language. |

**Lexical index** (ADR-005 Decision 1, not a separate ORM-mapped table): SQLite gets an `FTS5` virtual table (`knowledge_chunk_fts`), rebuilt/synced on write by the knowledge-chunk repository since FTS5 has no ORM row class; Postgres gets a generated `search_vector tsvector` column plus a GIN index, maintained automatically by Postgres itself with no application-side sync required. Both are created by `init_db()`'s dialect branch for ephemeral dev/test databases; the real baseline Alembic migration carries the equivalent DDL for migrated databases.

### 3.5 Writing, Memory, and Conversation (`app/modules/writing/infrastructure/models.py`)

| Table | Key columns | Notes |
|---|---|---|
| `writing_profiles` | `profile_id` (PK), `agent_id` (FK), `user_id` (FK → users), `status` | Partial unique index enforces "at most one **active** Writing Profile per Agent" — dialect-branched (`sqlite_where`/`postgresql_where`); a 2026-09-18 Postgres-migration bug where only the SQLite branch was set (silently becoming a full unique index on Postgres) is fixed and tested. |
| `profile_characteristics` | `characteristic_id` (PK), `profile_id` (FK) | Index on `profile_id` added 2026-09-21 (unindexed "list characteristics" query). |
| `profile_characteristic_sources` | `link_id` (PK), `characteristic_id` (FK), `document_id` (FK); unique `(characteristic_id, document_id)` | |
| `memory_records` | `record_id` (PK), `agent_id` (FK), `status`, `superseded_record_id` (self-FK) | Composite index `(agent_id, status)` added 2026-09-21 — runs on every chat reply's context assembly. |
| `memory_provenance_links` | `link_id` (PK), `record_id` (FK), `source_type`, `conversation_id`/`element_id`/`document_id` (nullable, exclusive arc) | CHECK constraint enforces exactly one target set per `source_type`. `review_decision_id` was dropped with the Draft/Review pipeline (ADR-012). Index on `record_id` added 2026-09-21. |
| `conversations` | `conversation_id` (PK), `agent_id` (FK), `status`, `deleted_at` | Composite index `(agent_id, deleted_at)` added 2026-09-21. |
| `messages` | `message_id` (PK), `conversation_id` (FK), `direction`, `sequence`; unique `(conversation_id, sequence)` | |
| `message_context_links` | `link_id` (PK), `message_id` (FK), `target_type`, `document_id`/`element_id`/`chunk_id`/`memory_record_id` (nullable, exclusive arc) | `draft_version_id` dropped with the Draft/Review pipeline (ADR-012); this link entity is now evidence-grounding's sole carrier. Index on `message_id` added 2026-09-21. |
| `writing_segments` | `segment_id` (PK), `agent_id` (FK), `name`, `instructions`; unique `(agent_id, name)` | **No baseline entity** — added 2026-10-02 as a named part of a project with its own saved writing instructions; deliberately simple CRUD, not a supersession model. |

**Removed by ADR-012** (historical only, preserved in [04_Logical_Data_Model.md](database/04_Logical_Data_Model.md) §3.15–§3.18, §4.2 as removed-in-place sections, and in git history): `Draft`, `Draft Version`, `Review`, `Review Decision`, `Draft Evidence Link`. No table, model, or code reference to any of these five exists anywhere in `backend/app/` today — confirmed by direct search, not inferred from the ADR alone.

### 3.6 Workers and Platform (`app/workers/models.py`, `app/ai/models.py`, `app/core/rate_limit_models.py`)

| Table | Key columns | Notes |
|---|---|---|
| `work_items` | `work_item_id` (PK), `kind`, `state`, `payload_reference`, `idempotency_key` (unique) | The durable outbox (ADR-006). No foreign key to anything — a free-text `payload_reference` outbox by design. Composite index `(state, work_item_id)` added 2026-09-30 to support concurrent claiming. |
| `ai_usage_records` | `id` (PK), `user_id` (FK → users), `tokens`, `recorded_at` | **No baseline entity** — added 2026-09-21 as ADR-011's deferred per-user AI quota mechanism; one row per checked action, summed over a rolling 24h window, not a running counter. |
| `rate_limit_counters` | `key` (PK, string), `counter`, `expires_at` (Unix epoch float) | **No baseline entity** — backing store for the rate limiter, replacing `slowapi`'s default in-memory storage so limits survive a redeploy without adding Redis. Not user content; not RLS-protected. |

---

## 4. Relationships at a Glance

```
User ──1:1(MVP)── Agent ──1:1,permanent── Project ──1:N── ResearchDocument
                     │                                         │
                     ├──1:N── KnowledgeElement ──1:N── KnowledgeChunk ──N:M── ResearchDocument
                     │                                  (via ChunkEvidenceLink)   (evidence)
                     │                                         │
                     │                                  KnowledgeChunkEmbedding (1:1, derived)
                     │
                     ├──1:N── MemoryRecord (self-referencing supersession chain)
                     ├──1:N── Conversation ──1:N── Message ──N:M── {Document,Element,Chunk,MemoryRecord}
                     │                                              (via MessageContextLink, exclusive arc)
                     ├──1:N── WritingProfile ──1:N── ProfileCharacteristic ──N:M── ResearchDocument
                     │                                                        (via ProfileCharacteristicSource)
                     └──1:N── WritingSegment
```

`User` also owns `Session`/`AuthSession`, `PasswordResetToken`, `EmailVerificationToken` (authentication boundary, outside the Agent tree) and `AiUsageRecord` (platform/billing, outside the Agent tree). `WorkItem` and `RateLimitCounter` have no ownership chain at all.

---

## 5. Notable Constraints and Indexes

* **Enum storage deviation.** SQLAlchemy's default `Enum` column stores each Python enum member's `.name` (e.g. `"OPEN"`), not its documented lowercase `.value` (e.g. `"open"`) — invisible through the ORM but fatal to any raw-SQL CHECK constraint or partial unique index written against the baseline's documented enumerated values. The `writing` module fixed this via `values_callable` (`_enum_column` helper in `infrastructure/models.py`); the pre-existing `agent`, `document`, and `knowledge` modules still use the default and are flagged, unfixed, as a known non-blocking deviation (per [Project_Status.md](Project_Status.md)).
* **Exclusive-arc CHECK constraints** on `memory_provenance_links` and `message_context_links` enforce "exactly one target reference set" at the database layer, not just in application code.
* **Partial unique indexes**, dialect-branched for SQLite and Postgres, enforce "at most one active X" rules (`writing_profiles`) — see §3.5 for the real cross-dialect bug this caught.
* **2026-09-21 and 2026-09-30 real-traffic index audits** added every index flagged above; before them, several hot-path queries (chat context assembly, document listing, knowledge search) ran unindexed FK scans. Each addition is documented inline in the relevant model file with the specific query it serves — read the model file's comments directly for the exact justification rather than assuming an index exists because a column looks like it should have one.

---

## 6. Row-Level Security

Beyond application-level query filtering, every tenant-owned table carries a Postgres Row-Level Security policy (added 2026-09-21, forced 2026-09-21 — see `backend/alembic/versions/cff25673e0e3_add_row_level_security_policies.py` and `c65baaf64ccf_force_row_level_security.py`):

* **Policy shape.** Each policy's `USING`/`WITH CHECK` condition walks the table's real foreign-key chain back to `agents.user_id`, resolved via `app_current_user_id()` (a SQL function reading the `app.current_user_id` Postgres session variable, set per-transaction by `app/database/session.py`'s `"begin"` event listener from a Python `ContextVar` populated once `get_current_user_id` resolves identity). A session variable left unset resolves to `NULL`, and `column = NULL` is always false in SQL — every policy fails closed with no special-casing.
* **Protected tables (16):** `agents`, `projects`, `knowledge_elements`, `knowledge_chunks`, `knowledge_chunk_embeddings`, `memory_records`, `conversations`, `messages`, `research_documents`, `writing_profiles`, `profile_characteristics`, `profile_characteristic_sources`, `chunk_evidence_links` (the only table checked against **two** independent FK chains — both the chunk and the document must resolve to the current user), `memory_provenance_links`, `message_context_links`, `ai_usage_records`.
* **Deliberately excluded, each for a stated reason:** `users` (the ownership root itself), `sessions`/`password_reset_tokens`/`email_verification_tokens` (looked up by secret token hash before any `user_id` is known — RLS would create a chicken-and-egg problem on the first query of a request), `work_items` (no FK to anything), `rate_limit_counters` (not user content).
* **Enforcement role.** Migrations always run as the Postgres table-owner role (`neondb_owner`, which has `rolbypassrls`). The running application instead connects as a separate, restricted role (`scholaros_app`: `NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`, CRUD-only grants, no DDL rights) — confirmed live in production. `FORCE ROW LEVEL SECURITY` additionally closes the door against any future role/ownership drift, though it is not load-bearing against current production behavior (the app's own role already cannot bypass RLS).
* **The background Work Item executor connects through a third, unrestricted engine**, deliberately outside RLS — see [Technical_Design_Document.md](Technical_Design_Document.md) §10 item 4 for why, and for the real production outage this tradeoff caused before the dedicated worker engine existed.

---

## 7. Migration History

Schema changes are owned by Alembic (`backend/alembic/versions/`), 14 revisions as of 2026-10-09:

| Revision | Summary |
|---|---|
| `2dc6158c48d9` | Baseline schema (full current schema at Postgres-cutover time, dialect-branched for the lexical index) |
| `cff25673e0e3` | Add Row-Level Security policies (step 1 of 5; no-op until the app connects as a restricted role) |
| `2e1d18abf226` | Create the `scholaros_app` restricted role (step 2 of 5) |
| `c65baaf64ccf` | `FORCE ROW LEVEL SECURITY` on all 16 policy-protected tables (step 5 of 5) |
| `4d323d592976` | Add `rate_limit_counters` table |
| `3c841981a6d4` | Add `ai_usage_records` table |
| `988ef4146382` | Add `writing_segments` table |
| `b017cd8cd1c0` | Add index on `work_items.state` (concurrent-claim support) |
| `c7afc0adbc04` | Add `publication_year` to `research_documents` |
| `e151d6a4fdf6` | Add `doi` and `doi_verification_status` to `research_documents` |
| `e0429480c207` | Add Google Sign-In fields to `users` |
| `e0316c6e0352` | Add `password_reset_tokens` table |
| `1791af381140` | Add email verification (`email_verification_tokens`, `users.email_verified`) |
| `e3b0a1ae4624` | Add indexes on high-traffic query paths (the 2026-09-21/09-30 index audits of §5) |

Local/test SQLite databases do not run these migrations; they bootstrap via `init_db()`'s `create_all()` plus the dialect-branched lexical-index setup described in §3.4. The two paths are kept deliberately parallel, not DRY against each other, since they serve different purposes (ephemeral dev/test bootstrap vs. real schema evolution).

---

## 8. References

* [04_Logical_Data_Model.md](database/04_Logical_Data_Model.md) — the frozen logical model this document extends
* [05_Constraints_and_Integrity.md](database/05_Constraints_and_Integrity.md) — the frozen integrity contract
* [08_Database_Design_Review_and_Readiness_Assessment.md](database/08_Database_Design_Review_and_Readiness_Assessment.md) §23–§25 — the baseline's own correction record (ADR-009, ADR-010, ADR-012)
* ADR-004 (Storage and Memory Strategy), ADR-005 (Retrieval and Search Strategy), ADR-009, ADR-010, ADR-011, ADR-012
* [Technical_Design_Document.md](Technical_Design_Document.md) — the companion system-level reference
* [Baseline_Register.md](Baseline_Register.md) — freeze status of the Database Baseline
