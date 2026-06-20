# PC FLIP PROFIT MAXIMIZER — PRD v6

*A programmable, AI-powered PC flipping intelligence platform*

Last updated: 2026-06-17

---

## Overview

A web application that automatically discovers undervalued PCs ("gems") across multiple UK sourcing platforms, evaluates them using a multi-model LLM pipeline, tracks market data over time, suggests upgrade paths using live eBay pricing benchmarks, and helps execute flips end-to-end.

---

## Core Objectives

- Automate deal discovery across auction sites, classifieds, and marketplaces
- Build centralised market intelligence (benchmark prices, demand signals, sold history)
- Enable data-driven flipping decisions via AI classification + profit estimation
- Reduce manual effort in finding deals, pricing upgrades, and writing listings
- Learn from historical flip outcomes to improve future estimates

---

## Architecture

### Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (app router), TypeScript, Tailwind CSS |
| Backend | Python 3.12, FastAPI, async SQLAlchemy |
| Scraping | Playwright (headless Chromium via browser pool) |
| Database | PostgreSQL |
| Cache / queues | Redis, in-process asyncio queues |
| Containerisation | Docker Compose |
| Ports | Frontend: 4310, Backend: 4311 |

### Backend structure

```
app/
  api/           # FastAPI routers (one file per domain)
  models/        # SQLAlchemy ORM models
  swarms/        # Scheduled background jobs
  services/      # Business logic, scrapers, LLM, pricing
  scrapers/      # Platform-specific scraper modules
  db/            # DB session, migrations
```

---

## Data Sources

### Active sources (enabled in DB)

| Source | Type | Method | Notes |
|---|---|---|---|
| eBay UK | Classifieds / fixed-price | eBay Browse API v1 | Primary source; BuyItNow listings |
| eBay UK Auctions | Auction | eBay Browse API v1 | Same API, `itemType=AUCTION` filter; separated at ingest |
| Gumtree | Classifieds | Playwright scraper | Cookie popup handling; location-aware |
| Preloved | Classifieds | httpx scraper | UK-only classifieds |
| BidSpotter | Liquidation auction | Playwright (GlobalAuctionPlatform) | Fixed June 2026: was using wrong URL endpoint |
| i-bidder | Liquidation auction | Playwright (GlobalAuctionPlatform) | Same DOM as BidSpotter; fixed same session |
| Wilsons Auctions | Liquidation auction | Playwright | Next.js RSC site; search param `?search=`; cards `.cc-card` |
| Apex Auctions | Liquidation auction | Playwright (BidJS SPA) | Navigates into each of 16 UK auctions; lot cards `.lot.timed-listing` |
| Vinted | Marketplace | Vinted API client | Evaluated June 2026: 96% REJECT — sellers price near eBay resale value; few gems expected |
| Amazon | Marketplace | Playwright | New / warehouse deals |
| Temu | Marketplace | Playwright / Apify | Parts and accessories; delivery filter enforced |
| AliExpress | Marketplace | Playwright | Parts and accessories |
| Alibaba | B2B marketplace | Playwright | Bulk component pricing reference |

### Disabled / blocked sources

| Source | Status | Reason |
|---|---|---|
| Lots.co.uk | Disabled | Cloudflare WAF block — 403 even via Apify proxies |
| The Saleroom | Code only, not in DB | GlobalAuctionPlatform DOM; too sparse PC inventory |
| John Pye | Disabled | Site migrated to `jpub4.johnpye.co.uk`; old scraper broken; high rewrite effort |
| Merkandi | Disabled | Cloudflare Error 1005 — hard IP/ASN ban |
| Wholesale Clearance UK | Disabled | Fixed-price retail, not auction |
| Facebook Marketplace | Bypassed in cooldown | Requires auth; scraper exists but needs session management |

### GlobalAuctionPlatform note

BidSpotter, i-bidder, and The Saleroom share identical robots.txt and DOM structure (`.lot-single` cards, `h3 a` titles, `.opening-price strong` prices). Fixes port directly between them. All use `/en-*/search-results?searchTerm=` endpoint, not `/auction-catalogues`.

### Piece-count false positive fix

Auction titles like "350 PC LINEA" use "PC" to mean "pieces". A regex guard (`\b\d+\s*[xX]?\s*pc\b`) prevents these from matching the `pc` keyword in `_AUCTION_PC_KW`. Residual false positive: "frame" contains "ram" as substring — acceptable, fails downstream spec-parsing.

### Cooldown bypass

All auction sources + major marketplaces bypass the per-source cooldown gate so they always run on schedule:
`eBay UK`, `eBay UK Auctions`, `Facebook Marketplace`, `Gumtree`, `Preloved`, `BidSpotter`, `Lots.co.uk`, `The Saleroom`, `i-bidder`, `Wilsons Auctions`, `Apex Auctions`, `Amazon`, `Temu`, `AliExpress`, `Alibaba`, `BargainHardware`, `CherryTree Inc`

---

## Swarms (Background Jobs)

### Flip Opportunities Swarm (hourly)

`app/swarms/flip_opportunities.py`

1. Iterates enabled data sources from DB
2. Calls `fetch_listings()` in `scraper.py` — routes to correct platform adapter
3. Deduplicates against existing listings (fingerprint hash)
4. Saves new listings to DB with `status=active`
5. Queues new listings for LLM evaluation
6. Marks previously-seen listings as `missing` or `removed` if no longer found

### Upgrade Parts Swarm (daily)

`app/swarms/upgrade_parts.py`

Tracks component pricing for: RAM, GPU, SSD, PSU.
Stores new/used/refurb prices, links, images.

### PC Cases Swarm (daily)

`app/swarms/cases.py`

Builds catalogue of budget, premium, and themed cases for use in the build wizard.

### Accessories Swarm (daily)

`app/swarms/accessories.py`

Tracks keyboards, mice, monitors, and peripherals for bundling.

### Benchmark Refresh (daily)

`app/services/benchmark_refresh_job.py`

Fetches CPU benchmark scores from UserBenchmark / PassMark / Cinebench reference data. Powers the profit estimation engine and playbook pricing. Also refreshes playbook `pricing_model` and `profit_model` from live eBay sold data.

---

## LLM Evaluation Pipeline

### Architecture

In-process `asyncio.Queue` (max 2000 items), drained by 6 background workers.

```
New listing ingested
    → queue_for_claude() check (skip if recently evaluated, unless force-eval)
    → asyncio queue (max 2000)
    → 6 workers, 1s gap between calls per worker
    → evaluate_listing() in claude_evaluator.py
    → verdict written to DB (claude_verdict, claude_reasoning, claude_model_used)
```

### Model priority

1. **Anthropic Claude Haiku** (`claude-haiku-4-5-20251001`) — primary; fast, cheap, reliable structured JSON
2. **OpenRouter** (configurable model, default `meta-llama/llama-3.1-8b-instruct:free`) — fallback when Anthropic unavailable or rate-limited
3. **Ollama local** (configurable model) — last resort; free but slow (~14 min/call on CPU); avoid for production throughput

### Output

Each listing gets:
- `claude_verdict`: `GOOD` / `MAYBE` / `REJECT`
- `claude_reasoning`: one-sentence explanation
- `claude_model_used`: which model produced the verdict
- `estimated_profit`: LLM-estimated flip profit in GBP

### Vinted findings (June 2026)

Evaluated all 1,428 active Vinted listings:
- 1 GOOD (Dell Precision 3440 i5-10600 @ £180 → ~£96 estimated profit)
- 10 MAYBE (avg £107 estimated profit; mostly Dell/HP workstations)
- 1,417 REJECT (96%)

Conclusion: Vinted sellers price close to eBay resale value, leaving little flip margin. Vinted is likely to remain a low-yield source.

---

## Classification Engine

Each listing receives a classification based on profit estimate, source, specs, and LLM verdict:

| Classification | Label | Meaning |
|---|---|---|
| `amazing_gem` | Amazing Gem | Strong buy signal; high profit, clean specs |
| `gem` | Gem | Good buy; solid profit margin |
| `already_flipped` | Already Flipped | Good value but previous owner already upgraded |
| `no_profit` | No Profit Left | Fair market price, no margin |
| `overpriced` | Overpriced | Above market value |
| `unclassified` | Unclassified | Not yet evaluated |

### Gem heuristics (targeting)

Prioritised signals in titles and descriptions:
- "no HDD", "no hard drive", "no storage"
- "no GPU", "no graphics"
- "untested", "spares or repair"
- "collection only", "local collection"
- Poor / incomplete title (short, missing RAM/CPU details)

Target profile: < £150, DDR4, no storage, no GPU, local collection, weak title.

### Exclusions

Mini PCs / NUCs excluded at parse time (use laptop CPUs, soldered RAM, proprietary PSUs, low upgrade ceiling):
`mini pc`, `mini-pc`, `intel nuc`, `nuc pc`, `stick pc`, `pc stick`, etc.

---

## Listing Lifecycle

```
Discovered → active
  → still found on next scan: stays active
  → not found on scan: missing
  → not found for extended period: removed
  → user marks as purchased + sold: sold
```

Listings are never deleted — only versioned and status-updated. This preserves the historical price and data trail.

---

## Profit & Estimation Engine

`app/services/estimator.py`

### Inputs

- Base price (listing price)
- Parsed specs (CPU, RAM, storage, GPU, condition)
- Component upgrade costs (from upgrade parts catalogue)
- Live eBay sold data (benchmark fetcher)
- Platform fees (eBay ~13% + PayPal equivalent)

### Outputs

- `estimated_resale_value`: predicted sell price on eBay
- `estimated_profit`: resale - base - upgrades - fees
- `profit_confidence`: low / medium / high (based on data availability)

### Daily refresh

The estimation engine recalculates profit estimates daily for all active listings as benchmark prices move.

### Learning loop

Flip outcomes (actual sell price vs estimated) feed back into the retraining pipeline to improve future estimates.

---

## Benchmark Intelligence System

`app/services/benchmark_fetcher.py`, `app/api/benchmarks.py`

- Stores CPU benchmark scores (UserBenchmark / PassMark normalised)
- Powers resale value estimation by correlating benchmark score with eBay sold prices
- Daily refresh job; manual refresh via `POST /benchmarks/refresh`
- API endpoints: `/benchmarks/status`, `/benchmarks/top`, `/benchmarks/lookup`, `/benchmarks/refresh-runs`

---

## Playbooks System

11 canonical build strategies, each with pricing linked to live eBay benchmark data.

`app/services/playbook_seeder.py`

### Canonical playbooks

| Name | Target use case |
|---|---|
| Budget Gamer | Entry-level gaming build |
| Mid-level Gamer | 1080p gaming, GTX 1660 tier |
| High-end Gamer | 1440p gaming, RTX 3070+ tier |
| Ultra-Budget Flip | Quick flip, no upgrades needed |
| Office Station Flip | Business PC, SSD + RAM upgrade |
| Content Creator | Video editing, fast CPU + RAM |
| AI Workstation | Local LLM / ML workloads, lots of RAM |
| Dev Workstation | Developer setup, multi-core CPU |
| Student Build | Budget, reliable, portable |
| Family PC | All-rounder, quiet, low power |
| Gift-from-parents PC | Clean, good-looking, affordable |

Retired playbooks (preserved in DB for FK refs): Mainstream Gamer, RGB Showcase, Competitive Gaming, Premium Showcase, and earlier AI-proposed variants.

### Playbook economics refresh

`refresh_playbook_economics_from_benchmarks()` — runs daily; updates `pricing_model` and `profit_model` on all active playbooks using current benchmark data. Never rebuilds from scratch — additive update only.

---

## Spec Parser

`app/services/spec_parser.py`

Extracts structured fields from free-text listing titles and descriptions:
- CPU (model, generation, clock speed)
- RAM (size GB, type DDR3/DDR4/DDR5)
- Storage (type SSD/HDD/NVMe, capacity)
- GPU (model)
- Condition (used, untested, spares)
- Form factor (tower, SFF, mini, all-in-one — mini excluded)

---

## Build Wizard

`app/api/build_wizard.py`, `app/services/build_wizard.py`

1. User selects a listing (the base PC)
2. System shows parsed specs and compatibility
3. User selects upgrade components: RAM, GPU, SSD, PSU, case
4. System calculates total cost and estimated resale
5. Generates eBay listing title + description via `selling_toolkit.py`

---

## Flip Workflow

### States

```
Active listing
  → "Flip This" → active_flip
  → Building (components selected, ordering)
  → Ready for sale (listed on eBay)
  → Sold (outcome captured)
```

`app/api/flips.py`, `app/models/flip.py`

---

## Selling Toolkit

`app/services/selling_toolkit.py`

- Generates eBay-optimised listing titles
- Generates full item descriptions (HTML/plain text)
- Suggests pricing based on benchmark data and current eBay comps
- Future: auto-post to eBay, Facebook Marketplace, Gumtree

---

## Demand Explorer

`app/api/demand.py`, `app/services/demand_service.py`

- Tracks demand signals by CPU generation, form factor, and price band
- Sources: internal sold data, Reddit price check threads, external signals
- API: `/demand/categories`, `/demand/summary`, `/demand/auction-intel`, `/demand/external-signals`

---

## Search Configuration

`app/api/search_config.py` (via settings router)

User-configurable per source:
- Price range (min/max)
- Search terms (prioritised list, cycled per run)
- Condition filter
- Keyword includes / excludes

Term cycling: `app/services/term_cycle.py` — rotates through search term list each run to avoid repetition and maximise coverage.

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/` (dashboard) | Gems table, scatter chart, super gems modal, stats |
| `/opportunities` | Full listing browser with filters |
| `/super-gems` | Super gems gallery (3D flip cards) |
| `/flips` | Active flip tracker |
| `/parts` | Upgrade parts catalogue |
| `/cases` | PC case catalogue |
| `/playbooks` | 11 canonical build strategies |
| `/benchmarks` | CPU benchmark scores + refresh controls |
| `/demand` | Demand explorer and market signals |
| `/market-pricing` | Live eBay price benchmarks |
| `/ram-watch` | RAM price tracker |
| `/selling` | Listing generator + selling toolkit |
| `/search-config` | Search term and config management |
| `/sources` | Data source management (enable/disable) |
| `/schedule` | Swarm schedule viewer |
| `/logs` | Backend log viewer |
| `/settings` | API keys, model config, proxy config |
| `/chat` | Hermes companion bot |
| `/intel` | Market intelligence dashboard |
| `/community` | Community / Reddit signals |

---

## AI Companion (Hermes)

`app/api/companion.py`, `app/services/companion_service.py`

- Chatbot interface for querying listings, evaluating deals, suggesting upgrades
- Personality: dry humour, direct, helpful
- Backed by same LLM stack as evaluator (Haiku → OpenRouter → Ollama)
- Can accept manual listing entries and insert them into the pipeline

---

## Source Health & Antibot

`app/services/source_health.py`, `app/services/antibot_preflight.py`

- Per-source health tracking (success rate, last error, last seen count)
- Antibot preflight checks before scraping (detects Cloudflare, login walls, empty results)
- Browser pool (`app/services/browser_pool.py`): single shared Chromium instance with CDP reconnect fallback to headless launch

---

## Manual Listing Submission

`app/api/manual_submit.py`

- `POST /manual-submit` — user pastes a URL or raw listing; system scrapes and inserts
- `POST /listings/force-eval-source` — bypasses `should_queue_for_claude` gate to force re-evaluation of all listings from a given source

---

## Analytics & Telemetry

`app/api/analytics.py`, `app/services/search_telemetry.py`

- Per-term result counts (found / new / error) logged each run
- Source-level health metrics
- Listing classification breakdown over time
- Profit estimate accuracy (actual vs predicted)

---

## Data Retention Policy

- Listings are never deleted — status updated (`active` → `missing` → `removed` → `sold`)
- Price history retained indefinitely
- Component prices snapshotted daily
- Flip outcomes retained for model retraining

---

## Configuration (Environment)

Key env vars / settings:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude Haiku evaluator (primary LLM) |
| `OPENROUTER_API_KEY` | OpenRouter fallback LLM |
| `OPENROUTER_PRIMARY_MODEL` | Model name on OpenRouter |
| `OLLAMA_BASE_URL` | Ollama local endpoint (last-resort LLM) |
| `OLLAMA_MODEL` | Model name for Ollama |
| `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` | eBay Browse API credentials |
| `EBAY_ENVIRONMENT` | `production` or `sandbox` |
| `EBAY_PLAYWRIGHT_STATE_PATH` | Saved browser session for eBay Playwright fallback |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `FB_HEADLESS` | `0` = show browser (dev), `1` = headless |

---

## Known Limitations / Open Work

| Item | Status |
|---|---|
| Lots.co.uk | Hard-blocked by Cloudflare; no viable bypass found including Apify proxy rotation |
| John Pye | Site migrated; scraper needs full rewrite for uncertain payoff |
| The Saleroom | Code exists, not in DB; too sparse PC inventory to justify enabling |
| Vinted | Low yield expected (96% REJECT); max_price raised to £2000 to capture higher-value items |
| Facebook Marketplace | Scraper exists but requires authenticated session management |
| eBay auto-post | Listing poster code exists (`ebay_listing_poster.py`) but not wired to UI workflow |
| Image generation | Planned; not implemented |
| Vector memory (pgvector) | Planned; not implemented |

---

## Long-Term Vision

- Predictive market intelligence engine (buy timing, demand forecasting)
- Semi-autonomous flip cycle (discover → evaluate → buy suggestion → list → track)
- Data-driven resale optimisation informed by historical outcomes
- Community demand signals (Reddit, forums) feeding gem scoring
