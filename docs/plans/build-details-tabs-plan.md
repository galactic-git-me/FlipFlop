# Build Details Page Restructure & Playbook Automation — Implementation Plan

Source of truth: "Flip Flop Algorithm Playbook" artifact (fa529446-25a2-4cc4-be2e-5d2b23009c32), fetched fresh 2026-08-13. This is a **scoping/architecture plan**, not code. It covers every playbook row tagged `App Automation`, `eBay Config`, or `Both`, everything in the playbook's "Build candidates" section, and every existing field/component already on the Flip detail page.

Rows tagged `Manual` (17, 18, 26, 28–30, 32, 34, 39, 42) and `—`/Disputed-N/A (27, 31) are intentionally excluded — they're judgment calls, not buildable features.

---

## Step 0 — What already exists (FlipFlop codebase inventory)

Stack: two Next.js 16/React 19 apps (`flipflop-admin` — internal ops, `flipflop-storefront` — customer-facing) on a Python `flipflop-api` backend (SQLAlchemy models, Alembic migrations, APScheduler-based job runner at `app/workers/scheduler.py`). The page in question is the **Flip detail page**: `flipflop-admin/app/flips/[id]/page.tsx`, backed by the `Flip` model (`flipflop-api/app/models/flip.py`) joined to a `Listing` model (`flipflop-api/app/models/listing.py`) — note: FlipFlop's `Listing` model is the **original purchase source** (what the parts were bought from), not the eBay sale listing. That naming collision with "the eBay listing" used throughout the playbook is worth flagging early to avoid confusion during build.

The backend already has real infrastructure this plan can hook into:
- `app/services/ebay_browse.py` — eBay Browse API client (app-level OAuth via `ebay_compliance.py`), already used for live component pricing.
- `app/services/ebay_listing_poster.py` — a REST-based listing creator (assumes a user access token; OAuth flow for it isn't confirmed present — see open item below).
- `app/workers/scheduler.py` — an APScheduler wrapper already running ~17 named background jobs (price refresh, benchmark refresh, playbook evolution, etc.). New scheduled automation in this plan should register here, not invent a second job runner.

Existing fields/sections found on the Flip detail page, none of which the playbook's new items should crowd out:

| Component | Where | Backing field |
|---|---|---|
| Stage tracker + progress bar | `page.tsx:557-606` | `Flip.stage` |
| Listing card (title, source URL, spec pills, source name + cost) | `page.tsx:609-651` | `Listing.title/url/cpu/gpu/ram_gb/...`, `Flip.base_cost` |
| Cost basis & profit estimate (base/upgrade/total cost, est. resale, fee %, est. profit) | `page.tsx:654-687` | `Flip.base_cost/upgrade_cost/total_cost/current_estimated_resale/platform_fee_pct/current_estimated_profit` |
| Sold-state fields (sale price, actual profit, sale platform) | `page.tsx:690-708` | `Flip.actual_sale_price/actual_profit/sale_platform` |
| Playbook selector + Upgrade Slots (parts list, part picker) | `page.tsx:75-298` | `Flip.selected_upgrade_ids`, `Part` catalog |
| eBay listing generator (AI title/description) | `page.tsx:718-756` | `Flip.generated_title/generated_description` |
| Notes field | `page.tsx:759-769` | `Flip.notes` |
| Sold form modal (sale price, platform, profit preview) | `page.tsx:772-854` | writes sold-state fields above |
| Compatibility Check panel | `page.tsx:856-922` | client-side only, not persisted |
| Purchase Plan checklist | `page.tsx:924-1014` | client-side, via `api.flips.purchasePlan` |
| Stage-advance controls (Mark as Building/Ready/Sold) | `page.tsx:1016-1056` | drives `Flip.stage` |
| Profit breakdown sub-page | `flips/[id]/profit.tsx` | `api.flips.profitBreakdown` |

**Gaps found, corrected from playbook assumptions:** the playbook (rows 8, 21, 44) refers to "the existing minimum-offer field" as if it's already built. It is not — there is no minimum-offer, asking-price, or Best-Offer-toggle field anywhere in the codebase today. There's also no photo-upload UI rendered on this page (`generated_images_urls`/`image_generation_status` exist on the model but aren't wired to any component), and no editable title/description/category/condition fields (the only title/spec fields shown are read-only, pulled from the *source* `Listing`). All of these are net-new builds under this plan, not modifications to something pre-existing.

**Structural finding — parts list doesn't fit the tab structure at all.** The Playbook/Upgrade-Slots section, the part picker, the Compatibility Check panel, and the Purchase Plan checklist are all **build-assembly** content — they exist and matter before any eBay listing is even being prepared. Forcing them into one of the seven listing-oriented tabs (Listing Content, Photos, Item Specifics, Pricing, Dispatch & Delivery, Live Listing Management, Other) would misrepresent what they are. Recommendation: keep these as a **separate, non-tabbed "Build" zone** at the top of the page (largely as they exist today), with the new tab strip appearing as a second, listing-focused zone once a build is ready to be marketed. The stage tracker and stage-advance controls are page-level chrome spanning both zones, not tab content.

---

## 1. Not page UI — background services, scheduled jobs, external integrations, browser extension

### 1.1 Relist/Recreate Engine — *background/scheduled service*
Ends and republishes a listing on a randomized ~7–8 day timer: reworded title, swapped main image, price step-down toward a configurable floor, landing at a new random time inside the build's originally-selected traffic band (never the same clock time twice).
- **Covers rows:** 2, 3 (firing logic), 5, 6 (folded in — no separate price-only nudge), 7 & 9 (guardrails baked into the job, not left to willpower).
- **Depends on:** Deferred-listing scheduler UI (traffic band selection, §3.6), Sold-comp pricing engine (§1.3, for the price floor/step), Listing generator (§1.5, reworded title), Photos component (§3.2, alternate main image).
- **Registers into:** existing `app/workers/scheduler.py` APScheduler instance.
- **⚠️ External API risk — verify before building:** eBay's modern Sell API (Inventory/Fulfillment) does not have a clean 1:1 equivalent to the legacy Trading API's `RelistItem`/`EndItem`+`AddItem` pair. Confirm which API generation `ebay_listing_poster.py` targets and whether true end-and-recreate (new item ID, not just a revision) is achievable via API before assuming this is a pure backend job. If it isn't fully API-covered, this becomes a **browser-extension** candidate (automating Seller Hub's own "End & Sell Similar" action) rather than a scheduled API call — do not silently plan it as one.
- **Open decision:** default price step-down % and floor value per cycle (playbook leaves both "configurable" with no numeric default given).

### 1.2 Deferred-listing publish job — *background/scheduled service*
The job that actually fires a listing live at the date/time chosen in the Live Listing Management tab's picker (§3.6 owns the picker UI; this owns the firing).
- **Covers row:** 3.
- **Depends on:** eBay listing-create API path (§1.1's same open item applies).

### 1.3 Sold-comp pricing engine — *background service + external integration*
Computes the BIN anchor (top of active-listing range) and the sold-comp target/floor, and auto-drops price toward the sold-comp median if nothing sells within a configurable window (default 7 days).
- **Covers rows:** 19, 20, 22, 23.
- **⚠️ External API risk:** eBay's public Browse API surfaces *active* listings well but sold-comp/historical-sold data typically requires the restricted-access Marketplace Insights API. Confirm FlipFlop's eBay developer account has (or can get) that access tier before committing to this as a fully-automated engine — if not grantable, this degrades to a semi-manual "paste comps" flow.
- **Depends on:** Demand-check integration (§1.4) for the underlying sold/active dataset.

### 1.4 Demand-check integration — *external integration*
Fires automatically on build creation: pulls sold-vs-active counts for the same/similar spec over the last 90 days, surfaced next to the profit estimate.
- **Covers rows:** 10, 33 (the "don't hand-calculate sell-through" row is satisfied by this existing automatically, no separate feature needed).
- **Extends:** the existing `ebay_browse.py` pattern (already does comparable aggregation for component pricing) rather than a net-new client.
- **Surfaces on:** Pricing tab (§3.4).

### 1.5 Listing generator prompt update — *enhancement to existing service*
Not a new service — a prompt-wording fix to the AI generator that already produces `Flip.generated_title/description`: pull directly from the build's parts list, front-load item + key specs, use the full character budget, no keyword stuffing.
- **Covers rows:** 4, 24 (search-term matching folds into the same prompt rule).
- **Also drives:** auto-populated item specifics (row 25, §3.3) from the same parts-list data instead of manual retyping.

### 1.6 Auto-counter-offer engine — *background/event-driven service, external integration* (Both)
Rule 1: an offer within tolerance of the minimum gets countered roughly halfway between the offer and listing price. Rule 2: a second buyer counter gets one more counter at £5 off, then stops.
- **Covers rows:** 8, 21.
- **⚠️ External API risk — verify before building:** confirm eBay's Negotiation API actually supports programmatic *counter*-offers with this rule shape (vs. only accept/decline/send-offer-to-watchers), and whether offer events are push/webhook or require polling. If counters aren't fully API-scriptable, this is a **browser-extension** candidate, not a backend job.
- **Depends on:** the minimum-offer field and "offers not allowed" toggle — both **net new**, to live on the Pricing tab (§3.4; corrects the playbook's assumption these already exist, see Step 0 gap).

### 1.7 Margin-aware Promoted Listings suggestion — *external integration* (Both)
Suggests an ad rate that keeps spend inside an acceptable margin band using the build's existing profit estimate; flags builds too thin-margin to promote.
- **Covers row:** 40.
- **Needs:** eBay Marketing API (Promoted Listings) integration — read/set ad rate. Not yet present in the codebase; net-new client alongside `ebay_browse.py`.
- **Surfaces on:** Pricing tab or Live Listing Management tab (§3.4/§3.6) as a suggestion, not an auto-applied setting.

### 1.8 Keyword sourcing from eBay autocomplete + sold-listing titles — *external integration, feeds the Admin Tool*
Cross-build utility, explicitly named in the prompt as belonging in the admin tool, not a per-build tab. Needs an eBay autocomplete/suggested-terms endpoint plus sold-title text sourced from §1.3's data. See §2.2.
- **Covers row:** 38.

---

## 2. Admin tool (store-wide, not scoped to one build)

### 2.1 Performance & margin dashboard
Surfaces the 5 documented seller-performance metrics (defect rate, late-shipment rate, tracking upload/scan, unresolved cases, return rate) alongside real revenue/margin/sell-through numbers, instead of vanity view/watcher counts.
- **Covers rows:** 16, 37.
- **Needs:** eBay Account/Seller Performance API integration for the 5 metrics (net-new client) — margin/revenue/sell-through can be computed from existing `Flip` sale data already in the DB (`actual_sale_price`, `actual_profit`, `total_cost`), no new external dependency for that half.
- **Related:** row 36 (steady build/list cadence, not bursts) is best represented here too, as a simple derived stat ("days since last listing," rolling cadence average) rather than a standalone feature — it's descriptive, not something to gate or automate.

### 2.2 Title-keyword sourcing tool
Surfaces eBay's own autocomplete suggestions and sold-listing title phrasing for a given part/spec, as a cross-build reference rather than a per-listing lookup.
- **Covers row:** 38 (see §1.8 for the integration it's built on).

---

## 3. Build details page — tab structure

Per Step 0's structural finding: these seven tabs sit in a **second, listing-focused zone** of the page, alongside (not replacing) the existing non-tabbed Build zone (parts list, compatibility check, purchase plan, stage tracker/controls — all stay as-is, outside the tabs).

### 3.1 Listing Content — icon: `lucide-text`
- **Existing:** AI listing generator (title/description), currently at `page.tsx:718-756`. Migrates here unchanged in function.
- **New:** prompt fix for title/description generation (§1.5, rows 4, 24); default-to-Fixed-Price guardrail (row 44 — not a UI field, a template default enforced at listing-creation time, called out here so it isn't lost).
- **Dependency:** relies on the parts list (Build zone) as its data source.

### 3.2 Photos — icon: `lucide-image`
- **New:** photo upload UI (the model fields `generated_images_urls`/`image_generation_status` exist but nothing renders them today — this is net-new UI, not a migration).
- **New:** video attachment for the boot-up/benchmark clip (row 41, eBay-native feature, ≤1 min MP4/MOV) — the eBay capability is native/config, but the app still needs an upload control for it.
- **Depends on:** feeds the Relist/Recreate Engine's "swap main image" step (§1.1).

### 3.3 Item Specifics — icon: `lucide-list-checks`
- **New:** auto-populated item specifics (color/size/brand/condition/compatibility) sourced from the parts list (row 25), with manual override.
- **Dependency:** same parts-list source as §3.1; same prompt-generation pipeline (§1.5).

### 3.4 Pricing — icon: `lucide-tag`
- **Existing:** cost basis & profit estimate fields (`page.tsx:654-687`) — migrate here unchanged.
- **New:** demand-check output display (§1.4, rows 10/33) shown next to the profit estimate, per playbook spec.
- **New:** BIN price / sold-comp target / auto-drop floor fields, driven by the Sold-comp pricing engine (§1.3, rows 19, 20, 22, 23).
- **New:** minimum-offer field + "offers not allowed" toggle (rows 8, 21) — corrects the Step 0 gap; this is where the Auto-counter-offer engine's config lives.
- **New:** Promoted Listings ad-rate suggestion display (§1.7, row 40).
- **Existing (linked, not migrated):** the separate profit-breakdown sub-page (`flips/[id]/profit.tsx`) stays a linked detail view from this tab rather than being absorbed wholesale.

### 3.5 Dispatch & Delivery — icon: `lucide-truck`
- **eBay-native, account-level (rows 11–15):** handling time, returns policy, free shipping. **Open decision:** does FlipFlop need per-build variance here (e.g. a heavier full-build needing longer handling than a parts-only sale), or is one uniform Business Policy enough store-wide? If uniform, no per-build UI is needed at all — configure once natively in eBay and this tab just displays the active policy read-only. If variance is needed, this tab needs a policy-selector control. **This is a genuine open decision, not resolved by the playbook — flagging rather than guessing.**
- **New:** shipping-inclusive price calculator (row 35, "Both") — estimates box/freight cost from the build's weight and folds it into the flat listed price instead of exposing calculated shipping.
- **New:** local pickup/collection toggle (row 43, eBay-native per-listing option).

### 3.6 Live Listing Management — icon: `lucide-calendar-clock`
- **New:** deferred-listing date/time picker with traffic-band colour-coding (row 3's UI half — the scheduler itself is §1.2's background job).
- **Existing:** stage-advance "Mark as Ready for Sale" control conceptually lives here as the trigger that publishes the listing — though the control itself stays with the page-level stage tracker per the Step 0 structural note; this tab is where its *listing-specific* configuration (schedule, relist status) shows.
- **Existing:** the sold form modal (sale price, platform, profit preview, `page.tsx:772-854`) migrates here — it's the listing's terminal state.
- **New:** Relist/Recreate Engine status/history display (§1.1) — when the next recreate is scheduled, cycle count, current price step.
- **New:** Promoted Listings suggestion could alternatively surface here instead of Pricing — flagged as genuinely spanning both tabs (see below).

### 3.7 Other — icon: `lucide-more-horizontal`
- **Existing:** Notes field (`page.tsx:759-769`) — no better-fitting tab, migrates here unchanged.

### Items that genuinely span tabs (flagged per instructions, not forced into one)
- **Promoted Listings suggestion (row 40):** margin data lives in Pricing, but the suggestion is actionable only in the context of an active/about-to-go-live listing (Live Listing Management). Recommend showing it in both, sourced from one place.
- **Stage tracker / stage-advance controls:** span the entire page (Build zone + all listing tabs), not tab content — stay as page-level chrome as they are today.

---

## 4. Beyond-eBay scope note — design flags (not built now)

Per the playbook's "Scope note: beyond eBay," a later multi-platform phase will need website parity, cross-platform listing sync, and single-inventory safety. Flags for this plan to avoid a forced rebuild later:

- **Pricing rules, counter-offer rules, handling/returns/shipping stance, the demand-check gate, and performance/margin discipline (§1.3, §1.6, §3.5, §1.4, §2.1) should be authored as store-level policy config, not hardcoded as eBay-specific logic**, even though eBay is the only channel today — e.g. the counter-offer thresholds and price-decay window should live in a policy/config layer the engines read from, not inline in eBay-calling code.
- **The `Flip`/`Listing` data model conflation flagged in Step 0 matters here too:** once a second channel exists, "the build" (canonical) and "the eBay listing" (channel-specific) must be distinct records. This plan doesn't need to build that separation now, but new fields (generated title/description, BIN price, minimum offer, etc.) should be modeled as *listing content for the eBay channel* rather than bare `Flip` columns where reasonably possible, so a future `Listing`-per-channel table isn't a full rewrite.
- **Single-inventory safety** (a sale on one channel must reserve/end it everywhere) has no bearing on this eBay-only plan, but the stage-advance/sold-flow (§3.6) should treat "sold" as a single state transition on the canonical build record (which it already does via `Flip.stage`) rather than something that could exist independently per channel — this part of the existing design already happens to be future-compatible.

---

## 5. Cross-check — every qualifying row placed

| Rows | Feature/placement |
|---|---|
| 1 | Covered by existing stage-advance → publish flow (§0/§3.6); no new feature needed beyond ensuring the publish action isn't batched |
| 2, 3, 5, 6, 7, 9 | Relist/Recreate Engine (§1.1) + Deferred-listing picker (§3.6) + firing job (§1.2) |
| 4, 24 | Listing generator prompt fix (§1.5) → Listing Content tab (§3.1) |
| 8, 21 | Auto-counter-offer engine (§1.6) → Pricing tab fields (§3.4) |
| 10, 33 | Demand-check integration (§1.4) → Pricing tab (§3.4) |
| 11–15 | eBay-native Business Policies, open decision on per-build variance (§3.5) |
| 16, 37 | Performance & margin dashboard (§2.1, Admin Tool) |
| 19, 20, 22, 23 | Sold-comp pricing engine (§1.3) → Pricing tab (§3.4) |
| 25 | Auto item specifics (§1.5) → Item Specifics tab (§3.3) |
| 35 | Shipping-inclusive price calculator → Dispatch & Delivery tab (§3.5) |
| 36 | Cadence stat in Performance & margin dashboard (§2.1) |
| 38 | Title-keyword sourcing tool (§2.2, Admin Tool) + integration (§1.8) |
| 40 | Promoted Listings suggestion (§1.7) → Pricing/Live Listing Management (spans, §3) |
| 41 | Video upload control → Photos tab (§3.2) |
| 43 | Local pickup toggle → Dispatch & Delivery tab (§3.5) |
| 44 | Fixed-Price default guardrail → Listing Content tab (§3.1) |

All existing Step 0 components are placed in §3 (tab-by-tab) or explicitly kept in the non-tabbed Build zone (§0 structural finding). Nothing from the qualifying rows or the existing-component inventory is left unplaced.

**Nothing unplaceable.** The three genuine open decisions (relist price-step/floor defaults, per-build shipping-policy variance, and eBay API coverage for true end-and-relist / programmatic counter-offers) are flagged inline above rather than guessed at, since getting them wrong would mean rebuilding rather than reconfiguring.
