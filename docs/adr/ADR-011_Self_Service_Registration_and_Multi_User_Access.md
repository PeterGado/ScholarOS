# ADR-011: Self-Service Registration and Multi-User Access

**Status:** Accepted

**Date:** 2026-09-18

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** ADR-010's Decision item 1 and Compliance Rules' exclusion of registration/multi-account endpoints, and its Future Considerations item naming multi-user support as deferred. Everything else in ADR-010 (bcrypt hashing, the `Session`/`AuthSession` model, no automatic expiry, the naming-collision note) is unchanged and remains binding.

---

## Status

**Accepted.** The project owner has decided to open the application to real friend-testing, with an intent to eventually monetize a fully public version. This ADR authorizes real self-service registration and confirms the existing per-user isolation model extends to multiple real accounts without redesign.

---

## Context

ADR-010 built a real Authentication Boundary for exactly one pre-provisioned account, explicitly excluding registration and multi-account endpoints, citing the MVP's own Out-of-Scope table ("multi-user collaboration... authentication, authorization, and concurrency complexity beyond MVP scope"). That exclusion was correct for the MVP as originally scoped: a single personal tool, one user, no external access.

The project owner now wants friends to be able to use the application independently, each with their own isolated data, ahead of a real public/monetized deployment. Sharing the one existing account is not viable — every friend would see and could overwrite the others' documents, chats, and Writing Profile.

**A close reading of the existing implementation shows this requires far less change than ADR-010's own framing implied.** `User` (04 §3.1) already carries `username`/`password_hash`/`status` — no schema change. `AuthService.login()` already resolves credentials generically via `UserCredentialLookup.get_by_username()` — it was never hardcoded to one specific user, only ever provisioned with one. Every ownership check across every module (Agent, Project, Document, Knowledge, Writing, Memory, Conversation) resolves through `user_id`/`agent_id` generically, confirmed directly by this project's own Milestone 7 (Real Authentication Boundary) Stages 6-8 audit (2026-09-18): a fresh-environment live check proved cross-user access correctly rejected end to end. The one-Agent-per-User invariant (ADR-009) was never a one-*account*-per-system invariant; it already generalizes to many accounts, each reaching it once.

---

## Problem

How should ScholarOS allow multiple real people to create their own accounts, in a way that:

1. Reuses the existing Session/AuthSession model and per-user ownership isolation without redesigning either;
2. Protects the shared AI provider quota (one Gemini API key, used by every account) during a friends-only testing phase;
3. Does not permanently foreclose the stated future goal of fully open, monetized public access;
4. Keeps the Authentication Boundary independent of domain logic, per ADR-010 Decision item 5/§15.3 — unchanged by this ADR.

---

## Decision

1. **A real registration endpoint, `POST /auth/register`.** Takes a username and password, creates a new `User` row (via the existing `hash_password`, `app/auth/hashing.py` — no new hashing code), and immediately returns a session token via the existing login/session machinery (ADR-010 Decision item 2, unchanged) — no separate "confirm your account" step. No email, no email verification, no password reset flow — none of those are required by the stated goal (friend-testing, then a fully public product) and are not built here; they remain open questions for whenever they become load-bearing.

2. **Gated by an optional, config-driven invite code — not a permanent restriction.** `Settings.registration_invite_code` (env var `REGISTRATION_INVITE_CODE`): when set, `POST /auth/register` requires a matching `invite_code` field, rejecting a wrong or missing one exactly as ADR-010's login already collapses "wrong username" and "wrong password" into one non-enumerating rejection. When unset (empty), registration is open to anyone who can reach the endpoint. This is a deliberate two-phase design: gated now (friend-testing, protecting the shared Gemini quota), removable later by an operator changing one environment variable — never a code change — when the project owner is ready for the fully public, monetized phase this ADR's Context names as the eventual goal.

3. **No change to account cardinality's downstream consequences.** Each registered account gets exactly one Agent Workspace via the existing one-Agent-per-User flow (ADR-009), created the same way it already is today (first `POST /agents` call, or the frontend's existing onboarding flow) — registration only creates the `User` row; it does not itself create a workspace.

4. **`sync_configured_user` (ADR-010 Decision item 1) is unchanged and continues to run.** The project owner's own pre-provisioned account (via `AUTH_USERNAME`/`AUTH_PASSWORD_HASH`) remains the one account synced from configuration on every startup — registration is purely additive alongside it, not a replacement.

5. **Rate limiting on `POST /auth/login` and `POST /auth/register` remains an open item**, carried forward from ADR-010's own Future Considerations (which already flagged this "worth revisiting before any non-local/non-personal deployment"). Now that a real non-local deployment is in scope, this is flagged again, explicitly, as not resolved by this ADR — a real gap once the app is reachable by anyone with the invite code (or, later, by anyone at all).

---

## Rationale

* **Reuses what's already proven, adds nothing structurally new.** No new session model, no new ownership-check pattern, no new hashing code — this is additive on top of already-audited machinery (see Context).
* **The invite-code gate is a config toggle, not an architecture decision baked into the code path.** It can be lifted without a future ADR (removing a restriction this ADR itself authorizes as temporary is not the same as the account-cardinality decision ADR-010 made, which did need one) — though the project owner should still record in the journal when it's lifted, per this project's own "record state transitions" discipline.
* **Protects real, metered cost during the friend-testing phase** without building anything (billing, per-user quotas) that isn't yet needed for a small, invite-only group.

---

## Alternatives Considered

### Alternative 1: Give each friend a manually pre-provisioned account (extend `sync_configured_user` to a list)

**Rejected because:** the project owner's stated goal extends past friend-testing to full public access; building a config-driven allowlist now would need replacing with real registration later anyway. Building registration once, gated now and ungated later, avoids doing this twice.

### Alternative 2: Fully open registration, no gate at all

**Rejected because:** the AI provider quota (one shared Gemini key) is a real, metered resource; an ungated public registration endpoint found by anyone (not just invited friends) during the testing phase risks exhausting it for no product benefit yet. Revisit when real per-user cost controls (billing, per-user rate limits) exist.

### Alternative 3: Email-based registration with verification

**Rejected for now because:** the stated near-term goal is friend-testing; email verification adds a real external dependency (an email-sending service) and a flow with no present requirement driving it. Not foreclosed for later — a genuinely public, monetized launch may well need it — but that is a separate, future decision.

---

## Consequences

### Positive

* Friends can test the application with fully isolated accounts and data, no code path shared with the owner's own account beyond what already exists.
* The path to fully public access is a config change (clear the invite code), not a future rearchitecture.
* Zero changes to Agent/Project/Document/Knowledge/Writing domain or application code — confirmed by this ADR's own Context; only `app/auth/` gains a new, additive capability.

### Negative

* The `users` table now has no upper bound on account creation while ungated (post-invite-code-removal) — no housekeeping/cleanup is built for abandoned or abusive accounts. Acceptable for now; revisit before a genuinely public launch.
* No rate limiting on registration or login (carried forward from ADR-010, restated here) — a real gap once the app is reachable outside this machine, regardless of the invite-code gate.

### Neutral

* This ADR does not decide billing, quotas, or per-user resource limits for the eventual public/monetized phase — those are separate, future decisions this ADR does not attempt to anticipate.

---

## Repository Impact

* `app/auth/`: new `registration.py` (`RegisterUserUseCase`), new exceptions (`UsernameAlreadyTakenError`, `WeakPasswordError`, `InvalidInviteCodeError`), new `RegisterRequest` schema, new `POST /auth/register` route.
* `app/core/config.py`: new `registration_invite_code: str | None` field.
* `docs/database/*`, `docs/architecture/*`: no change — no schema or architectural-boundary change, per Rationale above.
* `docs/Baseline_Register.md`: no change — this ADR does not correct a frozen baseline document, unlike ADR-009/ADR-010.

---

## AI Engineering Implications

* `RegisterUserUseCase` must reuse `hash_password`/`verify_password` (`app/auth/hashing.py`) exactly as `AuthService` does — no parallel hashing implementation.
* The invite-code comparison must not leak, via timing or error-message content, whether a supplied invite code was "close" to correct or whether a given username already exists when the invite code itself was wrong — mirror `AuthService.login`'s existing non-enumerating precedent.
* `REGISTRATION_INVITE_CODE` must be read through the existing `Settings` pattern, never hardcoded or read ad hoc, per ADR-010 Decision item 1's own precedent for `AUTH_USERNAME`/`AUTH_PASSWORD_HASH`.

---

## Compliance Rules

* Registration creates exactly one `User` row per call; it never creates an Agent Workspace directly (that remains the existing, separate onboarding flow).
* When `REGISTRATION_INVITE_CODE` is set, no registration may succeed without a matching code — enforced in `RegisterUserUseCase`, never duplicated or re-checked elsewhere.
* Password hashing continues to use `bcrypt` via the existing `app/auth/hashing.py` functions exclusively (ADR-010 Decision item 3, unchanged).

---

## Related ADRs

| ADR | Relationship |
|---|---|
| ADR-009 (Agent and Project Domain Model Introduction) | The one-Agent-per-User invariant this ADR relies on generalizing to many users without change. |
| ADR-010 (Authentication Boundary — Single-User Session Model) | This ADR supersedes its account-cardinality exclusion only; every other decision in ADR-010 remains binding, per this document's own header. |

---

## Future Considerations

* **Removing the invite-code gate** for a fully public launch: a configuration change (clear `REGISTRATION_INVITE_CODE`), not a code change — record the transition in the journal when it happens.
* **Rate limiting** on `/auth/login` and `/auth/register`: still not addressed, carried forward from ADR-010 and restated here as more urgent now that real external deployment is in scope.
* **Billing/monetization and per-user quotas**: explicitly out of scope for this ADR; a future decision for whenever the fully public phase is actually scoped.
* **Password reset / email verification**: not built; revisit if/when they become load-bearing for the public phase.

---

## References

* `docs/adr/ADR-009_Agent_and_Project_Domain_Model_Introduction.md`
* `docs/adr/ADR-010_Authentication_Boundary_Single_User_Session_Model.md`
* `docs/Project_Status.md` (Milestone 7 Stage 7 audit, 2026-09-18 — the cross-user isolation evidence this ADR's Context relies on)
