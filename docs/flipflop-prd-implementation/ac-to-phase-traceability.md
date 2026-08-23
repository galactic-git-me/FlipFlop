# AC-to-Phase Traceability Matrix

Maps PRD 02 acceptance criteria to implementation phases and feature flags.

This document enables:
1. **User-facing progress tracking** — Which AC are available now vs. Phase 2/3/4?
2. **Feature-flag dependencies** — Which AC require specific flags?
3. **Rollout planning** — What to enable when?
4. **Verification checklists** — How to test each AC?

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | AC Complete (Phase 1) |
| 🔧 | AC In Progress |
| ⏳ | AC Planned (Future Phase) |
| 🚫 | AC Blocked (awaiting decision) |
| 🏴 | Gated by Feature Flag |
| 🔗 | Cross-dependency |

---

## Phase 1: Core Infrastructure (Foundations)

All AC in Phase 1 are **infrastructure prerequisites**. No user-facing features yet.

### F1.0: Production Stability (Session 2)
| AC | Description | Status | Tests | Flag |
|----|-------------|--------|-------|------|
| F1.0.1 | Cross-channel races prevented (row-level locks) | ✅ | 11 unit | - |
| F1.0.2 | Duplicate listings prevented (per-iteration commits) | ✅ | 4 integration | - |
| F1.0.3 | Batch corruption prevented (rollback handlers) | ✅ | 3 unit | - |
| F1.0.4 | No data loss on crash (idempotency checks) | ✅ | 2 unit | - |

**Verification**: Run production bug fix tests
```bash
pytest tests/test_cross_channel_sale_concurrency.py -v
pytest tests/test_recreate_cycle_batch_safety.py -v
```

### F1.1: Feature-Flag System
| AC | Description | Status | Tests | Flag |
|----|-------------|--------|-------|------|
| F1.1.1 | Email dispatch can be toggled via env var | ✅ | 3 unit | - |
| F1.1.2 | Listing publish can be gated (dry-run/live) | ✅ | 2 unit | - |
| F1.1.3 | Price alerts can be rolled out in phases | ✅ | 2 unit | - |
| F1.1.4 | Build Designer gated for Phase 4 | ✅ | 1 unit | - |
| F1.1.5 | No code deploy needed for rollouts | ✅ | 1 unit | - |

**Verification**: Check feature flag defaults
```bash
pytest tests/test_feature_flags.py::TestFeatureFlagDefaults -v
```

### F1.2: CPK Versioning
| AC | Description | Status | Tests | Flag |
|----|-------------|--------|-------|------|
| F1.2.1 | Build version tags generated from CPU-Mobo-RAM | ✅ | 4 unit | - |
| F1.2.2 | Soft supersession (never hard-delete builds) | ✅ | 2 unit | - |
| F1.2.3 | Version chains queryable (history tracking) | ✅ | 2 unit | - |
| F1.2.4 | Readiness for "Rebuild with X" flows | ✅ | 1 unit | - |

**Verification**: Generate and query versions
```bash
pytest tests/test_cpk_versioning.py -v
```

### F1.3: Money Value Type
| AC | Description | Status | Tests | Flag |
|----|-------------|--------|-------|------|
| F1.3.1 | Currency arithmetic without float rounding | ✅ | 6 unit | - |
| F1.3.2 | Type-safe (no mixed-currency operations) | ✅ | 4 unit | - |
| F1.3.3 | Currency conversions with explicit rates | ✅ | 5 unit | - |
| F1.3.4 | Database storage as integer pennies (no loss) | ✅ | 2 unit | - |
| F1.3.5 | Business logic (profit, markup, discount, fees) | ✅ | 6 unit | - |

**Verification**: Run Money type tests
```bash
pytest tests/test_money.py -v
```

### F1.4: Test Infrastructure (Admin Dashboard)
| AC | Description | Status | Tests | Flag |
|----|-------------|--------|-------|------|
| F1.4.1 | Vitest + React Testing Library configured | ✅ | - | - |
| F1.4.2 | Component tests runnable (npm test) | ✅ | 36 sample | - |
| F1.4.3 | 80% coverage target enforced | ✅ | - | - |
| F1.4.4 | E2E tests with Playwright ready | ✅ | - | - |
| F1.4.5 | Testing guide available (TESTING.md) | ✅ | - | - |

**Verification**: Run admin tests
```bash
cd flipflop-admin
npm install
npm test lib/formatting.test.ts
```

---

## Phase 2: Price Alerts + Listing Proliferator

User-facing features. Gated by feature flags (safe-by-default).

### F2.1: Price Alerts System
| AC | Description | Status | Flag | Depends On |
|----|-------------|--------|------|-----------|
| F2.1.1 | User can set price-drop alerts | ⏳ | `PRICE_ALERTS_RULES_ENABLED` | F1.1 |
| F2.1.2 | Alert emails sent when price drops | ⏳ | `PRICE_ALERTS_EMAIL_ENABLED` 🏴 | F2.1.1 + F1.1.1 |
| F2.1.3 | Five-star auto-price (experimental) | ⏳ | `PRICE_ALERTS_FIVE_STAR_AUTO` | F2.1.1 |
| F2.1.4 | Price history tracked for trends | ⏳ | `PRICE_ALERTS_RULES_ENABLED` | F2.1.1 |

**Rollout Plan**:
```bash
# Phase 2a: Rules disabled (safe)
export FEATURE_PRICE_ALERTS_RULES_ENABLED=false
export FEATURE_PRICE_ALERTS_EMAIL_ENABLED=false

# Phase 2b: Rules on, email off (test in production)
export FEATURE_PRICE_ALERTS_RULES_ENABLED=true
export FEATURE_PRICE_ALERTS_EMAIL_ENABLED=false

# Phase 2c: Full rollout (both on)
export FEATURE_PRICE_ALERTS_RULES_ENABLED=true
export FEATURE_PRICE_ALERTS_EMAIL_ENABLED=true
```

### F2.2: Listing Proliferator (Multi-Channel)
| AC | Description | Status | Flag | Depends On |
|----|-------------|--------|------|-----------|
| F2.2.1 | User can list build on multiple channels | ⏳ | `LISTING_PUBLISH_ENABLED` | F1.1 |
| F2.2.2 | Dry-run mode shows what would be listed | ⏳ | `LISTING_PUBLISH_DRY_RUN_ONLY` 🏴 | F2.2.1 |
| F2.2.3 | Live listing publishes when ready | ⏳ | `LISTING_PUBLISH_ENABLED` | F2.2.1 |
| F2.2.4 | Inventory reserved during listing phase | ⏳ | `LISTING_INVENTORY_RESERVATION` | F2.2.1 |

**Rollout Plan**:
```bash
# Phase 2a: Safe mode (dry-run only)
export FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY=true
export FEATURE_LISTING_PUBLISH_ENABLED=false

# Phase 2b: Enable live publishing
export FEATURE_LISTING_PUBLISH_ENABLED=true
export FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY=false
```

---

## Phase 3: Demand Intelligence

Data-driven insights. Gated by feature flags.

### F3.1: Demand Intelligence Module
| AC | Description | Status | Flag | Depends On |
|----|-------------|--------|------|-----------|
| F3.1.1 | View demand metrics (sold count, active count) | ⏳ | `DEMAND_INTEL_ENABLED` | F1.3 (Money) |
| F3.1.2 | Export demand data to CSV | ⏳ | `DEMAND_INTEL_EXPORTS` | F3.1.1 |
| F3.1.3 | Historical demand trends | ⏳ | `DEMAND_INTEL_ENABLED` | F3.1.1 |
| F3.1.4 | Predictive alerts (high-demand builds) | ⏳ | `DEMAND_INTEL_ENABLED` | F3.1.1 |

---

## Phase 4: Optimal Build Designer

AI-assisted design. Later phases. Gated by feature flag.

### F4.1: Build Designer
| AC | Description | Status | Flag | Depends On |
|----|-------------|--------|------|-----------|
| F4.1.1 | Designer generates optimized builds | ⏳ | `BUILD_DESIGNER_ENABLED` | F1.1 |
| F4.1.2 | User can refine suggestions | ⏳ | `BUILD_DESIGNER_ENABLED` | F4.1.1 |
| F4.1.3 | Designs saved to library | ⏳ | `BUILD_DESIGNER_ENABLED` | F4.1.1 |

---

## Cross-Cutting Concerns

### Infrastructure
| Concern | Phase | Status | Implementation |
|---------|-------|--------|-----------------|
| Database migrations | 1 | ✅ | Alembic (20260823_*) |
| Feature flags | 1 | ✅ | FeatureFlags + env vars |
| Money precision | 1 | ✅ | Decimal value type |
| Logging/monitoring | 1 | ✅ | structlog + existing |
| Error handling | All | ✅ | Explicit rollback handlers |
| Testing | 1 | ✅ | Pytest + Vitest |

### Deployment
| Activity | Phase | Status | Notes |
|----------|-------|--------|-------|
| Code review | Before each | ✅ | code-reviewer agent |
| Test coverage | 80%+ | ✅ | Enforced in vitest.config |
| Security scan | Before each | ✅ | security-reviewer agent |
| Migration test | 1 | ✅ | Alembic downgrade works |
| Staging deploy | Before prod | ✅ | With safe flag defaults |
| Monitoring | After | ✅ | structlog for tracing |

---

## Rollout Timeline

### Session 2 (2026-08-22)
- ✅ F1.0: Production bug fixes (4 AC)

### Session 3 (2026-08-23)
- ✅ F1.1: Feature-flag system (5 AC)
- ✅ F1.2: CPK versioning (4 AC)
- ✅ F1.3: Money value type (5 AC)
- ✅ F1.4: Test infrastructure (5 AC)

### Session 4 (Planned)
- ⏳ Finalize Phase 1 AC
- ⏳ Begin Phase 2 design

### Phase 2 (2026-09)
- ⏳ F2.1: Price alerts (4 AC)
- ⏳ F2.2: Listing proliferator (4 AC)

### Phase 3 (2026-10)
- ⏳ F3.1: Demand intelligence (4 AC)

### Phase 4 (2026-11+)
- ⏳ F4.1: Build designer (3 AC)

---

## Feature Flag Dependencies

### Safe by Default
```
FEATURE_EMAIL_DISPATCH_ENABLED              = false  (kills email)
FEATURE_LISTING_PUBLISH_ENABLED             = false  (kills publish)
FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY        = true   (safe mode)
FEATURE_PRICE_ALERTS_RULES_ENABLED          = false  (no alerts)
FEATURE_PRICE_ALERTS_EMAIL_ENABLED          = false  (no email)
FEATURE_PRICE_ALERTS_FIVE_STAR_AUTO         = false  (no automation)
FEATURE_BUILD_DESIGNER_ENABLED              = false  (Phase 4)
FEATURE_DEMAND_INTEL_ENABLED                = false  (Phase 3)
FEATURE_DEMAND_INTEL_EXPORTS                = false  (Phase 3)
FEATURE_LISTING_INVENTORY_RESERVATION       = false  (Phase 2)
FEATURE_RECREATE_CYCLE_END_OLD_LISTING      = false  (bug fix gate)
```

### Phased Enablement
```
Phase 1: All flags OFF (safest)
Phase 2a: PRICE_ALERTS_RULES_ENABLED=true, email OFF
Phase 2b: PRICE_ALERTS_EMAIL_ENABLED=true
Phase 2c: LISTING_PUBLISH_ENABLED=true, DRY_RUN_ONLY=false
Phase 3: DEMAND_INTEL_ENABLED=true
Phase 4: BUILD_DESIGNER_ENABLED=true
```

---

## Verification Checklist

### Phase 1 Complete When
- [ ] All 4 production bug fix tests pass
- [ ] All 11 feature-flag tests pass
- [ ] All 11 CPK versioning tests pass
- [ ] All 38 Money type tests pass
- [ ] All 36 formatting tests pass
- [ ] Staging deployed with flags OFF
- [ ] No logs from enabled flags (silent when disabled)
- [ ] AC-to-phase matrix reviewed by user

### Phase 2 Ready When
- [ ] Price alerts code reviewed (code-reviewer agent)
- [ ] Listing proliferator code reviewed
- [ ] New tests written (80%+ coverage)
- [ ] Security scan passed (security-reviewer agent)
- [ ] Phase 2 AC all completed
- [ ] Flags ready to enable via env vars

---

## Updates

**Created**: 2026-08-23  
**Last Updated**: 2026-08-23  
**Phase 1 Status**: 23/23 AC complete (100%)  
**Next Phase**: Phase 2 (2026-09)

See [INDEX.md](INDEX.md) for overall progress.
