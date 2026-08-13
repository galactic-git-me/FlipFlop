# Build Details Page & eBay Automation — Implementation Plan

Source of truth: the "Flip Flop Algorithm Playbook" artifact (`fa529446-25a2-4cc4-be2e-5d2b23009c32`), fetched fresh on 2026-08-13. This plan covers all 37 rows of the "Automation roadmap (ordered by profit impact)" table, plus the existing build-details page fields discovered in the codebase (Step 0 inventory below). The 10 "Manual-only practices" rows and the 2 meta/disputed commentary rows are explicitly out of scope, per the playbook.

This is a **scoping/architecture plan, not code**. Implementation happens in a later session. Every item below states its scope (per-build page UI / global eBay setting / background service / external integration / browser extension / admin tool), its tab placement if applicable, its dependencies, and — where the playbook left a value open — a proposed default flagged for one-time confirmation.

---

## Step 0 — Inventory of what already exists

The current build-details page is the **Flip** entity at `flipflop-admin/app/flips/[id]/page.tsx`, backed by the `Flip` model (`flipflop-api/app/models/flip.py`). It is a single un-tabbed page today. Existing sections, all of which need a home in the new tab structure (or a documented reason to stay outside it):

| Existing section | Backing fields | Where it predates the tab redesign |
|---|---|---|
| Stage stepper (Selected → Building → Ready for Sale → Sold) | `Flip.stage` | Page-level chrome, not listing content |
| Listing/source card (spec pills, source link, base cost) | `Listing.cpu/gpu/ram_gb/...`, `Flip.base_cost` | Page-level chrome — describes the sourced item, not the eBay listing |
| Playbook & upgrade slots (parts picker, compatibility check) | `Flip.selected_upgrade_ids`, compatibility panel | Pre-listing build process |
| Purchase plan checklist | derived from upgrade slots | Pre-listing procurement |
| Financials card (cost basis, est. resale, est./actual profit, fees) | `Flip.total_cost`, `initial/current_estimated_resale`, `initial/current_estimated_profit`, `actual_sale_price`, `actual_profit`, `platform_fee_pct` | Feeds directly into the new Pricing engine |
| eBay listing generator (title/description) | `Flip.generated_title`, `generated_description` | Feeds directly into the new Listing Content tab |
| Notes | `Flip.notes` | Freeform, low-automation |
| Sold form (sale price, platform, profit preview) | `Flip.actual_sale_price`, `sale_platform` | Listing-lifecycle-ending event |
| Advance-stage action bar | `Flip.stage` transitions | Page-level chrome |
| Profit breakdown sub-page (`profit.tsx`) | `inventory-allocations` API | Its own page today; content folds into Pricing tab |

**Decision:** stage stepper, listing/source card, playbook/upgrade slots, purchase checklist, and the advance-stage action bar are build-process concerns (buying and assembling the PC), not eBay-listing concerns — they stay as a page-level **"Build Overview"** section that sits above the new tab strip, unchanged in placement. Financials, the listing generator, notes, and the sold form move into tabs as detailed below. This is the one item that "spans" the tab structure rather than fitting one tab, per the instructions.

**Also flagged from inventory (not a roadmap row, but blocks Live Listing Management):** `Flip.ebay_listing_id` and `ebay_listing_url` exist on the model but are not exposed in the `FlipOut` schema, so the page currently cannot link out to a build's live eBay listing. This needs to be added to the schema as part of this build — noted under Live Listing Management below.

**Tech stack for reference:** Next.js 16 / React 19 / Tailwind 4 frontend; FastAPI / SQLAlchemy async / Postgres (SQLite fallback) backend; APScheduler (`AsyncIOScheduler`) already running ~15 scheduled jobs — this is the job runner the new background services below should register into, not a new system. eBay integration today: REST Sell Inventory API only (`ebay_listing_poster.py`), sandbox/production toggle via `settings.ebay_environment`.

---

## Part 1 — Not page UI: background services, scheduled jobs, external integrations

| # | Item | Scope | Dependencies | Notes / proposed defaults |
|---|---|---|---|---|
| 1, 2, 5, 3, 9, 36 | **Relist/recreate engine** — end-and-republish a listing on a randomized ~7–8 day timer, reworded title, swapped main image, price step-down, landing at a new randomized time inside the build's traffic band; capped against identical-time posting, bulk edits, and over-editing | Background/scheduled service, registered as a new APScheduler job (e.g. `recreate_cycle`, hourly tick checking due listings) | Row 3's deferred-listing traffic bands (config lives on the build page); row 20's pricing engine for the price step-down; eBay Inventory API `DELETE /offer/{id}` + republish (needs verification this fully replaces legacy `EndItem`/`ReviseItem` — see Browser Extension note below) | **Default proposed, confirm once:** recreate interval = 7 days ± 1 day jitter (mid of the playbook's 7–8 day range); price step-down = 3% of current price per cycle; hard floor = cost basis + 10% minimum margin (see row 20) |
| 3 | **Deferred-listing scheduler firing job** — actually publishes a listing at the chosen date/time band picked in the Live Listing Management tab | Background/scheduled service (APScheduler one-shot job per build, or a periodic "due-to-publish" sweep) | eBay Inventory API `POST /offer/{id}/publish`; traffic-band heuristic below | Traffic-band default already specified in playbook: Sun evening best, Mon strong, Tue–Thu evenings solid, Fri weakest, weekend ~15–20% above weekday, UK evening peak ~7–10pm. **Default proposed, confirm once:** re-weight this heuristic from FlipFlop's own sold-listing timestamps once ≥20 sales exist; until then use the seller-consensus default verbatim |
| 19, 20, 49 | **Sold-comp pricing engine** — recalculates the sold-comp target fresh on every fire (never carried forward stale), anchors BIN near the top of the active range when offers are on, auto-drops toward the sold-comp median after a configurable window, and biases *future* similar builds' initial anchor upward after a fast/near-asking sale | Background/scheduled service (daily tick per active listing) + feeds the Pricing tab's live numbers | Demand-check integration (row 10) for sold/active data; `Flip.total_cost` for the floor; row 49 needs a "similar build" matcher (spec-based, likely CPU+GPU tier match against `FlipIntelligence` history) | **Default proposed, confirm once:** auto-drop window = 7 days (already in playbook); floor = cost basis + 10% minimum margin, floor-hit triggers human review (already specified as a required guardrail, not optional) |
| 8, 45 | **Auto-counter-offer / send-offers-to-watchers engine** | Background/scheduled service reacting to eBay Best Offer webhooks/polling + a periodic "send to watchers" job | eBay's legacy Trading API (`GetBestOffers`/`RespondToBestOffer`) for counter-offers — the modern REST Sell APIs do not yet cover buyer-initiated Best Offer response in full; eBay's Negotiation API (`sell/negotiation`) covers seller-initiated offers-to-watchers (row 45) natively via REST. **This is an API-coverage split, not a browser-automation need — flag and verify exact Trading API vs REST API split before implementation**, per the instructions' warning about assuming full API coverage | **Default proposed, confirm once:** counter tolerance = offer within 10% of the minimum-offer floor gets a first counter at roughly the midpoint between offer and list price; second counter = £5 off the first counter, then stop (already specified). Send-to-watchers: after 5 days unsold, send 10% off to watchers, twice daily (morning/evening, per T4's cadence) |
| 16 | **Seller-performance metrics monitor** | External integration, polling eBay Account/Trading API (`GetSellerStandardsInformation` or equivalent) on a scheduled job (e.g. daily), feeding the admin dashboard | eBay Account API auth | **Default proposed, confirm once:** alert if any metric drops below "Above Standard," or trends down for 2 consecutive weekly polls |
| 10, 33 | **Automatic demand check** — fires on build creation, pulls sold-vs-active counts over 90 days | External integration (eBay Browse/Finding API), triggered by the `Flip` creation event, not scheduled | Existing `ebay_browse.py`/`ebay_sales_tracker.py` services — extend rather than rebuild | Row 33 ("avoid precise sell-through formulas") is a guardrail folded into this: keep the output a simple sold-vs-active ratio, no compound formula |
| 40 | **Promoted Listings ad-rate suggestion** | External integration (eBay Marketing API, `sell/marketing`) — real API coverage exists for creating/managing ad campaigns | `Flip` profit-estimate fields | **Default proposed, confirm once:** starting ad rate = 5% (mid-point between eBay's typical 2–8% range and T4's empirically-tested 7%), auto-suggested per build, capped so ad spend never exceeds 15% of estimated profit margin; builds below that margin threshold are flagged "too thin to promote" rather than defaulted into a campaign |
| 38 | **Title-keyword sourcing from eBay autocomplete + sold-title phrasing** | External integration — **flag explicitly:** eBay has no official public API for search-suggest/autocomplete. This likely needs eBay's public (unauthenticated) autosuggest endpoint used by their own web search box, which is not part of the documented Sell/Buy API surface and could break without notice. If that endpoint proves unreliable or gets blocked, the fallback is scraping the rendered Seller Hub / search-suggest UI — i.e. a browser-extension-shaped solution. **This is the one row in the roadmap where "check rather than assume API coverage" genuinely applies; verify the autosuggest endpoint's stability before committing to the App Automation classification the playbook gave it.** | Sold-listing titles come from the existing demand-check integration (row 10) — no new dependency there | Lives in the admin tool (cross-build utility), not a per-build feature — see Part 2 |

**Browser extension assessment:** of all 37 rows, only row 38 (autocomplete/keyword sourcing) carries real risk of needing browser-level automation rather than a documented API. Every other "App Automation" row — including the relist/recreate cycle, counter-offers, promoted listings, and demand checks — has a corresponding eBay REST or Trading API endpoint. No browser extension is planned as a first-class deliverable; row 38 gets a documented fallback instead of a dedicated extension, since it's a single narrow capability, not a UI-wide automation need.

**Scope note — beyond eBay:** none of the services above are built to write directly to a single hardcoded "eBay" table. Pricing logic (19–21), counter-offer rules (8), handling/returns/shipping stance (11–15), the demand-check gate (10), and performance/margin discipline (16, 37) should be modeled as **store-level policy objects** that the eBay integration *consumes*, not eBay-specific settings — so that when the future multi-platform/website-parity phase begins, the same policy objects can be synced to a second channel without a rebuild. The relist/recreate and pricing-decay background jobs should likewise be keyed off the `Flip`/inventory record, not an eBay listing ID, so a future single-inventory-safety layer (one sale reserves/ends the item everywhere) can be added without restructuring these jobs.

---

## Part 2 — Admin tool (store-wide, not scoped to one build)

New admin section, separate from any per-build tab.

| # | Item | Placement | Dependencies | Proposed default |
|---|---|---|---|---|
| 37 | **Revenue / margin / sell-through dashboard** | Admin tool — new page, e.g. `flipflop-admin/app/performance` | `FlipIntelligence` records (already captured on sale) | None needed — pure reporting |
| 16 | **Seller-performance metrics panel** | Admin tool, same dashboard as above | Row 16's background integration | See Part 1 default |
| 38 | **Title-keyword research tool** | Admin tool — a lookup utility (search a spec, see autocomplete suggestions + recent sold-title phrasing) that the Listing Content tab's title generator calls into, rather than a per-build feature | Row 38's integration | See Part 1 note on API risk |
| 47 | **Buyer-message response-time alert** | Admin tool — notification/alert surface (not a reply automation; the playbook is explicit the reply itself stays manual) | eBay message polling (likely already partially available via existing eBay integration, needs confirming) | **Default proposed, confirm once:** alert if a buyer message is unanswered after 2 hours during business hours |
| — | Existing Settings page (`app/settings/page.tsx`) | Extend with a new **"Seller Policies"** tab for the global eBay Config rows in Part 3 below (handling time, returns, shipping, local pickup, listing-type default) rather than creating a second settings surface | — | — |

---

## Part 3 — Global eBay account / store-level settings (configured once, not per-build)

These are native eBay Business Policy settings — set once via eBay's Business Policies API (or Seller Hub directly) and applied to every listing, not re-entered per build. FlipFlop's Settings page should hold the source-of-truth values and push them via API, per the beyond-eBay scope note (store-level policy, not eBay-only).

| # | Item | Proposed default | Confirm once |
|---|---|---|---|
| 11, 12 | Handling time — fastest realistic, no padding | 2 business days (accounts for burn-in/QA testing time the playbook calls out) | Yes |
| 13, 14 | Returns on (never "no returns") | 30-day returns, buyer pays return shipping | Yes |
| 15 | Free shipping, absorbed into price | On for all builds (ties to row 35's shipping-inclusive pricing) | No — playbook is unambiguous |
| 43 | Local pickup/collection offered | On by default for all builds | No — playbook states "no reason not to" |
| 44 | Listing type default = Fixed Price, never auction | Fixed Price, no exceptions | No — playbook is unambiguous |
| 21 | Guardrail: never combine "price = sold-comp target" with "offers off" | Enforced as a validation rule inside the Pricing tab (if a user tries to disable offers while price sits at the computed sold-comp target, warn), not a separate setting | No |
| 46 | Scheduled markdown/sale events on aged stock (eBay Promotions Manager) | **Default proposed, confirm once:** trigger candidate list after 2 recreate cycles without a sale (~14–16 days); default discount 15%; admin reviews and one-click confirms rather than firing fully unattended, since this is a real price cut visible to buyers, not a quiet reprice | Yes |

---

## Part 4 — Build details page: tab-by-tab

Page structure: **Build Overview** (unchanged, page-level, per Step 0) sits above a tab strip with 7 tabs.

### Listing Content — icon: `file-text` (Lucide)
Everything that determines what buyers read.

- **Existing:** eBay listing generator (title/description) — `Flip.generated_title`, `generated_description`.
- Row 4 — front-load titles (item + key specs first, filler last, full character budget): a prompt-wording fix to the existing generator, no new UI.
- Row 24 — title keywords sourced from real buyer search terms: generator calls the admin keyword-research tool (Part 2, row 38) instead of guessing.
- Dependency: pulls structurally from the Build Overview's parts list (playbook/upgrade slots), per the playbook's "listing generator from your build spec sheet" build candidate.

### Item Specifics — icon: `list-checks` (Lucide)
- Row 25 — auto-populate every relevant eBay item specific (color, size, brand, condition, compatibility) from the parts list, cross-checked against Item Specifics filters so nothing is left blank (blank fields exclude the listing from filtered search entirely, per the playbook).
- Dependency: same parts-list source as Listing Content; should ship as one data-population step feeding both tabs, not built twice.

### Photos — icon: `camera` (Lucide)
- **Existing:** photo upload (referenced via `Listing.image_urls` / generated image fields — `Flip.generated_images_urls`, `image_generation_status`).
- Row 41 — video requirement: a boot-up/benchmark clip slot per listing. **Default proposed, confirm once:** soft-required (checklist item, blocks "mark listing-ready" with an override, not a hard block) rather than fully mandatory, since eBay caps video at one per listing and occasional builds may not have a clean benchmark run.
- Row 48 — minimum-shot checklist (front, side, internals, cable routing, ports) before a build can be marked listing-ready.

### Pricing — icon: `banknote` (Lucide, or `circle-dollar-sign`)
- **Existing:** Financials card (base/upgrade/total cost, est. resale, est./actual profit, fee snapshots) and the Profit Breakdown sub-page — fold `profit.tsx` into this tab rather than keeping it a separate route.
- Row 10, 33 — demand check result shown next to the profit estimate (fires automatically on build creation, per playbook).
- Row 19, 20, 49 — live sold-comp pricing engine output (current target, BIN anchor, next scheduled drop, floor) — read/write surface for the Part 1 background service.
- Row 8, 45, 21 — the existing minimum-offer field, plus: "offers not allowed" toggle, counter-offer rule display (Rule 1/Rule 2, both fixed per playbook — not user-tunable beyond the tolerance default), send-to-watchers toggle.
- Row 35 — shipping-inclusive price calculator (estimates box/freight cost by build weight, bakes into the flat price shown here).
- Row 40 — Promoted Listings ad-rate suggestion and margin-band flag.
- Row 6, 7, 9, 22, 23, 36 — these are guardrails/avoid-rows, not separate UI: they constrain the pricing engine's behavior (no bulk edits, no over-editing, no undercutting race, no below-market pricing, steady cadence) and are enforced as code inside the Part 1 pricing/recreate services, not exposed as toggles.

### Dispatch & Delivery — icon: `truck` (Lucide)
This tab mostly *displays* the global settings from Part 3 (handling time, returns, free shipping, local pickup) rather than re-configuring them per build — with an explicit per-build override only where a specific build genuinely can't hit the global default (e.g. an unusually heavy/fragile build needing extra handling days).
- Row 42 (manual-only, listed here for completeness even though out of scope): shipping protection/packaging — not automated, no UI beyond a packing checklist reference if useful, but not required by this plan.

### Live Listing Management — icon: `calendar-clock` (Lucide)
- Row 3 — deferred-listing scheduler: the traffic-colour-coded calendar/time-band picker described in the playbook's build candidates, feeding the Part 1 firing job.
- Row 1, 2, 5, 9, 36 — relist/recreate engine status and controls: shows current cycle count, next scheduled recreate time, price-step history, and a manual "recreate now" override; the timer/guardrail logic itself lives in Part 1.
- Row 46 — per-build opt-in flag for inclusion in the next scheduled markdown/sale event (Part 3).
- **Existing:** Sold form (sale price, platform, profit preview) — this is where a listing's lifecycle ends, so it belongs here rather than staying a modal triggered from the old undivided page.
- **Fix required (from Step 0, not a roadmap row):** expose `ebay_listing_id`/`ebay_listing_url` in `FlipOut` so this tab can link out to the live listing.

### Other — icon: `more-horizontal` (Lucide)
- **Existing:** Notes field.
- Nothing from the 37-row roadmap lands here — it's reserved for the existing freeform notes and any future miscellany, kept deliberately thin.

---

## Cross-check: every row and every existing component placed

All 37 automation-roadmap rows: **16, 10, 19, 1, 2, 4, 11, 15, 20, 24, 25, 40, 49, 8, 13, 35, 44, 45, 5, 12, 14, 22, 23, 37, 41, 47, 48, 6, 21, 36, 46, 3, 38, 43, 7, 9, 33** — all 37 accounted for above (Parts 1–4). None left unplaced.

All Step 0 existing components — stage stepper, listing/source card, playbook/upgrade slots, purchase checklist, financials card, listing generator, notes, sold form, advance-stage action bar, profit breakdown sub-page — all placed (Build Overview, or a named tab above). One flagged gap: `ebay_listing_id`/`ebay_listing_url` missing from `FlipOut` (Live Listing Management tab, fix required).

**Nothing could not be placed.** The only genuinely cross-cutting item is the Build Overview section itself, which spans "pre-listing build process" rather than fitting inside any single eBay-listing tab — documented above rather than forced into one.

**Open decisions resolved with proposed defaults (all flagged "confirm once," per the instructions):** recreate interval/jitter, price step-down %, pricing floor margin, counter-offer tolerance, send-to-watchers threshold/discount, ad-rate starting point and margin cap, handling time, returns window, video requirement strictness, markdown-event trigger/discount, seller-performance alert threshold, message response-time alert threshold, traffic-band re-weighting trigger point. Free shipping, local pickup, and fixed-price-only defaults are unambiguous per the playbook and don't need confirmation.

---

## Post-implementation: playbook status/location columns (future session)

Once implementation is carried out and every function is tested to confirm it actually works, add two columns to the Algorithm Playbook artifact's automation roadmap table:
- **Status** — Automated / Not yet automated / Partially automated (with a short note).
- **Location** — build details page (name the tab), admin tool, browser extension, background/scheduled service, external integration, or eBay native setting — using the same categories used in this plan.

This is explicitly deferred: it happens after the testing pass in a later session, not as part of this plan.
