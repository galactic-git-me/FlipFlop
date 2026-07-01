# FlipFlopOS — Master Product Requirements Document (As-Built)

**Document status:** Living document — reflects the actual current state of the codebase
**Last synced to codebase:** 2026-07-01
**Scope:** `flipflop-api` (FastAPI backend), `flipflop-admin` (Next.js internal dashboard), `flipflop-storefront` (Next.js customer site)

> This document describes what is **actually implemented** today, not a future roadmap. For proposed/future modules see [`customer-experience-platform-prd.md`](./customer-experience-platform-prd.md) (Customer Experience Platform — not yet built) and [`../superpowers/plans/2026-06-28-flipflop-made-to-order-prd.md`](../superpowers/plans/2026-06-28-flipflop-made-to-order-prd.md) (Made-to-Order flow). Update this document whenever a feature ships.

---

## 1. Product Overview

FlipFlopOS is a vertically integrated platform for a PC-flipping and made-to-order PC building business. It spans three applications sharing one Postgres database and one FastAPI backend:

- **flipflop-api** — business logic, marketplace scraping, AI evaluation, playbook engine, orders, payments.
- **flipflop-admin** — internal dashboard for sourcing, building, inventory, fulfilment, and analytics.
- **flipflop-storefront** — public site where customers configure and buy a PC.

The business operates in two overlapping modes: **flipping** (buy underpriced used components/PCs off marketplaces, refurbish, resell) and **made-to-order building** (customer configures a spec from a Playbook, pays, a build is sourced and assembled to order). Both modes share the same component/pricing/demand intelligence layer.

---

## 2. Architecture Summary

| Layer | Technology | Notes |
|---|---|---|
| Backend | FastAPI (Python), SQLAlchemy async, Postgres, Redis | Routers under `app/api/*.py` and `app/routes/*.py`; services under `app/services/`; scheduled jobs under `app/workers/` (APScheduler) |
| Admin | Next.js (App Router) | `flipflop-admin/app/<route>` |
| Storefront | Next.js (App Router) | Route groups `(app)` (configurator) and `(auth)` (login/signup/OAuth callback) |
| Payments | Stripe | PaymentIntents + webhook-driven order creation |
| Auth | JWT (email/password) + OAuth (Google, GitHub) | `Customer` model, bearer-token dependency |
| AI | Ollama (local) → OpenRouter (free tier) → Claude API (paid) fallback chain | Used for chat, gem recommendations, listing evaluation |
| Scraping | Playwright-based browser automation | eBay, Facebook Marketplace, Gumtree; proxy/anti-bot rotation |
| Deployment | Docker Compose (dev: hot-reload; local: production-like) | All services bind `0.0.0.0`; internal hostname `andromeda-ts` |

---

## 3. Backend API Surface

### 3.1 Marketplace & Sourcing

| Router | Purpose |
|---|---|
| `sources.py` | Register/enable/disable scraper sources (eBay, Facebook, Gumtree, Amazon), track source health |
| `source_search_terms.py` | Define/update per-source search queries (e.g. eBay search "RTX 3060") |
| `listings.py` | Aggregate, search, filter, dedupe, and classify marketplace listings (gem / amazing_gem / overpriced / no_profit) |
| `manual_submit.py` | Admin manually submits/corrects a listing outside automated scraping |
| `swarms.py` | Multi-agent swarm tasks — parallel searches across sources for component price discovery |
| `facebook.py` | Facebook Marketplace–specific scrape/post/message tracking |
| `search_telemetry.py` | Tracks user searches/clicks/refinements for search UX tuning |
| `preflight.py` | Health checks for scrapers/API/DB before a scan run |

### 3.2 Flips (Resale Pipeline)

| Router | Purpose |
|---|---|
| `flips.py` | Full flip lifecycle: create/list/update, stage transitions (`selected → building → ready_for_sale → sold`), cost tracking, sale-platform tracking |
| `reselling.py` | Pricing recommendations, margin calculation, platform comparison (eBay vs Facebook vs Gumtree) |
| `ebay_listings.py` | Create/update/track eBay listings, pull sales data, fee tracking |
| `ebay_compliance.py` | Validate condition descriptions and listing policy adherence before posting |
| `vendors.py` | Supplier pricing, lead times, reliability scores |

### 3.3 Components, Parts & Inventory

| Router | Purpose |
|---|---|
| `parts.py` | Component catalogue search by category/spec, cached market prices, condition tracking (new/used/refurb) |
| `catalogue.py` | Admin catalogue: review queue for pending playbook variants, approve/reject, case CRUD, slot configuration |
| `public_catalogue.py` | Customer-safe subset of playbooks/variants exposed to the storefront |
| `inventory.py` | Purchased-component inventory with landed cost (base + shipping − discount) |
| `inventory_allocations.py` | Reserve/deallocate inventory items against a specific order |

### 3.4 Playbooks & Build Generation

| Router | Purpose |
|---|---|
| `playbooks.py` | CRUD, demand signal tracking, proposal workflow, seeding |
| `build_wizard.py` | Multi-agent build pipeline: `/generate` (full wizard), `/generate-gem-matrix` (gem-first builds), `/plan` (step-by-step purchase plan), `/playbooks` (active list) |
| `manual_builds.py` | User-entered custom PC specs outside playbook templates |

### 3.5 Orders, Payments & Fulfilment

| Router | Purpose |
|---|---|
| `orders.py` (`/api/orders`) | Available build slots (rolling 8-week window), checkout sessions, capacity overrides, order detail retrieval |
| `routes/quotes.py` | Build spec → quote (component cost + labour + overhead) with delivery slot |
| `routes/payments.py` | Stripe PaymentIntent create/confirm/status/refund |
| `routes/webhooks.py` | Stripe webhook — `payment_intent.succeeded` creates the `Order` record |
| `routes/admin.py` (`/api/admin`) | Admin order list/detail, status updates, checklist management, photo upload, shipping tracking |
| `routes/guides.py` (`/api/guides`) | Welcome Guide PDF generation and status |
| `schedule.py` | Scheduling for scrapes, market scans, demand-analysis runs |

### 3.6 Auth & Accounts

| Router | Purpose |
|---|---|
| `routes/auth.py` | Signup (email/password/name), login (→ JWT), `/me` (current profile) |
| `routes/oauth.py` | Google/GitHub authorization URLs, callback → token exchange → customer create/link |

### 3.7 Benchmarks, Pricing & Demand Intelligence

| Router | Purpose |
|---|---|
| `benchmarks.py` | Fetch/refresh CPU/GPU benchmark scores (gaming/workstation/single-thread), normalize to 0–100 |
| `price_benchmarks.py` | Historical component price trends, refresh, deal alerts |
| `ram_watch.py` | DDR4/DDR5 market monitoring, purchase-timing recommendations |
| `demand.py` | Purchase-intent/search-pattern event recording, feeds demand classifier |
| `intel.py` | Competitive pricing, trend analysis, demand patterns |
| `analytics.py` | Profit by playbook, conversion rates, inventory ROI, demand trends |

### 3.8 AI & Chat

| Router | Purpose |
|---|---|
| `chat.py` | Hermes AI multi-turn chat (listing evaluation, build advice, profit projections) |
| `companion.py` | Lightweight local-first companion LLM (Ollama gemma) for quick queries |
| `routes/gems.py` (`/api/gems`) | List/review AI-generated gem builds, filter by risk level |

### 3.9 System & Ops

| Router | Purpose |
|---|---|
| `alerts.py` | Create/list/acknowledge alerts (price drops, anomalies, system errors) |
| `settings_router.py` | App-level settings (max concurrent flips, auto-buy limits, scan intervals) |
| `config.py` | App configuration (scraper intervals, AI model choice) |
| `logs.py` | Retrieve logs/audit trail |
| `debug.py` | Dev-only reset/seed/trigger utilities |

---

## 4. Data Model (SQLAlchemy, `app/models/*.py`)

Grouped by domain — see the codebase survey for full column-level detail; this is the entity map.

**Marketplace & Inventory:** `Listing`, `ListingArchive`, `Flip`, `Part`, `InventoryItem`, `InventoryAllocation`

**Playbooks & Catalogue:** `Playbook`, `PlaybookProposal`, `PlaybookSlot`, `CatalogueVariant`, `CaseCatalogue`, `GemBuild`

**Customers & Orders:** `Customer`, `Order`, `OrderChecklist`, `OrderPhoto`, `BuildCapacity`, `BuildCapacityOverride`

**Order Personalization:** `DesktopTheme`, `OSComponent`, `WelcomeGuide`

**Hardware Reference:** `HardwareBenchmark`, `ComponentPerformanceMetric`, `BenchmarkRefreshRun`

**Demand & Market Intelligence:** `DemandEvent`, `GoogleTrendsTimeSeries`, `GoogleTrendsGeo`, `RedditPost`, `SteamHardwareStat`, `ExternalDemandSignal`

**Ingestion & Telemetry:** `DataSource`, `SourceSearchTerm`, `SourceRun`, `ListingRaw`, `ListingNormalized`, `SearchTelemetry`, `SearchConfig`, `PriceHistory`

**ML / Outcomes:** `OutcomeEvent`, `RetrainCheckpoint`, `ModelVersion`, `TrainingRun`

**System:** `AppSettings`, `AlertEvent`, `FlipIntelligence`, `Component`, `VendorPrice`

**Order state machine** (`OrderStatus`): `awaiting_sourcing → parts_ordered → building → qa → ready_to_ship → shipped → completed`

**Flip state machine** (`FlipStage`): `selected → building → ready_for_sale → sold`

**Playbook lifecycle** (`PlaybookStatus`): `active | candidate | deprecated | retired`

---

## 5. Admin Dashboard (`flipflop-admin`)

| Route | Function |
|---|---|
| `/playbooks` | List/edit playbooks by status, specs, upgrade/profit/search strategy, demand %/margin history, proposals |
| `/flips`, `/flips/[id]` | Flip pipeline board and detail view — stage, costs, profit, upgrades, eBay listing link, sale price entry |
| `/orders`, `/orders/[id]` | Order list/detail — status, checklist, photos, shipping tracking |
| `/inventory` | Stock by category, landed cost, source, quantity |
| `/catalogue`, `/catalogue/slots`, `/catalogue/variants`, `/catalogue/cases` | Variant review queue (approve/reject/hide), slot tier config, case CRUD |
| `/benchmarks` | Hardware benchmark reference data, refresh trigger |
| `/demand` | Google Trends / Reddit / Steam demand analytics |
| `/intel` | Market intelligence, margin analysis, anomaly alerts |
| `/ram-watch` | RAM price monitor and purchase-timing alerts |
| `/community` | Reviews/testimonials |
| `/chat` | Admin-facing Hermes AI chat test surface |
| `/sources` | Scraper source enable/disable, health, error logs |
| `/selling` | Listing templates, eBay fee schedules, platform choice logic |
| `/settings` | Concurrency limits, auto-buy config, scan intervals, LLM selection |
| `/super-gems` | Gem/amazing_gem opportunity matrix by component category |
| `/opportunities` | Derived build recommendations, missing-component/profit-edge alerts |
| `/schedule` | Scheduled job management (scrapes, demand runs, benchmark refresh) |
| `/search-config` | Per-source/per-playbook search term & filter config |
| `/market-pricing` | Price trend intelligence, resale price recommendations |
| `/metrics` | Business KPIs — builds/week, avg profit/flip, demand fulfillment, inventory ROI |
| `/parts` | Component search, market prices, preferred vendors |
| `/cases` | Case catalogue CRUD |
| `/logs` | Scraper/API error logs, audit trail |

---

## 6. Storefront (`flipflop-storefront`)

### 6.1 Routes

- `(app)` — landing page (playbooks, featured gems, testimonials); `(app)/configurator` — freeform custom build
- `(auth)/signup`, `(auth)/login`, `(auth)/callback` — email/password + Google/GitHub OAuth
- `configure/[slug]` — playbook-specific configurator (tier select → 3D viewer → slot component picker → case/theme → pricing sidebar)
- `order/summary` — review + "Confirm & Pay"
- `order/[reference]` — order tracking (status, delivery date, build photos)

### 6.2 Customer Journeys

**A — Playbook build:** browse playbooks → pick tier (Budget/Mid/High) → live 3D view updates per component pick → choose case/theme → review order summary → Stripe payment → order created `awaiting_sourcing` → admin builds/ships → customer gets Welcome Guide.

**B — Custom/freeform build:** `/configurator` → component-by-component picker with live pricing/performance-per-pound → order summary → payment.

**C — Admin flip sourcing** (internal): `/super-gems` → filter gem-classified listings by category → create flip → select upgrades → estimate resale → mark `ready_for_sale` → post to eBay → record actual sale price.

### 6.3 Key Frontend Components

- `MotherboardViewer3D` — Three.js/GLTF live 3D build visualization with clickable component hotspots
- `CasePicker` — case grid (brand, form factor, transparent-panel badge, RRP)
- Theme/OS selection flow — `DesktopTheme` (Rainmeter config + background) and `OSComponent` (license inventory) selectable at configure/summary time

---

## 7. Services Layer (`app/services/`)

**AI:** `ai_service.py` (Hermes chat, Ollama→OpenRouter→Claude fallback), `companion_service.py` (local quick-query LLM), `gem_service.py` (Claude-powered build recommendations from 30-day demand), `claude_evaluator.py` + `claude_eval_queue.py` (async listing evaluation), `classifier.py` (ML gem/overpriced classifier)

**Playbooks:** `playbook_evolution.py` (demand-driven playbook proposal engine), `playbook_seeder.py` (initial seed data)

**Build generation:** `build_wizard.py` (Wizard→Composer→Validator→Ranker pipeline), `component_search.py`, `component_models.py`, `component_pricer.py`, `estimator.py`, `build_performance_summary.py`

**Demand:** `demand_service.py`, `external_demand.py` (Google Trends + Reddit + Steam synthesis)

**Benchmarks:** `benchmark_fetcher.py`, `benchmark_normaliser.py`, `benchmark_scorer.py`, `benchmark_refresh_job.py`

**Marketplace/eBay:** `ebay_pricing.py` (fee calc, ~12.7% FVF), `ebay_sales_tracker.py`, `ebay_browse.py`, `ebay_listing_poster.py`, `listing_generator.py`, `listing_ingest_queue.py`, `listing_validator.py`, `live_prices.py`, `resale_scraper.py`

**Scraping infra:** `scraper.py`, `playwright_scraper.py`, `manual_scraper.py`, `antibot_preflight.py`, `proxy.py`, `source_health.py`, `browser_pool.py`

**Commerce:** `auth_service.py`, `oauth_service.py`, `payment_service.py` / `stripe_service.py`, `quote_service.py`, `email_service.py`

**Ops/support:** `alerts.py`, `redis_client.py`, `image_processor.py`, `spec_parser.py`, `price_refresh.py`, `selling_toolkit.py`, `guide_service.py` (ReportLab Welcome Guide PDF), `autonomous_loop.py` (auto-buy loop, if enabled), `part_gem_evaluator.py`, `part_gem_scorer.py`

**Workers:** `scheduler.py` (APScheduler — market scans, benchmark refresh, demand analysis, playbook evolution checks)

---

## 8. Payments (Stripe)

- PaymentIntent create/confirm/status/refund (`routes/payments.py`), GBP, pence-denominated
- Webhook (`routes/webhooks.py`) on `payment_intent.succeeded` creates the `Order`
- Metadata carries `order_reference` (format `FF-YYYY-NNNNN`)
- Legacy Stripe Checkout session path also present for line-item-based checkout
- Signature verification via `STRIPE_WEBHOOK_SECRET`

---

## 9. Auth & Accounts

- Email/password: bcrypt hash, JWT issuance, `Customer` model (email, name, address, phone)
- OAuth: Google + GitHub, `Customer` stores `google_id`/`google_email`, `github_id`/`github_username`, `oauth_provider`
- Bearer-token dependency (`get_current_user`) gates authenticated routes
- No password-reset flow currently implemented (see Chapter 12, Gaps)

---

## 10. AI/LLM Integration

| Capability | Model chain | Purpose |
|---|---|---|
| Hermes chat | Ollama gemma (local) → OpenRouter free tier → Claude (paid) | Listing evaluation, build advice, profit projection, compatibility Q&A |
| Gem recommendations | Claude API | Analyzes 30-day order demand + market prices → generates build recs with margin/risk (low/medium/high) |
| Listing classification | Trained classifier + async Claude evaluator | gem / amazing_gem / already_flipped / no_profit / overpriced |
| Playbook evolution | Demand-signal-driven proposal engine | Suggests playbook spec changes from Trends/Reddit/Steam signal shifts |

System prompts inject live market context (current GPU/RAM/SSD prices, eBay fee %, sweet-spot specs) so recommendations stay grounded in current data rather than static training knowledge.

---

## 11. Marketplace & Demand Intelligence

**Sources scraped:** eBay (Playwright automation + listing/sales API integration), Facebook Marketplace (scrape + manual/restricted post), Gumtree (UK local listings), Amazon (RRP price monitoring only).

**Demand signals ingested:** Google Trends (query + geo breakdown), Reddit (r/buildapc, r/pcgaming post volume/score), Steam Hardware Survey (GPU/CPU/RAM/OS adoption %), internal order/search telemetry.

**Analytics surfaced:** business KPIs (`/metrics`), playbook performance (margin %, days-to-sell, demand %), component price trend charts, competitor pricing checks.

---

## 12. Known Gaps / Not Yet Implemented

These are referenced by other planning docs but confirmed **not present** in the current codebase as of this survey:

- No password-reset / forgot-password flow
- No Customer Experience Platform module (Packaging Playbooks, Procurement, Photography/QC gates, USB Builder, per-order 3D asset publish) — full spec exists at [`customer-experience-platform-prd.md`](./customer-experience-platform-prd.md), zero implementation yet
- No AR viewer
- No carrier/shipping-label API integration (tracking numbers are manually entered)
- No multi-warehouse/multi-currency procurement
- No automated social-sharing/posting integration
- Admin nav is a flat, ungrouped list (23 top-level items) not yet organized around any specific operator workflow — pending optimization

---

## 13. Environment & Deployment

- Docker Compose: `docker-compose.dev.yml` (hot-reload dev containers) and `docker-compose.local.yml` (production-like, no volume mounts)
- Ports: storefront `13000`, admin `13001`, API `18000`, Postgres `15432`, Redis `16379`
- All services bind `0.0.0.0`; inter-service hostname is `andromeda-ts` (Docker `extra_hosts`), never `localhost`
- Claude Design System applied to both storefront and admin `globals.css` (deep charcoal `#0f1419` + gold `#d4af37`, serif/sans typography, shared component classes: `.card`, `.btn-primary`, `.badge`, etc.)

---

*This document should be updated whenever a new module ships or an existing one changes shape materially — treat it as the single source of truth for "what does FlipFlopOS actually do today."*
