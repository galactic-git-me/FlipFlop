# Phase 2 Progress — Price Alerts + Listing Proliferator

**Status**: Phase 2 started (2026-08-23)  
**Current Work**: F2.1 Price Alerts domain model  
**Target Completion**: 2026-09

---

## Phase 2 Acceptance Criteria

### F2.1: Price Alerts System (4 AC)

| AC | Description | Status | Tests | Commit |
|----|-------------|--------|-------|--------|
| F2.1.1 | User can set price-drop alerts | ✅ COMPLETE | 13 | 2d9e8ea6 |
| F2.1.2 | Alert emails sent when price drops | ✅ COMPLETE | 9 | e7f19bdb |
| F2.1.3 | Five-star auto-price (experimental) | ✅ COMPLETE | 18 | 1a56b460 |
| F2.1.4 | Price history tracked for trends | ⏳ TODO | - | - |

### F2.2: Listing Proliferator (4 AC)

| AC | Description | Status | Tests | Notes |
|----|-------------|--------|-------|-------|
| F2.2.1 | User can list on multiple channels | ⏳ TODO | - | eBay + Storefront |
| F2.2.2 | Dry-run mode shows what would list | ⏳ TODO | - | Preview before publish |
| F2.2.3 | Live listing publishes when ready | ⏳ TODO | - | Gated by flag |
| F2.2.4 | Inventory reserved during listing | ⏳ TODO | - | Phase 2 |

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

## Completed F2.1 Phase (3/4 AC)

| AC | Description | Tests | Status |
|----|-------------|-------|--------|
| F2.1.1 | Set price alerts | 13 | ✅ |
| F2.1.2 | Alert emails | 9 | ✅ |
| F2.1.3 | Five-star auto-price | 18 | ✅ |
| F2.1.4 | Price history | - | ⏳ |
| **Subtotal** | | **40** | **✅ 3/4** |

## Next Steps (Session 6)

### Immediate
1. **Price Alert Email Service** (F2.1.2)
   - Integrate with email service
   - Use EMAIL_DISPATCH_ENABLED flag
   - Send when alert triggered

2. **Five-Star Auto-Pricing** (F2.1.3)
   - Auto-reduce price if rating < 5 stars
   - Use Money type for calculations

3. **Price History** (F2.1.4)
   - Track price changes over time
   - Enable trend analysis

### Then
4. **Listing Proliferator** (F2.2)
   - Multi-channel listing support
   - Dry-run mode
   - Live publishing gated by flag

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
| Feature Flags | 11 | ✅ Pass |
| CPK Versioning | 11 | ✅ Pass |
| Money Type | 38 | ✅ Pass |
| Admin Formatting | 36 | ✅ Pass |
| Concurrency | 11 | ✅ Pass |
| **Phase 1 Total** | **107** | **✅ Pass** |
| **Phase 2 Complete** | **40** | **✅ Pass** |
| **GRAND TOTAL** | **147** | **✅ Pass** |

---

## Commit Log (Phase 2 Start)

```
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

**Last Updated**: 2026-08-23  
**Next Milestone**: Complete F2.1 (Price Alerts) with email service  
**See Also**: [ac-to-phase-traceability.md](ac-to-phase-traceability.md)
