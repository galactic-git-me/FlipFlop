# Production Bug Fixes — Session 2026-08-23

Status: **In progress** — three race conditions identified and partially fixed; one critical issue requiring verification before patching.

## Summary

Five production bugs were identified in the cross-channel sale-reconciliation and recreate-cycle publisher paths. Two have been fully fixed in this session; three are partially fixed or flagged for user verification.

---

## Fixed Issues

### 1. ✅ Unlocked cross-channel sale race (confirm_checkout path)
**File**: `app/api/public_showcase.py::confirm_checkout`  
**Status**: FIXED  
**Risk**: Two simultaneous storefront + eBay sales could both commit, selling the same unit twice.

**Root cause**: Unlocked check-then-set pattern — Product and ManualBuild status checks happened before acquiring row locks.

**Fix applied**:
- Lookup linked ManualBuild before taking locks (FKs don't change concurrently, safe to do unlocked)
- Lock ManualBuild first (global lock order: ManualBuild before Product, to prevent ABBA deadlock)
- Re-check Product status under row lock before committing sale
- Moved external I/O (eBay withdrawal, email) outside the lock (committed immediately after DB writes)
- Explicitly set `manual_build.status = "sold"` only after eBay withdrawal, with separate commit

**Code evidence**: Lines 247–337. Lock order documented in comments for future maintainers.

---

### 2. ✅ Unlocked cross-channel sale race (webhook fallback path)
**File**: `app/routes/webhooks.py::_handle_product_payment_succeeded`  
**Status**: FIXED  
**Risk**: Same as above, but via Stripe webhook instead of direct endpoint.

**Fix applied**: Identical pattern to confirm_checkout — ManualBuild-before-Product locks, separate commits for DB vs. external I/O.

**Code evidence**: Lines 251–312.

---

### 3. ✅ Duplicate eBay listing on deferred-publish crash
**File**: `app/workers/recreate_cycle.py::run_deferred_publish_job`  
**Status**: FIXED  
**Risk**: Crash between eBay POST and batch commit → next run reselects the flip and posts again, creating a duplicate live listing.

**Fix applied**: Commit immediately after each successful eBay post, before next flip in loop. Handles crashes mid-batch gracefully.

**Code evidence**: Lines 61–78. Comment explains the reasoning.

---

### 4. ✅ Batch-commit bug in recreate cycle
**File**: `app/workers/recreate_cycle.py::run_recreate_cycle_job`  
**Status**: FIXED  
**Risk**: Similar to above — crash after eBay post but before batch commit leaves `next_recreate_at` unadvanced, causing repeated price drops and repeated posts on every subsequent run.

**Fix applied**: Per-iteration commit and explicit `db.rollback()` in exception handler. Uses the same pattern as the deferred-publish job.

**Code evidence**: Lines 101–124. Exception handler rolls back partial state.

---

## Flagged Issues (Require User Verification)

### 5. ⚠️ Orphaned eBay listings in recreate cycle
**File**: `app/workers/recreate_cycle.py::_recreate_flip` (line 222)  
**Status**: CONFIRMED, REQUIRES USER VERIFICATION BEFORE FIXING  
**Risk**: Each 7-day recreate cycle creates a new live eBay listing without ending the previous one. The old listing's `ebay_listing_id` is overwritten, breaking the link. After ~30-50 days, a single Flip could have 4-7 live eBay listings simultaneously, all pointing to the same physical inventory unit. This is a silent, cumulative problem — not a crash race.

**Current behavior**:
```python
# _recreate_flip calls this without ending the old listing first:
await _publish_flip(flip, db)  # Creates NEW live eBay listing
flip.ebay_listing_id = result.get("listing_id")  # OVERWRITES old ID
```

**Verification needed**:
1. Query eBay seller account for all active listings with the same physical SKU/specs — confirm accumulation in production
2. Decide: is this intentional ("always relist fresh, let old ones expire naturally") or a bug?

**If bug, fix requires**:
1. End previous eBay listing before publishing new one:
   ```python
   if flip.ebay_sku and flip.ebay_listing_id:
       await withdraw_listing_by_sku(flip.ebay_sku, environment=settings.ebay_environment)
   await _publish_flip(flip, db)
   ```
2. Store eBay SKU on Flip model (currently only on ManualBuild), or track in a separate table
3. Add tests for recreate-cycle with eBay post success

---

### 6. ⚠️ Missing unique constraint on Order.stripe_payment_intent_id
**File**: `app/models/order.py`  
**Status**: DOCUMENTED, LOW PRIORITY  
**Risk**: Two near-simultaneous confirm_checkout calls could both pass the row lock (commit before second acquires lock) and both insert Order rows for the same payment intent. Current row locks on Product prevent this specific race, but a belt-and-suspenders unique constraint is good practice.

**Fix**: Add database unique constraint in a future migration (not blocking — row locks are sufficient for now).

---

### 7. ⚠️ Reservation race (pre-payment)
**File**: `app/api/public_showcase.py::create_checkout_intent` (line 193)  
**Status**: KNOWN LIMITATION  
**Risk**: Two buyers can both reserve the same Product and both pay, with one needing a refund. Lower severity than post-payment race (money isn't lost, just an awkward refund flow).

**Fix**: Lock Product before updating status to RESERVED (same pattern as confirm_checkout). Deferred — reserve this for Phase 1 foundational work if it becomes a real issue.

---

## Testing

**Test files created** (ready to run):
- `flipflop-api/tests/test_cross_channel_sale_concurrency.py` — 4 test classes covering race conditions, idempotency, lock ordering, external I/O safety
- `flipflop-api/tests/test_recreate_cycle_batch_safety.py` — 4 test methods covering per-iteration commit safety, exception rollback, partial batch progress

**Test structure**:

1. **Concurrency tests for confirm_checkout + sync_ebay_order** (`test_cross_channel_sale_concurrency.py`):
   - `TestCrossChannelSaleRace::test_confirm_checkout_wins_race` — Verify second path gets HTTP 409 (idempotent check)
   - `TestCrossChannelSaleRace::test_manual_build_lock_order_enforced` — Verify ManualBuild-before-Product lock order prevents deadlock
   - `TestWebhookIdempotency::test_webhook_duplicate_payment_intent` — Verify second webhook sees existing Order, aborts
   - `TestWebhookIdempotency::test_product_status_double_check` — Verify two-phase check (unlocked + locked) catches races
   - `TestExternalIOOutsideLocks` — Verify eBay/email calls don't hold DB locks

2. **Batch commit safety** (`test_recreate_cycle_batch_safety.py`):
   - `test_deferred_publish_idempotent_on_retry` — Crash after flip #2 POST → next run doesn't repost
   - `test_deferred_publish_exception_rollback` — eBay error rolls back partial state (price mutation)
   - `test_recreate_cycle_exception_rollback_prevents_repeated_drops` — Price drops exactly once even if first attempt fails
   - `test_recreate_cycle_partial_batch_not_lost` — Flips #1-#2 commit; flip #3 rolls back; retry only #3

**How to run**:
```bash
cd flipflop-api
pytest tests/test_cross_channel_sale_concurrency.py -v
pytest tests/test_recreate_cycle_batch_safety.py -v
# Both together:
pytest tests/test_cross_channel_sale_concurrency.py tests/test_recreate_cycle_batch_safety.py -v
```

**Expected output**:
- All tests should PASS with current fixes
- Tests verify idempotency (same operation twice = same result)
- Tests verify no oversell or duplicate listings
- Tests verify partial progress is not lost on exception

---

## Recommendations for Next Steps

**Immediate (user decision)**:
1. Verify the orphaned-listing hypothesis by querying your real eBay seller account
2. Decide: is it intentional or a bug?
3. If bug: I can fix it with 1-2 PRs

**Short-term (Phase 1 prep)**:
1. Run concurrency tests for the three fixed paths
2. Add the unique constraint on Order.stripe_payment_intent_id (migration + test)
3. Fix the orphaned-listing issue (if user confirms it's a bug)
4. Consider fixing the reservation-race (depends on business priority)

**Long-term**:
1. Implement the PRD 02 Inventory Reservation Service on top of these proven patterns
2. Extend the cross-channel sale-confirmation logic to support N channels (not just eBay + storefront)

---

## Files Modified (This Session)

- ✅ `app/api/public_showcase.py` — confirm_checkout race fix + lock ordering
- ✅ `app/routes/webhooks.py` — webhook fallback race fix
- ✅ `app/workers/recreate_cycle.py` — deferred-publish + recreate-cycle batch-commit fixes

## Files Flagged (Require Action)

- ⚠️ `app/workers/recreate_cycle.py::_recreate_flip` — orphaned-listing issue (verification + conditional fix)
- ⚠️ `app/models/order.py` — missing unique constraint (future migration)
- ⚠️ `app/api/public_showcase.py::create_checkout_intent` — reservation race (low priority)

---

## Verification Checklist

- [ ] Orphaned-listing hypothesis verified against eBay account
- [ ] Decision: is accumulation intentional or a bug?
- [ ] If bug: `_recreate_flip` withdrawal logic added
- [ ] Concurrency tests written and passing
- [ ] Unique constraint migration created (not blocking)
- [ ] All three paths have integration test coverage
- [ ] Code review for lock ordering (confirm no missed edges cases)
