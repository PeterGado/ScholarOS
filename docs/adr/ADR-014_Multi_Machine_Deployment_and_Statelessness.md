# ADR-014: Multi-Machine Deployment — Eliminating the Single-Machine Point of Failure

**Status:** Accepted (2026-10-10, same day as proposal) — the ADR was written and reviewed before any infrastructure change was made, per the explicit lesson ADR-012 and ADR-013 both record (an ADR should precede implementation, not follow it), then accepted and implemented immediately given the small, well-verified scope of Decision items 1–2.

**Date:** 2026-10-10

**Author:** Lead AI Software Engineer

**Governance Framework:** Engineering Governance Framework v2.0

**Supersedes:** Nothing is removed or reversed. This ADR narrows ADR-007 Decision item 1's "single-node" MVP framing for the specific, now-outgrown case of the backend's own machine count. It does not revisit ADR-003 (Modular Monolith) or ADR-006 (in-process async executor): this ADR proposes running more copies of the same single deployable unit, not splitting it into separate services.

---

## Status

**Accepted and implemented (2026-10-10).** This ADR was written and reviewed as a design proposal *before* `backend/fly.toml` or `backend/Dockerfile` were touched — unlike ADR-012 and ADR-013, which recorded decisions already live in production, this one follows the order those two ADRs' own Future Considerations/AI Engineering Implications sections say should have been followed from the start. Once reviewed, the small, fully-verified scope of Decision items 1–2 (a configuration change plus a one-line `Dockerfile` edit, with no code change) was accepted and implemented the same day.

---

## Context

The single-machine backend deployment has been flagged repeatedly, independently, as a real availability risk — not a hypothetical one: the project owner's own direct instruction ("make it stateless," "multiple servers"), and [ADR-013](ADR-013_Production_Deployment_Cutover_and_Schema_Growth.md) Decision item 2, which recorded `min_machines_running = 1` as current reality and flagged it in its own Future Considerations as "the next thing expected to change."

`backend/fly.toml`'s own comment gives the actual reason the backend has stayed at one machine: the in-process Work Item executor (ADR-006) needs to keep polling continuously, so the one machine can never be allowed to auto-stop. Nothing in that reasoning ever ruled out running *more* machines — it was simply never decided or done.

**Independently, and found while researching this ADR**, the codebase already contains three pieces of dated, explicit evidence that a prior session anticipated and partly prepared for exactly this move, without ever finishing or formally deciding it:

1. `WorkItemRepository.claim_next_queued()` (2026-09-30): *"On Postgres, uses a single atomic UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED) ... so two callers can never both come back with the same row."* This already safely handles N concurrent claimers today — the executor's own `work_item_worker_count` threads within one process — using a database-level locking primitive that is exactly as safe across separate processes as it is across threads in one process. Nothing about this mechanism assumes a single machine.
2. `WorkItemRepository.requeue_stale_running()` (2026-09-30): the same `FOR UPDATE SKIP LOCKED` protection, with a docstring stating outright: *"not a concern yet with this rollout's single-machine design, but cheap to make correct now ... for two Fly machines restarting together."*
3. `PostgresRateLimitStorage` (2026-09-21): replaces `slowapi`'s default in-memory store specifically, per its own docstring, *"so that rate-limit state ... would work correctly if this app is ever run on more than one machine (ADR-006 pins it to one today)."*

Beyond those three, a direct search of the codebase for other in-process state (module-level mutable caches, global variables) found none beyond `get_settings()`'s `@lru_cache` over the immutable settings object (safe — identical, deterministic across processes) and each `WorkItemExecutorLoop`/`QueueHealthMonitor` instance's own thread-lifecycle bookkeeping (not shared or business state). Session and authentication state is already entirely database-backed (`AuthSession`, ADR-010) — there is no sticky-session requirement to design around. Row-Level Security's tenant-isolation context (ADR-013 Decision item 3) is set per-transaction from a per-request value, never from anything process-global, so it is correct regardless of machine count by construction. ADR-004 Decision item 5's "in-process working cache for assembled context" was never actually implemented — `context_assembly.py` is a pure function with no caching layer, so there is no cache-coherence question to design around either.

**In short: the application is already close to stateless by the ordinary meaning of the term.** The actual gap between today and a redundant, multi-machine deployment is narrower and more concrete than "make it stateless" might suggest on its own.

---

## Problem

What specifically stands between the current single-machine deployment and running two or more machines safely, and what is the smallest correct change that closes that gap — without designing for a scale this project does not have, per this ADR's own non-functional requirements (below) and the architecture-designer discipline of planning for the actual failure mode (one machine going down) rather than a hypothetical high-throughput future?

---

## Non-Functional Requirements

Stated explicitly, since none were written down anywhere before this ADR:

- **Availability target:** no single machine failure (crash, host maintenance, bad deploy) should cause a full backend outage. No formal uptime percentage is set — this is a personal-scale MVP, not a service with an SLA, and inventing one would be exactly the kind of unsupported number [`docs/Product_Requirements_Document.md`](../Product_Requirements_Document.md) §9 already flagged this project as not having for its own success criteria.
- **Scale target:** unchanged from today — this project has no measured concurrent-user or request-volume figures anywhere in the repository (confirmed while researching the Technical Design Document). This ADR is about redundancy, not throughput; it explicitly does not plan for a scale this project has no evidence it needs.
- **Deployment strategy:** zero-downtime rolling deploys, building on Fly's existing rolling-strategy behavior (already observed in this project's own deploy logs: machines are updated one at a time, each passing health checks before traffic moves to it).
- **Cost:** a second `shared-cpu-1x`/512mb machine (`backend/fly.toml`'s current `[[vm]]` size), roughly doubling backend compute cost — named directly in Consequences, not hidden.

---

## Decision

1. **Run at least two Fly machines for the backend** (`min_machines_running = 2` in `backend/fly.toml`), eliminating the literal single point of failure. Both machines run the identical container image — web server and Work Item executor together, exactly as today (ADR-006) — not a new service or a new deployable unit.

2. **Move schema migration out of each machine's own startup into a Fly `release_command`**, run exactly once per deploy, before new machines receive traffic — rather than `backend/Dockerfile`'s current `CMD alembic upgrade head && uvicorn ...`, which runs the migration on every machine's own boot. This is the one genuine correctness gap that running multiple machines introduces and a single machine never could: `alembic upgrade head` is safe to run once, but is not designed to be run concurrently by several processes against the same database without a coordinating coordination point, and Fly's deploy model already provides exactly that natively.

   Concretely: `backend/Dockerfile`'s `CMD` becomes `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers` only; `backend/fly.toml` gains:
   ```toml
   [deploy]
     release_command = "alembic upgrade head"
   ```

3. **No other code change is required.** Every other item that would normally need verification for a multi-machine move is already safe, cited in Context above: Work Item claiming and stale-running recovery (`SKIP LOCKED`), rate limiting (`PostgresRateLimitStorage`), session/auth (DB-backed `AuthSession`), Row-Level Security (per-transaction, not process-global).

4. **`work_item_worker_count` (currently 3 threads per machine) is left unchanged.** With 2 machines, total concurrent claimers rises from 3 to 6 — still small relative to this project's actual, unmeasured-but-evidently-personal-scale load, and `SKIP LOCKED` claiming has no coordination cost that scales badly with claimer count at this scale. Revisit only if real contention is actually observed (Future Considerations).

5. **The unified web+executor process shape is kept; splitting web and worker into independently-scalable Fly process groups is explicitly out of scope for this decision.** [`07_Operational_Architecture.md`](../architecture/07_Operational_Architecture.md) §5.3 already names "modular boundaries ... permits selective extraction ... when a boundary proves to be a scaling or team bottleneck" as a lever for later, *conditional* use — that condition (an actual observed bottleneck) does not exist yet, and designing the split now would be solving a problem this project does not have.

---

## Rationale

* **Most of the real work already happened, undated and undecided — this ADR's job is to verify it, name the one real gap, and decide to finish it**, not to design a new system. Items 1 and 3 are closer to a configuration change plus a verification record than a design.
* **`release_command` is the Fly-native answer to the migration-race question**, not a novel mechanism this project would need to build and maintain — using the platform's own coordination point is simpler and more visible than wrapping the migration in an application-level advisory lock (see Alternative 2).
* **Keeping the unified process shape (Decision item 5) matches this project's own established discipline** of staging infrastructure changes to the smallest one that solves the actual, current problem (ADR-004 and ADR-007's own MVP-stage reasoning, and ADR-013's confirmation of how that staging actually played out) — redundancy is the problem this ADR solves; independent web/worker scaling is a different problem this project has no evidence it has yet.

---

## Alternatives Considered

### Alternative 1: Split web and worker into separate Fly process groups now

**Rejected for now:** no observed bottleneck motivates it yet — see Decision item 5. Named explicitly in Future Considerations as the next lever if a single process group stops being enough, consistent with `07_Operational_Architecture.md` §5.3's own framing of this as a later, conditional lever rather than a default.

### Alternative 2: Wrap `alembic upgrade head` in a Postgres advisory lock inside the existing per-machine `CMD`, instead of a `release_command`

**Considered, rejected:** would work, but reinvents a coordination mechanism the deployment platform already provides more simply and more visibly — a failed `release_command` fails the deploy cleanly before any new machine ever receives traffic; a failed advisory-lock-wrapped migration buried inside a machine's own boot sequence is harder to distinguish from any other startup failure during an incident.

### Alternative 3: Move off the Postgres durable-outbox pattern to a message-broker-based queue (e.g. SQS, Redis-backed)

**Rejected:** [ADR-006](ADR-006_Async_Processing_and_Event_Coordination.md) already made and justified this decision, and nothing about running multiple machines requires revisiting it — `SKIP LOCKED` claiming already provides the same exactly-once-claim guarantee a broker would, with no new operational dependency.

### Alternative 4: Set a specific numeric availability SLA (e.g. 99.9%) for this ADR's Non-Functional Requirements section

**Rejected:** no traffic, incident, or reliability data exists anywhere in this repository to ground a specific number in — inventing one would be exactly the kind of unsupported figure the Product Requirements Document already flagged as absent from this project's own success criteria (§9). The qualitative target ("no single machine failure causes a full outage") is honest about what is actually known.

---

## Consequences

### Positive

* Eliminates the literal single point of failure for both the API tier and background processing, closing the gap the project owner and ADR-013 both named directly.
* Enables genuine zero-downtime rolling deploys — a new machine passes its health check and receives traffic before the old one is removed — directly addressing the "if it crashes, can you roll back? instant recovery" requirement for the ordinary case of a bad deploy or a single machine fault. (Full blue-green — instantly promoting the *previous release*, not just another machine on the current one — is a larger, separate decision; see Future Considerations.)
* No new operational dependency: no Redis, no message broker, no second platform account. The entire concrete change is a `fly.toml`/`Dockerfile` edit plus verifying what the codebase had already quietly built toward.

### Negative

* Roughly doubles backend compute cost (one more `shared-cpu-1x`/512mb machine) — a real, small, named cost, not hidden in this decision.
* `QueueHealthMonitor` (added earlier in the same session as this ADR) and its Sentry reporting now run redundantly on each machine — harmless (Sentry deduplicates identical messages by default) but not deduplicated at the source. Accepted as a minor inefficiency rather than solved now; revisit only if it proves noisy in practice.

### Neutral

* This ADR confirms, more than it changes, how the application already behaves — most of its length is a verification record of existing, dated engineering work, not new design.

---

## Repository Impact

**Made, 2026-10-10:**

* `backend/fly.toml`: `min_machines_running` 1 → 2; new `[deploy] release_command = "alembic upgrade head"`.
* `backend/Dockerfile`: `CMD` no longer runs `alembic upgrade head`.
* `docs/architecture/07_Operational_Architecture.md`: cross-reference addition noting this ADR as the realization of §5.3 item 3 ("Stateless API tier ... so API instances scale horizontally").
* `docs/roadmaps/Engineering_Plan.md` §3.1: updated to reference this ADR as scoped and implemented, in place of the previously-open "stateless, multi-server architecture" item.
* `docs/Baseline_Register.md`: new correction line for Architecture Baseline v1 (its fourth), narrowing ADR-007 Decision item 1's single-node MVP framing — the same correction discipline ADR-009/010/013 already established.

---

## AI Engineering Implications

* No application code changes are proposed — this is an infrastructure-configuration decision plus a verification record.
* Any future work that *would* require an application code change for multi-machine correctness (e.g., introducing new in-process state) must re-verify against this ADR's Context section before assuming it is safe — the absence of in-process state was confirmed by direct search for this ADR, not asserted from memory, and that search does not automatically stay true as the codebase grows.
* Splitting web and worker into separate process groups (Alternative 1) should itself get a new ADR before implementation if it is ever pursued, per the same lesson ADR-012 and ADR-013 both record.

---

## Compliance Rules

* No new module-level mutable state (caches, counters, in-memory registries) may be added to the backend without an explicit multi-machine-safety review — the guarantee this ADR relies on (no hidden in-process state) is a standing constraint, not a one-time check.
* Any change to `backend/fly.toml`'s machine count or `backend/Dockerfile`'s `CMD`/release process should be treated as touching this ADR's Decision items 1–2, not as a routine deployment tweak.

---

## Related ADRs

| ADR | Relationship |
|---|---|
| ADR-003 (Modular Monolith) | Unchanged — this ADR runs more copies of the same deployable unit, not a service split. |
| ADR-006 (Async Processing and Event Coordination) | The durable-outbox/`SKIP LOCKED` design this ADR relies on for safe multi-machine claiming was already specified here; this ADR is the first to actually exercise it across more than one process. |
| ADR-007 (Deployment Strategy) | Decision item 1's "single-node" MVP framing is narrowed by this ADR for the backend's machine count specifically; ADR-007's broader staged-deployment philosophy is unchanged. |
| ADR-010 (Authentication Boundary) | The DB-backed `AuthSession` design this ADR relies on for stateless session handling across machines was already decided here. |
| ADR-013 (Production Deployment Cutover and Schema Growth) | Named the single-machine fact as "the next thing expected to change" in its own Future Considerations; this ADR is that change, proposed. |

---

## Future Considerations

* **Full blue-green deployment** (instantly promotable rollback to the previous release, not just redundancy within the current one) if rolling-deploy-with-health-checks ever proves insufficient to shrink a bad deploy's blast radius fast enough.
* **Splitting web and executor into separate Fly process groups** (Alternative 1) if their resource needs actually diverge in practice — not designed now, named here so it is reached for deliberately rather than reinvented under pressure.
* **Revisiting `work_item_worker_count`** if real claim contention is observed under two or more machines (Decision item 4) — not expected at this project's current scale, but not asserted as permanently fine either.
* **External uptime monitoring for `/health/queue`**, already named in [`docs/roadmaps/Engineering_Plan.md`](../roadmaps/Engineering_Plan.md) §3.2, becomes more valuable once multiple machines each have their own health worth distinguishing.

---

## References

* `backend/fly.toml`, `backend/Dockerfile` — the two files this ADR's concrete changes touch.
* `backend/app/workers/repository.py` (`claim_next_queued`, `requeue_stale_running`) — the already-built multi-claimer-safe locking this ADR relies on.
* `backend/app/core/rate_limit_storage.py` (`PostgresRateLimitStorage`) — the already-built DB-backed rate limiting this ADR relies on.
* [`docs/Technical_Design_Document.md`](../Technical_Design_Document.md) §10 item 1 — the single-machine limitation as recorded before this ADR proposed closing it.
* [`docs/roadmaps/Engineering_Plan.md`](../roadmaps/Engineering_Plan.md) §3.1 — the medium-term item this ADR is scoping.
* [`docs/Product_Requirements_Document.md`](../Product_Requirements_Document.md) §9 — the absence of quantitative success/scale metrics this ADR's Non-Functional Requirements section is honest about rather than inventing around.
* ADR-003, ADR-006, ADR-007, ADR-010, ADR-013.
