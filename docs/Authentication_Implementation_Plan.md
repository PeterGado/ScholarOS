# Authentication Implementation Plan — Milestone 7, Stage 1

**Status:** Planning complete. No code written, no files modified, no dependencies installed.
**Governs:** Milestone 7 (Real Authentication Boundary) implementation, Stages 2-8.
**Authoritative sources:** ADR-010, `05_Backend_Architecture.md` §15/§15.4, `04_Logical_Data_Model.md` §3.1/§3.2, `05_Constraints_and_Integrity.md` §5/§17, ADR-008.
**Not a frozen baseline document** — supersedable as later stages refine it, same status as `Backend_Implementation_Plan.md`.

---

## 1. Current-State Findings

Verified by fresh inspection (not assumed from prior reports):

* **`get_current_user_id`** (`app/core/dependencies.py:19-35`): queries `User` by a hard-coded `_BOOTSTRAP_USERNAME = "default-user"`, creating it on first use if missing. No credential check of any kind. Signature: `(db: Session = Depends(get_db)) -> int`.
* **`User` ORM model** (`app/database/shared_models.py`): `user_id, username, display_name, status, created_at, updated_at`. **No `password_hash` column exists in code** — the frozen Logical Data Model was corrected by ADR-010, but the implementation has not caught up yet. This is expected (ADR-010 authorized, not yet implemented) but worth stating plainly: code and doc are currently out of sync on this one attribute.
* **No `Session`/`AuthSession` ORM model exists anywhere in `backend/`.**
* **No `app/auth/` package exists.**
* **`bcrypt` is not installed**, directly or transitively (`pip show bcrypt` → not found). No password-hashing or session-token library is present.
* **`UnitOfWork`** (`app/core/unit_of_work.py` Protocol, `app/database/unit_of_work.py` `SqlAlchemyUnitOfWork`) is generic and reusable as-is for `AuthSession` writes — no change needed to it.
* **`init_db()`** (`app/database/session.py:45-60`) imports each module's ORM models by hand before `create_all` — a new `AuthSession` model must be added to that import list the same way.
* **Exception handling** (`app/api/exception_handlers.py`) is a centralized `add_exception_handler` registry keyed by exception type → HTTP status, with a consistent `{error_type, detail}` envelope. New auth-specific exceptions (invalid credentials, invalid/expired token) slot into this same mechanism.
* **Router aggregation** (`app/api/router.py`): flat `include_router()` calls; adding `app/auth/routes.py`'s router is a one-line addition.
* **`main.py`**'s `lifespan` currently only calls `init_db()`. It is the natural place to add the credential-provisioning sync call.
* **`POST /agents`** (`app/modules/agent/interface/routes.py`) already depends on `get_current_user_id` — will pick up real auth automatically once that dependency's body changes, no route change needed.
* **`POST /projects/{project_id}/documents`** (`app/modules/document/interface/routes.py`) — concrete finding: **this route has no identity dependency at all today**, not even the bootstrap placeholder. It trusts `project_id` from the URL with zero notion of who is asking. This route needs a dependency *added*, not modified.
* **`CreateAgentWorkspaceUseCase`** already takes `user_id: int` as a plain parameter and enforces one-Agent-per-user — this is unaffected by anything in this plan.
* **`UploadResearchDocumentUseCase`** (`app/modules/document/application/use_cases.py`) takes no `user_id` at all — consistent with the route having no identity dependency.
* **Tests**: `tests/e2e/test_agent_workspace_api.py` and `test_document_upload_api.py` call the API directly with no `Authorization` header. Once auth is enforced, every one of these will start failing with 401 unless given a login step. `tests/e2e/conftest.py`'s `client` fixture uses `monkeypatch` to redirect the module-level engine/session and a `dependency_overrides` entry for the content store — the same two mechanisms will be needed to inject a test-known `AUTH_USERNAME`/`AUTH_PASSWORD_HASH` via `Settings`.
* **`pyproject.toml`**: `fastapi, uvicorn[standard], pydantic, pydantic-settings, sqlalchemy, python-multipart` (+ dev: `pytest, httpx`). No crypto/session library present.

---

## 2. Architecture Interpretation

Governing decision: ADR-010 + `05_Backend_Architecture.md` §15.4. Authentication is a **boundary**, not a `modules/` bounded context (§15 sits alongside §16 Infrastructure Boundary in the Domain Inventory's structure, not in §4.1's ten business domains). This plan places it as `app/auth/`, parallel to `app/database/` and `app/storage/` — consumed by API routes through `core/dependencies.py`, exactly like existing repositories. Domain and application layers remain unaware of it, except for one deliberate exception analyzed in §8 below (an application-layer ownership check that receives a plain `user_id: int`, not any auth-specific type).

---

## 3. Authentication Boundary Design

```text
Login Request                                Authenticated HTTP Request
    ↓                                             ↓
POST /auth/login (app/auth/routes.py)        Authorization: Bearer <token>
    ↓                                             ↓
AuthService.login()  (app/auth/service.py)   get_current_user_id (core/dependencies.py)
    ↓                                             ↓
verify bcrypt hash (app/auth/hashing.py)     AuthService.verify_token() (app/auth/service.py)
    ↓                                             ↓
User row (existing User model)               AuthSessionRepository.get_by_token_hash()
    ↓                                             ↓
generate token (app/auth/tokens.py)          found & not ended → AuthenticatedIdentity(user_id)
    ↓                                             ↓
AuthSessionRepository.create()               get_current_user_id returns identity.user_id (int)
    ↓                                             ↓
return raw token to client                   → API route → Application use case → Domain
(never stored raw - see §7)                    (user_id flows in exactly as it does today)


Logout
    ↓
POST /auth/logout, same Authorization header as any authenticated request
    ↓
get_current_user_id resolves it first (must be a valid session to log out of one)
    ↓
AuthService.logout() → AuthSessionRepository.end(session)  (sets ended_at)
```

**Responsibility placement:**
* `app/auth/routes.py` — HTTP parsing/serialization only (login/logout endpoints), identical discipline to `agent`/`document` routes.
* `app/auth/service.py` — orchestrates verify-credentials → create-session (login) and end-session (logout); the one place session/credential logic is allowed to live.
* `app/auth/hashing.py`, `app/auth/tokens.py` — narrow, single-purpose helpers (bcrypt verify; token generate + hash).
* `app/auth/repository.py` — the only code that touches the `AuthSession` table directly.
* `core/dependencies.py`'s `get_current_user_id` — the sole integration point between the boundary and every other route; unchanged signature (`() -> int`), per ADR-010's own AI Engineering Implications.

---

## 4. Credential Provisioning Semantics

**Not ambiguous — already decided by ADR-010 Decision item 1**, which states credentials are "**synced into the `User` table on every application startup** (create-if-missing, update-if-changed)." This is **Option B**: configuration is authoritative and reconciled every startup, not "provision once and ignore thereafter."

**Consequences (for completeness, not because the choice is open):**
* *Positive:* rotating the password is just "change `AUTH_PASSWORD_HASH`, restart" — no separate admin action or database surgery needed.
* *Negative:* if configuration ever reverts (e.g., a stale `.env` gets redeployed), the active credential silently reverts too, on the next restart. Worth one sentence in `backend/README.md`, not a design change.

No ADR clarification needed — this section closes with the existing decision restated, not reopened.

---

## 5. Session Lifecycle

| Event | Behavior |
|---|---|
| Session creation | On successful login: `AuthSession(user_id, token_hash=sha256(raw_token), started_at=now, last_active_at=now, ended_at=None)`. |
| Token generation | `secrets.token_urlsafe(32)` (256 bits, CSPRNG) — stdlib `secrets`, not `uuid4` or `random`. |
| Token validation | Hash the presented token (sha256), look up by `token_hash`. Not found → 401. Found but `ended_at IS NOT NULL` → 401. Otherwise valid. |
| `last_active_at` | Updated on every successful authenticated request (not just login). |
| Logout | Sets `ended_at = now`. Requires a currently-valid session (goes through the same validation as any authenticated request first). |
| Ended sessions | Permanently invalid — matches the frozen lifecycle's sole transition, `open → ended` (`05_Constraints_and_Integrity.md` §5); no reactivation. |
| **Expired sessions (time-based)** | **Explicitly decided this session: none for Milestone 7.** No automatic idle or absolute timeout. A session remains valid until explicit logout, indefinitely. This was flagged as an open decision (three separate places in the planning brief); the project owner resolved it directly — do not add time-based expiry. |
| Invalid tokens (never existed) | 401. |
| Malformed `Authorization` header (not `Bearer <token>`, empty token, wrong scheme) | 401 — caught explicitly, never an unhandled exception reaching the generic 500 handler. |
| Missing `Authorization` header | 401. |

---

## 6. Session Token Storage

**Recommendation: store a hash of the token, not the raw value** — and it must be a **fast, deterministic hash (SHA-256)**, not `bcrypt`. This distinction matters and is worth being precise about: bcrypt is deliberately slow and per-call-salted, which makes "look up a row by its bcrypt hash" impossible without iterating every row — that's fine for a password (verified against exactly one known user) but wrong for a session token (must be looked up by value across all live sessions on every request). SHA-256 of a 256-bit random token gives an efficient, indexable, unique lookup key while still meaning a stolen database file alone cannot be used to impersonate a session — the raw token is never at rest, only in the client's possession and transiently in memory per-request.

**Flag, per the planning brief's own instruction:** the Logical Data Model's `Session.session_token` attribute is described as "Exchanged credential" — read most literally, that describes storing the credential itself. Storing a hash instead is a *physical realization* choice (the same kind of decision `06_Physical_Design_Strategy.md` makes for other entities), not a change to the logical relationship or any invariant — directly analogous to how `password_hash` doesn't store the literal password either. **This does not require a new ADR** in this plan's assessment: it is consistent with, not contrary to, ADR-010's own security posture, and no compliance rule in ADR-010 specifies the column's physical format. Recommend documenting it as a one-line addition to `06_Physical_Design_Strategy.md` when Stage 3 implements it, not elevating it to a new ADR. Flagged in §19 for explicit confirmation before Stage 3, since it's the one place this plan makes a call ADR-010 didn't literally spell out.

---

## 7. Identity Abstraction

```python
# app/auth/identity.py
@dataclass(frozen=True)
class AuthenticatedIdentity:
    user_id: int
```

* Lives in `app/auth/` — it is a boundary-internal type, not a domain or application concept.
* `get_current_user_id` (unchanged location, `core/dependencies.py`) internally calls `AuthService.verify_token(...)  -> AuthenticatedIdentity`, then returns `identity.user_id` — a plain `int`. **Every existing call site is untouched**: `agent/interface/routes.py`'s `user_id: int = Depends(get_current_user_id)` continues to work exactly as written, satisfying ADR-010's own constraint that only the function's body changes.
* Application use cases (`CreateAgentWorkspaceUseCase`, and the proposed change to `UploadResearchDocumentUseCase` in §8) receive `user_id: int` — never `AuthenticatedIdentity`, never a token, never a `Request` object.
* Domain entities (`Agent`, `Project`, `ResearchDocument`) never see any of this — confirmed unchanged, zero import path from `domain/` to `app/auth/` anywhere in this plan.

---

## 8. Authorization / Ownership

**Current gap, concretely:** `POST /projects/{project_id}/documents` today checks only that the project exists (`ProjectNotFoundError`) — it does not check that it belongs to the caller. In a true single-user system this is harmless today (there is only one possible owner), but it is a real gap the moment real authentication exists: identity and ownership are meant to travel together.

**Recommendation:** add one ownership check, in the **application layer**, not the API layer — consistent with how `CreateAgentWorkspaceUseCase` already enforces its own invariant (one Agent per user) rather than leaving it to the route. `UploadResearchDocumentUseCase.execute()` gains a `user_id: int` parameter; before proceeding, it resolves `Project → Agent → User` (already-available repository calls: `ProjectRepository.get_by_id` → `AgentRepository.get_by_id` on the project's `agent_id` → compare `agent.user_id`) and raises a `ProjectNotFoundError` — **the same error as "doesn't exist,"** not a distinct 403 — if the owning chain doesn't match. Returning "not found" rather than "forbidden" avoids confirming to a caller that a project they don't own exists at all, standard practice for ownership checks.

* **Agent creation:** already correctly scoped (one-Agent-per-user).
* **Document upload:** gains the check above.
* **Future Knowledge/Writing-Style access:** same pattern applies once those modules exist, one hop shorter (Agent-scoped directly, no Project intermediary) — noted for forward consistency, not built now.

This is **not** a general RBAC system: one check, one relationship chain, no roles or permissions table. Flagged in §19 since it's new application-layer behavior not spelled out verbatim by an existing requirement ID (closest: API-037, "protect project data from unauthorized access").

---

## 9. API Contract

| Route | Method | Auth required | Purpose |
|---|---|---|---|
| `/health` | GET | No | Unchanged, stays public. |
| `/auth/login` | POST | No | Verify credentials, issue a session token. |
| `/auth/logout` | POST | Yes | End the current session. |
| `/agents` | POST | **Yes (already wired)** | Unchanged route; `get_current_user_id`'s new body applies automatically. |
| `/projects/{project_id}/documents` | POST | **Yes (dependency must be added)** | Gains identity + the ownership check in §8. |

**`POST /auth/login`** — JSON body (consistent with the rest of this API, which is JSON except the multipart upload's file-bytes exception): `{"username": str, "password": str}` → `{"access_token": str, "token_type": "bearer"}`, status 200. Invalid username **or** invalid password → the same 401 with a generic message (no enumeration of which was wrong). Missing/malformed body → 422 (Pydantic, standard).

**`POST /auth/logout`** — no body; `Authorization: Bearer <token>` only; 204 No Content on success; 401 if the token is missing/invalid/already ended.

**Never exposed:** `password_hash`, `token_hash`, `AuthSession.session_id`, or any other internal session row field — the login response contains exactly `access_token` and `token_type`.

**ADR-008 consistency:** contracts remain code-first (Pydantic schemas + FastAPI routes); OpenAPI is generated, not hand-authored; no new `docs/api/` artifact.

---

## 10. Module / Package Placement

```text
backend/app/auth/
├── __init__.py
├── identity.py       # AuthenticatedIdentity (§7)
├── hashing.py         # bcrypt hash/verify for passwords - separate from tokens.py because
│                       # it's a genuinely different algorithm for a different purpose
├── tokens.py           # secrets.token_urlsafe generation + sha256 hashing for storage (§6)
├── models.py            # AuthSession ORM model - named to avoid the sqlalchemy.orm.Session
│                         # collision ADR-010 Decision item 6 requires avoiding
├── repository.py         # AuthSessionRepository: create, get_by_token_hash, end
├── provisioning.py        # sync_configured_user(db): create-if-missing/update-if-changed (§4)
├── service.py               # AuthService: login(), logout(), verify_token() - the one place
│                             # credential/session orchestration logic is allowed to live
├── schemas.py                # LoginRequest, TokenResponse (Pydantic, HTTP-facing only)
└── routes.py                  # POST /auth/login, POST /auth/logout
```

Nine small, single-purpose files — no folder created for conceptual completeness alone; every file corresponds to one responsibility already named in §3's flow diagram. This mirrors the granularity already used inside e.g. `modules/document/domain/` (separate `entities.py`, `enums.py`, `exceptions.py`, `ports.py`, `repositories.py`), not a new pattern.

**Changes elsewhere:**

| Location | Change |
|---|---|
| `app/core/config.py` | Add `auth_username: str`, `auth_password_hash: str` settings fields. |
| `app/core/dependencies.py` | Rewrite `get_current_user_id`'s body (§7); remove `_BOOTSTRAP_USERNAME` and its now-unused `User` import; add `get_auth_service`-style providers for the login/logout routes, mirroring the existing provider pattern. |
| `app/api/router.py` | Add `from app.auth import routes as auth_routes` + `include_router`. |
| `app/database/session.py` | `init_db()` gains an import of `app.auth.models` so `AuthSession` registers on `Base.metadata`. |
| `app/modules/document/interface/routes.py` | Add the `get_current_user_id` dependency (currently absent entirely) and pass `user_id` through. |
| `app/modules/document/application/use_cases.py` | `UploadResearchDocumentUseCase.execute()` gains `user_id: int` and the ownership check (§8). |
| `app/modules/agent/interface/routes.py` | **No change** — already correctly wired. |
| `main.py` | `lifespan` gains a call to `app.auth.provisioning.sync_configured_user(...)` alongside `init_db()`. |
| `tests/` | See §14. |

---

## 11. Dependency Direction

```text
API (routes)  →  app/auth (boundary)  →  Infrastructure (AuthSession ORM, bcrypt, SQLAlchemy)
API (routes)  →  Application (use cases)  →  Domain (entities)
```

Both directions are acceptable and match the existing architecture exactly — `app/auth` is consumed the same way `app/storage`'s `FilesystemStorage` already is (a boundary/infrastructure dependency injected via `core/dependencies.py`, never imported by domain or application code).

Explicitly verified clean against every prohibited arrow the brief lists:
* **Domain → FastAPI / bcrypt / SQLAlchemy / HTTP:** none — domain entities are unchanged, still framework-free dataclasses.
* **Application → bearer token parsing:** none — `UploadResearchDocumentUseCase` receives a plain `user_id: int`; it never sees a `Request`, a header, or a token.

---

## 12. File Impact Matrix

| File | Category | Why |
|---|---|---|
| `app/auth/*` (9 files, §10) | **Create** | New boundary package authorized by ADR-010. |
| `app/core/config.py` | **Modify** | Add `auth_username`/`auth_password_hash` settings. |
| `app/core/dependencies.py` | **Modify** | `get_current_user_id` body replaced (signature unchanged); new auth-service providers added. |
| `app/api/router.py` | **Modify** | Register `app/auth/routes.py`'s router. |
| `app/database/session.py` | **Modify** | `init_db()` imports `AuthSession` for metadata registration. |
| `main.py` | **Modify** | `lifespan` calls credential-sync alongside `init_db()`. |
| `app/modules/document/interface/routes.py` | **Modify** | Add identity dependency (currently absent). |
| `app/modules/document/application/use_cases.py` | **Modify** | Add `user_id` param + ownership check. |
| `app/modules/agent/interface/routes.py` | **No change** | Already correctly wired. |
| `app/modules/agent/*`, `app/modules/project/*` (domain/application/infrastructure) | **No change** | Confirmed zero impact — identity flows in as a plain int exactly as today. |
| `tests/e2e/conftest.py` | **Modify** | Auth-credential test fixture support (§14). |
| `tests/e2e/test_agent_workspace_api.py`, `test_document_upload_api.py` | **Modify (test only)** | Every unauthenticated call needs a login step or will start returning 401. |
| `tests/unit/`, `tests/integration/` (existing files) | **No change** | These exercise domain/application/persistence directly, not through HTTP identity — unaffected. |
| New `tests/unit/test_auth_*.py`, `tests/integration/test_auth_*.py`, additions to `tests/e2e/` | **Create** | Per §14. |
| `pyproject.toml` | **Modify (Stage 2, not now)** | Add `bcrypt` dependency — not touched in this planning stage. |

**`get_current_user_id` disposition:** **replaced in body, kept in signature and location.** Not wrapped, not deprecated, not removed — this was the explicit design intent from the moment it was written (its own docstring: "Replace this function's body, not its call sites"), and this plan honors that exactly.

---

## 13. Dependency / Package Analysis

* **bcrypt:** not present, direct or transitive. **One new direct dependency required**: `bcrypt` (the package itself, not `passlib` — already decided in ADR-010 Decision item 3, to avoid `passlib`'s known bcrypt-backend version friction).
* **Session token generation/hashing:** no new dependency — `secrets.token_urlsafe` and `hashlib.sha256` are both stdlib.
* **No JWT library needed** — consistent with ADR-010 rejecting stateless JWT.
* Not installed or modified in `pyproject.toml` during this stage, per the brief's constraint.

---

## 14. Testing Strategy

**Unit** (`tests/unit/test_auth_*.py`, no DB):
* Password hashing: correct password verifies true, wrong password verifies false, hash is never equal to the plaintext.
* Token generation: two calls produce different tokens; token has expected entropy characteristics (length/charset, not a statistical entropy test).
* `AuthenticatedIdentity` construction.
* Malformed `Authorization` header parsing (missing "Bearer ", empty token, wrong scheme) → the parsing helper's own unit behavior, independent of the full request cycle.

**Integration** (`tests/integration/test_auth_*.py`, real SQLite via the existing `build_engine`/`init_db` pattern):
* `sync_configured_user`: creates the user when absent; updates `password_hash`/`username` when config changes; does not duplicate on repeated calls (mirrors `test_init_db_is_idempotent`'s style).
* `AuthSessionRepository`: create, get-by-token-hash (found/not-found), end (sets `ended_at`), uniqueness of `token_hash`.
* Login → session row exists with correct `user_id`; logout → `ended_at` set; a second lookup after logout returns "invalid" from the service layer.

**API/E2E** (`tests/e2e/test_auth_api.py` + retrofits to the two existing e2e files):
* Login success (200, correct schema, no password/hash in response).
* Invalid username, invalid password (both 401, same generic message).
* Missing credentials (422).
* Malformed `Authorization` header on a protected route (401).
* Missing `Authorization` header on a protected route (401).
* Authenticated `POST /agents` (201, unchanged from today's behavior once logged in).
* Unauthenticated `POST /agents` (401 — this **replaces** the current "second call is always 409" test's premise; see below).
* Authenticated document upload (201).
* Ownership failure (a project that doesn't belong to the authenticated user → 404, per §8).
* Logout (204), then using the same token again (401).
* `/health` without authentication (200, unchanged).

**Existing tests requiring adaptation (concrete, not hypothetical):**
* `tests/e2e/test_agent_workspace_api.py::test_second_call_for_the_single_bootstrap_user_returns_409` — its docstring explicitly reasons from "every request resolves to the same bootstrap user." Once real login exists, its premise changes: the test should become "the same authenticated user calling `POST /agents` twice → 409" (still valid and still a good test — the *reason* changes from "no auth" to "same logged-in identity," but the assertion is unaffected). Needs a login step added.
* Every other `client.post(...)` call across both e2e test files needs an `Authorization` header from a login fixture, or it will fail with 401 instead of its current expected status.
* `tests/e2e/conftest.py`'s `client`/`db_engine` fixtures need a companion (e.g., `auth_headers(client)`) that seeds a known test `AUTH_USERNAME`/`AUTH_PASSWORD_HASH` via a `Settings`/`get_settings` override (the same `dependency_overrides` mechanism already used for `get_content_store`) and performs a real login call, returning the header dict for reuse.

---

## 15. Security Review

**Required for this milestone:**
* Passwords never logged, never returned in any response — only ever bcrypt-compared.
* `bcrypt`'s own verify function used for comparison (timing-safe by construction) — never a naive `==` on hashes.
* Session tokens generated via `secrets` (CSPRNG), never `uuid4`/`random`.
* Tokens stored hashed (§6), never raw, at rest.
* 401 (not 404/422) for every identity failure — bad username, bad password, missing header, malformed header, invalid token, ended token — with the same generic message where distinguishing would enable enumeration (username vs. password specifically).
* `.env` already gitignored (confirmed in `backend/.gitignore`) — no new secret-exposure surface introduced.
* Test fixtures use an obviously-fake test-only username/password, isolated from any real `.env` by the existing `monkeypatch`/`dependency_overrides` test infrastructure (confirmed: tests never touch the real configured database or settings today, and this plan doesn't change that).
* No internal session fields (`session_id`, `token_hash`, timestamps) ever serialized into an API response.

**Future hardening (explicitly not required for this milestone, not built now):**
* Rate limiting on `POST /auth/login` (already named in ADR-010's Future Considerations).
* Idle/absolute session timeout (explicitly declined this session — §5).
* Audit logging of login attempts.
* HTTPS/transport security enforcement (a deployment concern, ADR-007 territory, not application code).
* Brute-force lockout / failed-attempt throttling.

---

## 16. PostgreSQL Compatibility

* `User.password_hash`, `AuthSession` columns: plain `String`/`DateTime` types, following the exact pattern every existing entity already uses (`Agent`, `Project`, `ResearchDocument`) — no SQLite-specific type introduced.
* Timestamps: same pattern as existing entities (Python-side `datetime.now(timezone.utc)` defaults) — this plan does not introduce a new timestamp convention, and does not attempt to fix the pre-existing question of explicit `DateTime(timezone=True)` typing, since that applies equally to every entity already in the codebase, not something new to auth.
* `token_hash` uniqueness: a standard unique index, Postgres-compatible without change.
* `AuthSession.user_id` FK to `users.user_id`: identical pattern to `Agent.user_id`, `Project.agent_id`.
* Transaction boundaries: reuses the existing `UnitOfWork`/`Session` pattern — no new transactional model.

**Nothing identified that would make a future SQLite → PostgreSQL migration harder.** Alembic is not introduced — the repository does not have it today, and nothing in this plan requires it.

---

## 17. Traceability

* **ADR-010** — governs the entire boundary design (§2-§10 here).
* **`05_Backend_Architecture.md` §15/§15.4** — boundary responsibilities and realized mechanism.
* **`04_Logical_Data_Model.md` §3.1 (`User.password_hash`), §3.2 (`Session`)** — the entities realized.
* **`05_Constraints_and_Integrity.md` §5 (lifecycle), §17 (non-exposure)** — session state transitions and the credential-non-exposure rule, both honored exactly (§5, §15).
* **ADR-008** — API contract remains code-first; honored (§9).
* **NFR-009, NFR-010, NFR-024, MVP-001, API-036, API-037** — the underlying requirements this milestone fulfills.
* **Existing Agent ownership invariant** (one-Agent-per-user) — unaffected, already correct.

**Traceability gap identified:** the Document-ownership check proposed in §8 is a reasonable extension of API-037 but isn't the literal text of any existing requirement ID. Flagged, not silently added — see §19.

---

## 18. Implementation Staging Proposal

| Stage | Objective | Key files | Tests | Gate |
|---|---|---|---|---|
| **2 — Boundary Scaffolding** | `app/auth/` package skeleton exists; `bcrypt` added to `pyproject.toml`; `Settings` gains the two config fields. No behavior yet. | `app/auth/__init__.py` + empty modules; `pyproject.toml`; `config.py` | Boot smoke test only | App still boots, `/health` still 200 |
| **3 — Persistence** | `AuthSession` ORM model + repository; registered in `init_db()`. | `models.py`, `repository.py`, `session.py` | Integration: create/get/end/uniqueness | Schema creates cleanly, existing 66 tests still pass |
| **4 — Credential Provisioning** | `hashing.py`, `provisioning.py`; wired into `main.py` lifespan. | `hashing.py`, `provisioning.py`, `main.py` | Integration: create-if-missing, update-if-changed, idempotent | Fresh boot provisions the configured user correctly |
| **5 — Login/Logout Service + API** | `tokens.py`, `service.py`, `schemas.py`, `routes.py`; router wired. | all remaining `app/auth/*`, `api/router.py` | Unit (hashing/tokens) + API (login/logout happy+error paths) | Login/logout work over real HTTP in isolation |
| **6 — Authenticated Request Integration** | `get_current_user_id` rewritten; dependency added to the document route. | `core/dependencies.py`, `document/interface/routes.py` | API: authenticated/unauthenticated on both business routes | Both business routes correctly require auth |
| **7 — Authorization/Ownership** | `UploadResearchDocumentUseCase` gains `user_id` + ownership check. | `document/application/use_cases.py` | Unit + integration: ownership failure case | Cross-owner access correctly rejected |
| **8 — Testing & Final Validation** | Full regression; fresh-environment real-HTTP exercise (mirroring Milestone 6 Stage 6); security review re-confirmation; OpenAPI re-inspection; governance sync. | test suite, `Project_Status.md`, journal | Full suite green | Milestone 7 complete |

Each stage stops for explicit authorization before the next begins, per the established discipline — this plan does not authorize auto-progression.

---

## 19. Risks and Unresolved Decisions

These are the plan's own recommendations, not blocking questions — flagged explicitly per the brief's instruction not to silently decide, awaiting a quick confirm-or-redirect before Stage 2:

1. **Token storage: hashed (SHA-256), not raw** (§6). Recommended, not a new ADR in this plan's assessment — but it is a deviation from the Logical Data Model's literal "exchanged credential" wording, so flagged for explicit sign-off.
2. **Document ownership check** (§8) — new application-layer behavior, reasonable extension of API-037 but not its literal text.
3. **Login body format: JSON, not OAuth2 form-encoding** (§9) — low-stakes, easily changed, but a real choice made without a separate question.
4. **`AUTH_PASSWORD_HASH` generation tooling** — recommend a documented one-liner in `backend/README.md` (e.g., a `python -c "..."` command using `bcrypt` directly) rather than a new script file, to avoid file proliferation for a one-time operational step. Needs confirmation before Stage 2 so the README update has a settled answer.

**Already resolved, recorded here for completeness, not open:**
* Idle/absolute session timeout — none, per explicit decision this session (§5).
* Credential provisioning semantics — Option B, already decided by ADR-010 (§4).

---

## 20. Final Readiness Verdict

**READY FOR STAGE 2**

The plan is complete and internally consistent; every explicit "do not silently decide" instruction in the brief has either been resolved by ADR-010 directly, resolved by the project owner this session (timeout), or carried forward as a clearly-flagged, low-stakes recommendation (§19, items 1-4) rather than left as an invented assumption. None of the four flagged items block starting Stage 2's scaffolding — they matter starting Stage 3 (persistence format) and Stage 5 (login contract), so there is time to confirm them without stalling.
