# Technical Design Document

**Document:** Technical_Design_Document.md

**Status:** Active

**Date:** 2026-10-10

---

## 1. Purpose and Scope

This document is a synthesis-level technical reference for engineers who need to orient themselves in the ScholarOS backend quickly. It does not define architecture or make decisions — it organizes and cross-references decisions already recorded in the frozen **Architecture Baseline v1** (`docs/architecture/01`–`07`) and the ADR set (`docs/adr/ADR-001` through `ADR-012`), and verifies them against the real, current implementation (`backend/app/`, `backend/alembic/`, `backend/fly.toml`).

Where this document and an authoritative source disagree on detail, the authoritative source governs: [01_Architecture_Overview.md](architecture/01_Architecture_Overview.md) for the layered architecture, [05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) for service boundaries, and the ADRs for specific technology and deployment decisions. Per [09_Documentation_Standards.md](governance/09_Documentation_Standards.md) §2, this document cross-references rather than duplicates; read it alongside those sources, not instead of them.

For the data model, see the companion [Backend_Schema_Reference.md](Backend_Schema_Reference.md). For the current project state and milestone history, see [Project_Status.md](Project_Status.md) and [Baseline_Register.md](Baseline_Register.md).

---

## 2. System Overview

ScholarOS is a FastAPI/SQLAlchemy backend and a React frontend, organized as a **modular monolith** (ADR-003) running as a single deployable process. The backend realizes the layered architecture of [01_Architecture_Overview.md](architecture/01_Architecture_Overview.md) §3 and the five backend layers of [05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) §3: a service boundary layer (FastAPI routers), an orchestration layer (use cases composing repositories and the AI service layer), a domain service layer (per-module `domain`/`application`), an intelligence layer (the AI provider gateway and knowledge/writing pipelines), and a data access layer (SQLAlchemy repositories behind each module's `infrastructure/`).

Each business module under `backend/app/modules/` (`agent`, `project`, `document`, `knowledge`, `writing`) follows the same internal shape — `domain/` (entities, enums, exceptions, repository interfaces, framework-free), `application/` (use cases), `infrastructure/` (SQLAlchemy models and repository implementations), `interface/` (Pydantic schemas and FastAPI routes) — a clean/hexagonal layering applied uniformly, confirmed directly in the module directories rather than asserted from the architecture docs alone. `app/auth/` and `app/workers/` are boundary packages, not business domains, matching [05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) §15 (Authentication Boundary is architecturally parallel to the Infrastructure Boundary, not a tenth domain) and ADR-010 Decision item 5.

The product-facing domain model is: a **User** registers and owns exactly one **Agent** (their permanent research workspace, ADR-009), which owns exactly one **Project** (the raw topic and source documents), and which scopes everything the system learns and remembers — Knowledge, Memory, Conversation, Writing Profile. The original Draft → Review → Decision writing pipeline was removed and replaced by a chat/memory model (ADR-012); writing now happens through **Conversation**/**Message**, with **Memory Record** carrying forward persistent context. See [Backend_Schema_Reference.md](Backend_Schema_Reference.md) for the full current entity set.

---

## 3. Technology Stack

| Layer | Choice | Governing decision |
|---|---|---|
| Language/runtime | Python 3.12+, FastAPI, Pydantic v2 | ADR-002 |
| Persistence access | SQLAlchemy 2.x ORM, behind a data access layer per module | ADR-002; [05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) §16 |
| Structured core (production) | Neon-hosted PostgreSQL | ADR-004 (SQLite → PostgreSQL migration path); cutover confirmed in [Project_Status.md](Project_Status.md) (2026-10-09 entry) — see §8 below for the discrepancy this creates against ADR-004/007's written text |
| Structured core (local dev/test) | SQLite, with WAL mode and explicit transaction demarcation | ADR-004; `backend/app/database/session.py` |
| Vector index | JSON-encoded float list in a `knowledge_chunk_embeddings` column (Postgres and SQLite alike) | ADR-004 Decision 3 / ADR-005 Decision 5 — see §9 for how this differs from ADR-004's named migration target (pgvector) |
| Lexical index | SQLite FTS5 virtual table (dev/test) or Postgres generated `tsvector` + GIN index (production) | ADR-005 Decision 1 |
| Object store | Local filesystem (dev) or S3-compatible store (`STORAGE_BACKEND=s3`, production) | ADR-004 Decision 4; `app/storage/s3_compatible.py` |
| AI provider gateway | `Protocol`-typed `TextGenerationProvider`/`EmbeddingProvider` interfaces, concrete providers selected by configuration | ADR-002 Decision 3; `app/ai/providers/` |
| Async execution | In-process, durable-outbox work item queue | ADR-006 |
| Testing | pytest (unit, integration, e2e); ruff + mypy in CI | ADR-002 Decision 4; recent commit history |
| Deployment | Fly.io (backend container) + Vercel (frontend) + Neon (Postgres) | ADR-007 (local-first text; see §8 for the production reality) |

The rationale for each stack choice is recorded in ADR-002 and is not repeated here; this table exists to map decision to current realization.

---

## 4. Module and Domain Boundaries

The domain inventory of [05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) §4.1, as corrected by ADR-009, is realized as eight module/boundary packages in `backend/app/`:

| Domain (architecture) | Code location | Notes |
|---|---|---|
| Agent | `app/modules/agent/` | Owns exactly one User→Agent mapping (unique `user_id`); one-Agent-per-user enforced at the DB layer |
| Project | `app/modules/project/` | Narrowed scope: identity, topic, Research Document ownership only (ADR-009) |
| Document | `app/modules/document/` | Research Document intake, DOI verification (`app/ai/crossref.py`), processing status |
| Knowledge | `app/modules/knowledge/` | Extraction, chunking, hybrid retrieval (ADR-005) |
| Writing | `app/modules/writing/` | Writing Profile, Memory, Conversation/Message, Writing Segment — the chat/memory model (ADR-012) |
| Capability | *(not yet implemented in code)* | Registered in architecture (§13–§14 of [04_AI_Architecture.md](architecture/04_AI_Architecture.md)) but no `app/modules/capability/` exists; the AI provider factory (`app/ai/providers/factory.py`) currently serves the equivalent routing role informally |
| Authentication Boundary | `app/auth/` | Session-based auth (ADR-010), registration (ADR-011), Google OIDC sign-in, password reset, email verification — all additive to `app/auth/`, none requiring a schema redesign |
| Infrastructure Boundary | `app/database/`, `app/storage/`, `app/workers/` | Data access layer, object storage abstraction, async executor |

Cross-module calls flow through each module's public interface (use cases and repository interfaces), never through another module's ORM models directly, consistent with ADR-003's module-boundary discipline. The Capability/Capability-Entry registry described in the architecture documents has no dedicated persistence or module in the current codebase; AI capability selection is currently handled directly by the provider factory and the use cases that call it, not through a formal registry. This is a gap between the architecture documents and the implementation worth flagging rather than silently treating as realized.

---

## 5. Authentication Boundary

Realized in `app/auth/` exactly as ADR-010 and ADR-011 specify, and now extended further than either ADR documents in detail (see [Project_Status.md](Project_Status.md)'s 2026-10-09 entry):

* **Session model** (ADR-010): `POST /auth/login` verifies a bcrypt password hash and creates a server-side `AuthSession` row with a random token; subsequent requests present it as `Authorization: Bearer <token>`. No automatic expiry exists by design (ADR-010 Decision item 2) — a session is valid until explicit logout.
* **Self-service registration** (ADR-011): `POST /auth/register`, originally gated by an optional invite code, now fully open in production.
* **Beyond ADR-011's recorded scope, built additively in the same `app/auth/` shape** (per [Project_Status.md](Project_Status.md), not yet covered by a dedicated ADR): Google Sign-In via verified OIDC ID tokens (`app/auth/google_oauth.py`), password reset via email, email verification gating document upload/chat for password accounts, account linking between a Google identity and a password account, and rate limiting (`slowapi`) on every auth-sensitive endpoint.
* **Row-Level Security as a second, independent enforcement layer** (2026-09-21 security pass): every tenant-scoped table carries a Postgres RLS policy walking its foreign-key chain back to `agents.user_id`; the running app connects as a restricted, non-superuser role (`scholaros_app`) with `FORCE ROW LEVEL SECURITY`, so even a query that forgets a `WHERE` clause cannot cross tenants. See [Backend_Schema_Reference.md](Backend_Schema_Reference.md) §6 for the full policy inventory.

Domain services never see sessions, tokens, or hashes — they receive only a resolved `user_id`, exactly as [05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) §15.2 requires.

---

## 6. AI Provider Abstraction

`app/ai/providers/base.py` defines the gateway contract as two `Protocol`s — `TextGenerationProvider.generate()` and `EmbeddingProvider.embed()`/`embed_batch()` — exactly the provider-agnostic boundary ADR-002 Decision 3 requires. `app/ai/providers/factory.py` is the single place that reads `settings.ai_provider` and dispatches to a concrete implementation:

* `google_genai.py` — the production default, backed by the Gemini API.
* `openai_compatible.py` — an OpenAI-compatible HTTP provider.
* `fake.py` — test-infrastructure only; never selected in production, exists so hermetic e2e specs can run in CI without a real provider key.
* `failover.py` and `rate_limited.py` — composable wrappers around a concrete provider (failover between providers; request-rate limiting), not separate provider identities.

Business and domain code depend only on the `Protocol` types, never on a concrete provider class or an HTTP client — the import boundary ADR-002 requires. Provider selection and credentials are entirely configuration-driven (`app/core/config.py`), never branched on in business logic.

---

## 7. Async Work-Item Processing

The durable outbox pattern of ADR-006 is realized as the `WorkItem` table (`app/workers/models.py`) and an in-process executor (`app/workers/executor.py`). Two implementation details worth knowing, verified directly in code rather than assumed from the ADR:

* **The executor runs on real OS threads, not `asyncio` tasks.** Every call beneath it (a synchronous SQLAlchemy `Session`, the synchronous `google-genai` client) is blocking; running it on `asyncio` would hold the single event loop hostage for the duration of every AI call, freezing all concurrent HTTP traffic. Threads let the OS interleave I/O waits (DB round trips, outbound provider calls) properly. `worker_count` (default low) controls how many threads run concurrently within the one machine.
* **Stale-`RUNNING` recovery.** A Work Item claimed but never completed (e.g., a process crash mid-generation) is recovered once at executor startup (`requeue_stale_running`) rather than being silently stuck forever — this closes a gap that was open through the Project Writing milestone (see [Project_Status.md](Project_Status.md) Risks table) and is now a general, kind-agnostic worker concern, not specific to any one pipeline.
* **A dedicated queue health monitor** (`app/workers/health.py`, added 2026-10-10) periodically checks for an unresolved Work Item older than a configured threshold and reports to Sentry, closing the "process alive but queue not moving" blind spot that caused a real production outage (§9).

---

## 8. Storage and Retrieval

**Storage** (ADR-004): the structured core has migrated from the originally-specified SQLite MVP to Neon PostgreSQL in production, with SQLite retained for local development and tests. The object store similarly supports both a local filesystem backend and an S3-compatible backend, selected by `STORAGE_BACKEND`.

**Retrieval** (ADR-005): hybrid retrieval is fully implemented — a lexical branch (SQLite FTS5 or Postgres `tsvector`+GIN, dialect-branched in `app/database/session.py`'s `init_db()`) and a semantic branch (cosine similarity over the JSON-encoded embedding column), fused via reciprocal rank fusion. Cross-encoder reranking remains deferred, as ADR-005 anticipated.

---

## 9. Deployment Topology

Production runs on three managed platforms, confirmed directly against `backend/fly.toml` and the codebase's own documentation of the cutover (not inferred from the architecture text alone):

* **Backend — Fly.io.** A single Fly machine (`backend/fly.toml`: `min_machines_running = 1`, `auto_stop_machines = "off"`). This is deliberate, not an oversight: the in-process Work Item executor (§7) must keep polling continuously even with no incoming HTTP traffic, so the machine cannot be allowed to idle-stop the way a purely stateless API could.
* **Frontend — Vercel.**
* **Database — Neon PostgreSQL**, with Row-Level Security enforced via a restricted application role (§5) and schema owned by Alembic (14 revisions as of 2026-10-09; see [Backend_Schema_Reference.md](Backend_Schema_Reference.md) §7).

---

## 10. Known Current Architectural Limitations

These are real, current properties of the running system, not hypothetical risks — each is confirmed against code or configuration, not assumed from the architecture documents.

1. **Single-machine, in-process background worker.** `fly.toml` pins exactly one machine (`min_machines_running = 1`); the Work Item executor runs as threads inside that one process (§7). There is no horizontal scaling of background work today. ADR-003's extraction path and ADR-006's durable-queue extraction path remain the documented route if this becomes a bottleneck; neither has been exercised yet.
2. **Embeddings are not in a dedicated vector store.** ADR-004 named "a dedicated vector store (e.g., pgvector on PostgreSQL)" as the migration path beyond the MVP's embedded index. The current implementation stores embeddings as a JSON-encoded float list in an ordinary Postgres column (`knowledge_chunk_embeddings.embedding_vector`), with similarity computed in application code — functionally equivalent to the embedded-index MVP decision, but not yet the pgvector migration ADR-004 anticipated for the post-cutover stage. Worth tracking as the chunk corpus grows.
3. **ADR-004 and ADR-007's written text still describe a local-first, SQLite-first deployment model.** Production has moved to Fly.io + Vercel + Neon Postgres (§9), confirmed in [Project_Status.md](Project_Status.md)'s 2026-10-09 entry and in `fly.toml` itself, but neither ADR has been corrected or superseded to record this — unlike ADR-009/010/012's explicit correction pattern for the database baseline. A reader relying on ADR-007's Decision section alone would not learn that the cloud cutover already happened. This is a documentation gap, not a code defect, and is reported here rather than silently worked around.
4. **The background executor runs with elevated database privileges, deliberately outside Row-Level Security.** Because the executor processes work queued by many different users without ever being request-scoped, it connects through a second, unrestricted engine (`worker_engine` in `app/database/session.py`) rather than the RLS-restricted role the web tier uses. This was the direct cause of a real production outage (2026-09-30: the executor's connection had no `current_user_id` set, so every RLS-protected table was invisible to it, not just rows it shouldn't see) before the dedicated worker engine was introduced. The current design is a considered tradeoff, not an oversight, but it does mean RLS provides no defense-in-depth for the one component with the broadest data access.
5. **No automatic session expiry.** Per ADR-010 Decision item 2, a session remains valid indefinitely until explicit logout. This is a stated MVP tradeoff, not a defect, but it means a lost or leaked token remains usable until the user (or an operator) notices.
6. **The Capability registry described in the architecture documents is not implemented.** See §4 — AI capability routing happens informally through the provider factory and individual use cases, not through a dedicated `Capability`/`Capability Entry` persistence layer.

---

## 11. References

* [01_Architecture_Overview.md](architecture/01_Architecture_Overview.md) — layered architecture
* [05_Backend_Architecture.md](architecture/05_Backend_Architecture.md) — service boundaries, authentication and infrastructure boundaries
* [07_Operational_Architecture.md](architecture/07_Operational_Architecture.md) — storage, deployment, and scalability assumptions
* ADR-002 (Technology Stack and Provider Abstraction), ADR-003 (Modular Monolith), ADR-004 (Storage and Memory Strategy), ADR-005 (Retrieval and Search Strategy), ADR-006 (Async Processing), ADR-007 (Deployment Strategy), ADR-009 (Agent/Project Domain Model), ADR-010 (Authentication Boundary), ADR-011 (Self-Service Registration), ADR-012 (Chat/Memory Model)
* [Backend_Schema_Reference.md](Backend_Schema_Reference.md) — the companion data-model reference
* [Project_Status.md](Project_Status.md), [Baseline_Register.md](Baseline_Register.md) — current state and freeze discipline
