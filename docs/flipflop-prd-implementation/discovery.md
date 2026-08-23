# Discovery: FlipFlop Demand Intelligence + AI Commerce Copilot

Status: **Phase 0 draft — pending PRD reconciliation agent + Critical Reviewer pass.** Do not begin implementation from this document alone.

Repos: `C:\Users\mclar\CODING\FlipFlop` (main app) and sibling `C:\Users\mclar\CODING\FlipFlopXtension` (browser extension).

## 1. Architecture

- **flipflop-admin**: Next.js App Router, TypeScript, Redux Toolkit + TanStack Query, Zod, Playwright for E2E. Next.js route handlers under `app/api/**/route.ts` act as a thin BFF proxy in front of the Python backend. Frontend API client: `flipflop-admin/lib/api.ts`, `lib/admin-api.ts`, `lib/admin-token.ts`.
- **flipflop-api**: Python FastAPI (async), SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Alembic migrations (`alembic.ini`, `app/migrations/versions/*.py`). 40+ route modules under `app/api/`.
- **Database: Postgres only.** `app/database.py` raises `RuntimeError` if `DATABASE_URL` doesn't start with `postgresql`, with an explicit comment that SQLite caused serialization stalls under concurrent load and "must never silently downgrade to SQLite again." **This contradicts CLAUDE.md's PM2 table ("SQLite-backed gem_radar_standalone") and the task brief's assumption** — that description is stale. The root `flipflop.db` file is a legacy/dev artifact, not the live DB.
- Communication: admin frontend → Next.js API routes → FastAPI backend over REST/JSON.

## 2. Existing AI chatbot ("Hermes")

- `app/api/chat.py` (`POST /chat/`) → `app/services/ai_service.py::chat()`.
- Provider fallback chain: **Ollama local (`gemma4:e4b`, primary) → OpenRouter free models → Anthropic Claude Haiku (last resort)**. Confirms local Ollama is genuinely the primary path.
- System prompt hardcodes personality + **stale hardcoded market prices** (e.g. "GTX 1060 6GB: ~£75 used") baked into the prompt — a static snapshot, not live-computed. Direct candidate for replacement once a shared valuation service exists.
- **No tool-calling/function-calling pattern** — plain prompt completion. `generate_listing_content`, `generate_product_images`, `chat_with_images`, `generate_ebay_listing` are separate helper functions each building their own prompt, not a dispatch-to-tools architecture. PRD 02's requirement that "the chatbot orchestrates shared services... does not own duplicate business logic" is a real architectural shift, not a restatement of current behaviour.
- `selling_principles.md` is injected fresh into prompts per existing project convention — reuse this pattern for new prompt injection needs.
- Frontend: `app/chat/page.tsx`, `components/hermes-companion.tsx` (floating widget).
- Separate multimodal path (`chat_with_images`) for OCR-style tasks (e.g. performance card reading) — unrelated to main text chat.

## 3. Favourites / star ratings — CRITICAL, UNRESOLVED

- Model: `app/models/favourite.py`, table `gem_radar_favourites`. Columns: `id`, `term`, `cpk`, `category`, `matched_listing_ids` (JSON dedup ledger), `created_at`, `last_matched_at`.
- **No star-rating field exists anywhere in the schema.** Broad search for `rating`/`star` across backend and frontend found nothing tied to Favourites. Closest analog: `classification` field on `GemRadarScoredListing` (GEM/SUPER_GEM labels from `app/gem_radar/deal_classification.py`) — a computed deal-quality label, not a user-assigned rating.
- **Open question for the user**: does "star rating" in PRD 02 refer to (a) this GEM/SUPER_GEM classification displayed as stars in the UI (nothing to migrate, just re-point the UI), or (b) a genuinely separate feature not found by static search (check `super-gems-modal.tsx` / `super-gems/page.tsx` — closest existing "starred items" UI)? **This must be resolved before any Price Alerts migration touches this data**, since a destructive-migration mistake here would violate the PRD's own "star ratings must survive without loss" acceptance criterion.
- API: `app/api/favourites.py` — `GET /favourites`, `GET /favourites/search?q=`, `GET /favourites/matrix`, `POST/PATCH/DELETE /favourites/{id}`. Write endpoints gated by `require_operator` (fail-open if no key configured — see Auth).
- Matching logic: `app/gem_radar/favourite_matching.py` — shared fuzzy-term matcher used by both `/favourites/search` and a background alert hook in `phase2_runner.py` (`favourite_gem_match`). **Any Price Alerts migration must preserve/re-wire this shared module, not duplicate it.**
- Frontend: `components/FavouritesModal.tsx`.

## 4. Notifications / header badge

- No dedicated notification/unread-count/badge subsystem found (searched `notification|unread|badge` across `app/api` — 4 incidental hits only).
- Existing substrate to build on: `app/services/alerts.py` (`emit_alert`, called from `scheduler.py`), `app/models/alert_event.py`, `app/api/alerts.py`. **Not yet read in depth — required follow-up before designing PRD 02's insight inbox / header badge on top of it**, rather than building a parallel system.
- `tests/test_autonomous_notifications.py` exists — read for expected behaviour before extending.

## 5. Listings / inventory / builds

- `Build` model (`app/models/build.py`) is explicitly documented as "a thin orchestration/routing record shared by flip-origin and Made-to-Order-origin physical units," referencing **`docs/prd/flipflop-commerce-and-cxp-platform-prd.md Ch.6.1`** — confirms a pre-existing, more foundational PRD already governs this area. Fields: `build_type` (FLIP/MADE_TO_ORDER/PREBUILT), `flip_id`, `order_id`, `pcbuild_id`, `manual_build_id`, `playbook_id`, `spec_json`, `status`.
- Related models: `inventory.py`, `inventory_allocation.py`, `listing_archive.py`, `component_catalogue.py`, `manual_build.py`, `draft_build.py`.
- Related routes: `listings.py`, `inventory.py`, `inventory_allocations.py`, `build_wizard.py`, `build_stage_items.py`, `build_comparison.py`, `pc_builder.py`, `manual_submit.py`, `drafts.py`.
- `data/ai_generated_builds.json` is a runtime artifact from `app/services/ai_build_generator.py::generate_ai_builds` (scheduler-wired), not source code.

## 6. Product identity / CPK

- `app/gem_radar/cpk_consolidation.py` — "Canonical Product Key (CPK) consolidation and pricing aggregation," groups listings by CPK (**LLM-derived**, not rule-based fuzzy matching) and aggregates pricing. Key functions: `consolidate_cpk_pricing(db)`, `get_cpk_price(db, cpk, use_new=True)`, `lookup_cpk_confidence(db, cpk)`.
- Also present: `cpk_market.py`, `cpk_extractor.py`, `cpk_pipeline.py`, model `app/models/gem_radar_cpk_market_price.py`.
- CPK identity resolution already exists and is LLM-driven — a materially different mechanism from the extension's static category-lookup (`cpkCategoryForEbayCategory`) and from the fuzzy-term `favourite_matching.py`. PRD 01/02 should build on this rather than introduce a third identity mechanism.

## 7. Vendor data / market prices — DUPLICATION CONFIRMED (named PRD requirement)

Grep for `market_price|valuation|estimate_value|calc.*price|scored\.json` inside `flipflop-api/app` returned **54 matching files**. Distinct, apparently-independent valuation/pricing code paths:

| Module | Apparent role |
|---|---|
| `app/gem_radar/cpk_consolidation.py` | CPK-level price aggregation across vendors |
| `app/gem_radar/cpk_market.py`, `cpk_pipeline.py` | Additional CPK/market pricing logic (undiffed vs. above) |
| `app/services/ebay_pricing.py` | eBay-specific pricing |
| `app/services/price_refresh.py` | Scheduled price refresh job |
| `app/services/market_research.py` | Market research/valuation |
| `app/services/benchmark_scorer.py` | Performance-benchmark scoring |
| `app/services/resale_scraper.py` | Resale price scraping |
| `app/services/gem_service.py` | Gem/deal evaluation |
| `app/gem_radar/scoring.py`, `deal_classification.py` | GEM/SUPER_GEM classification |
| `app/api/builds_pricing.py`, `app/services/quote_service.py` | Build-level/customer-quote pricing |
| `app/services/amazon_bestsellers.py`, `app/gem_radar/adapters/amazon_price.py` | Amazon reference pricing |
| `ai_service.py` `SYSTEM_PROMPT` | Static hardcoded prices baked into chatbot prompt |

**This confirms the PRDs' premise.** A dedicated deep-dive pass (own exploration budget) is required before consolidation design to determine genuine overlap vs. legitimately distinct layers (e.g. CPK aggregate price vs. per-listing deal classification vs. customer quote pricing may be different concerns, not pure duplication). **Not fully diffed — required Phase 0/1 follow-up.**

## 8. eBay integration — hybrid, more capable than assumed

Two parallel mechanisms:
- **Official APIs**: `ebay_trading_api.py` (legacy XML Trading API — comment notes "the modern REST Sell APIs don't cover [some capability]"; supports `revise_fixed_price_item`, `get_best_offers`, `respond_to_best_offer`, `get_member_messages`), `ebay_oauth.py`, `ebay_token_manager.py`, `ebay_listing_poster.py`, `ebay_fulfillment_policies.py`, `ebay_shipping_fulfillment.py`, `ebay_order_sync.py`, `ebay_media.py`, `ebay_negotiation.py`, `ebay_catalog.py`, `ebay_marketing.py`, `ebay_sales_tracker.py`.
- **Browser automation**: `browser_pool.py`, `playwright_scraper.py`, `component_search.py`, `antibot_preflight.py`. `data/ebay_playwright_state.json` is Playwright's persisted session state; `data/ebay_production_token_cache.json` is the cached OAuth token.

**Conclusion**: write capability already exists via the official Trading API (revise price, respond to offers, order sync) — PRD 02's "full API publish" channel classification for eBay should likely be **stronger than a from-scratch assumption**, not "assisted." The scraping side (sold comps, some search) remains fragile/anti-bot-dependent per the Extension Investigator's findings below. **Open question**: confirm per-operation which path is authoritative before finalizing PRD 02's channel capability matrix.

### 8b. Extension sold-price retrieval (from Extension Investigator — FlipFlopXtension, read-only)

- **No official API exists for eBay sold/completed listings** (Marketplace Insights API "isn't provisioned"). The only working path found in the whole system is **real, signed-in-browser DOM scraping** of `ebay.co.uk/sch/i.html?...LH_Sold=1&LH_Complete=1...`, via the browser extension's content scripts (`src/content/ebay-extractor.ts`, `src/background/scan-orchestrator.ts`). Explicit code comment: "neither direct HTTP nor headless Playwright got past eBay's sign-in wall on this specific search... only a real, signed-in browser tab does" — referencing prior experiments at `flipflop-api/experiments/ebay_manual_login_scrape.py` and `check_ebay_login.py` (sibling repo, not yet read).
- Active listings can use the official eBay Browse API (proxied through `flipflop-api`) or DOM scraping as fallback.
- Data contract: extension POSTs `ExtractedListing[]` JSON to `flipflop-api` endpoints — `/api/gem-radar/sold-comps`, `/api/gem-radar/scans`, `/api/gem-radar/scans-queued`, `/api/builds/sold-comps` — with `X-Admin-Key` and an `Idempotency-Key` (SHA-256 of `searchRunId:sourceUrl`). CPK/identity resolution happens **server-side** in `flipflop-api`, not in the extension — the extension only forwards the backend-assigned `cpk`/`query`.
- Reusable, portable utilities (small, pure, zero DOM/extension-API coupling): `src/lib/condition.ts` (regex-based condition normaliser, order-sensitive to avoid "used - spares or repair" false-matching "used") and `src/lib/dedupe.ts` (listing-level URL/ID dedup). **Directly adoptable** for PRD 01's condition taxonomy.
- `BenchmarkStatSchema` (`src/lib/types.ts:200-218`) already matches the shape PRD 01's Market Valuation Service needs: `status: ok|insufficient_sample|unavailable`, median/trimmedMean/min/max, sampleSize, exclusions with reasons, freshness. **Recommend adopting this schema shape** rather than designing from scratch.
- **Recommendation: do not port the DOM-scraping logic.** It's tightly coupled to Chrome's content-script lifecycle and depends on an authenticated real-browser session that headless Playwright reportedly could not replicate for this specific search. Consume its output via the existing `/api/gem-radar/sold-comps` ingestion contract instead.
- Reliability: 6-hour throttle per search, bounded to 3 pages / 200 listings, sign-in gating before navigation, blocked-page detection (Cloudflare/CAPTCHA pattern matching), per-card fault isolation, retry/backoff with 429 handling. Documented history of selector breakage (eBay `.s-item` → `.s-card` markup change in 2025; Scan.co.uk "50%+ data loss" incident per `INVESTIGATION_REPORT.md`) — fragility is real and ongoing, mitigated by graceful degradation, not prevented.
- No explicit ToS-compliance review artifact found in this repo. Uses the user's own real session cookies (`credentials: "include"`), no header/fingerprint spoofing or proxy rotation found in `src/`. Self-imposed conservative throttling, not derived from published eBay rate-limit docs.
- **Unresolved**: actual production reliability/failure rate of the sold-comps flow (not measured here); whether eBay's Marketplace Insights API has ever been formally evaluated for cost/access; legal/ToS review status (may exist in `flipflop-api/experiments/`, out of this pass's scope).

## 9. Jobs / scheduler

- `app/workers/scheduler.py` — APScheduler (`AsyncIOScheduler`, `IntervalTrigger`). ~15+ interval jobs registered (cases swarm, external demand ingestion, playbook evolution, autonomous loop, outcome capture, model retraining + watchdog, compliant market ingestion, benchmark refresh, RAM watcher, price refresh, catalogue pipeline/digest, deferred publish ×2, markdown-event scans, offer poll + send-to-watchers, message poll, AI build generation, email monitor, eBay sales tracker).
- Job history: in-memory only (`deque(maxlen=50)` per job) — **lost on process restart, not persisted to DB.**
- Idempotency/retry-safety **not confirmed at individual job-function level** — only the registration file was read. Required follow-up before PRD 01/02's "idempotent, resumable, rate-limited" job requirements can be verified against current behaviour.
- `data/scheduler_state.json` — persisted job-run bookkeeping (next/last-run timestamps).

## 10. Tests

- **Backend**: pytest, ~50 files under `flipflop-api/tests/` — gem radar scoring/observations/inventory, benchmarks, catalogue, eBay (oauth/media/trading api/listing poster), quotes, pricing engine/bias, offer engine/poll job, security, e2e customer journey, database integrity, storage retention, manual build automation. `test_security.py` exists — read before touching auth.
- **Frontend**: `playwright.config.ts` present for E2E, but **no unit test framework wired up** (no Jest/Vitest config or `*.test.ts(x)` files found outside `node_modules`). Gap vs. the 80%-coverage standard — flag for the TDD phase of new frontend work.

## 11. Auth — two coexisting mechanisms (architectural debt)

1. `app/api/deps.py::require_operator` — header-key check (`X-Admin-Key`). **Fails open** if no key configured ("Backward compatible... keep local-dev access open"). Gates `favourites.py` and other older routers.
2. `app/routes/admin_auth.py::get_current_admin` — JWT-based (`AdminUser`, `admin_login`/`get_admin_by_token`), **but bypasses auth entirely for loopback requests** by design ("admin UI is a personal tool running on this PC"). Non-loopback requires valid JWT. Used on newer routers (e.g. `assets_admin.py`).

**New PRD work should pick one auth pattern consistently** (likely the newer JWT one) rather than adding a third. Flag to Solution Architect.

## 12. Email

- `app/services/email_service.py` — plain `smtplib.SMTP_SSL` (port 465), gracefully no-ops (logs warning, returns `False`) if unconfigured. `send_order_confirmation_email`, `send_shipment_update_email` and likely more. Inline HTML strings, no templating engine, no external transactional provider. **Directly reusable for PRD 02's Price Alerts email** (default `mac@theflipflop.shop` per PRD).
- Separate `app/services/email_monitor.py` — inbound email monitoring (e.g. eBay message replies), different concern from outbound sending. Not read in depth.

## Note on uncommitted files (git status at session start)

- `flipflop-api/app/api/assets_admin.py` — confirmed unrelated: it's the Component 3D Asset Registry CRUD API (Meshy pipeline: `MISSING → MESHY_DRAFT → CLEANED → VALIDATED → FINAL`), matching prior project memory. Uncommitted work-in-progress — will not be touched or committed as part of this PRD work.
- Modified `.json` files under `flipflop-api/data/` (`ai_generated_builds.json`, `ebay_playwright_state.json`, `ebay_production_token_cache.json`, `scheduler_state.json`) are runtime-generated state/cache artifacts from normal app operation, not incomplete feature work.

## 14. User decisions (2026-08-22)

1. **Star ratings**: do not exist yet. Build as a genuinely new user-assigned rating feature, separate from the existing Gem classification (`gem/amazing_gem/already_flipped/no_profit/overpriced`). No legacy data to migrate — the "preserve star ratings" acceptance criterion in PRD 02 §7.1/§17.7 is satisfied trivially (there is nothing to lose) once the new field exists.
2. **Multi-channel publishing**: build the new canonical listing model + N-channel Listing Proliferator as PRD 02 describes, treating it as the eventual replacement for the existing 2-channel Dual-Channel Watcher (`flipflop-commerce-and-cxp-platform-prd.md` §9). Plan an explicit migration off the old Watcher once the new system's sale-reconciliation/reservation logic is proven safe in production — do not run two independent double-sell-prevention mechanisms concurrently once the new one is live. Until the new Watcher-equivalent is proven, the OLD Watcher remains authoritative for any live eBay+website dual-listing safety — the new Proliferator's inventory-reservation logic must not go live for real channels until it has passed the same or stronger safety bar (see plan.md).

## Unresolved questions requiring follow-up before/during implementation

1. **Star ratings**: no schema found anywhere in the codebase. Must be clarified with the user before any Price Alerts migration — see §3.
2. **Market-price/valuation duplication**: 54 files touch pricing/valuation; only surface-level roles identified. Requires a dedicated deep-dive pass to map real overlap before designing the single shared Market Valuation Service.
3. **Notifications substrate**: `alerts.py`/`alert_event.py`/`api/alerts.py` look like the right foundation for the insight inbox/header badge but weren't read in depth.
4. **Scheduler job idempotency**: not confirmed at individual job-function level.
5. **CLAUDE.md accuracy**: PM2 table's "SQLite-backed" description is stale (actual DB is Postgres-only) — informational, not urgent; no CLAUDE.md edit will be made without being asked.
6. **eBay write-path authority**: confirm per-operation whether the official Trading API or Playwright is authoritative before finalizing PRD 02's channel capability matrix.
7. **Two coexisting auth mechanisms**: needs a decision, not a third pattern.
8. **Pre-existing related PRDs**: `docs/prd/flipflop-master-prd.md`, `docs/prd/flipflop-commerce-and-cxp-platform-prd.md`, `docs/prd/customer-experience-platform-prd.md` already exist and at least one is directly referenced by the live `Build` model. **A reconciliation pass against the two new PRDs is in progress and required before Step 3 (architecture/plan.md) can be finalized** — results to be appended to this document.
9. Sold-comps pipeline's actual production reliability/failure rate, and whether eBay's Marketplace Insights API has been formally evaluated.
10. Whether the extension's DOM-scraping approach for sold data has had any legal/ToS review — no such artifact found in either repo pass so far.

## 13. Reconciliation against pre-existing PRDs — CRITICAL

Three PRDs already exist in `docs/prd/`: `flipflop-master-prd.md` (306 lines, as-built survey), `flipflop-commerce-and-cxp-platform-prd.md` (806 lines), `customer-experience-platform-prd.md` (1222 lines).

**Verdict: (c) partially overlapping/conflicting — needs reconciliation, not greenfield.**

### PRD 01 (Demand Intelligence)
Mostly **formalization/extension of already-implemented functionality**: `demand.py`, `intel.py`, `price_benchmarks.py`, `ram_watch.py`, admin routes `/demand`, `/intel`, `/opportunities`, `/market-pricing`. Demand signals already ingested from Google Trends/Reddit/Steam Hardware Survey. What's genuinely new: formal median/confidence/provenance-tagged valuation, explicit max-buy-price formula, condition-separated (new/used active/sold) valuation as a first-class contract. **Low conflict risk if framed as "extend/consolidate existing intel/demand routers into one service" rather than building a parallel system.**

### PRD 02 (AI Commerce Copilot) — HIGH OVERLAP RISK
- **Gems already exist as-built**: `/super-gems` admin route, `GemBuild` model, `routes/gems.py` (`/api/gems`), and an existing classification taxonomy `gem / amazing_gem / already_flipped / no_profit / overpriced` with risk levels `low/medium/high`, generated via Claude API from 30-day order demand + market prices. PRD 02's "Recent Gems and Super Gems" is a **rename/consolidation of this existing pipeline**, not new — must be explicitly reconciled (rename `/super-gems`? merge into new insight inbox? keep separate?).
- **Price Alerts overlaps existing `alerts.py`** (generic alerts system already handling "price drops, anomalies, system errors") — must extend, not duplicate.
- **Listing Proliferator / Multi-Channel Publisher directly collides with an existing, more mature safety mechanism**: `flipflop-commerce-and-cxp-platform-prd.md` §9 (lines 373-441) already defines a "Dual-Channel Listing & Email/Notification Watcher" with a sale-reconciliation mechanism explicitly built to prevent double-selling (§9.5, "the core dual-listing safety mechanism," Objective C1) — but scoped to **two** channels, not N. **Building PRD 02's open-ended multi-channel publisher without integrating with this existing Watcher risks reintroducing the exact double-sell bug the Watcher exists to prevent.** This is the single highest-risk overlap found in discovery.
- **AI chat/copilot already exists**: Hermes (`chat.py`) plus a separate local-first Ollama "companion" (`companion.py`) — PRD 02 expands rather than replaces this, consistent with discovery §2.
- **Build Designer**: no existing match. Adjacent but distinct: `playbooks.py`/`playbook_evolution.py` (demand-signal-driven playbook proposals) and a **customer-facing** "Made-to-Order 3D Configurator" (`flipflop-commerce-and-cxp-platform-prd.md` §10.9/§12). PRD 02's Optimal Build Designer is admin-internal and appears genuinely net-new — but naming must not collide with "Configurator" in nav/routes.

### Star ratings / Favourites — confirmed undocumented anywhere
Zero matches for "star," "favourite," or "favorite" across all three existing PRDs, and no schema found in the codebase (§3 above). **This concept has no documented origin in either the codebase or any existing PRD.** This is a hard stop requiring direct user clarification before any Price Alerts migration work begins — see Decision Memo.

### Conventions to preserve
- Router naming: domain-named, not `*_service.py` (e.g. `demand.py`, `intel.py`, `alerts.py`, `gems.py`).
- AI model chain already established: Ollama (local) → OpenRouter (free) → Claude (paid) — new Copilot work should reuse this chain, not introduce a new one.
- `GemBuild`, `PlaybookProposal` are existing data-model entities to extend, not shadow.
- Reservation/lifecycle pattern precedent: `ProcurementReservation` mirrors `inventory_allocation`'s status enum exactly — any new reservation-like concept (e.g. inventory reservation in PRD 02 §10.4) should follow this same lifecycle-reuse convention.
- No existing "Phase N" roadmap language in these three docs — the new PRDs' phase numbering is a fresh convention, not a continuation of an existing one.
- New reporting screens go under the existing "Reporting & Analytics" nav grouping, not new top-level nav entries — though the master PRD itself flags current nav as "flat, ungrouped... pending optimization."
