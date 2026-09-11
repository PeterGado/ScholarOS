# ADR-010: Authentication Boundary — Single-User Session Model

**Status:** Accepted

**Date:** 2026-09-10

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** None (tenth ADR). Records an architecturally significant correction to the frozen **Database Baseline v1** (`docs/database/01`–`08`) and the frozen **Architecture Baseline v1** (`docs/architecture/01`–`07`), per `04_Repository_Governance.md` §4.4, and satisfies the escalation this project's own governance already required: ADR-008 item 5 names "authentication model" as a decision that must not be made silently in code. This ADR is that decision.

---

## Status

**Accepted.** Following clarification from the project owner, this ADR authorizes a real Authentication Boundary for ScholarOS's backend, replacing the placeholder `get_current_user_id` bootstrap-user mechanism introduced during Backend Implementation (Milestone 6). It governs a correction to the `User` entity in Database Baseline v1 and an extension to the Authentication Boundary section of Architecture Baseline v1. It does not itself implement the boundary — implementation is a subsequent, separately-authorized stage.

---

## Context

The backend's first vertical slice (Milestone 6) shipped with `core/dependencies.py`'s `get_current_user_id`: every request resolves to the same single bootstrap `User` row, with no credential verification of any kind. This was deliberately scoped as a disclosed placeholder — Stage 5's own report named it "the one placeholder most relevant to the next real-auth milestone" — not a completed authentication system.

The requirement for real authentication already exists in the frozen baseline:

* `05_Backend_Architecture.md` §15 (Authentication Boundary) already specifies *what* the boundary must do — establish and verify identity before any service is accessed (NFR-009), authorize access to project data (API-036, API-037), stay independent of domain logic so schemes can change later (NFR-024) — but deliberately leaves *how* undecided, consistent with API-041's "authentication framework" being explicitly out of SRS scope.
* MVP-001 and the MVP scope's constraint #4 require "a single authenticated user per deployment" — but the MVP's own Out-of-Scope table explicitly excludes **multi-user collaboration**, citing "authentication, authorization, and concurrency complexity beyond MVP scope" as the reason.

These two statements are not in tension once read precisely: the MVP requires *real* authentication for its one user (not a placeholder), but explicitly does not require *multi-user account management* (registration, roles, multiple concurrent accounts). The project owner confirmed this reading directly: exactly one pre-provisioned account, real login, no self-registration, no email verification, no password reset, no multi-user administration — and the account must not be hard-coded in source, only seeded from configuration.

A second, load-bearing finding from re-reading the frozen baseline: `04_Logical_Data_Model.md` §3.2 already defines a **Session** entity — `session_id`, `user_id`, `session_token` ("Exchanged credential," a candidate key), `started_at`, `last_active_at`, `ended_at` — with a documented lifecycle (`open → ended`) already present in `05_Constraints_and_Integrity.md` §5. This entity was specified at Milestone 5 (2026-08-07), before any authentication mechanism existed, and precisely matches a server-side, DB-backed opaque-token session model. It has never been implemented. Choosing a stateless mechanism (e.g., JWT) now would leave this already-designed entity unused and introduce a second, divergent mechanism where a matching one already exists in the frozen baseline.

---

## Problem

How should ScholarOS authenticate its single MVP user, in a way that:

1. Satisfies NFR-009 / MVP-001's requirement for real authentication, not a placeholder;
2. Stays within the MVP's explicit exclusion of multi-user account complexity;
3. Provisions the one account from configuration, never from source code;
4. Builds on what the frozen Database Baseline v1 already specifies, rather than introducing a redundant mechanism;
5. Keeps the boundary independent of domain logic (§15.3), so a future multi-user or third-party-identity scheme is a boundary change, not a domain rewrite.

---

## Decision

1. **Exactly one pre-provisioned account.** No registration, email verification, password reset, or multi-account endpoints are built. The account's username and a **pre-hashed** bcrypt password hash are read from configuration (`AUTH_USERNAME`, `AUTH_PASSWORD_HASH` — the hash, never a plaintext password, per governance `03_AI_Engineering_Standards.md` §9) and **synced into the `User` table on every application startup** (create-if-missing, update-if-changed) — configuration is the source of truth, the database row is a cache of it, and nothing about the account is hard-coded in source. Generating `AUTH_PASSWORD_HASH` itself (from an operator-chosen password, at provisioning time, before the app ever runs) is an operational step the implementation stage must provide a documented, deterministic way to perform — this ADR does not specify the tool, only that one must exist.

2. **Session model, not a bearer token scheme.** Authentication uses the already-specified `Session` entity (`04_Logical_Data_Model.md` §3.2): `POST /auth/login` verifies the submitted password against the stored bcrypt hash and, on success, creates a `Session` row with a cryptographically random `session_token` (`secrets.token_urlsafe`), returning it to the client. Subsequent requests present it as `Authorization: Bearer <session_token>`; the authentication dependency looks it up and rejects it if missing or already `ended_at` (the sole transition `05_Constraints_and_Integrity.md` §5 documents). `last_active_at` may be refreshed on each authenticated request as activity metadata only. `POST /auth/logout` sets `ended_at`. **There is no automatic, time-based session expiry in this milestone — no idle timeout, no absolute lifetime.** This is a definitive decision, not an open question: a session is valid until explicitly ended via logout, full stop. `last_active_at` must never be read as a validity check. Introducing automatic expiry in a later milestone is a new decision requiring its own ADR, not a silent extension of this one.

3. **Password hashing via `bcrypt`** (the package directly, not `passlib`, to avoid its known bcrypt-backend version friction). Hashes are never logged or returned in any API response.

4. **`User` gains a `password_hash` attribute** (correction to Database Baseline v1, §3.1) — the only schema change this decision requires. `Session` needs no schema change; it was already fully specified.

5. **Realized as a new boundary package (`app/auth/` in the backend), not a `modules/` bounded context.** Architecture's Domain Inventory (§4.1) does not list Authentication among the ten business domains (Agent, Project, Document, Knowledge, Memory, Conversation, Capability, Review, Author Profile, Configuration) — it is a *boundary* (§15), architecturally parallel to the Infrastructure Boundary (§16), not a business capability. Placing it under `modules/` would misrepresent it as a domain with its own aggregate.

6. **Naming note for implementation:** the Logical Data Model's entity is named `Session`, which collides with SQLAlchemy's own `Session` type already imported throughout the codebase (`sqlalchemy.orm.Session`). Implementation must name the domain/ORM classes something unambiguous in code (e.g., `AuthSession`) while documenting the traceability back to `04 §3.2`'s `Session` — the *logical* vocabulary is unchanged, only the code-level identifier avoids the collision.

---

## Rationale

* **Builds on frozen design instead of duplicating it.** The `Session` entity has sat fully specified and unimplemented since Milestone 5; using it is more consistent with "treat the current repository as authoritative" than introducing JWT and leaving it orphaned.
* **Revocability matters for a personal tool.** A DB-backed session can be ended instantly (lost device, suspicion of compromise) by a single row update. A stateless JWT cannot be revoked before its expiry without an additional blocklist — extra machinery this project doesn't otherwise need.
* **No server-side session *store* dependency beyond what's already built.** The structured core (SQLite, ADR-004) already holds `User`; `Session` is one more table in it — no new infrastructure category.
* **Config-as-source-of-truth satisfies "don't hard-code the account" precisely**, and matches "seeded via environment/config at deploy time" from the project owner directly.
* **Independent of domain logic**, per §15.3: no domain service (Agent, Project, Document) knows anything about sessions, hashing, or tokens — they only ever see a resolved `user_id`, exactly as today's placeholder already provides it.

---

## Alternatives Considered

### Alternative 1: Stateless JWT bearer tokens

**Rejected because:** no revocation before expiry without added machinery (a blocklist); and it leaves the already-frozen `Session` entity unimplemented and effectively orphaned, diverging from the baseline for no compensating benefit at this project's scale (single user, single node, ADR-007).

### Alternative 2: OAuth2 / third-party identity provider

**Rejected because:** introduces a real external dependency and a consent/authorization flow for a single, self-hosted, personal-use account — direct scope violation of the MVP's explicit multi-user/collaboration exclusion, and of "don't build registration... those are future capabilities."

### Alternative 3: Plaintext password in configuration, hashed only at comparison time

**Rejected because:** the chosen design (pre-hashed `AUTH_PASSWORD_HASH` in configuration) achieves the same "no hard-coded account, seeded from config" outcome without ever holding the plaintext password at rest in a config file — strictly better at no extra operational cost (a one-time hash-generation step at provisioning time).

---

## Consequences

### Positive

* Real authentication for the one MVP user, closing the gap Stage 5/6 explicitly flagged.
* No orphaned schema: the `Session` entity finally has a purpose.
* Trivial session revocation.
* Authentication remains a boundary concern; zero changes required to Agent, Project, or Document domain/application code — `get_current_user_id`'s call site and return type (`int`) are unchanged, only its implementation is replaced.

### Negative

* Every authenticated request now costs one additional DB lookup (Session verification) — acceptable at this project's scale (single user, SQLite, ADR-004), revisit only if it ever becomes a measured bottleneck.
* **No automatic session expiry means a session row stays valid indefinitely until explicit logout.** If a client loses its token without logging out (cleared storage, lost device), the session remains "open" in the database with no way to reach it again — an accepted MVP tradeoff for a single-user, self-hosted tool, not a defect. The session table also grows without bound over time with no automatic pruning; negligible at single-user MVP scale, but worth remembering before any future multi-user phase.

### Neutral

* This ADR does not decide whether a future multi-user phase reuses this `Session`-based model or replaces it — per §15.3, that is a boundary-layer decision to make when multi-user work is actually scoped (ADR-009's Future Considerations precedent: "not a redesign, a change to this service's uniqueness enforcement/scope only").

---

## Repository Impact

* `docs/database/04_Logical_Data_Model.md` §3.1 (User) — add `password_hash` attribute. Correction to Database Baseline v1 per `04_Repository_Governance.md` §4.4, applied immediately following this ADR.
* `docs/database/05_Constraints_and_Integrity.md` — add one data-validation rule: `password_hash` is never exposed in an API response or log.
* `docs/architecture/05_Backend_Architecture.md` §15 — extended with a note recording the concrete mechanism decision and a cross-reference to this ADR, following the append-don't-renumber discipline established by ADR-009.
* `docs/Baseline_Register.md` — a further-correction note, mirroring the existing ADR-009 entry.
* **Not yet built:** the `app/auth/` package, the `Session`/`AuthSession` ORM model and repository, the login/logout routes, and the rewrite of `core/dependencies.py`'s `get_current_user_id`. This ADR authorizes that work; it does not perform it. Implementation proceeds as a separately-authorized, staged effort (mirroring Milestone 6's Stage 1-6 discipline), starting with an implementation plan.

---

## AI Engineering Implications

* Any future AI-assisted session must treat `User.password_hash` as a field that is never included in a Pydantic response schema, never logged, and never passed to any AI provider (it is not knowledge, memory, or content — it is a credential).
* The naming-collision note (Decision item 6) is binding: implementation must not name the ORM/domain class `Session`, to avoid confusion with `sqlalchemy.orm.Session` throughout the existing codebase.
* `get_current_user_id`'s signature and call site are unchanged; only its body changes. Any future work must not spread session-verification logic outside the `app/auth/` boundary into route handlers or domain/application code.

---

## Compliance Rules

* No endpoint other than `POST /auth/login` accepts a password.
* No registration, password-reset, or multi-account endpoint may be added under this ADR — doing so requires a new ADR, since it changes the account-cardinality decision made here.
* Session verification (token lookup, `ended_at` check, `last_active_at` refresh as activity metadata only — never as a validity check) lives only in the `app/auth/` boundary package, never duplicated in route handlers. No automatic expiry, idle-timeout, or cleanup logic may be introduced without a new ADR — see Decision item 2.
* `AUTH_USERNAME` / `AUTH_PASSWORD_HASH` must be read through the existing `Settings` (`app/core/config.py`) pattern — no separate, ad hoc configuration mechanism.

---

## Related ADRs

| ADR | Relationship |
|---|---|
| ADR-002 (Technology Stack and Provider Abstraction) | This decision uses the same FastAPI/SQLAlchemy stack; no new stack element beyond a password-hashing library. |
| ADR-004 (Storage and Memory Strategy) | `Session` lives in the structured core (SQLite MVP), consistent with the existing storage-category mapping. |
| ADR-008 (API Contract Governance During Backend Implementation) | This ADR fulfills item 5's escalation requirement: "authentication model" required a new ADR before implementation, not a silent code decision. |
| ADR-009 (Agent and Project Domain Model Introduction) | Precedent for this ADR's correction mechanism (frozen-baseline correction via a new ADR, append-don't-renumber discipline) and for keeping the Authentication Boundary independent of the Agent/Project domain model it gates access to. |
| ADR-007 (Deployment Strategy) | Single-node MVP deployment is why revocability (Session) was weighed against JWT the way it was (Alternatives Considered #1) — no horizontal-scaling session-sharing concern at this stage. |

---

## Future Considerations

* **Multi-user support** (multiple real accounts, roles, registration): explicitly deferred, matching the MVP's own Out-of-Scope table. When scoped, it is a change to this boundary's account-cardinality assumption, not a redesign of the session mechanism itself.
* **Automatic session expiry** (idle timeout, absolute lifetime): explicitly not built in this milestone — this ADR's Decision item 2 is definitive, not tentative: no such logic exists. If a future milestone adds one, that is a new decision requiring its own ADR (it changes what "valid session" means), not an extension of this one. Not to be confused with the session-row-growth housekeeping note in Consequences, which is about database size, not validity.
* **Rate limiting on `POST /auth/login`**: not addressed by this ADR; worth revisiting before any non-local/non-personal deployment.

---

## References

* `docs/architecture/05_Backend_Architecture.md` §15 (Authentication Boundary)
* `docs/database/04_Logical_Data_Model.md` §3.1 (User), §3.2 (Session)
* `docs/database/05_Constraints_and_Integrity.md` §5 (Lifecycle Constraints)
* `docs/srs/05_Non-Functional_Requirements.md` (NFR-009, NFR-010, NFR-024)
* `docs/srs/09_API_Requirements.md` (API-036, API-037, API-041)
* `docs/srs/10_MVP_scope.md` (MVP-001, Out-of-Scope table)
* `docs/adr/ADR-007_Deployment_Strategy.md`
* `docs/adr/ADR-008_API_Contract_Governance_During_Backend_Implementation.md`
* `docs/adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md`
* `docs/governance/03_AI_Engineering_Standards.md` §9 (Security Standards — secrets never hardcoded, stored in environment variables)
* `docs/journal/2026-09-10.md` (this ADR's authorizing session)
