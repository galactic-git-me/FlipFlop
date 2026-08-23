# Phase 2 Progress — Price Alerts + Listing Proliferator

**Status**: F2.1 ✅ + F2.2 ✅ COMPLETE (2026-08-23)  
**Next**: Phase 3 (Demand Intelligence) or Deploy to Staging  
**Target Completion**: 2026-09

---

## Phase 2 Acceptance Criteria

### F2.1: Price Alerts System (4 AC)

| AC | Description | Status | Tests | Commit |
|----|-------------|--------|-------|--------|
| F2.1.1 | User can set price-drop alerts | ✅ COMPLETE | 13 | 2d9e8ea6 |
| F2.1.2 | Alert emails sent when price drops | ✅ COMPLETE | 9 | e7f19bdb |
| F2.1.3 | Five-star auto-price (experimental) | ✅ COMPLETE | 18 | 1a56b460 |
| F2.1.4 | Price history tracked for trends | ✅ COMPLETE | 10 | 54d0ff8d |

### F2.2: Listing Proliferator (4 AC) ✅ COMPLETE

| AC | Description | Status | Tests | Commit |
|----|-------------|--------|-------|--------|
| F2.2.1 | User can list on multiple channels | ✅ COMPLETE | 13 | b0245839 |
| F2.2.2 | Dry-run mode shows what would list | ✅ COMPLETE | 14 | b0245839 |
| F2.2.3 | Live listing publishes when ready | ✅ COMPLETE | 14 | 52954228 |
| F2.2.4 | Inventory reserved during listing | ✅ COMPLETE | 14 | 52954228 |

---

## What's Done (Session 5 - Phase 2 Continuation)

### F2.1.1: Price Alerts Domain ✅ (Complete)

**Database Schema**:
- `price_alerts` table: Target price + active state + trigger info
- `price_alert_events` table: Immutable audit trail

**Models** (`app/models/price_alert.py`):
- `PriceAlert`: Alert record (user + build + target)
- `PriceAlertEvent`: Event log (triggered, dismissed, re_armed)

**Service** (`app/services/price_alerts.py`):
- `create_alert(build_id, email, target_price)` — Create new alert
- `list_active_alerts(build_id)` — Get all active for build
- `check_and_trigger_alerts(build_id, current_price)` — Detect drops
- `dismiss_alert(alert_id)` — User dismisses
- `re_arm_alert(alert_id)` — Re-enable alert
- `get_alert_history(alert_id)` — Audit trail

**Design Patterns**:
- Money type for price precision (no float errors)
- Pennies storage (integers, 100% precision)
- Feature-flag gating (FEATURE_PRICE_ALERTS_RULES_ENABLED)
- Immutable event log (audit trail)
- Idempotent operations (safe on retry)

**Tests** (`test_price_alerts.py`): 13 tests
- Alert creation and validation (3)
- Price drop detection (3)
- Alert lifecycle (2)
- Event audit trail (2)
- Money type precision (2)
- Feature-flag gating (1)

**Commit**: `2d9e8ea6` (feat: start Phase 2 - implement Price Alerts domain)

### F2.1.2: Price Alert Email Service ✅ (Complete)

**Features**:
- Individual alert emails (build info + price comparison + savings)
- Summary emails (batch notifications for multiple alerts)
- Savings calculation using Money type
- Feature-flag gated (FEATURE_PRICE_ALERTS_EMAIL_ENABLED)
- HTML formatted emails with action links
- Error handling and logging

**Tests**: 9 tests
- Email sent when alert triggers (1)
- Email suppressed by feature flag (1)
- Email content formatting (1)
- Summary emails for multiple alerts (1)
- Summary savings calculation (1)
- Error handling for missing builds (1)
- SMTP error handling (1)
- Money precision in emails (2)

**Commit**: `e7f19bdb` (feat: implement Price Alert email service)

### F2.1.3: Five-Star Auto-Pricing ✅ (Complete)

**Purpose**: Automatically adjust price down if seller rating drops below 5 stars.
Prevents stale listings with outdated pricing when seller reputation changes.

**Discount Matrix**:
- 5.0 stars: 0% (no reduction)
- 4.5 stars: 3% reduction
- 4.0 stars: 5% reduction
- 3.0 stars: 10% reduction
- 2.0 stars: 20% reduction
- 1.0 stars: 25% reduction

**Features**:
- Star-rating → discount lookup
- Automatic price adjustment
- Feature-flag gated (FEATURE_PRICE_ALERTS_FIVE_STAR_AUTO)
- Only applies to listed/ready builds
- Human-readable explanations
- Audit logging

**Tests**: 18 tests
- Discount calculation by rating (5)
- Price adjustment calculations (5)
- Discount explanations (3)
- Auto-apply functionality (5)
- Money type precision (2)

**Example**:
```python
current = Money(99.99, "GBP")
rating = 4.5
adjusted = calculate_adjusted_price(current, rating)
# Returns Money(96.99, "GBP") (3% reduction)
```

**Commit**: `1a56b460` (feat: implement Five-Star Auto-Pricing)

---

## Completed F2.1 Phase (4/4 AC) ✅

| AC | Description | Tests | Status |
|----|-------------|-------|--------|
| F2.1.1 | Set price alerts | 13 | ✅ |
| F2.1.2 | Alert emails | 9 | ✅ |
| F2.1.3 | Five-star auto-price | 18 | ✅ |
| F2.1.4 | Price history | 10 | ✅ |
| **Subtotal** | | **50** | **✅ 4/4** |

## Phase 2 Complete ✅ (Session 6)

### F2.1: Price Alerts ✅ Complete
All 4 AC implemented and tested (50 tests):
- ✅ Price Alerts Domain (13 tests)
- ✅ Email Notifications (9 tests)
- ✅ Five-Star Auto-Pricing (18 tests)
- ✅ Price History Tracking (10 tests)

### F2.2: Listing Proliferator ✅ Complete
All 4 AC implemented and tested (55 tests):
- ✅ Multi-channel Listing (13 tests) — eBay + Storefront simultaneously
- ✅ Dry-run Mode (14 tests) — Preview without committing
- ✅ Live Publishing (14 tests) — Gated by feature flag
- ✅ Inventory Reservation (14 tests) — Prevent overselling

### Next: Phase 3 or Deploy?

**Option 1**: Deploy Phase 1+F2.1+F2.2 to Staging (all flags OFF, safe)
**Option 2**: Continue Phase 3 Demand Intelligence (4 AC, ~45 tests)
**Option 3**: Both in parallel

---

## Phased Rollout

### Phase 2a: Rules Off (Safe)
```bash
export FEATURE_PRICE_ALERTS_RULES_ENABLED=false        # No alerts run
export FEATURE_PRICE_ALERTS_EMAIL_ENABLED=false        # No emails sent
```

### Phase 2b: Rules On, Email Off (Test)
```bash
export FEATURE_PRICE_ALERTS_RULES_ENABLED=true         # Alerts run
export FEATURE_PRICE_ALERTS_EMAIL_ENABLED=false        # Still no emails
```

### Phase 2c: Full Rollout (Both On)
```bash
export FEATURE_PRICE_ALERTS_RULES_ENABLED=true         # Alerts run
export FEATURE_PRICE_ALERTS_EMAIL_ENABLED=true         # Emails sent
```

---

## Test Summary

| Suite | Count | Status |
|-------|-------|--------|
| Price Alerts Domain | 13 | ✅ Pass |
| Price Alert Emails | 9 | ✅ Pass |
| Five-Star Pricing | 18 | ✅ Pass |
| Price History | 10 | ✅ Pass |
| Multi-Channel Publisher | 13 | ✅ Pass |
| Dry-Run Validator | 14 | ✅ Pass |
| Inventory Reservation | 14 | ✅ Pass |
| Live Publisher | 14 | ✅ Pass |
| Feature Flags | 11 | ✅ Pass |
| CPK Versioning | 11 | ✅ Pass |
| Money Type | 38 | ✅ Pass |
| Admin Formatting | 36 | ✅ Pass |
| Concurrency | 11 | ✅ Pass |
| **Phase 1 Total** | **107** | **✅ Pass** |
| **Phase 2 F2.1** | **50** | **✅ Pass** |
| **Phase 2 F2.2** | **55** | **✅ Pass** |
| **GRAND TOTAL** | **212** | **✅ Pass** |

---

## Commit Log (Phase 2a+b Complete)

```
b0245839 feat: add comprehensive tests for F2.2 (55 tests across all 4 AC)
52954228 feat: implement F2.2.1-F2.2.4 services and models (Phase 2 Listing Proliferator)
859f0e72 docs: Phase 2 F2.1 complete - 157 tests passing, all AC delivered
607dda18 docs: add F2.1 completion summary - Phase 2 Price Alerts ready
54d0ff8d feat: implement Price History tracking (F2.1.4) - PHASE 2 COMPLETE
acae0749 docs: update Phase 2 progress - F2.1.3 Five-Star Pricing complete
1a56b460 feat: implement Five-Star Auto-Pricing (F2.1.3)
e7f19bdb feat: implement Price Alert email service (F2.1.2)
65d597e4 docs: add Phase 2 progress tracker
2d9e8ea6 feat: start Phase 2 - implement Price Alerts domain (F2.1.1-2)
3d4dce84 docs: add session 4 final summary - Phase 1 complete
```

---

## Timeline

| Phase | Status | AC | Target |
|-------|--------|----|----|
| Phase 1 | ✅ COMPLETE | 23/23 | 2026-08-23 |
| Phase 2 | 🔧 IN PROGRESS | 8/8 | 2026-09-30 |
| Phase 3 | ⏳ PLANNED | 4/4 | 2026-10-31 |
| Phase 4 | ⏳ PLANNED | 3/3 | 2026-11-30 |

---

**Last Updated**: 2026-08-23 (F2.1+F2.2 COMPLETE)  
**Next Milestone**: Deploy to Staging OR Start Phase 3  
**See Also**: [f21-complete.md](f21-complete.md), [f22-complete.md](f22-complete.md), [ac-to-phase-traceability.md](ac-to-phase-traceability.md), [SESSION-5-COMPLETE.md](SESSION-5-COMPLETE.md)
