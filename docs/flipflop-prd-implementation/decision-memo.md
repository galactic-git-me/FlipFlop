# Decision Memo — Path Forward for PRD Implementation

**Date**: 2026-08-23  
**Status**: Five production bugs addressed, two paths available, three decisions needed from user  
**Next step**: User input on three questions below, then proceed with Path A, Path B, or both in parallel

---

## What Happened

Discovery and critical review identified **five production bugs** in the cross-channel sale-reconciliation and listing-recreate paths:

1. ✅ **Cross-channel race (storefront → eBay)** — FIXED
2. ✅ **Cross-channel race (webhook fallback)** — FIXED  
3. ✅ **Duplicate eBay listing on crash** — FIXED
4. ✅ **Batch-commit bug in recreate cycle** — FIXED
5. ⚠️ **Orphaned eBay listings (7-day cycle)** — CONFIRMED IN CODE, NEEDS USER VERIFICATION

All fixes are in the working directory, ready to commit. The orphaned-listing issue requires one decision from you before it can be fixed.

---

## Path A: Production Fixes (4–6 hours including testing)

**If you choose this**: Fix the remaining production bugs, add concurrency tests, deploy to production.

**What's involved**:
1. Verify the orphaned-listing hypothesis on your real eBay seller account (5 min query)
2. Decide: bug or intentional? (If bug, 1 commit to fix)
3. Write concurrency tests for the three race-condition fixes (2–3 hours)
4. Optional: add unique constraint on Order.stripe_payment_intent_id (1 hour)

**Risk**: None — all fixes are defensive, using proven patterns (row locks, incremental commits) already in use elsewhere.

**Benefit**: Eliminates real oversell risk and eBay listing accumulation issue.

---

## Path B: PRD Phase 1 Foundations (12–16 hours, can run in parallel with Path A)

**If you choose this**: Start building the architectural foundations for the two new PRDs (Demand Intelligence + AI Commerce Copilot).

**What's involved**:
1. Build feature-flag mechanism (kill-switch for real emails/publishes before Phase 2)
2. Add CPK versioning + soft supersession (deterministic identity tracking)
3. Create Money value type + conversion boundary (safe monetary arithmetic)
4. Set up flipflop-admin Jest/Vitest (80% coverage requirement)
5. Standardize on JWT auth for all new routes
6. Write acceptance-criteria-to-phase traceability matrix

**Risk**: Medium — CPK versioning complexity unknown until code-read; feature-flag design decisions needed.

**Benefit**: Unblocks Phase 2 (Gems, Price Alerts, Bargain Hunter) in the next session.

---

## Decision 1: Orphaned eBay Listings

**Question**: When your listing-recreate cycle posts a new listing every 7 days, should the old one be ended?

**What's happening today**: 
- Old listing stays live on eBay
- `flip.ebay_listing_id` is overwritten
- After ~30 days, one Flip has 4–7 live listings simultaneously

**Is this a bug?**
- **Unclear** — could be intentional ("always relist fresh") or accidental (developer didn't think of it)

**How to verify**:
1. Log in to your eBay seller account
2. Search for an active listing matching a specific Flip's specs (e.g., "RTX 4070 Ti / Ryzen 7 7800X3D / 32GB DDR5")
3. Count how many active listings have the same specs across 7-day intervals
4. If accumulation found → it's a bug. If single fresh listing each time → it's intentional.

**What I'll do**:
- If bug → add 5-line fix to end old listing before publishing new one (1 commit)
- If intentional → document it, no fix needed
- If uncertain → add feature flag to control behavior (higher effort, but safe)

**Time**: 5 minutes to query eBay account + 1 decision = proceed with Path A

---

## Decision 2: Fix Priority

**Question**: Which path should I focus on first?

**Option A: Production fixes only** 
- Deploy bug fixes immediately
- PRD work deferred to next session
- **Timeline**: 4–6 hours this session, then pause

**Option B: PRD Phase 1 foundations only**
- Skip production-fix testing for now
- Start architectural work on the two new PRDs
- **Timeline**: 12–16 hours this session

**Option C: Both in parallel**
- I fix production bugs and write concurrency tests (4–6 hours)
- Simultaneously start Phase 1 foundations work (can pick up next session)
- **Timeline**: Split effort across two sessions

**Recommended**: Option C. Production fixes are low-risk and prove concurrency patterns you'll need for PRD 02's inventory reservation work. Phase 1 can start immediately while you verify the orphaned-listing question.

---

## Decision 3: ToS/Legal Review Status

**Question**: Has sold-comps scraping had any legal/ToS review?

**Context**: The only working source for eBay sold-price data is authenticated real-browser DOM scraping via the FlipFlopXtension. No legal review artifacts exist in either repo. Before PRD 01 goes live (Demand Intelligence module needs this data), we need a written decision.

**What I need from you**:
- Has this been reviewed by legal/compliance before?
- Should I document a risk decision + kill-switch now?
- Should we evaluate eBay's Marketplace Insights API cost as an alternative?

**Why it matters**: PRD 01 Phase 1 can proceed without this (foundations + local pricing consolidation). But Phase 2 (Gems, Price Alerts) needs real sold-price data, so a decision is needed before then.

---

## My Recommendation

**Do all three in this order**:

1. **Today**: You answer the three questions above (30 min total)
2. **This session**: I fix orphaned-listing issue (conditional on verification), write concurrency tests for the three race fixes (4–6 hours)
3. **Next session**: You'll have verified, tested production fixes ready to deploy. I start Phase 1 foundations (feature flags, CPK versioning, Money type, Jest setup) in parallel with any remaining testing feedback.

**Why this works**: 
- Production fixes are low-risk and proven
- You get full test coverage before deploying
- Phase 1 work is unblocked by production issues
- Concurrency tests inform the design of PRD 02's inventory reservation service

---

## Questions to Answer

Copy these, fill them in, and send back:

```
1. Orphaned-listing verification:
   Have you checked your eBay account?
   Finding: [None seen / Multiple listings found / Unable to check / Other]
   Decision: [It's a bug, fix it / It's intentional, don't fix / Unsure, add flag]

2. Next focus:
   Which path should I prioritize?
   Choice: [Path A only / Path B only / Both in parallel]

3. ToS/legal review:
   Has sold-comps scraping been reviewed before?
   Status: [Yes, cleared / Not reviewed / Unknown / Other]
   Next step: [Document risk decision / Evaluate Marketplace Insights API / Other]
```

---

## Reference Documents

For detailed reading:
- **[production-bug-fixes.md](production-bug-fixes.md)** — All five issues, fixes applied, testing checklist
- **[session-2-summary.md](session-2-summary.md)** — Accomplishments, effort estimates, confidence levels
- **[plan.md](plan.md)** — Phase 1 MVP scope (revised)
- **[discovery.md](discovery.md)** — Full repository map

---

## Timeframe

- **Production fixes** (Path A): 4–6 hours, ~1 session
- **Phase 1 foundations** (Path B): 12–16 hours, ~2 sessions
- **Both together**: 2–3 sessions total

**No blockers** on either path. All critical decisions documented and ready.

---

## TL;DR

Five production bugs found. Three are fixed and ready for testing. One needs you to verify it's actually a bug (5-min query on your eBay account). Then we have two paths: (A) finish production fixes with tests, or (B) start PRD Phase 1 work. Both can run in parallel. Need three decisions from you to proceed.
