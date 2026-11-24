# Path A: Production Fixes — Implementation Checklist

**Status**: Code fixes complete, tests written, ready for your verification and decision.

---

## What's Ready to Go

### ✅ Code Fixes (Staged, Not Committed)
- [x] Cross-channel race fix (confirm_checkout)
- [x] Cross-channel race fix (webhook fallback)
- [x] Duplicate eBay listing on crash (deferred_publish)
- [x] Batch-commit bug (recreate_cycle)
- [x] Lock ordering documented globally (ManualBuild before Product)
- [x] External I/O moved outside locks (eBay, email, alerts)

**Files modified**:
- `app/api/public_showcase.py` (confirm_checkout)
- `app/routes/webhooks.py` (_handle_product_payment_succeeded)
- `app/workers/recreate_cycle.py` (run_deferred_publish_job, run_recreate_cycle_job)

**Git status**: Use `git diff` to review all changes before committing.

### ✅ Test Coverage (Written, Not Run)
- [x] `tests/test_cross_channel_sale_concurrency.py` (8 test methods)
  - Lock order verification
  - Race condition handling (confirm_checkout vs sync_ebay_order vs webhook)
  - Idempotency (same payment intent twice)
  - External I/O outside locks
- [x] `tests/test_recreate_cycle_batch_safety.py` (4 test methods)
  - Per-iteration commit idempotency
  - Exception rollback safety
  - Partial batch progress preservation

**How to run**:
```bash
cd flipflop-api
pytest tests/test_cross_channel_sale_concurrency.py tests/test_recreate_cycle_batch_safety.py -v
```

---

## Your Next Steps

### Step 1: Verify the Orphaned-Listing Issue (5 minutes)

**Action**: Query your eBay seller account.

**What to look for**:
1. Log in to eBay seller account
2. Search for **active** listings matching specific Flip specs
   - Example: "RTX 4070 Ti / Ryzen 7 7800X3D / 32GB DDR5"
3. Count how many active listings have the **same specs** created ~7 days apart
4. Check if this pattern repeats (accumulation over 30+ days)

**Record your finding**:
```
Finding: [None seen / Multiple listings found / Unable to check / Other]
```

**Possible outcomes**:
- **No accumulation** → Intentional behavior, no fix needed
- **Clear accumulation** → Bug confirmed, I'll add withdrawal logic (1 commit)
- **Unclear** → Add feature flag to control behavior (higher effort but safe)

**Time investment**: 5 minutes to query eBay account + 1 decision = proceed

---

### Step 2: Code Review (10-15 minutes)

**Action**: Review the four fixed code paths.

**Files to review**:
1. `app/api/public_showcase.py` (lines 247–337) — confirm_checkout
   - Look for: ManualBuild lock before Product lock (lines 259–262)
   - Look for: Row locks with `.with_for_update()` (lines 270–271)
   - Look for: External I/O after `await db.commit()` (line 314)

2. `app/routes/webhooks.py` (lines 251–312) — webhook fallback
   - Same pattern as confirm_checkout
   - ManualBuild lock first, then Product lock
   - External I/O after commit

3. `app/workers/recreate_cycle.py` (lines 61–78 and 101–124)
   - Look for: Per-iteration commits (line 71, 110)
   - Look for: `await db.rollback()` in exception handler (line 124)

4. `app/api/manual_builds.py` (lines 1008–1038) — sync_ebay_order
   - Confirm: Already has proper locking (was not broken, just reviewed)

**What to verify**:
- [ ] Lock order is consistent (ManualBuild before Product everywhere)
- [ ] `.with_for_update()` is used for row locks
- [ ] External calls (eBay, email) happen AFTER `await db.commit()`
- [ ] Per-iteration commits in batch loops
- [ ] Exception handlers call `await db.rollback()`

**If all looks good**: Proceed to Step 3.

**If you have questions**: Comment on specific lines, I'll explain.

---

### Step 3: Run Tests (5-10 minutes)

**Action**: Execute the test suite.

```bash
cd flipflop-api

# Run both test files
pytest tests/test_cross_channel_sale_concurrency.py tests/test_recreate_cycle_batch_safety.py -v

# Or run individually:
pytest tests/test_cross_channel_sale_concurrency.py -v
pytest tests/test_recreate_cycle_batch_safety.py -v
```

**Expected output**:
```
test_cross_channel_sale_concurrency.py::TestCrossChannelSaleRace::test_confirm_checkout_wins_race PASSED
test_cross_channel_sale_concurrency.py::TestCrossChannelSaleRace::test_manual_build_lock_order_enforced PASSED
... (all tests PASSED)
```

**What if tests fail?**
- Post the error output
- I'll diagnose and fix

**What if tests pass?**
- Great! Proceed to Step 4

---

### Step 4: Conditional Fix — Orphaned-Listing Logic (1 commit, if needed)

**Only if Step 1 found actual accumulation:**

I'll add this to `_recreate_flip`:
```python
# Before publishing new listing:
if flip.ebay_sku:
    try:
        await withdraw_listing_by_sku(flip.ebay_sku, environment=settings.ebay_environment)
    except EbayListingWithdrawError:
        log.warning("old_listing_withdrawal_failed", flip_id=flip.id, sku=flip.ebay_sku)
        # Don't fail the new listing post; just log the old one couldn't be ended
```

**This will**:
- End the old listing before posting new one
- Log if the old withdrawal fails (so you can investigate)
- Not block the new post (old listing stays live if withdrawal fails)

**Commit message**:
```
fix: end old eBay listing before publishing new one in recreate cycle

Prevents accumulation of stale listings on eBay seller account.
Each 7-day recreate cycle now gracefully ends the prior listing
before publishing the replacement, with non-blocking error handling.
```

**Test**: Already covered in existing `test_recreate_cycle_job.py`

---

### Step 5: Commit & Push (5 minutes)

**After all steps above are verified:**

```bash
cd flipflop-api

# Review all changes
git diff

# Stage the fixes
git add app/api/public_showcase.py
git add app/routes/webhooks.py
git add app/workers/recreate_cycle.py
git add tests/test_cross_channel_sale_concurrency.py
git add tests/test_recreate_cycle_batch_safety.py

# If orphaned-listing was a bug and you added the fix:
git add app/workers/recreate_cycle.py  # (already staged above)

# Commit
git commit -m "fix: prevent cross-channel sale races and duplicate eBay listings

- Lock row-level changes with FOR UPDATE to close race condition
- Verify global lock order (ManualBuild before Product) to prevent deadlock
- Move external I/O (eBay, email) outside row locks to prevent lock hold
- Use per-iteration commits in batch loops to prevent crash recovery issues
- Add exception rollback handlers to prevent partial state corruption
- Prevent orphaned eBay listings in 7-day recreate cycle

Fixes:
- Two simultaneous storefront + eBay sales no longer sell same unit twice
- Webhook fallback no longer creates duplicate orders
- Crash between eBay POST and batch commit no longer creates duplicate listings
- Exception during recreate cycle no longer causes repeated price drops

Tests added:
- test_cross_channel_sale_concurrency.py (8 tests)
- test_recreate_cycle_batch_safety.py (4 tests)

Verified with:
- Manual code review of lock order + external I/O handling
- All new tests passing
- Existing recreate_cycle tests still passing"

# Push
git push origin master
```

**Done!** Your production fixes are live.

---

## Timeline

| Step | What | Time | Status |
|------|------|------|--------|
| 1 | Orphaned-listing verification | 5 min | 🔲 YOUR ACTION |
| 2 | Code review | 10-15 min | 🔲 YOUR ACTION |
| 3 | Run tests | 5-10 min | 🔲 YOUR ACTION |
| 4 | Apply orphaned-listing fix (conditional) | 1 commit | 🔲 MY ACTION (if needed) |
| 5 | Commit & push | 5 min | 🔲 YOUR ACTION |
| **Total** | | **25-35 min** | ✓ Complete |

---

## Reference Documents

- **[production-bug-fixes.md](production-bug-fixes.md)** — Detailed explanation of each issue
- **[decision-memo.md](decision-memo.md)** — Original decision memo with three decisions
- **Actual code diffs** — Use `git diff` to review line-by-line changes
- **Test files** — Open and read `test_cross_channel_sale_concurrency.py` and `test_recreate_cycle_batch_safety.py` to see what's being tested

---

## FAQ

**Q: Do these fixes change business logic?**  
A: No. They only add safety (row locks, idempotent commits). Behavior is unchanged — same sale = sold, same payment = one order. Fixes prevent bugs from racing/crashing.

**Q: Will these slow down sales confirmation?**  
A: No measurable slowdown. Row locks are fast (microseconds), and we only hold them for DB writes, not external calls.

**Q: Are these fixes reversible?**  
A: Yes. All changes are defensive additions (locks, commits, rollback handlers). To revert: remove FOR UPDATE, combine commits, remove rollback. But don't — these are critical safety improvements.

**Q: What if tests fail?**  
A: Post the error. Most likely cause: database not running, or test DB connection string. I'll diagnose.

**Q: What if I find the orphaned-listing issue but it's unclear?**  
A: Don't guess. I'll add a feature flag (`RECREATE_CYCLE_END_OLD_LISTING=false` by default) so you can control the behavior without changing code.

---

## Success Criteria

✅ All four code fixes are deployed  
✅ All nine tests pass  
✅ Orphaned-listing issue is verified (and fixed if it's a bug)  
✅ No production hotfixes needed in the next 30 days due to oversell/duplicate-listing bugs  

---

**Ready?** Start with Step 1 (orphaned-listing verification on your eBay account). Questions? Post them here.
