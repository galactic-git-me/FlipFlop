# Critical Review Pass 1 — verdict: NO-GO for Phase 1

Full critique from the independent Critical Reviewer agent. See discovery.md and plan.md for context.

## Verdict
**NO-GO for Phase 1 implementation as currently planned.** The plan's central "consolidation" claim is unsound (it doesn't know about several existing modules that already do much of what it proposes to build), and its safety story for real emails/publishes rests on infrastructure (feature flags) that doesn't exist yet.

## CRITICAL findings

1. **Incomplete module census.** plan.md's absorption table never read `app/services/pricing_engine.py`, `app/services/compatibility_engine.py`, `app/services/configurator_compatibility.py`, or `app/gem_radar/opportunity_scoring.py` — all of which already implement large parts of what PRD 01/02 ask for (robust median/percentile pricing, liquidity scoring, deterministic compatibility gates, channel pricing with margin floors). Building "new" versions of these would create duplicates, not consolidation.
2. **"Market Valuation Service" mostly wraps, doesn't subsume.** Of ~13 pricing-related modules, only the hardcoded chatbot prices are a clean absorption; everything else is wrap/defer/unknown. Net result could be N+1 pricing paths, not one source of truth.
3. **CPK identity is LLM-derived, but PRDs require deterministic dedup.** No stability measurement, no deterministic core key, no confidence gate, no snapshot-freezing for reproducible historical trends. This breaks PRD 01 AC#10 and PRD 02 AC#2 if CPK groupings drift between runs.
4. **ToS/marketplace risk is documented then dropped.** The only sold-price data source depends on scraping an authenticated eBay session with no legal review artifact anywhere. The plan reduces this to "read some experiment files" instead of a written risk decision + kill switch + Marketplace Insights API cost evaluation.
5. **No feature-flag infrastructure exists**, yet Phase 2 ships real automated emails (five-star → auto rule → scheduled evaluation → SMTP send) with no human-in-the-loop gate. A bad scrape (selector break → £0 prices) could flood real inboxes with false "99% off" alerts.
6. **Watcher cutover is hand-waved.** "Bake-in period" has no numeric exit criteria, and running the old and new double-sell-prevention systems concurrently (as currently phrased) creates a NEW oversell vector — two writers reserving the same inventory row.

## HIGH findings
- Money representation conflict: plan mandates integer pence, but existing pricing code uses floats throughout — no conversion boundary or rounding policy defined.
- Described tests are labels, not specs — missing adversarial fixtures (PRD 01 §19), missing prompt-injection test for untrusted listing text flowing into a soon-to-be-tool-calling LLM (PRD 02 §13).
- Over-engineering: ~24 new tables proposed up front for an N-channel abstraction when Phase 5 only targets the 2 channels that already work.
- Missing acceptance-criteria coverage: PRD 01's entire persistence layer (`marketplace_observation`, `normalised_listing`, `sale_duration_observation`, `data_quality_issue`, etc.) is absent from the migration plan; several PRD 01/02 acceptance criteria (days-to-sell back-testing, comparable-evidence drill-down, exports, watchlists, briefings, live-edit approval gate, header badge, five-star-rating-drops-below-five lifecycle) have no owning phase/task.

## MEDIUM / LOW findings
- Star-ratings decision (build new) not consistently reflected — discovery.md's own unresolved-questions list still calls it a "hard stop," contradicting the resolved decision.
- Auth mechanism still undecided despite gating publish/live-edit endpoints.
- Existing job idempotency never assessed, only new jobs addressed.
- eBay write-path authority (Trading API vs Playwright per operation) still unresolved despite the plan already committing to a capability-matrix model that depends on the answer.
- Frontend test-framework gap is bigger than a bullet point — zero existing unit tests against an 80%-coverage standing rule.
- Minor doc bugs: broken cross-reference (discovery §11 vs PRD 02 §11), section-ordering issue burying the M1 contradiction.

## Minimum changes required before Phase 1 can safely begin
1. Complete module census at function level across `app/services/**` and `app/gem_radar/**`; rewrite the absorption table as DELETE / CALL-THROUGH / OUT-OF-SCOPE per module.
2. Measure CPK stability empirically; define a deterministic identity core + confidence gate + frozen snapshots.
3. Written ToS/risk decision, Marketplace Insights API cost evaluation, scraping kill switch.
4. Build feature-flag mechanism + suppressed-email path as first Phase 1 deliverables, before any alert code.
5. Read the Dual-Channel Watcher's actual §9.5 implementation now; replace "bake-in" with a shadow-mode cutover spec with numeric exit criteria.
6. Money type + conversion boundary + rounding policy + property tests.
7. AC-to-phase traceability matrix covering both PRDs in full, including PRD 01's missing persistence layer.
8. Cut Phase 1 migrations from ~24 tables to the ~8 that Phases 1-2 actually need.
9. Reconcile discovery.md's stale "hard stop" language on star ratings; add a Favourites-deprecation task.
10. Decide the auth mechanism and a scoped five-operation permission model.

Items 1-5 are blocking. Items 6-10 are each hours of work and should close in the same pass.

---

## Follow-up investigation results (2026-08-23)

Three parallel read-only investigations were run to close blockers 1, 3, 5.

### Blocker 1 (module census) — RESOLVED, revised verdicts produced
Read all 18 pricing/compatibility/CPK files at function level. Revised absorption table (supersedes plan.md §2):

| File | Verdict |
|---|---|
| `pricing_engine.py` | CALL-THROUGH — becomes canonical; `builds_pricing.py` and `ebay_pricing.py` currently reimplement the same floor/anchor math with different constants |
| `compatibility_engine.py` | CALL-THROUGH — `configurator_compatibility.py` already imports its private helpers directly; promote to shared public module |
| `configurator_compatibility.py` | OUT-OF-SCOPE — genuinely distinct (customer configurator UI) |
| `opportunity_scoring.py` | CALL-THROUGH — the correct core economics engine; `benchmark_scorer.py` and `gem_radar/scoring.py` should converge on it instead of maintaining 3 parallel scoring schemes |
| `cpk_consolidation.py` | DELETE (pending confirm no live callers) — superseded by `cpk_market.py`'s live rolling-window aggregate |
| `cpk_market.py` | OUT-OF-SCOPE — this IS the authoritative CPK market-price accumulator, keep as canonical |
| `cpk_pipeline.py` | OUT-OF-SCOPE — correct live CPK-assignment entry point |
| `cpk_extractor.py` | OUT-OF-SCOPE — needs versioning additions (see CPK stability below), not consolidation |
| `ebay_pricing.py` | CALL-THROUGH — duplicates pricing_engine's floor/anchor concept with a 3rd formula set |
| `price_refresh.py` | OUT-OF-SCOPE — separate JSON-file legacy path, flag staleness/duplication risk for later |
| `market_research.py` | DELETE (pending confirm no live callers) — stale hardcoded fallback, functionally superseded |
| `benchmark_scorer.py` | DELETE — stale hardcoded tables, 3rd independent scoring formula |
| `resale_scraper.py` | CALL-THROUGH — duplicates price_refresh/cpk_market fetching independently |
| `gem_service.py` | OUT-OF-SCOPE — distinct concern (speculative build stock, not deal scoring) despite name collision with "Gem Radar" |
| `quote_service.py` | OUT-OF-SCOPE — distinct customer quoting flow, correctly isolated, uses Decimal |
| `builds_pricing.py` | CALL-THROUGH — endpoint layer fine, inline floor/anchor math (10% margin, hardcoded) should call `pricing_engine.py` instead |
| `gem_radar/scoring.py` | CALL-THROUGH — 3rd parallel classification model, boundary constants duplicated (not imported) into `deal_classification.py` |
| `gem_radar/deal_classification.py` | CALL-THROUGH — correct as CPK-offset classifier, but hardcodes boundary constants that must manually stay in sync with `scoring.py`'s |

**Net verdict revision**: original plan's "one Market Valuation Service absorbing 6 modules" undersold the mess (found 18 files, ~4 parallel scoring/classification systems: `opportunity_scoring`, `gem_radar/scoring`, `deal_classification`, `benchmark_scorer`) but the consolidation IS achievable — `opportunity_scoring.py` + `cpk_market.py` are already the right architectural core; the work is making everything else call through them instead of reimplementing.

### CPK stability — CONFIRMED UNSTABLE, blocks reproducible trends as feared
- CPK assignment is LLM-based (Ollama/Qwen2:7b, `temperature=0.1` — reduces but does not eliminate variance), hash = `sha256(category|brand|model)[:16]`.
- Confidence IS stored per-assignment (`cpk_confidence` column) but **model version/extraction method is NOT persisted** — cannot tell which model produced a given CPK.
- **No versioning/snapshot mechanism exists.** Reassignment does a **hard delete** of the prior `gem_radar_listing_cpk` and `gem_radar_cpk_listing_price` rows before re-extracting — not a soft supersession. A January grouping is architecturally indistinguishable from a March re-run.
- `opportunity_scoring.py`/`cpk_market.py` have **no reassignment-handling logic** — when a CPK changes, price history silently splits (old observations orphaned under stale key, new key starts from zero, `MIN_LISTINGS_FOR_SETTLED_PRICE=2` means the listing drops out of classification until 2 new observations accumulate). Partial backfill exists for `gem_radar_sold_observations` (matches on `match_key`, but only fills `NULL` rows, never re-points already-attached rows) — no backfill at all for `gem_radar_cpk_listing_price`.
- **Confirmed money representation gap**: pricing/CPK pipeline is float throughout (only `quote_service.py` uses Decimal, unrelated to acquisition pricing). Systemic pre-existing gap, not newly introduced by this plan.

### Blocker 5 (Watcher) — CRITICAL: the PRD's §9 mechanism does not exist; what exists has a live, reachable duplicate-listing bug
- `channel_watcher_service.py` (named in `flipflop-commerce-and-cxp-platform-prd.md` §9.3 as the implementation) **does not exist** — confirmed via glob, zero matches. The PRD's own text labels it "new." **§9 describes unbuilt work, not a system to extend.** This overturns the earlier assumption (critical-review-1 C6, plan.md Phase 5/6) that a mature Watcher exists to shadow/replace.
- What actually exists is `app/services/cross_channel_guard.py` — a much smaller mechanism, wired live into `public_showcase.py::confirm_checkout` (storefront) and `manual_builds.py::sync_ebay_order` (eBay side).
- **No row lock, no unique constraint, no advisory lock anywhere** — both sale-confirmation paths use an in-Python check-then-set (`if product.status == SOLD: raise 409`) with no DB-level concurrency control. This is a textbook TOCTOU race: two near-simultaneous sale confirmations on the two different endpoints could both read "not sold" and both proceed. **This is a live oversell vector today, independent of any new PRD work.**
- Partial-failure handling is explicitly documented as intentional: the module docstring states withdrawal failures are "logged loudly but never raised past the caller... leaves a stale listing live instead." The caller sets `ebay_withdrawn = True` unconditionally once the call is *attempted*, regardless of actual outcome. No CRITICAL alert, no retry, no needs_attention state — contrary to what PRD §9.5 calls for.
- Zero test coverage found for this mechanism (`cross_channel_guard|withdraw_ebay_for_sold_build|withdraw_storefront_for_sold_build` — no matches in `tests/`).
- **Separately found: a real, reachable duplicate-eBay-listing bug** in `app/workers/recreate_cycle.py::run_deferred_publish_job` — it loops over multiple flips calling the real eBay create-listing API per flip, but only commits the whole batch once at the end. A crash after flip #3's eBay POST succeeds but before the batch commit means flip #3 gets **listed on eBay twice** on the next run (no idempotency check against an existing live offer/SKU before re-posting).
- By contrast, `ebay_sales_tracker.py`'s `poll_sales` → `flip_sale_processor.py::process_flip_sale` IS correctly idempotent (`if flip.stage == sold: return None`, evaluated before any external side effect) — this is the right pattern to copy elsewhere.

### eBay write-path authority — RESOLVED
All eBay writes are REST (Inventory API / httpx), not Playwright — confirmed across create-listing, revise-price, withdraw/end-listing. Only `RespondToBestOffer` and message polling still use the legacy Trading API (XML), and that's intentional (REST doesn't cover those operations yet) — not a fallback/ambiguity. `ebay_trading_api.py::revise_fixed_price_item` exists but is dead code (zero call sites) — do not resurrect it; it's documented as incompatible with REST-created listings.

### Blocker 3 (feature flags) / auth / ToS / logging / email kill-switch — RESOLVED
- **No feature-flag infrastructure exists.** Settings has ~6 ad-hoc booleans (`ebay_use_api`, `ram_watch_enabled`, `email_monitor_enabled`, `auto_buy_autonomous`, `web_only`, `ebay_reselling_enabled`), no central toggle abstraction, no per-request/percentage targeting. Would need to be built from scratch.
- **Auth split**: `require_operator` (fail-open header-key) used by 5 routers; `get_current_admin` (JWT, loopback-bypass) used by 10 routers. Migration effort to standardize: ~15 files, moderate.
- **No ToS/legal review artifacts exist anywhere in the repo.** The `experiments/ebay_manual_login_scrape.py`/`check_ebay_login.py` files referenced by the extension's code comments **no longer exist** — `experiments/` today contains only a stale browser-profile cache. Whatever legality assessment those scripts' comments referred to is not recoverable from this repo. No LEGAL.md/COMPLIANCE.md anywhere.
- **Logging**: structlog, consistently used, but **no correlation-ID/request-ID middleware exists** — would be new infrastructure.
- **Email has zero environment kill switch** beyond "no-ops if SMTP unconfigured" — `_send()` has no `app_env` check; if real SMTP credentials are ever present in a dev environment, real emails go out with nothing to stop it.

## Revised go/no-go

**Still NO-GO for any code that touches real channel writes, real email, or real inventory reservation** — but for a different, more urgent reason than originally scoped: **the pre-existing dual-channel sale-reconciliation code has a live, unlocked race condition and a live, reachable duplicate-listing bug, independent of the new PRDs.** This should be surfaced to the user as its own item, separate from PRD prioritization, since it's a current production risk with real inventory and a real eBay seller account.

**Conditional GO** for Phase 1 foundational work that does NOT touch real channels/email/reservations: consolidating the pricing/scoring modules per the revised census table, building the feature-flag mechanism, adding CPK versioning, building the Star Rating feature (net-new, isolated), and building the Insight Inbox read-only scaffolding. None of this requires resolving the Watcher/race-condition question first.

---

## Second critical review pass (2026-08-23) — verified the applied fixes, found them incomplete

A second independent reviewer verified plan.md's revisions AND re-read the actual code of the two bug fixes applied earlier. Findings:

**Plan document status**: 3 of 10 original items fully resolved (module census, feature-flag design, money-type plan), 4 partially resolved, 3 not resolved (AC traceability matrix not yet written, migration table not actually cut from ~24 to ~8, star-ratings "hard stop" language in discovery.md §3/§13 never removed despite being superseded by §14's decision). Several internal contradictions found (plan.md §1 still calls the non-existent Watcher "the current, production" mechanism in one place while Phase 5 correctly says it doesn't exist).

**Code fix verification — found real problems, now fixed in this session:**
1. **A third unlocked sale path was missed**: `app/routes/webhooks.py::_handle_product_payment_succeeded` (the Stripe webhook fallback for `confirm_checkout`) had the identical unlocked check-then-set race. **Fixed**: added the same `SELECT ... FOR UPDATE` locking, in the same ManualBuild-before-Product order.
2. **The two locking fixes used inconsistent lock order** — `sync_ebay_order` locked ManualBuild then Product; `confirm_checkout` locked Product then (implicitly, via UPDATE) ManualBuild. This is a textbook ABBA deadlock: Postgres would abort one transaction, and in `confirm_checkout`'s case that could happen *after* the eBay listing was already withdrawn (an external call that doesn't roll back) but before the storefront Order committed — a worse outcome (payment taken, eBay listing dead, order lost) than the original race. **Fixed**: standardized on ManualBuild-before-Product everywhere; `confirm_checkout` now looks up and locks any linked ManualBuild before locking Product.
3. **External I/O (eBay withdrawal, SMTP) was being held under the row lock** for the whole request in `confirm_checkout`, since `get_db`'s dependency only commits once at request end. This meant a slow eBay call or SMTP timeout held a lock (and a pooled DB connection) for its full duration, making the ABBA deadlock above far more likely to actually occur, not just theoretically possible. **Fixed**: added an explicit `await db.commit()` immediately after the sale-critical DB writes (Product SOLD, Order created), before any external calls, releasing the lock. Applied to both `confirm_checkout` and the webhook fallback.
4. **An ordering bug in my own fix**: the first pass of this fix set `manual_build.status = "sold"` *before* calling `withdraw_ebay_for_sold_build` — but that function's own idempotency guard skips the withdrawal entirely once `status == "sold"`, so eBay withdrawal would have silently never fired. **Fixed**: status is now set only after the withdrawal call succeeds, matching the original (pre-fix) ordering, with a second small commit.
5. **`run_recreate_cycle_job` had the same batch-commit bug as `run_deferred_publish_job`**, and was worse — its exception handler logged and continued *without rolling back*, meaning a flip's partial price-drop mutation could get committed on the *next* iteration's commit even though its own eBay post failed, with `next_recreate_at` never advancing — causing repeated price erosion and repeated eBay posting attempts for that flip on every subsequent run. **Fixed**: added per-iteration commit and `db.rollback()` in the except block, matching the pattern applied to the sibling job.

**Not fixed, requires user input — flagged, not silently patched:**
- **`_recreate_flip` (same file) appears to never end the prior eBay listing before creating a new one.** It calls `_publish_flip` with no `listing_id`/`sku`, and `post_flip_to_ebay` mints a fresh SKU when none is passed — so each 7-day recreate cycle may create a brand-new live eBay listing while `flip.ebay_listing_id` is overwritten, losing the only pointer to the previous one. If accurate, this means the recreate cycle has been silently accumulating orphaned live listings on the real eBay seller account. **This needs verification against the actual eBay account before any code change**, and fixing it properly requires either storing the eBay SKU on `Flip` (a schema change) or confirming this is intentional "always relist fresh" behavior rather than a bug — a decision for the user, not something to guess at unattended.
- `Order.stripe_payment_intent_id` has no unique DB constraint (only `nullable=True, index=True`), so the idempotency check-then-insert pattern used in both `confirm_checkout` and the webhook has no database-level backstop against a true simultaneous double-insert. Row locks now prevent this for the Product/ManualBuild race specifically, but a belt-and-suspenders unique constraint would still be good practice — deferred as a small future migration, not urgent given the row locks now in place.
- The reservation step (`_load_buyable_product`/checkout-intent creation, before payment) is still unlocked — two buyers could both reserve and both pay, with one needing a refund. Lower severity than the sale-confirmation race (money isn't lost, just an awkward refund), left as a known limitation for now.
