# Deferred Checklist

**Document:** Deferred_Checklist.md

**Status:** Active - tracking items intentionally not actioned during the 2026-10-11
production-readiness pass, grouped by what actually unblocks each one.

**Date:** 2026-10-11

---

## 1. Purpose

A real external checklist (40 items, covering SEO/frontend polish, security hardening, and a
few bigger feature asks) was triaged against the codebase on 2026-10-11. Most items were
already done or structurally not applicable to this architecture - see
`docs/Production_Security_Confirmation.md` for that full accounting. This document tracks only
the items that were deliberately *not* actioned, organized by the real-world trigger that would
make each one worth doing - not a TODO list to work through immediately.

---

## 2. Blocked on a custom domain

These are currently fine on the free-tier/`.vercel.app`/`.fly.dev` setup, but become real
decisions the moment a custom domain exists.

### 2.1 Transactional email sender address

**Current:** `password_reset_from_address` (`backend/app/core/config.py:234`) defaults to
`ScholarOS <onboarding@resend.dev>` - Resend's own shared sender address, usable with zero
domain setup.

**When a domain exists:** verify a sending domain in Resend (SPF/DKIM records), then switch
this setting to a real address on that domain (e.g. `ScholarOS <noreply@yourdomain.com>`).
Shared sender addresses are more likely to be flagged by spam filters than a verified custom
domain, and `onboarding@resend.dev` visibly signals "unconfigured" to anyone who reads a reset
email closely.

### 2.2 CORS allowed origins

**Current:** `cors_allowed_origins` (`backend/app/core/config.py:165`) defaults to only the
local dev origins; production is presumably configured via the `CORS_ALLOWED_ORIGINS` env var
to the real `*.vercel.app` URL (verify the live Fly secret value when touching this).

**When a domain exists:** add the new domain to the allowed-origins list. Forgetting this step
after a domain migration silently breaks every authenticated request from the new domain (CORS
rejects it client-side) without an obviously-related error message.

### 2.3 Cloudflare Turnstile widget hostname

**Current:** the Turnstile widget (Cloudflare dashboard) is configured for
`scholaros-frontend-nine.vercel.app` only.

**When a domain exists:** add the new hostname to the same widget (Cloudflare lets you edit the
hostname list without recreating the widget/site key). Registration from an unlisted hostname
fails Turnstile verification.

### 2.4 Meta tags / OG image / canonical URLs

**Current:** `frontend/index.html`'s `og:url`, canonical links, and any hardcoded
`*.vercel.app` references point at the current domain.

**When a domain exists:** update these to the real domain - low priority (doesn't break
functionality, only social-preview/SEO accuracy) but easy to forget since nothing fails loudly
if left stale.

---

## 3. Blocked on a paid tier

### 3.1 Neon (database)

**Current real limits, confirmed 2026-10-11** (free tier):
- **Connections:** 104 total, 7 reserved for the superuser, 97 usable. Connection pool settings
  (`web_engine_pool_size`/`max_overflow`, `worker_engine_pool_size`/`max_overflow`,
  `backend/app/core/config.py`) were retightened against this real number - worst-case ceiling
  is now 60 across 2 Fly machines, ~37 of headroom.
- **Backup/PITR:** 6-hour point-in-time rollback window, 1GB WAL history cap, exactly one
  manual snapshot (already taken 2026-10-11 to lock in a recovery point).

**When upgrading Neon's plan:** re-verify the real connection ceiling and consider loosening
the pool settings back up if genuinely needed under real load (don't loosen pre-emptively -
only if connections are observed timing out waiting for the pool). Re-evaluate the PITR window
- a longer window than 6 hours meaningfully changes the real-world recoverability story for a
disaster-recovery scenario discovered late. More than one manual snapshot also becomes
available, worth using for pre-deploy checkpoints before risky migrations.

### 3.2 VirusTotal (upload malware scanning)

**Current:** `app.core.virus_scan.is_known_malicious` (`backend/app/core/virus_scan.py`) does a
free-tier **hash-only lookup** against VirusTotal's existing analysis database - it catches
already-known malware by SHA-256 hash, but will never catch a brand-new, never-before-seen
malicious file, since that would require uploading the actual file content for a fresh scan.
Free tier is also rate-limited (check VirusTotal's current published limits before relying on
high upload volume - they change their tier structure periodically).

**On a paid VirusTotal tier:** consider adding real file-upload-and-scan as a second layer,
most naturally wired into the existing async Work Item executor pipeline (mirrors how document
extraction already happens in the background) rather than blocking the synchronous upload
request - VirusTotal's own file-analysis flow is asynchronous (minutes, not seconds) and
doesn't fit cleanly into a request/response cycle. This is a real architecture change, not a
config flip - scope it properly when it's actually being built, including what happens to a
document already stored/queued by the time a delayed scan comes back positive.

### 3.3 Fly.io (compute)

**Current:** 2 machines, `shared-cpu-1x:512MB` each (ADR-014). Fine for the project's actual
current traffic.

**On a paid Fly tier / real growth:** this is the natural trigger for the 500k-concurrent-user
scaling question (§4.1 below) - don't do capacity planning for a traffic level that isn't real
yet, but this is the signal that it's time to.

---

## 4. Deferred by explicit choice (2026-10-11), not blocked on anything specific

These were deliberately not scoped when offered, independent of domain/tier - revisit only when
there's a real, concrete trigger (not just because this list exists).

### 4.1 500k-concurrent-user architecture

A real capacity-planning exercise (connection pooling at that scale, horizontal scaling beyond
2 machines, caching, CDN in front of the API, database read replicas) - likely far beyond what
this project needs today. Don't start this speculatively; start it when real traffic growth
makes it a genuine near-term concern, not a hypothetical one.

### 4.2 Turnitin-style originality-check feature

**Important distinction, easy to conflate:** this is a *different* idea from the
already-declined "AI-detector evasion" feature (helping AI-generated text slip past
Turnitin/GPTZero undetected - declined earlier, documented in `docs/Project_Status.md`,
`docs/Product_Requirements_Document.md`, `docs/vision/Vision.md`, as facilitating academic
dishonesty). This item is the opposite, legitimate use case: letting a user check their *own*
document's originality before submitting it, the same thing a university's own Turnitin
integration already does for them. If this is ever pursued, scope it as its own real research
task first - Turnitin's actual API access/cost/partnership requirements are not a simple public
signup, unlike VirusTotal or Cloudflare.

### 4.3 General web search (beyond Wikipedia)

Wikipedia-backed background enrichment already exists and is live
(`backend/app/ai/wikipedia.py`, wired into `context_assembly.py`). General web search (e.g. via
Firecrawl or a similar provider) for grounding AI replies in live, non-Wikipedia web sources
does not exist. Needs a real provider/cost decision before scoping.

### 4.4 Loading/error state for the Wikipedia search step specifically

Bundled with §4.3 when originally raised, but actually a smaller, separable question: does the
frontend show a clear loading/error state *specifically* for the Wikipedia background-enrichment
step during chat reply generation, or does it only show the generic "thinking" state for the
whole reply? Never independently verified - genuinely unknown, not confirmed either way. Worth
a quick, standalone check if this is ever revisited, independent of the larger Firecrawl
decision in §4.3.

---

## 5. Also still open (not from the checklist, carried over from the production-readiness pass)

Recorded here only as a pointer - the real, detailed status lives in
`docs/Production_Security_Confirmation.md`, which should always be read fresh rather than
trusted from this summary:

- **Data retention policy for actual content** (Memory Record deletion/retraction) - an owner
  policy decision, not something code review can resolve.
- **Whether the 6-hour Neon PITR window is acceptable long-term** - see §3.1 above; also an
  owner decision, separate from the mechanical "upgrade the plan" trigger.

---

## 6. Maintenance

When any item here is actually picked up: move its entry out of this document and into the
relevant real documentation (`Production_Security_Confirmation.md` for security items, a new
ADR for anything architecturally significant like 500k-user scaling or VirusTotal's
upload-and-scan mode) - this file is a holding area for deferred work, not the permanent record
of a decision once it's actually made.
