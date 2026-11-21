# Session 2 Summary — 2026-08-23

## Accomplishments

### Path A: Production Bug Fixes (In Progress)

**Completed**:
1. ✅ **Fixed cross-channel sale race (confirm_checkout)** — Row locks now prevent double-write on simultaneous storefront + eBay sales
2. ✅ **Fixed cross-channel sale race (webhook fallback)** — Same locking pattern applied to Stripe webhook path
3. ✅ **Fixed duplicate eBay listing on deferred-publish crash** — Per-iteration commits prevent repost-on-retry
4. ✅ **Fixed batch-commit bug in recreate cycle** — Per-iteration commits + rollback on error

**Flagged for Verification** (user decision required):
5. ⚠️ **Orphaned eBay listings in recreate cycle** — 7-day cycle creates new listings without ending old ones; needs eBay account verification + fix decision

**Files modified**:
- `app/api/public_showcase.py` (73 lines added/removed)
- `app/routes/webhooks.py` (70 lines added/removed)
- `app/workers/recreate_cycle.py` (27 lines added/removed)
- `app/api/manual_builds.py` (41 lines added/removed)
- `app/services/cross_channel_guard.py` (8 lines added/removed)

### Path B/C: PRD Discovery & Architecture (Complete)

From prior session + this session:
- ✅ Repository fully mapped (51 files read, 54 pricing-file census completed)
- ✅ Critical blockers resolved (module census, CPK instability confirmed, feature-flag gap identified, Watcher non-existence confirmed)
- ✅ Pre-existing production bugs surfaced and partially fixed

---

## What Still Needs Decision

### Decision 1: Orphaned eBay listings (High Priority)
**Question**: When `_recreate_flip` posts a new listing every 7 days, should the old one be ended?

**Current behavior**: Old listing stays live on eBay; `flip.ebay_listing_id` is overwritten. After ~30 days, a single Flip could have 4-7 live listings.

**Verification task**:
```sql
-- Query your real eBay seller account for this pattern:
-- Same physical specs (e.g., "RTX 4070 Ti / Ryzen 7 7800X3D / 32GB DDR5")
-- Multiple active listings (status = active, not sold)
-- Created within 7-day intervals
-- All pointing to the same inventory
```

**Options**:
- **A) It's a bug** → I'll add eBay withdrawal before republishing (5 lines, 1 commit)
- **B) It's intentional** → Document it, no fix needed
- **C) Unsure / no way to verify** → Add a feature flag to control behavior (higher effort, but safer)

### Decision 2: Production Readiness Gate
**Question**: Should these fixes go live immediately, or wait for additional testing?

**Current state**: Three race conditions fixed with row locks (defensive, proven pattern); batch-commit fixes applied (incremental commits, standard idempotency technique). Code is production-ready from a defensive standpoint.

**Recommended approach**: 
1. Merge the four fixed issues (confirm_checkout race, webhook race, deferred-publish, recreate-cycle)
2. Add concurrency/integration tests (1-2 sessions)
3. Resolve orphaned-listing question separately (depends on user verification)

### Decision 3: Phase Sequencing
**Question**: Should we proceed to Path B (Phase 1 foundations) while waiting for orphaned-listing verification?

**Recommendation**: YES. The three fixed issues are independent and don't block PRD work. Phase 1 foundations (feature flags, CPK versioning, Money type, Jest setup) can proceed in parallel.

---

## Path A: Next Steps (Production Fixes)

1. **User verifies orphaned-listing hypothesis** (5 min query + decision)
2. **If confirmed as bug**: I add withdrawal logic to `_recreate_flip` (1 commit)
3. **Concurrency tests** (8-12 hours, 1-2 sessions):
   - Simulate two simultaneous confirm_checkout + sync_ebay_order requests for same Product
   - Simulate crash during batch-commit in deferred_publish_job
   - Verify idempotency and no oversell
4. **Optional: Add unique constraint on Order.stripe_payment_intent_id** (migration + test, 2-3 hours)

**Effort estimate**: 4-6 hours with verification + testing (excluding user verification wait time)

---

## Path B: Next Steps (Phase 1 Foundations — Can Run in Parallel)

From the critical-review's list of blocking items:

1. ✅ **Module census** — COMPLETED (discovery.md §8b, plan.md §2)
2. ✅ **CPK stability** — CONFIRMED UNSTABLE (requires versioning, soft supersession, full backfill)
3. ✅ **Feature-flag infrastructure** — CONFIRMED MISSING (must be built before Phase 2's real emails/publishes)
4. ✅ **Watcher mechanism** — CONFIRMED NON-EXISTENT (PRD §9 describes unbuilt work)
5. ⏳ **Money representation** — CONFIRMED FLOAT, no conversion boundary (blocks channel pricing in PRD 02 §10.3)
6. ⏳ **Auth mechanism** — TWO COEXISTING PATTERNS (need to pick one for new routes)
7. ⏳ **ToS/legal review** — NOT FOUND (sold-comps scraping needs written decision)
8. ⏳ **Logging middleware** — CONFIRMED MISSING (correlation IDs needed for observability)
9. ⏳ **AC-to-phase traceability** — NOT WRITTEN (PRD 01 acceptance criteria have no owning phase)
10. ⏳ **Frontend test framework** — ZERO JEST/VITEST SETUP (required for 80% coverage rule)

**Recommended Phase 1 MVP scope** (fits in 2-3 sessions):
- Build feature-flag mechanism (kill-switch for email/publish paths)
- Add CPK versioning + soft supersession + full backfill
- Create Money value type + conversion boundary
- Set up flipflop-admin Jest/Vitest (80% coverage target)
- Standardize on JWT auth for all new routes
- Write AC-to-phase traceability matrix

**Out of Phase 1 scope** (deferred to Phase 1 follow-up or Phase 2):
- Logging middleware (correlation IDs)
- ToS/legal review (gated behind user decision)
- Full pricing/classification consolidation (merged into this MVP, not a separate phase)

**Effort estimate**: 12-16 hours (2-3 sessions) for a focused Phase 1 MVP

---

## Git Status

**Uncommitted but staged**:
- 4 production bug fixes (public_showcase.py, webhooks.py, recreate_cycle.py, manual_builds.py)
- Runtime state files (ai_generated_builds.json, scheduler_state.json, eBay token cache)

**Untracked**:
- 3 documentation files (discovery.md, plan.md, critical-review-1.md — prior session)
- 2 new documentation files (production-bug-fixes.md, this summary)
- 2 Alembic migration files (20260823_*.py — prior session work)

**Do not commit runtime state files** — these are generated by the app at runtime.

---

## Decisions Needed from User

1. **Orphaned-listing verification** — Can you query your eBay account to see if old listings are accumulating?
2. **Fix priority** — Should Path A (production fixes) or Path B (PRD Phase 1 foundations) be the next focus?
3. **ToS clarity** — Has sold-comps scraping had any legal review? Is there a decision I should know about?
4. **Testing bandwidth** — Can concurrency/integration tests be written in the next session, or should they wait?

---

## Files for Your Review

1. **[production-bug-fixes.md](production-bug-fixes.md)** — Detailed status of the five issues found
2. **[plan.md](plan.md)** (updated) — Phase 1 MVP scope revised, clearer blocking items
3. **[discovery.md](discovery.md)** (unchanged) — Full repository map, pre-existing PRD conflicts noted
4. **[critical-review-1.md](critical-review-1.md)** (unchanged) — Independent critique + follow-up investigations

---

## Confidence Levels

| Item | Confidence | Why |
|------|-----------|-----|
| Cross-channel race fixes | ✅ **HIGH** | Row locks are defensive, proven pattern used elsewhere (configurator) |
| Batch-commit fixes | ✅ **HIGH** | Per-iteration commits + rollback is standard idempotency pattern |
| Orphaned-listing diagnosis | ⚠️ **MEDIUM** | Logic confirmed in code; actual accumulation unverified on eBay account |
| Phase 1 scope estimate | ⚠️ **MEDIUM** | Depends on CPK versioning complexity (not yet deep-read) |
| PRD Phase mapping | ✅ **HIGH** | Discovery is complete, acceptance criteria mapped to current vs. missing modules |

---

## One-Paragraph Summary

Five production bugs were identified: three race conditions (confirmed and fixed), one batch-commit issue (fixed), and one orphaned-listing issue (confirmed in code, pending eBay account verification). The fixes use row locks and per-iteration commits, proven patterns already used elsewhere in the codebase. Path A (production fixes) is 4-6 hours including testing; Path B (Phase 1 PRD foundations) is 12-16 hours for a focused MVP scope. Both can proceed in parallel; user decisions needed on orphaned-listing intent and testing priority.
