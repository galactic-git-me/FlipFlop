# Implementation Plan: FlipFlop Demand Intelligence + AI Commerce Copilot

Status: **Draft v3 — production bugs partially fixed (2026-08-23), PRD Phase 0 discovery complete.** Five production issues identified: three race conditions FIXED, one batch-commit issue FIXED, one issue requiring verification FLAGGED. See [production-bug-fixes.md](production-bug-fixes.md) for detailed status. Do not implement full-scope PRD features yet; complete Path A verification first.
Depends on: [discovery.md](discovery.md), [critical-review-1.md](critical-review-1.md) (including its follow-up section)

## 1. Current-state architecture (summary — see discovery.md for evidence)

- `flipflop-admin` (Next.js/TS, Redux Toolkit + TanStack Query) → BFF route handlers → `flipflop-api` (FastAPI/Postgres/SQLAlchemy 2.0/Alembic).
- Demand/pricing logic scattered across ~54 files (`intel.py`, `demand.py`, `price_benchmarks.py`, `cpk_consolidation.py`, `cpk_market.py`, `cpk_pipeline.py`, `ebay_pricing.py`, `benchmark_scorer.py`, `resale_scraper.py`, `gem_service.py`, `quote_service.py`, hardcoded prices in `ai_service.py`).
- Gems already exist (`/super-gems`, `GemBuild`, `routes/gems.py`, classification taxonomy).
- Generic alerts already exist (`alerts.py`, `alert_event.py`, `api/alerts.py`).
- eBay: official Trading API (writes: revise price, respond to offers, order sync) + Playwright browser automation (scraping: sold comps, some active search) + FlipFlopXtension (the only working sold-comps source, via authenticated real-browser DOM scraping).
- Two auth mechanisms coexist (`require_operator` header-key, fail-open; `get_current_admin` JWT, loopback-bypass).
- Existing Dual-Channel Watcher (`flipflop-commerce-and-cxp-platform-prd.md` §9) is the current, 2-channel, production double-sell-prevention mechanism.
- No frontend unit-test framework wired up (Playwright E2E only).
- Scheduler (APScheduler) job history is in-memory only; per-job idempotency not yet confirmed.

## 2. Target architecture — service boundaries and ownership (revised per module census)

Corrected against the function-level census in critical-review-1.md's follow-up section. Verdict key: **DELETE** (functionality subsumed, module removed after confirming no live callers), **CALL-THROUGH** (kept as a thin wrapper delegating to the canonical implementation), **OUT-OF-SCOPE** (genuinely distinct concern, left alone).

| New/canonical service | Verdict per absorbed module | Owns |
|---|---|---|
| **Market Valuation Service** (wraps `opportunity_scoring.py` + `cpk_market.py` — NOT built from scratch, these are already the right core) | `cpk_consolidation.py` DELETE (confirm no live callers first); `ebay_pricing.py` CALL-THROUGH; `resale_scraper.py` CALL-THROUGH; `market_research.py` DELETE (confirm no live callers); `benchmark_scorer.py` DELETE; hardcoded prices in `ai_service.py` DELETE; `cpk_pipeline.py`/`cpk_extractor.py` OUT-OF-SCOPE (own CPK versioning work, see below) | `getMarketValuation`, condition-separated New/Used/Refurb/Open-box Active/Sold, low/median/high, sample size, freshness, confidence, provenance — adopts the extension's `BenchmarkStatSchema` shape |
| **Opportunity/Classification consolidation** (converge on `opportunity_scoring.py`) | `gem_radar/scoring.py` CALL-THROUGH; `deal_classification.py` CALL-THROUGH (extract shared boundary constants both currently hardcode independently); `benchmark_scorer.py` DELETE (also listed above — its scoring formula is redundant with this) | One scoring/classification model instead of four; `price_refresh.py` OUT-OF-SCOPE for now (separate legacy JSON path, flag for later) |
| **Pricing consolidation** (converge on `pricing_engine.py`) | `builds_pricing.py`'s inline floor/anchor math CALL-THROUGH (currently reimplements with a hardcoded 10% margin vs `pricing_engine`'s `DEFAULT_MIN_MARGIN_PCT`); `ebay_pricing.py`'s `calculate_pricing_tiers` CALL-THROUGH | Single floor/anchor/step-down/channel-pricing formula set — PRD 02 §10.3 channel pricing builds on this, not from scratch |
| **Compatibility consolidation** (promote `compatibility_engine.py`'s private extraction helpers to a shared public module) | `configurator_compatibility.py` OUT-OF-SCOPE (distinct customer-facing concern) but its dependency on `compatibility_engine`'s private helpers should become a public import | Compatibility hard-gate for PRD 02's Optimal Build Designer reuses this, does not reimplement it |
| **Demand & Opportunity Service** | `demand.py`, `intel.py` extended, not replaced | `getDemandMetrics`, `estimateDaysToSell`, `calculateMaxBuyPrice`, `generateMarketBriefing` |
| **Gem Service** (extends existing) | `gem_service.py` OUT-OF-SCOPE (distinct: speculative-build recommender, not deal scoring, despite name collision — flag rename risk); `routes/gems.py`/`/super-gems` reconciled, not duplicated | Gem/Super Gem classification via the Opportunity/Classification consolidation above |
| **Insight Inbox Service** (new) | extends `alerts.py`/`alert_event.py` | `assistant_insight`, unread state, action history |
| **Price Alert Service** (new, on top of Insight Inbox) | extends `alerts.py`, reuses `favourite_matching.py`'s fuzzy matcher | rules, evaluation, email idempotency (extends `email_service.py`) |
| **Star Rating Service** (new, small, isolated) | none — genuinely new per user decision | user-assigned rating field, decoupled from Gem classification |
| **Listing Review Service** (new) | none identified | performance ingestion (channel-supported only — confirmed eBay REST/Inventory API is the write-authoritative path), health score, approved-edit workflow |
| **Build Optimisation Service** (new) | `playbooks.py`/`playbook_evolution.py` (demand-signal input only) | compatibility hard-gate (via consolidated `compatibility_engine.py`), scenario generation — must not collide with the customer-facing 3D Configurator's naming/routes |
| **Channel Adapter & Publishing Orchestrator** (new, phased) | **The old "Dual-Channel Watcher" this was meant to shadow/replace does not exist** — `channel_watcher_service.py` was never built; the PRD's §9 describes unbuilt work. What exists (`cross_channel_guard.py`) is much smaller and had a live race condition (now fixed — see status note above). Revised approach: build the new Reservation/Reconciliation Service properly from the start, using `process_flip_sale`'s crash-safe idempotency pattern as the template, rather than treating this as "shadow an existing mature system" | canonical listing model, per-channel adapters (eBay + website first, matching the 2 channels that actually work today), N-channel publish |
| **Inventory Reservation / Order Reconciliation Service** (new) | No mature reference implementation to match/exceed exists (see above) — build with `SELECT ... FOR UPDATE` row locking from day one (per the fix just applied to `cross_channel_guard.py`), plus the CRITICAL `double_sale` alert path PRD §9.5 calls for but was never implemented | transactional reservation, race-condition handling, alerting on partial failure |

The chatbot (Hermes) becomes a thin orchestration layer calling these services via typed function-calling (this is a real architectural change — today it's plain prompt completion with duplicated helper functions). No business logic moves into prompts.

### CPK identity versioning (new, required — was previously undesigned)

Confirmed unstable: CPK is LLM-derived (Ollama/Qwen2:7b), reassignment does a hard delete of prior rows with only partial backfill, no model-version/extraction-method persisted, no snapshot mechanism. Required additions to `cpk_extractor.py`/`cpk_pipeline.py` before the Market Valuation Service can claim reproducible historical trends (PRD 01 AC#10):
1. Persist `model_version`/`extraction_method` alongside the existing `cpk_confidence` column.
2. Replace hard-delete-on-reassignment with soft supersession (`superseded_at`, keep old row) so a January CPK snapshot is reconstructable in March.
3. Add a full backfill path for `gem_radar_cpk_listing_price` on reassignment (currently `gem_radar_sold_observations` has partial backfill, `cpk_listing_price` has none).
4. Add a minimum-confidence gate below which listings go to a review queue (`data_quality_issue`) instead of entering a valuation cohort.

### Money representation (new, required)

Confirmed float throughout the pricing/CPK pipeline (only `quote_service.py` uses `Decimal`, and it's unrelated/isolated). This is a pre-existing systemic gap, not introduced by this plan. Required: a `Money` value type, one documented float(pounds)→int(pence) conversion boundary at the API/persistence edge, an explicit rounding policy, and property tests for monetary invariants — added as an explicit Phase 1 task, not assumed away.

## 3. Canonical typed contracts (illustrative — finalize in Phase 1)

```
MarketValuation { productKey, condition, geography, window,
  low, median, high, trimmedMean?, sampleSize, observationWindow,
  newestObservation, sourceCoverage, deliveryTreatment, trend, confidence,
  status: "ok" | "insufficient_sample" | "unavailable", unavailableReason? }
```
(Shape adapted directly from the extension's existing `BenchmarkStatSchema` — see discovery.md §8b — to avoid inventing a third schema across FlipFlop + FlipFlopXtension + this new service.)

```
AssistantInsight { id, type, priority, createdAt, readAt?, entityRefs[],
  confidence, lifecycleStatus: new|viewed|shortlisted|actioned|purchased|rejected|dismissed|snoozed|expired|failed,
  actionHistory[] }

PriceAlertRule { id, origin: manual_admin|five_star_automatic|system,
  sourceEntity?, productMatch, conditionSet, absoluteThreshold?, percentBelowMarket?,
  benchmarkSelection, vendors[], sellerConstraints?, priority, channels[], enabled }

CanonicalListing { id, sourceType, content{title,specs,media[],condition,qty},
  costs{}, delivery{}, returns{}, warranty{}, provenance{field:source} }

ChannelCapability { channel, mode: full_api|assisted|export_only|unavailable }
```

All monetary values: integer minor units + currency (GBP pence). All timestamps: UTC persisted, UK-local displayed.

## 4. Database migrations

Alembic, additive-only, no destructive changes. New tables per discovery.md §11 shared-concepts list (`assistant_insight`, `assistant_action`, `user_feedback`, `gem_event`, `listing_performance_snapshot`, `listing_review`, `listing_change`, `price_alert_rule`, `price_alert_event`, `notification_delivery`, `build_playbook`, `build_proposal`, `build_proposal_component`, `proposal_prediction`, `sales_channel_connection`, `channel_capability`, `listing_group`, `channel_listing`, `publish_job`, `publish_attempt`, `inventory_reservation`, `channel_order_event`, `audit_event`, `component_star_rating` [new, per user decision]).

Rollback: every migration paired with a `downgrade()` that only drops newly-added tables/columns — no destructive changes to existing `gem_radar_favourites`, `Build`, `Listing`, `GemBuild`, or `Inventory*` tables. Backfill jobs run idempotently and are re-runnable.

## 5. Background jobs, idempotency, concurrency

- All new jobs registered through the existing APScheduler pattern in `scheduler.py`, but each new job must persist its own idempotency key/run state to DB (not the current in-memory-only `_job_history`), addressing the discovery gap.
- Price Alert evaluation: transactional, one initial email per unique `(source_listing_id, rule_id, trigger_event)` — idempotency key persisted, checked before send.
- Inventory reservation: DB-level transactional reservation with row locking (Postgres `SELECT ... FOR UPDATE` or equivalent) around "reserve unit → pause/end other listings" — explicit concurrency test required before this touches real channels (per user decision, gated behind proving parity with the old Watcher first).

## 6. Permissions, audit, secrets

- **Decision needed in Step 2 (open item)**: pick ONE auth mechanism for all new routes — recommend `get_current_admin` (JWT) since it's the newer pattern, keeping `require_operator` only on the legacy routes that already use it (no expansion of the fail-open header-key pattern to new surfaces).
- `audit_event` table records actor, time, inputs, generated output, approval, external request/response ID, outcome, with secret/token redaction.

## 7. Feature flags & staged rollout

Each Phase 2+ feature ships behind a config flag (extend existing `settings` pattern in `flipflop-api/app/config.py` or equivalent — to confirm exact mechanism during Phase 1). No channel publish, no live listing edit, and no real email send in default-off state until explicitly enabled.

## 8. Observability

Structured logs + correlation IDs across publish/alert workflows, extending existing logging setup (to be confirmed which logging library is already in use — follow-up).

## 9. Test strategy

- Backend: pytest, extend the existing ~50-file suite. New: idempotency tests (duplicate alert scans, duplicate publish retries), concurrency tests (simultaneous cross-channel "sold" events), migration tests, contract tests for the new typed services.
- Frontend: **first Jest/Vitest unit-test setup for flipflop-admin is now in scope** (gap identified in discovery.md §10) — required before Phase 2 frontend work, per user's 80%-coverage standing rule.
- E2E: extend existing Playwright config.

## 10. Phase-by-phase plan

### Phase 0 — Discovery & architecture (this document + discovery.md)
Status: in progress, pending Critical Reviewer pass.

### Phase 1 — Shared foundations
- ~~Deep-dive diff of the 54 pricing-related files~~ **DONE** — see revised §2 absorption table above.
- Build Market Valuation Service as a facade over `opportunity_scoring.py` + `cpk_market.py` (already the correct core — not built from scratch), converging `ebay_pricing.py`/`resale_scraper.py`/etc. onto it per the CALL-THROUGH/DELETE verdicts above, adopting the extension's `BenchmarkStatSchema` shape.
- **Build the feature-flag mechanism from scratch** — confirmed none exists (only ~6 ad-hoc `Settings` booleans, no toggle abstraction). This is a blocking Phase 1 deliverable, not a "confirm exact mechanism" task — required before any Phase 2 alert/email code is written.
- **Build the email dispatch kill switch** — confirmed `email_service.py` has zero environment-based guard beyond "no-ops if SMTP unconfigured." Add an explicit `EMAIL_DISPATCH_ENABLED` flag (via the new flag mechanism) that writes `notification_delivery` rows as `suppressed` when off, so the full pipeline is testable without ever sending.
- CPK identity versioning work (see §2) — model version persistence, soft supersession, full backfill on reassignment, confidence gate.
- Money representation: `Money` value type, conversion boundary, rounding policy, property tests.
- Persistent Insight Inbox on top of `alerts.py`/`alert_event.py`.
- Audit table, job idempotency persistence (existing jobs, not just new ones — `run_deferred_publish_job`'s crash-duplicate bug is now fixed as a template for the pattern to apply elsewhere).
- **Written ToS/legal risk decision required** — confirmed no legal review artifacts exist anywhere in either repo; the extension code comments reference `experiments/ebay_manual_login_scrape.py`/`check_ebay_login.py`, but those files no longer exist in `flipflop-api/experiments/` (only a stale browser-profile cache remains). Whatever legality assessment they represented is not recoverable — a fresh, written decision is needed, not a reading task.
- Set up flipflop-admin frontend unit-test framework (Vitest recommended).
- Standardize on `get_current_admin` (JWT) for all new routes; existing `require_operator` consumers (5 routers) migrate opportunistically, not blocking.
- Correlation-ID/request-ID logging middleware — confirmed structlog is in use but has no per-request correlation ID; new infrastructure, not a "confirm which library" task.
- Read the actual `cross_channel_guard.py` implementation (done, see below) before designing the Reservation/Reconciliation Service.
- Author an AC-to-phase traceability matrix covering both PRDs in full (PRD 01 §17 + §12's persistence layer, PRD 02 §17) as a Phase 1 deliverable — several ACs (comparable-evidence drill-down, days-to-sell back-testing, exports, watchlists, five-star-drops-below-five lifecycle, header badge) currently have no owning phase and must be explicitly scheduled or descoped in writing.

**Status note**: two urgent pre-existing production bugs were found and fixed independently of this phased plan (not phase-gated — fixed immediately given live risk): (1) unlocked race condition in the cross-channel sale-confirmation path (`cross_channel_guard.py`, `public_showcase.py`, `manual_builds.py` — now use `SELECT ... FOR UPDATE`), (2) duplicate-eBay-listing bug in `run_deferred_publish_job` (`recreate_cycle.py` — now commits per-flip instead of batching).

### Phase 2 — Gems, Bargain Hunter, Price Alerts, Star Ratings
- Rename/consolidate `/super-gems` into the new Copilot inbox (reconcile, don't duplicate) — explicit decision needed on whether `/super-gems` stays as a standalone screen or becomes a filtered view of the Insight Inbox.
- Build new Star Rating feature (net-new per user decision) — small, isolated schema addition.
- Price Alert rules/evaluation/email — extend `alerts.py`, reuse `favourite_matching.py`.
- Used Bargain Hunter using Market Valuation Service.

### Phase 3 — Listing Review & Demand Review
- Performance ingestion limited to what channels actually support (confirm eBay Trading API's supported performance metrics — likely partial; do not fabricate unsupported metrics).
- Demand Review as a chatbot summary layer over the Demand & Opportunity Service — no recalculation in prose.

### Phase 4 — Optimal Build Designer
- Compatibility hard-gate as deterministic code.
- Playbook integration with `playbooks.py`/`playbook_evolution.py` for demand signal input only.
- Explicit naming/route audit to avoid collision with the customer-facing 3D Configurator.

### Phase 5 — Listing Proliferator foundation (dry-run only)
- **Correction**: there is no mature "old Watcher" to shadow — `channel_watcher_service.py` was never built; PRD §9 describes unbuilt work. The existing `cross_channel_guard.py` mechanism (now race-fixed) is the actual current baseline, not a system to eventually retire in favour of something already proven — it IS the not-yet-fully-proven system.
- Canonical listing model, channel registry/adapters — concrete for eBay + website only (the 2 channels that actually work today), no generic N-channel adapter interface until a 3rd channel's real constraints are known (avoids the over-engineering the critical review flagged in the original ~24-table migration set — cut to the ~8 tables Phases 1-2 actually need, defer channel/proposal tables to Phase 5 itself).
- Dry run only — no real publish, no real channel writes.
- Test suite must cover what `cross_channel_guard.py` currently doesn't: concurrent-sale race scenarios (now closeable via the same row-lock pattern just applied), and the CRITICAL `double_sale` alert path on partial withdrawal failure (currently silent — logged only, no alert, no retry).

### Phase 6 — Multi-channel operations (real publish, gated)
- Enable real publish for eBay + website first, only after Phase 5's test suite (including simulated concurrent-sale races, ≥100 iterations, asserting exactly one reservation succeeds) passes.
- No "migrate off the old Watcher" step needed — `cross_channel_guard.py`'s row-locked version (post-fix) can remain the live mechanism until the new Reservation/Reconciliation Service is proven, at which point cut over via a single atomic ownership flag with a documented rollback, not a vague "bake-in period."
- Additional channels added incrementally, each requiring its own capability audit (full_api/assisted/export_only/unavailable) before enabling.

## 11. Open items still requiring resolution before Phase 1 code changes

1. Deep-dive diff of the 54 valuation-related files (assign as first Phase 1 task, not skippable).
2. Read `alerts.py`/`alert_event.py`/`api/alerts.py` in full.
3. Confirm eBay Trading API's actual supported performance-metrics surface for Listing Review.
4. Confirm exact feature-flag mechanism already in use (or absence thereof) in `flipflop-api/app/config.py`.
5. Confirm logging/observability library already in use.
6. Bake-in period for retiring the old Watcher — needs explicit user sign-off before Phase 6, not assumed.
