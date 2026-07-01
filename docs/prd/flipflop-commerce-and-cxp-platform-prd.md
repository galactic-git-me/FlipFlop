# FlipFlopOS — Unified Commerce & Customer Experience Platform
## Implementation PRD (Extension to the Existing System)

**Document status:** Draft v1.0 — Engineering Source of Truth
**Extends:** [`flipflop-master-prd.md`](./flipflop-master-prd.md) (as-built system) and supersedes/absorbs [`customer-experience-platform-prd.md`](./customer-experience-platform-prd.md) (prior CXP-only draft — its schema for Packaging Playbooks, Procurement, Documents, USB, Photography, 3D, Final QC and Cost Engine is retained and referenced here rather than repeated in full; this document adds the commerce architecture that sits above it)
**Do not redesign:** Authentication, Dashboard, Marketplace Search, Auction Analysis, Component Catalogue, Inventory, Build Playbooks, MES, Build Tracking, Listing Generator, Customer Portal, Profit Calculator, Reporting & Analytics — all extended, none rebuilt.

---

## 1. Executive Summary

FlipFlopOS today runs two parallel businesses on shared infrastructure: **flipping** (source underpriced used listings via `Listing`/`Flip`, refurbish, resell) and **made-to-order building** (customer configures against a `Playbook`, pays via Stripe, an `Order` is sourced and assembled). These two paths currently converge only loosely — a flip becomes an eBay listing via `ebay_listing_poster.py`; a storefront order becomes an `Order` via the checkout/payment webhook. There is no single model of "a thing we can sell," no dual-channel listing sync, no post-build automation pipeline, and no post-sale customer lifecycle beyond order fulfilment.

This PRD introduces the **Unified Commerce & Customer Experience Platform**, which:

1. Introduces a canonical `Product` entity — the thing that gets listed and sold — sitting between `Build` (a physical, benchmarked, sourced machine or a configurable template) and `Order` (any purchase, any channel).
2. Automates everything between "build physically finished" and "listed for sale": validation, OS provisioning, benchmarking, photography, 3D capture, document generation, USB generation, packaging prep, and profit calculation — the **Finalise Build** pipeline.
3. Lists finished pre-built Products simultaneously on **eBay Buy It Now** and the **FlipFlop storefront (Ready-to-Ship)**, with an **Email/Notification Watcher** that keeps both channels in sync and auto-delists the other channel the instant either one sells.
4. Extends the storefront configurator into a **premium 3D Made-to-Order Configurator** with live compatibility filtering, admin-curated public catalogue, and a global Fast Track delivery upsell — feeding the *same* fulfilment pipeline as pre-built Products.
5. Extends order fulfilment with the previously-specified **Customer Experience Platform** (Packaging Playbooks, Procurement, Documentation Generator, USB Builder, Photography, 3D publish, Final QC) — schema and workflow detail for these lives in the prior CXP PRD and is referenced, not repeated, below except where this integration changes it.
6. Adds a **Post-Sale Customer Lifecycle Engine** — delivery confirmation through referral/loyalty campaigns — as scheduled, event-driven automations reusing the existing `email_service.py` and `scheduler.py` infrastructure.
7. Adds a **Business Intelligence module** — AI-driven analysis across profitability, CLV, upgrade conversion, packaging cost, supplier performance, repeat purchase, review sentiment, and inventory performance — reusing the existing Hermes/Claude AI chain (`ai_service.py`) rather than introducing a second LLM integration.

Every workflow decision in this document is tested against: **does this increase the customer's excitement, confidence, and emotional attachment to the product?** (carried forward unchanged from the prior CXP PRD's philosophy, Chapter 2 there).

---

## 2. Product Philosophy

Unchanged in substance from the existing CXP PRD (Chapter 2 of that document): packaging and unboxing are the beginning of ownership, not the end of shipping; the benchmark is a Porsche configurator confirmation or a flagship phone unboxing, not "a PC arrived." This document extends that philosophy upstream and downstream:

- **Upstream (pre-sale):** the *listing* itself — on eBay or the storefront — is the first emotional touchpoint. Professional photography, an accurate 3D model, and a confident benchmark report displayed at the point of sale build the same anticipation a Packaging Playbook builds at the point of delivery. A gem-sourced flip should not look, read, or feel like a garage sale — it should read like a certified, tested, premium machine, because by the time it reaches Finalise Build, it has been.
- **Downstream (post-sale):** ownership does not end at delivery. A 7-day check-in that asks "how's the RGB sync working out?" and a 30-day survey that turns a happy customer into a public review are part of the same designed emotional arc as the unboxing — proof the business cares past the transaction, which is what earns the premium pricing and repeat purchases the philosophy targets.

---

## 3. Business Objectives

| # | Objective | Rationale |
|---|---|---|
| C1 | Zero double-sold Products across eBay + storefront | Dual-channel listing without sync risk is a direct revenue/reputation hazard — must be solved before dual-listing ships |
| C2 | Every finished build reaches "listable" state without manual document/photo/benchmark assembly | Removes the single biggest operator bottleneck between "built" and "earning" |
| C3 | Made-to-Order configurator matches the polish of the pre-built listings | A customer configuring a build should feel the same premium confidence as one buying a finished unit |
| C4 | Increase average order value via Fast Track and Upgrade Guide-driven upsell | Both are low-friction, low-cost-to-fulfil margin levers already partially scaffolded (delivery slots, Upgrade Guide) |
| C5 | Increase repeat purchase and referral rate via lifecycle automation | Extends existing Objective B4 (prior CXP PRD) with the machinery to actually execute on it, not just make it possible |
| C6 | Give the business owner one BI view that recommends action, not just reports numbers | Existing Reporting & Analytics module reports; this module additionally recommends |
| C7 | Preserve all existing flip/marketplace/playbook workflows unchanged | This is an extension; regression in Marketplace Search, Auction Analysis, or the flip pipeline is not acceptable |

---

## 4. Goals & Non-Goals

### Goals
- Introduce `Product` and unify `Build → Product → Order (any channel)` as the canonical sale model.
- Automate the Finalise Build pipeline (validation → provisioning → benchmarking → photography → 3D → documents → USB → packaging prep → profit calc → Product creation).
- Dual-list finished Products on eBay Buy It Now and storefront Ready-to-Ship; auto-delist the other channel on sale.
- Build the Email/Notification Watcher for offers, questions, watchers, basket adds, sales, payments — across both channels.
- Extend the storefront configurator to a premium 3D Made-to-Order flow with admin-curated catalogue visibility, live compatibility filtering, and global Fast Track toggle.
- Integrate the previously-specified Customer Experience Platform (Packaging Playbooks, Procurement, Documents, USB, Photography, 3D, Final QC) as the shared fulfilment pipeline for both pre-built and made-to-order Orders.
- Build the Post-Sale Customer Lifecycle Engine (delivery confirmation through referral programme).
- Build the AI-driven Business Intelligence module.

### Non-Goals (v1)
- Rebuilding Marketplace Search, Auction Analysis, Component Catalogue, Inventory, Build Playbooks, MES, Build Tracking, Listing Generator, Customer Portal, Profit Calculator, or Reporting & Analytics cores — all are extended additively.
- Real-time bidirectional eBay API webhook integration if eBay does not support the exact event (offers/watchers/questions) via API — see Chapter 9.4 for the documented fallback (polling) where push isn't available.
- Physical carrier/shipping label API integration (unchanged non-goal from prior CXP PRD).
- An "eBay Configurator" product listing type — explicitly deferred, but the data model is built to not preclude it (Chapter 12.6).
- Automated social posting / OAuth publishing to social platforms (share-kit asset generation only, per prior CXP PRD).
- Full loyalty-points ledger/currency system — v1 loyalty campaigns are discount-code-based, not a points economy (Chapter 16.7).

---

## 5. Architecture

### 5.1 The four primary entities

```
Component  ──sourced into──▶  Build  ──finalised into──▶  Product  ──sold as──▶  Order
```

- **Component** (existing: `Part`, `InventoryItem`, `HardwareBenchmark`) — unchanged. A physical or cataloguable part.
- **Build** (existing: `Flip` for flip-path builds, plus the Playbook-driven build spec used by Made-to-Order orders) — a specific assembled machine, or for Made-to-Order, the *build spec* that will be assembled once ordered. This PRD does not rename or restructure `Flip`; it adds a thin `Build` abstraction (Chapter 6.1) that both `Flip` and Made-to-Order build specs implement, so the Finalise Build pipeline (Chapter 8) has one input shape regardless of origin.
- **Product** (**new**) — the sellable unit. A Product either wraps a finished physical `Build` (pre-built, ready-to-ship path) or wraps a `Playbook` + selected options (configurable-template path, i.e. Made-to-Order). Every listing — eBay or storefront — points at exactly one `Product`.
- **Order** (existing, extended) — unchanged core purpose (a customer's purchase), extended so that every purchase, regardless of channel (storefront checkout, eBay Buy It Now, future eBay Configurator), converges on the same `Order` row and the same fulfilment pipeline.

### 5.2 Why introduce `Product` rather than reuse `Flip`

`Flip` today conflates "a physical unit we're refurbishing" with "a thing listed on eBay" (via `ebay_listing_id` on the model). This conflation breaks the moment a second sales channel is added, because a `Flip` cannot simultaneously represent "listed on eBay" and "listed on the storefront" without either duplicating listing-state fields per channel indefinitely, or introducing a proper listing/product layer. `Product` is that layer: one `Product` row, many `Listing` (channel) rows pointing at it (Chapter 6.3), no duplication, and a natural home for the Finalise Build outputs (photos, 3D asset, documents, benchmark results) that today live scattered or don't exist for the flip path at all.

### 5.3 End-to-end flow (pre-built path)

```
┌────────────┐   ┌────────────┐   ┌───────────┐   ┌──────────────┐   ┌───────────────┐
│  Sourcing  │──▶│ Procurement │──▶│ Inventory │──▶│ Build Planning│──▶│ Manufacturing │
└────────────┘   └────────────┘   └───────────┘   └──────────────┘   └───────┬───────┘
                                                                              ▼
                                                                    ┌─────────────────┐
                                                                    │ Finalise Build   │
                                                                    │ (Ch.8 pipeline)  │
                                                                    └────────┬────────┘
                                                                             ▼
                                                                     ┌───────────────┐
                                                                     │    Product     │
                                                                     │    created     │
                                                                     └───────┬───────┘
                                                                             ▼
                                                          ┌──────────────────┴──────────────────┐
                                                          ▼                                      ▼
                                                 ┌─────────────────┐                   ┌────────────────────┐
                                                 │ eBay Buy It Now │                   │ Storefront Ready-  │
                                                 │    listing      │                   │ to-Ship listing    │
                                                 └────────┬────────┘                   └──────────┬─────────┘
                                                          │                                       │
                                                          └──────────────┬────────────────────────┘
                                                                         ▼
                                                              ┌────────────────────┐
                                                              │  Watcher: sale on   │
                                                              │  either channel     │
                                                              └──────────┬─────────┘
                                                                         ▼
                                                          ┌──────────────────────────────┐
                                                          │ Auto-delist the OTHER channel │
                                                          │ Create Order, enter fulfilment│
                                                          └──────────────────────────────┘
```

### 5.4 End-to-end flow (Made-to-Order path)

```
Customer configures via 3D Configurator (Ch.12) ──▶ Compatibility-filtered selection ──▶
Standard or Fast Track delivery chosen ──▶ Payment (existing Stripe flow, unchanged) ──▶
Made-to-Order queue entry created ──▶ Build Planning ──▶ Manufacturing ──▶
Finalise Build (Ch.8, same pipeline) ──▶ Product created (configurable-template Product,
already "sold", no dual-listing step) ──▶ Order fulfilment (Ch.13, same CXP pipeline as
pre-built path) ──▶ Post-Sale Lifecycle (Ch.16)
```

Both paths converge at **Finalise Build** and at **Order fulfilment** — this convergence is the architectural point of this document. A Made-to-Order Product skips the dual-listing/Watcher step (Chapter 9) because it is created already-sold, but it produces an identical `Product` row (photos, documents, benchmark, 3D asset) for Customer Portal purposes, so a Made-to-Order customer gets exactly the same premium documentation suite as a pre-built buyer.

---

## 6. Database Schema

Extends the schema already defined in the prior CXP PRD (Chapter 7 there: `packaging_playbooks`, `procurement_*`, `cx_documents`, `usb_manifests`, `order_photos` extensions, `capture_3d_assets`, `quality_gate_*`, `cx_cost_records`). This chapter adds the commerce-layer tables.

### 6.1 `builds` (new, thin abstraction)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| build_type | Enum(`FLIP`, `MADE_TO_ORDER`) | |
| flip_id | FK → flips.id, nullable | set when `build_type = FLIP` |
| order_id | FK → orders.id, nullable | set when `build_type = MADE_TO_ORDER` (build spec is realized once the Order exists) |
| playbook_id | FK → playbooks.id, nullable | the Playbook this build was configured from, if any |
| spec_json | JSON | canonical component list for this specific physical unit — for `FLIP`, mirrors `Flip`'s selected components + upgrades; for `MADE_TO_ORDER`, mirrors `Order.specs` |
| status | Enum(`PLANNING`, `SOURCING`, `MANUFACTURING`, `FINALISED`, `CANCELLED`) | mirrors but does not replace `Flip.stage`/`Order.status` — this is the Finalise Build pipeline's own state, see Chapter 8.2 |
| created_at / updated_at | DateTime | |

`Build` is intentionally thin — a routing/orchestration record, not a data duplication layer. All detailed cost/component data continues to live on `Flip` or `Order` as it does today; `Build` exists so the Finalise Build pipeline (Chapter 8) has one consistent trigger/tracking object regardless of origin.

### 6.2 `products` (new — the canonical sellable unit)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| product_type | Enum(`PREBUILT`, `CONFIGURABLE_TEMPLATE`) | |
| build_id | FK → builds.id, nullable | set for `PREBUILT` (one finished physical unit) |
| playbook_id | FK → playbooks.id, nullable | set for `CONFIGURABLE_TEMPLATE` (the storefront-buyable template, pre-sale) |
| title | String | generated by existing `listing_generator.py`, reused (Chapter 9.2) |
| description | Text | generated, editable |
| price | Float | asking price (eBay + storefront, kept in sync — see Chapter 9.5 on price divergence handling) |
| status | Enum(`DRAFT`, `LISTED`, `RESERVED`, `SOLD`, `WITHDRAWN`) | `RESERVED` covers the brief window between "basket add" notification and confirmed sale, see Chapter 9.6 |
| sold_via_channel | Enum(`EBAY`, `STOREFRONT`), nullable | set at sale time |
| sold_order_id | FK → orders.id, nullable | |
| benchmark_report_document_id | FK → cx_documents.id, nullable | link to the generated Benchmark Report for this specific unit |
| capture_3d_asset_id | FK → capture_3d_assets.id, nullable | |
| hero_photo_url | String, nullable | pulled from `order_photos`/build photography, denormalized for fast listing-image rendering |
| profit_calculation_id | FK → profit_calculations.id, nullable | see 6.6 |
| created_at / updated_at | DateTime | |

A `PREBUILT` Product is created once, at the end of Finalise Build, from exactly one `Build`. A `CONFIGURABLE_TEMPLATE` Product represents "this Playbook is buyable right now" — one row per active, publicly-visible Playbook configuration, created/updated by the admin catalogue-curation action (Chapter 12.2), not by Finalise Build.

### 6.3 `listings` (extend existing `Listing` model — channel-specific presence of a Product)

The existing `Listing` model (per the master PRD) represents scraped marketplace listings (things FlipFlopOS is watching to *buy*). This is a different concept from "our own listing of a Product to *sell*" — to avoid overloading one model with two directions of meaning, this PRD introduces a **new** table, `product_listings`, rather than repurposing `Listing`:

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| product_id | FK → products.id | |
| channel | Enum(`EBAY`, `STOREFRONT`) | |
| external_listing_id | String, nullable | eBay item ID once posted; null for storefront (storefront uses `product_id` directly) |
| status | Enum(`PENDING`, `ACTIVE`, `SOLD`, `WITHDRAWN`, `FAILED`) | |
| listed_at | DateTime, nullable | |
| withdrawn_at | DateTime, nullable | |
| withdrawal_reason | Enum(`SOLD_OTHER_CHANNEL`, `MANUAL`, `EXPIRED`, `ERROR`), nullable | |
| view_count | Integer, default 0 | eBay-reported or storefront-tracked, refreshed by Watcher poll |
| watcher_count | Integer, default 0 | eBay "watchers" metric |
| offer_count | Integer, default 0 | |
| created_at / updated_at | DateTime | |

Unique constraint on (`product_id`, `channel`) while `status IN ('PENDING','ACTIVE')` — a Product can have at most one active listing per channel at a time.

### 6.4 `channel_events` (Email/Notification Watcher's event log)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| product_listing_id | FK → product_listings.id | |
| event_type | Enum(`OFFER_RECEIVED`, `QUESTION_RECEIVED`, `WATCHER_ADDED`, `BASKET_ADDED`, `SALE_CONFIRMED`, `PAYMENT_CONFIRMED`) | |
| payload_json | JSON | raw event data (offer amount, question text, etc.) |
| processed | Boolean, default false | |
| processed_at | DateTime, nullable | |
| resulting_action | String, nullable | e.g. "auto_delisted_storefront", "created_order_1042" |
| created_at | DateTime | |

### 6.5 `configurator_catalogue_visibility` (admin curation of publicly-selectable parts)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| playbook_slot_id | FK → playbook_slots.id | reuses existing `PlaybookSlot` |
| catalogue_variant_id | FK → catalogue_variants.id | reuses existing `CatalogueVariant` |
| is_publicly_visible | Boolean, default false | admin toggle — a variant existing in the catalogue does not mean a customer can pick it until this is true |
| display_order | Integer | |
| updated_by | FK → users.id | |
| updated_at | DateTime | |

### 6.6 `compatibility_rules` (configurator live filtering)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| rule_type | Enum(`SOCKET_MATCH`, `FORM_FACTOR_FIT`, `PSU_WATTAGE_MIN`, `CLEARANCE_MAX`, `RAM_TYPE_MATCH`, `CUSTOM`) | |
| subject_slot_id | FK → playbook_slots.id | the slot being constrained (e.g. CPU cooler) |
| constraint_json | JSON | rule-specific parameters (e.g. `{"requires_socket": "AM5"}`) |
| active | Boolean, default true | |

`compatibility_rules` is deliberately generic/data-driven (not hardcoded per-component logic) so new rule types can be added without a schema migration — evaluated by `compatibility_engine.py` (Chapter 12.4).

### 6.7 `profit_calculations` (extends existing Profit Calculator, per-Product)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| product_id | FK → products.id, nullable | |
| order_id | FK → orders.id, nullable | |
| component_cost | Float | |
| cx_cost | Float | from `cx_cost_records` (prior CXP PRD, Ch.7.18) |
| channel_fee | Float | eBay ~12.7% FVF if sold via eBay, 0 if storefront (Stripe fee tracked separately, existing) |
| gross_profit | Float, computed | |
| margin_pct | Float, computed | |
| computed_at | DateTime | |

This is additive to the existing Profit Calculator module — it gives per-Product/per-channel profit visibility (was the eBay sale or the storefront sale more profitable for an equivalent unit?) which the existing module does not currently disaggregate by channel.

### 6.8 Made-to-Order queue and Fast Track

| Column addition | Table | Notes |
|---|---|---|
| `fast_track_selected` | `orders` | Boolean, default false |
| `fast_track_fee` | `orders` | Float, default 0 (currently £49 per prompt spec, configurable — Chapter 12.7) |
| `promised_delivery_date` | `orders` | existing column — Fast Track recalculates this at order time (existing `BuildCapacity`/`BuildCapacityOverride` logic reused, not replaced) |

New table `made_to_order_queue`:

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| order_id | FK → orders.id, unique | |
| build_id | FK → builds.id, nullable | populated once Build Planning starts |
| priority | Enum(`STANDARD`, `FAST_TRACK`) | |
| queued_at | DateTime | |
| planning_started_at | DateTime, nullable | |

### 6.9 Post-sale lifecycle scheduling

New table `lifecycle_events` (generic scheduled/triggered customer-touchpoint ledger):

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| order_id | FK → orders.id | |
| event_type | Enum(`DELIVERY_CONFIRMED`, `GETTING_STARTED_EMAIL`, `CHECK_IN_7DAY`, `SATISFACTION_SURVEY_30DAY`, `REVIEW_REQUEST`, `MAINTENANCE_REMINDER`, `DRIVER_BIOS_UPDATE_NOTICE`, `WARRANTY_REMINDER`, `UPGRADE_CAMPAIGN`, `TRADE_IN_OFFER`, `LOYALTY_CAMPAIGN`, `REFERRAL_INVITE`) | |
| scheduled_for | DateTime | |
| status | Enum(`SCHEDULED`, `SENT`, `SKIPPED`, `FAILED`) | |
| sent_at | DateTime, nullable | |
| response_captured_json | JSON, nullable | e.g. survey score, review link clicked |
| created_at | DateTime | |

### 6.10 Business Intelligence recommendation log

New table `bi_recommendations`:

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| category | Enum(`PROFITABILITY`, `CLV`, `UPGRADE_CONVERSION`, `PACKAGING_COST`, `SUPPLIER_PERFORMANCE`, `REPEAT_PURCHASE`, `REVIEW_SENTIMENT`, `INVENTORY`) | |
| summary | Text | AI-generated recommendation text |
| supporting_data_json | JSON | the data snapshot the recommendation was derived from |
| confidence | Float | |
| status | Enum(`NEW`, `ACKNOWLEDGED`, `ACTIONED`, `DISMISSED`) | |
| created_at | DateTime | |

---

## 7. Entity Relationship Model

```
Playbook (existing) ──1:many──▶ PlaybookSlot (existing) ──1:many──▶ CatalogueVariant (existing)
                    │                                    │
                    │                                    └──1:1──▶ ConfiguratorCatalogueVisibility
                    │
                    ├──1:1──▶ PackagingPlaybook (prior CXP PRD)
                    │
                    └──1:many──▶ Build (new)

Build ──many:1──▶ Flip (existing, if build_type=FLIP)
Build ──many:1──▶ Order (existing, if build_type=MADE_TO_ORDER)
Build ──1:1──▶ Product

Product ──1:many──▶ ProductListing (new) ──1:many──▶ ChannelEvent (new)
Product ──1:1──▶ CXDocument (Benchmark Report, prior CXP PRD)
Product ──1:1──▶ Capture3DAsset (prior CXP PRD)
Product ──1:1──▶ ProfitCalculation (new)
Product ──1:1(optional)──▶ Order (sold_order_id)

Order (existing) ──1:1──▶ MadeToOrderQueue (new, if applicable)
Order ──1:many──▶ LifecycleEvent (new)
Order ──1:1──▶ CXCostRecord (prior CXP PRD)
Order ──1:many──▶ OrderPhoto, CXDocument, QualityGateResult (prior CXP PRD, unchanged)

CompatibilityRule (new) ──many:1──▶ PlaybookSlot
```

---

## 8. Finalise Build Pipeline

This is the automation core requested by the prompt's "Post-build / Pre-sale" section. It runs identically whether triggered by a completed flip build or a completed Made-to-Order build — the one place both business lines share fully automated logic.

### 8.1 Trigger

Fires when a `Build.status` transitions to `MANUFACTURING → FINALISED`-pending, i.e. the physical assembly is done and MES/Build Tracking (existing modules) mark the underlying `Flip`/`Order` as ready for finalisation. This mirrors the existing `READY_TO_PACKAGE` trigger point from the prior CXP PRD but occurs *before* packaging — Finalise Build produces the Product record and its supporting assets; Packaging (Chapter 13) happens after a Product is sold (for Made-to-Order) or immediately as part of listing prep (for pre-built, since a pre-built unit is boxed once, ready to ship the moment it sells, per Objective C2/the prompt's "Direct Website Ready-to-Ship" framing).

### 8.2 Pipeline stages (sequential, each independently retryable)

| Stage | Action | Reuses |
|---|---|---|
| 1. Hardware validation | POST/stress test confirms all components seated and functioning | New `hardware_validation_service.py`; result stored as a `QualityGateResult` (prior CXP PRD schema, check code `QC_HARDWARE_VALIDATION`) |
| 2. OS provisioning | Install Windows/Linux per `Order`/`Flip` spec, using existing `OSComponent` license inventory | Existing `os_component.py` model, extended provisioning script (new) |
| 3. Driver installation | Install GPU/chipset/peripheral drivers appropriate to the exact component list | New, references `static_file_refs` pattern from USB Templates (prior CXP PRD, 7.12) |
| 4. BIOS update | Flash to latest stable BIOS per motherboard model | New, logged as a `QualityGateResult` check |
| 5. Benchmarking | Run existing benchmark suite against the *actual assembled unit* (not the generic Playbook spec) | Existing Benchmark Recording module + `benchmark_scorer.py`; result feeds `CXDocument` type `BENCHMARK_REPORT` (prior CXP PRD, 18.3) |
| 6. Photography | Mandatory photo set captured | Photography Workflow, prior CXP PRD Chapter 20, unchanged |
| 7. 3D model generation | Capture/generate 3D asset | 3D Capture Workflow, prior CXP PRD Chapter 21, unchanged |
| 8. Customer documentation generation | Generate the relevant subset of the CX document suite that makes sense pre-sale (Build Certificate, Benchmark Report) — the remainder (Captain's Log, Welcome Letter, etc., which are customer-name-personalized) generate at Order-creation time instead, since a pre-built Product has no customer yet | Customer Experience Generator, prior CXP PRD Chapter 17, invoked in two passes (pre-sale generic pass here; post-sale personalized pass in Chapter 13 below) |
| 9. USB generation | Build the non-personalized portion of the USB manifest (drivers, BIOS, benchmarks, wallpapers) — personalized documents added post-sale | USB Builder, prior CXP PRD Chapter 19, same two-pass split as stage 8 |
| 10. Packaging preparation | Reserve packaging stock (Procurement reservation) for the resolved Packaging Playbook, but do not physically pack yet for pre-built units awaiting sale — physical packing happens at Chapter 13 for both paths, avoiding boxing a unit that then needs reopening for personalization inserts | Procurement reservation logic, prior CXP PRD Chapter 14.2 |
| 11. Profit calculation | Compute `ProfitCalculation` from component cost + reserved CX cost estimate | New service `profit_engine.py`, reuses `cost_rollup.py` (prior CXP PRD) logic |
| 12. Product creation | Create the `PREBUILT` Product row, link all generated assets | New `product_service.py` |

### 8.3 Failure handling

Each stage writes a `QualityGateResult`-style pass/fail (reusing prior CXP PRD's evidence pattern where applicable, e.g. photography/benchmark). A failed mandatory stage (hardware validation, OS provisioning, benchmarking) blocks Product creation — the `Build` stays in `MANUFACTURING` with a visible "blocked: [stage]" flag on the Build Tracking board (existing module, additive badge). Non-blocking stages (BIOS update, if a given motherboard has no update available) simply record `SKIPPED`.

### 8.4 Made-to-Order variant

Identical pipeline, triggered instead when a `made_to_order_queue` entry's Build completes manufacturing. Because the customer already exists (payment happened before Build Planning), stage 8/9's "personalized pass" runs immediately as part of this same pipeline invocation rather than waiting for a separate sale event — Made-to-Order Finalise Build produces a fully personalized document/USB set in one pass, and the resulting Product is created directly in `status = SOLD` (skipping Chapter 9's listing/Watcher flow entirely), then proceeds straight into Chapter 13 (Packaging & Final QC).

---

## 9. Dual-Channel Listing & the Email/Notification Watcher

### 9.1 Listing creation

On `PREBUILT` Product creation (Chapter 8.2 stage 12), the system automatically creates **two** `ProductListing` rows, one per channel, both `status = PENDING`:

- **eBay Buy It Now:** via existing `ebay_listing_poster.py`, extended to accept a `Product` (rather than only a `Flip`) as its source, pulling title/description from `listing_generator.py` (existing) and images from the Product's photography set.
- **Storefront Ready-to-Ship:** a new public storefront section (`/ready-to-ship`, Chapter 12.8) listing pre-built Products directly, using the same title/description/hero photo.

Both transition to `ACTIVE` once posting succeeds; a posting failure on one channel does not block the other (independent `status` per `ProductListing`).

### 9.2 Listing content generation

Reuses `listing_generator.py` (existing) unchanged for title/description synthesis, now additionally fed the Benchmark Report highlights and hero photo produced by Finalise Build — meaning listings produced under this pipeline are automatically richer (real benchmark numbers, real photos of the actual unit, not stock/generic images) than the current manual/semi-automated flip-listing process, directly serving Objective C2/C3.

### 9.3 The Watcher — scope

The Email/Notification Watcher (`channel_watcher_service.py`, new; scheduled via existing `scheduler.py`) continuously monitors, per active `ProductListing`:

- Offers received (eBay Best Offer if enabled; storefront has no offer mechanism in v1, so this applies to eBay only)
- Questions received (eBay buyer questions; storefront support inbox if one exists — otherwise routed to existing customer support channel)
- Watcher count changes (eBay "watchers" metric)
- Basket additions (storefront: item added to cart but not yet checked out)
- Sale confirmations (either channel)
- Payment confirmations (either channel — storefront via existing Stripe webhook, eBay via its payment API)

Each observed event writes a `ChannelEvent` row (Chapter 6.4).

### 9.4 Polling vs. push

Where the eBay API supports webhooks/push for a given event type, the Watcher registers for push. Where it does not (this varies by eBay API tier and event type — offers and watcher-count in particular are commonly polling-only in eBay's Trading/Sell APIs), the Watcher polls on a schedule (default every 5 minutes for active listings, configurable) via `scheduler.py`. This is documented explicitly as an assumption to be validated against the specific eBay API tier FlipFlopOS is provisioned with at implementation time — the schema (Chapter 6.4) is push/poll-agnostic so this can be tuned without a data model change.

### 9.5 Sale reconciliation — the core dual-listing safety mechanism (Objective C1)

```
Sale event received on Channel A (via push or poll)
        │
        ▼
Is this Product's other-channel ProductListing still ACTIVE?
        │
   ┌────┴────┐
  YES        NO (already withdrawn/sold — should not happen if this logic is correct;
   │          log as an ALERT-severity AlertEvent for manual review — this is the
   │          one scenario that must never silently pass)
   ▼
Immediately (synchronous, same request/job — not deferred to next poll cycle):
  1. Set Product.status = SOLD, sold_via_channel = A, sold_order_id = <new Order>
  2. Set winning ProductListing.status = SOLD
  3. Set losing ProductListing.status = WITHDRAWN, withdrawal_reason = SOLD_OTHER_CHANNEL
  4. Call channel-specific withdrawal API (eBay: end listing early; storefront: remove
     from Ready-to-Ship, show "sold" state if a customer already had it in an open tab)
  5. Create Order (existing Order model), status = AWAITING_SOURCING is skipped — a
     PREBUILT Product's Order enters directly at a new status READY_TO_PACKAGE-equivalent
     state, since sourcing/building is already done (see Chapter 9.7 state mapping)
  6. Log ChannelEvent.resulting_action = "auto_delisted_<channel>"
```

This reconciliation step is the single most safety-critical piece of new logic in this document (directly serving Objective C1) and is covered by dedicated tests (Chapter 25) including a simulated race condition (near-simultaneous sale signals from both channels within the same poll/push window) — the correct behavior is: the first event processed wins (enforced via a DB-level row lock / `SELECT ... FOR UPDATE` on the `Product` row during reconciliation), the second event's channel is treated as "already sold elsewhere," and — critically — if the second channel's sale cannot be technically prevented in time (e.g., eBay Buy It Now completed within seconds of a storefront sale), the system must flag this as a **double-sale incident** (new `AlertEvent` severity `CRITICAL`, category `double_sale`) for immediate manual intervention (contact customer, offer equivalent/refund) rather than attempting to silently auto-resolve a genuinely conflicting real-world sale.

### 9.6 Basket-add soft reservation

A storefront "basket add" event (Chapter 9.3) does not withdraw the eBay listing outright (too aggressive — many baskets abandon), but does set `Product.status = RESERVED` for a short window (default 15 minutes, configurable), during which the eBay listing remains live but a duplicate storefront basket-add or eBay offer against the same Product surfaces a "high demand" flag to the operator (informational only, not blocking) — this is a soft signal, not a hard lock, to avoid losing an eBay sale to an abandoned storefront cart.

### 9.7 Order status mapping for pre-built sales

Because a `PREBUILT` Product's Build is already finished, its resulting `Order` skips the sourcing/building phase of the existing `OrderStatus` enum. New handling: on Order creation from a pre-built sale, `Order.status` is set directly to the existing `ready_to_ship`-adjacent point in the state machine — specifically, it enters at whatever status the prior CXP PRD's extended state machine calls `READY_TO_PACKAGE` (prior CXP PRD, Chapter 6.4/27), since manufacturing is already complete; only the CX packaging/QC/documentation-personalization stage (Chapter 13 below) remains before shipping.

---

## 10. Screen Specifications (Commerce Layer — additive to prior CXP PRD screens)

### 10.1 Products list (`/admin/commerce/products`)

Table: thumbnail, title, type (Prebuilt/Configurable Template), status, listed channels (badges: eBay ✓/✗, Storefront ✓/✗), price, profit margin, days listed. Filters by status/type/channel. Row action → Product detail.

### 10.2 Product detail (`/admin/commerce/products/:id`)

Tabs: **Overview** (all linked assets — benchmark report, 3D asset, photos, profit calc), **Listings** (per-channel `ProductListing` status, view/watcher/offer counts, manual withdraw/relist action), **Events** (chronological `ChannelEvent` feed), **Order** (if sold, link through to the resulting Order/fulfilment screen from the prior CXP PRD's Order Packaging screen).

### 10.3 Channel Watcher dashboard (`/admin/commerce/watcher`)

Live feed (auto-refreshing) of recent `ChannelEvent` rows across all active listings, filterable by event type — this is the operational "what's happening on my listings right now" screen, directly serving the prompt's Email Watcher requirement as a visible surface, not just a background job.

### 10.4 Made-to-Order queue (`/admin/commerce/made-to-order`)

Kanban-style board (reusing existing Build Tracking visual pattern): columns Queued → Planning → Manufacturing → Finalising → Fulfilment, cards show priority badge (Standard/Fast Track — Fast Track cards visually distinguished, e.g. gold border), customer name, promised delivery date.

### 10.5 Configurator Catalogue Curation (`/admin/commerce/configurator-catalogue`)

Per-Playbook, per-slot list of all `CatalogueVariant` rows with a visibility toggle (`is_publicly_visible`) and drag-to-reorder `display_order` — this is how an admin controls exactly what a customer can pick in the public 3D configurator without touching the underlying (larger, review-queue-driven) catalogue used internally for sourcing.

### 10.6 Compatibility Rules editor (`/admin/commerce/compatibility-rules`)

List/edit `compatibility_rules` rows — rule type, subject slot, constraint JSON (presented as a structured form per rule type, not raw JSON editing, e.g. `SOCKET_MATCH` shows a simple "requires socket: [dropdown]" field).

### 10.7 Fast Track settings (`/admin/commerce/settings/fast-track`)

Single toggle: Fast Track enabled/disabled globally, plus fee amount field (default £49) and delivery-day-reduction field (default: standard 7-10 days → Fast Track target, e.g. 2-3 days, configurable, cross-checked against `BuildCapacity` to avoid promising a date the manufacturing floor cannot hit).

### 10.8 Business Intelligence dashboard (`/admin/reporting/business-intelligence`)

Card-based feed of `bi_recommendations`, grouped by category, each card: summary text, confidence, supporting-data expandable panel, action buttons (Acknowledge / Mark Actioned / Dismiss). Sits under the existing Reporting & Analytics nav section (consistent with the prior CXP PRD's Chapter 9.1 decision to avoid a duplicate top-level reporting entry).

### 10.9 Storefront: 3D Made-to-Order Configurator (`/configure/[slug]`, extends existing route)

Building on the existing configurator (per master PRD Chapter 6.1), this PRD specifies the **premium upgrade** to it:

- Full-screen 3D viewport (reusing `MotherboardViewer3D`, extended to render the *currently selected* case/component combination live, not a fixed motherboard-only view)
- Slot-by-slot picker sidebar, each slot showing only `is_publicly_visible = true` variants (Chapter 6.5), greyed-out/disabled state for any variant that fails a `compatibility_rules` check against the current selection (Chapter 12.4), with an inline tooltip explaining *why* ("Requires AM5 socket — incompatible with selected motherboard")
- Delivery option selector: Standard (7-10 days) vs. Fast Track (+£49, shows the recalculated promised date), Fast Track option hidden entirely if the global toggle (Chapter 10.7) is off
- Live price sidebar (existing pattern, extended to include Fast Track fee line item)
- "Continue" → existing order summary/payment flow, unchanged

### 10.10 Storefront: Ready-to-Ship (`/ready-to-ship`, new)

Public gallery of `PREBUILT` Products currently `status = LISTED` on the storefront channel — grid of hero photos, title, price, "benchmarked & tested" badge linking to the Benchmark Report, "Buy Now" CTA → existing checkout flow (treated as an instant-buy Order, no configuration step, no delivery-slot selection since the unit is already built — ships immediately per Chapter 13's already-prepared packaging).

---

## 11. User Stories

**Operations Manager**
- As an operations manager, I want a finished flip to automatically become a professionally listed Product on both eBay and our own site without manual document/photo assembly, so throughput isn't bottlenecked on my time.
- As an operations manager, I want to be certain a unit can never sell twice, so I never have to call a customer to apologize and refund.
- As an operations manager, I want to control exactly which catalogue variants a customer can select in the configurator, so I don't expose parts we don't have reliable supply of.

**Customer (Made-to-Order)**
- As a customer, I want to see incompatible parts clearly greyed out while configuring, so I don't have to learn PC compatibility rules myself.
- As a customer, I want the option to pay extra for faster delivery, so I can get my PC in time for a specific date if it matters to me.

**Customer (Ready-to-Ship / pre-built buyer)**
- As a customer, I want to see real benchmark results and real photos of the exact unit I'm buying, so I trust the "premium refurbished" claim.

**Business Owner**
- As a business owner, I want a dashboard that tells me *what to do* about profitability or churn risk, not just charts I have to interpret myself.
- As a business owner, I want post-sale touchpoints (check-ins, review requests, upgrade offers) to run automatically, so repeat purchase and referral doesn't depend on someone remembering to follow up.

---

## 12. Made-to-Order Configurator — Detailed Design

### 12.1 Slot/variant model (reuse, not redesign)

Slots and variants already exist (`PlaybookSlot`, `CatalogueVariant`, per the master PRD). This PRD does not change that model; it adds a visibility gate (6.5) and a compatibility gate (6.6) on top of it.

### 12.2 Admin approval workflow

An admin marks a `CatalogueVariant` publicly visible via the Configurator Catalogue Curation screen (10.5). This is independent of the variant's `status` in the existing review queue (`pending_review`/`active`/`hidden`) — a variant can be internally `active` (usable for sourcing/flips) without being publicly configurable, and vice versa is disallowed (a variant must be internally `active` before it can be made publicly visible — enforced validation, Chapter 20).

### 12.3 Live compatibility filtering — UX behavior

As a customer selects a component in one slot, the system re-evaluates all `compatibility_rules` referencing other slots and updates their available-variant lists client-side (via a `/api/v1/commerce/compatibility/evaluate` endpoint, Chapter 17) — greyed-out variants remain visible (not hidden) so the customer understands the full catalogue exists but sees why a specific combination doesn't work, supporting the premium/informed-configurator feel rather than a confusing disappearing-options UX.

### 12.4 Compatibility engine

`compatibility_engine.py` (new): given a partial selection (`{slot_id: variant_id}` map) and the full set of active `compatibility_rules`, returns per-slot `{variant_id: is_compatible, reason}`. Rule types (Chapter 6.6) cover the common real-world constraints (socket match, form-factor fit, PSU wattage minimum, case clearance maximum, RAM type match) with a `CUSTOM` escape hatch for anything not covered by the structured types, evaluated via a small rule-specific Python function registry rather than a generic rule interpreter (simpler, sufficient for v1 given the bounded rule-type list).

### 12.5 Fast Track

Global toggle (10.7) and per-order selection (6.8). Fast Track recalculates `Order.promised_delivery_date` by checking `BuildCapacity`/`BuildCapacityOverride` (existing) for the earliest slot that satisfies the Fast Track target window, rather than a fixed offset — so Fast Track never promises a date the floor cannot actually deliver, even during a capacity crunch (if no Fast Track-qualifying slot exists within a configurable maximum look-ahead, e.g. 5 days, the option is disabled in the UI for that specific day rather than silently overselling capacity).

### 12.6 Future-proofing for an eBay Configurator

No eBay Configurator is built in v1 (Non-Goal, Chapter 4). Future-proofing consists of: `Product.product_type = CONFIGURABLE_TEMPLATE` already models "a buyable template, not yet a specific built unit," and `made_to_order_queue` already models "a paid-for configuration awaiting build" independent of which channel it originated from — adding an `origin_channel` enum column (`STOREFRONT`, `EBAY_CONFIGURATOR`) to `orders` at that future point is a additive migration, not a redesign.

### 12.7 Fast Track fee configuration

Stored as a single tenant-level setting (extends existing `AppSettings`/settings pattern) rather than a new dedicated table — consistent with how other global toggles (auto-buy limits, scan intervals) are already stored.

### 12.8 Ready-to-Ship storefront section

New public route (10.10). Reuses existing storefront layout/header/footer components; the only new frontend work is the gallery grid and the instant-buy checkout variant (which is the existing checkout flow with the configuration step skipped, since the spec is already fixed).

---

## 13. Order Fulfilment (Packaging → Shipping) — Convergence Point

Both pre-built (post-sale) and Made-to-Order (post-manufacturing) Orders enter this stage identically. This chapter does not redefine the CXP fulfilment pipeline — it is the prior CXP PRD's Chapters 10 (Order Packaging screen), 13-24 (Packaging Playbooks, Procurement, Documentation Generator, USB Builder, Photography, 3D, Final QC, Cost Engine) — unchanged. The only integration point this document adds:

- **Personalization pass:** for a pre-built Product's Order, the generic pre-sale documents (Build Certificate, Benchmark Report — generated during Finalise Build, Chapter 8.2 stage 8) are now *re-generated* with the actual customer's name/details added (Captain's Log, Welcome Letter, QR Code Card, Warranty Pack, Getting Started/Upgrade Guides are generated fresh at this point, since they require a customer to exist). This is simply the Customer Experience Generator (prior CXP PRD, Chapter 17) running its normal trigger (`Order.status` entering the packaging stage) — no new logic required, since that trigger already exists; this note exists purely to clarify that pre-built Products correctly produce a *second*, personalized document pass rather than shipping the generic pre-sale versions.
- **Packaging Playbook resolution for pre-built Products:** resolved from the Product's originating `Playbook` (if the flip was built against a Playbook spec) or a default "Flip/Refurbished" Packaging Playbook tier if not (new seed Packaging Playbook, e.g. "Certified Refurbished," alongside the existing tier examples).

No new schema is introduced in this chapter — it is a pure integration/sequencing clarification.

---

## 14. Customer Portal Integration

Extends the prior CXP PRD's Chapter 25 (Customer Portal Integration) with one addition: the Portal's "Your Build Journey" page now also surfaces, for a Made-to-Order purchase, the fact that "your exact unit was benchmarked and photographed before packaging" (linking the same Benchmark Report / 3D asset a pre-built buyer sees) — reinforcing that a made-to-order customer receives the identical premium verification a pre-built buyer does, not a lesser experience for having waited longer.

---

## 15. Reporting

Extends the prior CXP PRD's Chapter 26 with commerce-layer reports:

| Report | Dimensions | Key metrics |
|---|---|---|
| Channel Performance | Channel (eBay/Storefront), date range | Sell-through rate, average days-to-sale, average sale price, profit margin by channel |
| Double-Sale Incident Log | Date range | Count, resolution outcome (refunded/substituted/manual), read directly from `AlertEvent` category `double_sale` (Chapter 9.5) |
| Configurator Funnel | Date range | Sessions started, compatibility-blocked selections encountered, completion rate, Fast Track attach rate |
| Fast Track Utilization | Date range | % of Made-to-Order Orders selecting Fast Track, incremental margin contributed, capacity impact |
| Lifecycle Engagement | Event type, date range | Send rate, open/click rate (where trackable via existing `email_service.py`), survey response rate, review conversion rate |

---

## 16. Post-Sale Customer Lifecycle Engine

### 16.1 Trigger model

Every `lifecycle_events` row (Chapter 6.9) is scheduled relative to a base event — for most, `Order.actual_delivery_date`; for a few (Getting Started email), `Order.status = SHIPPED`. Scheduling is computed at the moment the base event occurs (e.g., on delivery confirmation, the system immediately creates the 7-day and 30-day rows with `scheduled_for` set) and executed by the existing `scheduler.py` polling for due `lifecycle_events`.

### 16.2 Delivery confirmation

If carrier tracking data is available (per prior CXP PRD, Chapter 23.3, still non-blocking/manual-entry-capable in v1), `Order.actual_delivery_date` populates automatically or manually; this is the anchor for all subsequent lifecycle events.

### 16.3 Getting Started email

Sent on `SHIPPED` (not waiting for delivery), pointing the customer at the Customer Portal build journey page (already live per Chapter 5.4/CXP PRD Chapter 25) — reuses existing `email_service.py` send infrastructure.

### 16.4 7-day check-in

Short, low-pressure email ("How's [build nickname] treating you?") with a single-click "all good" / "need help" response captured into `response_captured_json`. A "need help" response creates a support ticket (existing support channel, if one exists — otherwise flagged as an `AlertEvent` for manual follow-up) rather than silently logging.

### 16.5 30-day satisfaction survey + review request

Combined touchpoint: short survey (score 1-5 + optional comment) followed immediately (same email, same page) by a review-platform link (Trustpilot/Google/eBay feedback, whichever the business uses) **only if** the survey score is ≥4 — a deliberate gate so the business isn't inviting a dissatisfied customer to leave a public review before their issue is addressed (a well-established practice; flagged here as a design decision, not left implicit).

### 16.6 Maintenance reminders / driver-BIOS update notices / warranty reminders

Scheduled at fixed offsets (e.g., 90-day maintenance tip, warranty-expiry-minus-30-days reminder) — content pulls from the same document data already generated (Getting Started Guide, Warranty Pack) so there is no new content-authoring burden, just re-surfacing at the right time.

### 16.7 Upgrade campaigns / trade-in offers / loyalty / referral

- **Upgrade campaigns:** re-surface the Upgrade Guide (prior CXP PRD, 18.5) at a chosen interval (e.g., 12 months) with a discount code for the identified upgrade path (RAM/GPU headroom already computed at document-generation time) — reuses existing discount/promo mechanism if one exists in the storefront checkout, otherwise flagged as a small additive Stripe-coupon integration (not a new payments system).
- **Trade-in offers:** triggered at a longer interval (e.g., 24 months), inviting the customer to trade in for a refreshed build — creates a lead record (reuses whatever CRM/lead concept exists, or a minimal new `trade_in_leads` table if none does) rather than an automated valuation (valuation remains a manual/admin-assisted step in v1).
- **Loyalty campaigns:** v1 scope is discount-code-based (per Non-Goal, Chapter 4) — e.g., "10% off your next build" issued after a successful review, not a points ledger.
- **Referral programme:** unique referral code per customer (generated at account creation or first order), tracked via existing `Customer` model (add `referral_code` and `referred_by_customer_id` columns) — reward issued (discount code) when a referred customer's Order is confirmed.

### 16.8 Opt-out

Every lifecycle email includes a standard unsubscribe/preference-center link (existing email infrastructure assumption); `lifecycle_events.status = SKIPPED` is set for any customer who has opted out, rather than silently not scheduling (preserves an audit trail of intended-but-suppressed touchpoints for BI purposes, Chapter 17).

---

## 17. Business Intelligence Module

### 17.1 Architecture

`bi_engine.py` (new service), scheduled (e.g., weekly) via `scheduler.py`, reuses the existing AI chain (`ai_service.py`, same Ollama→OpenRouter→Claude fallback already used for Hermes chat and gem recommendations — no second LLM integration introduced). Each run:

1. Pulls structured aggregates across the categories in Chapter 6.10 (profitability by channel/playbook, CLV by cohort, upgrade-guide-to-purchase conversion, packaging cost variance, supplier lead-time/price reliability, repeat-purchase rate, review sentiment — computed via basic sentiment scoring on captured review text if available, or via the 30-day survey score as a proxy if not, and inventory turn/dead-stock).
2. Passes the aggregate (not raw row-level data — cost and performance discipline) to the LLM with a structured prompt asking for a ranked list of specific, actionable recommendations, not generic commentary.
3. Stores each recommendation as a `bi_recommendations` row with the supporting aggregate snapshot attached, so a business owner can verify the reasoning, not just trust an opaque suggestion.

### 17.2 Example recommendation shapes (illustrative, not exhaustive)

- "Packaging cost for the 'Flagship Showcase' tier has risen 14% over 8 weeks, driven by a foam-insert price increase from Supplier X — Supplier Y offers the same spec at your prior price point." (Packaging Cost + Supplier Performance)
- "Customers who received the Upgrade Guide with a RAM-headroom recommendation converted to a RAM upgrade purchase at 3x the rate of those without — consider making this a proactive email at the 6-month mark rather than only portal-passive." (Upgrade Conversion)
- "Review sentiment for eBay-channel sales trails storefront-channel sales by a meaningful margin — the most common negative theme is packaging, not the product itself." (Review Sentiment + Channel Performance cross-reference)

### 17.3 Human-in-the-loop

Every recommendation requires explicit operator action (`Acknowledge`/`Mark Actioned`/`Dismiss`, Chapter 10.8) — the module never auto-executes a recommendation (e.g., it will never automatically switch suppliers or change prices); it surfaces, the business owner decides.

---

## 18. Business Rules

| ID | Rule |
|---|---|
| CBR-1 | A `Product` can have at most one `ProductListing` per channel in `PENDING`/`ACTIVE` status at any time. |
| CBR-2 | On confirmed sale via either channel, the other channel's active listing must be withdrawn synchronously, within the same processing transaction as Order creation — never deferred to a later job run. |
| CBR-3 | A double-sale (both channels confirm a sale for the same Product before withdrawal could take effect) must raise a `CRITICAL` `AlertEvent` and must never be silently auto-resolved. |
| CBR-4 | A `CatalogueVariant` must be internally `active` (existing review-queue status) before it can be marked `is_publicly_visible` in the configurator. |
| CBR-5 | Fast Track delivery date must never be promised beyond what `BuildCapacity`/`BuildCapacityOverride` can actually support; if no qualifying slot exists within the configured look-ahead window, Fast Track is unavailable for that day rather than falsely offered. |
| CBR-6 | A Made-to-Order Product/Order skips dual-channel listing entirely — it is created directly in a sold state. |
| CBR-7 | A pre-built Product's mandatory Finalise Build stages (hardware validation, OS provisioning, benchmarking) must all pass before Product creation — a Product is never listed from an unvalidated Build. |
| CBR-8 | The 30-day review-request touchpoint (Chapter 16.5) is only sent when the paired satisfaction survey score is ≥4 (or the touchpoint is configured to skip the gate entirely for a given tenant — gate is a configurable default, not hardcoded, but defaults ON). |
| CBR-9 | BI recommendations are advisory only — no automated action (price change, supplier switch, discount issuance) may be triggered directly by `bi_engine.py` without explicit operator confirmation. |
| CBR-10 | A `Build` row's `flip_id` and `order_id` are mutually exclusive — a Build is either a flip-origin build or a Made-to-Order-origin build, never both. |

---

## 19. Validation Rules

- `ProductListing` creation is rejected if an existing `PENDING`/`ACTIVE` row already exists for the same (`product_id`, `channel`) pair (enforced at the DB unique-constraint level, Chapter 6.3, not just application logic).
- `compatibility_rules.constraint_json` must validate against a per-`rule_type` JSON schema (e.g. `SOCKET_MATCH` requires a `requires_socket` string key) — rejected at save time if malformed, since a malformed rule would silently fail to filter anything, a worse outcome than a blocked save.
- Fast Track fee (`orders.fast_track_fee`) must be ≥ 0; disabling the global Fast Track toggle does not retroactively invalidate already-placed Fast Track orders (their fee/date stand as promised).
- `made_to_order_queue` cannot be created without a valid, completed payment (existing Stripe confirmation) — mirrors existing Order-creation validation, not new.
- Lifecycle event scheduling must not create duplicate `SCHEDULED` rows for the same (`order_id`, `event_type`) pair — idempotency check before insert, since delivery-confirmation could in theory fire more than once from a flaky carrier webhook.

---

## 20. Notifications

Extends the prior CXP PRD's Chapter 29 notification table with:

| Trigger | Recipient | Content |
|---|---|---|
| `ChannelEvent` type `OFFER_RECEIVED` or `QUESTION_RECEIVED` | Sales/Operations role | "New [offer/question] on [Product title] — [channel]" |
| Double-sale incident (`CRITICAL` `AlertEvent`) | Operations Manager, Business Owner | Immediate, highest-priority channel (SMS if configured, else email + in-app), full detail of both sale events |
| Finalise Build stage failure (mandatory stage) | Assigned operator | "[Build #X] blocked at [stage] — [error]" |
| Fast Track capacity exhausted for the day | Operations Manager | Informational — "Fast Track fully booked through [date]" |
| New `bi_recommendations` row created | Business Owner | Weekly digest (not per-recommendation spam) summarizing new items since last digest |
| Lifecycle "need help" response (7-day check-in) | Support role | "Customer [name] flagged an issue at day 7 — [Order #]" |

---

## 21. Security & Permissions

Extends the prior CXP PRD's Chapter 30 role table:

| Permission | Roles (default) |
|---|---|
| `commerce.product.view` | All admin roles |
| `commerce.product.manage_listings` | Operations Manager, Admin — manual withdraw/relist actions |
| `commerce.configurator_catalogue.edit` | Operations Manager, Admin |
| `commerce.compatibility_rules.edit` | Admin only (a malformed rule can silently break the customer-facing configurator) |
| `commerce.fast_track_settings.edit` | Admin only |
| `commerce.bi.view` | Business Owner, Admin |
| `commerce.bi.action` | Business Owner, Admin — the only roles that can mark a recommendation Actioned |
| `commerce.double_sale_incident.resolve` | Operations Manager, Admin — closing out a `double_sale` `AlertEvent` requires explicit resolution notes |

No new customer-facing security surface beyond what the prior CXP PRD already specifies (QR-token scoping, etc.) — the Ready-to-Ship storefront section (10.10) is fully public (no auth required to browse, standard checkout auth to purchase, consistent with existing storefront patterns).

---

## 22. API Design

Additive to the prior CXP PRD's API list (Chapter 31) and the existing FlipFlopOS API conventions.

```
# Products
GET    /api/v1/commerce/products
GET    /api/v1/commerce/products/{id}
POST   /api/v1/commerce/products/{id}/withdraw          # manual withdrawal, any channel
POST   /api/v1/commerce/products/{id}/relist

# Listings & Watcher
GET    /api/v1/commerce/products/{id}/listings
GET    /api/v1/commerce/channel-events                   # filterable feed for the Watcher dashboard
POST   /api/v1/commerce/channel-events/{id}/mark-processed

# Made-to-Order
GET    /api/v1/commerce/made-to-order/queue
GET    /api/v1/commerce/made-to-order/queue/{id}

# Configurator (public, storefront-facing)
GET    /api/v1/public/commerce/configurator/{playbook_slug}/catalogue   # visibility-filtered
POST   /api/v1/public/commerce/compatibility/evaluate                   # body: {selections: {slot_id: variant_id}}
GET    /api/v1/public/commerce/fast-track/availability?date=YYYY-MM-DD

# Ready-to-Ship (public)
GET    /api/v1/public/commerce/ready-to-ship
GET    /api/v1/public/commerce/ready-to-ship/{product_id}

# Finalise Build (internal/system-triggered, not customer-facing)
POST   /api/v1/commerce/builds/{id}/finalise/run          # manual re-trigger of a failed/partial pipeline
GET    /api/v1/commerce/builds/{id}/finalise/status

# Lifecycle
GET    /api/v1/commerce/orders/{order_id}/lifecycle-events
POST   /api/v1/commerce/orders/{order_id}/lifecycle-events/{id}/mark-sent   # manual override, e.g. resend

# Business Intelligence
GET    /api/v1/commerce/bi/recommendations
POST   /api/v1/commerce/bi/recommendations/{id}/action     # body: {status: ACKNOWLEDGED|ACTIONED|DISMISSED}
```

Standard response envelope matches existing conventions (success flag, data, error, pagination meta).

---

## 23. Acceptance Criteria

- [ ] A finished flip build automatically progresses through all Finalise Build stages and produces a `Product` with linked benchmark report, 3D asset, photos, and profit calculation, with no manual document assembly.
- [ ] A newly created `PREBUILT` Product is listed on both eBay and the storefront within the expected posting window, both `ProductListing` rows reaching `ACTIVE`.
- [ ] Simulating a sale event on either channel synchronously withdraws the other channel's listing and creates the correct `Order`, verified via integration test.
- [ ] Simulating a near-simultaneous sale on both channels raises a `CRITICAL` `double_sale` `AlertEvent` and does not silently resolve — verified via a dedicated race-condition test (Chapter 25).
- [ ] The public configurator only ever displays `is_publicly_visible = true` variants for a given slot, and correctly greys out any variant that fails an active `compatibility_rules` check against the current selection.
- [ ] Toggling Fast Track off globally immediately hides the option from the configurator for new sessions but does not alter already-placed Fast Track orders.
- [ ] A Made-to-Order Order, once its Build finalises, produces a fully personalized document/USB set in a single pass (no generic pre-sale-only version ever reaches the customer).
- [ ] A pre-built Product's Order correctly regenerates personalized documents (Captain's Log, Welcome Letter, QR Card, Warranty Pack) once a customer exists, distinct from the generic pre-sale Build Certificate/Benchmark Report.
- [ ] Lifecycle events schedule correctly relative to delivery confirmation/shipment and respect the review-request sentiment gate (CBR-8).
- [ ] The BI dashboard surfaces at least one recommendation per configured category against a seeded seven-week test dataset with known expected signal (e.g., an engineered packaging-cost spike is correctly surfaced).
- [ ] No regression in existing flip creation, eBay single-channel listing (prior to this feature), Playbook management, or storefront checkout flows — full existing test suite passes unchanged.

---

## 24. Testing Strategy

**Unit tests:** `compatibility_engine.py` rule evaluation per rule type; `profit_engine.py` arithmetic; Fast Track date-availability calculation against `BuildCapacity` fixtures; lifecycle event scheduling offset calculations.

**Integration tests:** full Finalise Build pipeline against a seeded completed Build fixture, asserting all 12 stages execute and a `Product` results; dual-listing creation and the full sale-reconciliation flow (Chapter 9.5) including the deliberate race-condition scenario; Made-to-Order end-to-end from configurator selection (with at least one deliberately incompatible combination attempted and rejected) through payment through Finalise Build through fulfilment through Customer Portal visibility.

**Regression tests:** full existing test suite (flip pipeline, single-channel eBay listing, Playbook CRUD, storefront checkout) re-run against the extended schema to confirm zero breakage — required gate before this feature is considered mergeable, given the explicit "do not redesign existing functionality" constraint.

**Load/soak:** Watcher polling load-tested against a realistic number of concurrently active listings to confirm the 5-minute default poll interval (Chapter 9.4) doesn't create a backlog; BI engine run-time tested against realistic multi-month data volume to confirm it fits its scheduled window.

**Manual/UAT:** operator walkthrough of the Watcher dashboard and Products screen with real (staging) eBay + storefront listings; customer-facing UAT of the configurator's compatibility greying/tooltip behavior on at least 2 mobile browsers, given this is the highest-visibility new customer-facing surface in this document.

---

## 25. Rollout Plan

**Phase 0 — Schema & shadow Finalise Build:** migrate new tables; run the Finalise Build pipeline in shadow mode (executes, logs, produces a `Product` record) without yet creating live listings — validates the automation pipeline against real completed builds with zero customer-facing risk.

**Phase 1 — Single-channel-first dual-listing:** enable live listing creation but initially only on the channel the business already uses today (assume eBay, since it predates the storefront Ready-to-Ship section) — validates Finalise Build → listing → sale → Order flow end-to-end before introducing the second channel and the reconciliation risk it brings.

**Phase 2 — Enable storefront Ready-to-Ship + full dual-channel reconciliation:** turn on the second channel and the sale-reconciliation/Watcher logic (Chapter 9) — this is the highest-risk phase (Objective C1) and should run with tightened alerting (every reconciliation event notified, not just failures) for an initial monitoring window before reverting to steady-state (failures/incidents only) notification volume.

**Phase 3 — Made-to-Order configurator upgrade:** ship the compatibility-filtered 3D configurator and Fast Track to the storefront, initially to a subset of Playbooks (start with the highest-margin/lowest-complexity tier to validate the compatibility rule set before covering the full catalogue).

**Phase 4 — Lifecycle engine:** enable post-sale automation, starting with the lowest-risk touchpoints (Getting Started email, 7-day check-in) before the review-gated 30-day survey and upgrade/trade-in/referral campaigns, which carry more brand-voice/commercial sensitivity and warrant a slower, content-reviewed rollout.

**Phase 5 — Business Intelligence:** enable once at least 8-12 weeks of Phase 1-4 data exists across channels/lifecycle events for the recommendations to be grounded in real signal rather than sparse/noisy early data.

**Rollback:** each phase is independently disableable via feature flag (reusing whatever flag mechanism the existing codebase uses, or a simple `AppSettings`-driven boolean per phase if none exists) without requiring a schema rollback, since all new tables are additive and no existing table's meaning changes — the only rollback consideration requiring care is Phase 2 (dual-channel), where disabling the storefront channel mid-flight must gracefully withdraw any live storefront `ProductListing` rows rather than leaving orphaned public listings.

---

## 26. Future Enhancements

- **eBay Configurator channel** (Chapter 12.6) — activate the already-modeled `product_type = CONFIGURABLE_TEMPLATE` for a second sales channel once eBay's configurator/variation listing capabilities are evaluated.
- **Real-time eBay push for offers/watchers**, replacing the Chapter 9.4 polling fallback, once/if eBay's API tier supports it.
- **Loyalty points ledger**, replacing the v1 discount-code-based approach (Chapter 16.7/Non-Goal), if repeat-purchase data (once available via Phase 5 BI) justifies the added complexity.
- **Automated trade-in valuation**, replacing the v1 manual-lead approach (Chapter 16.7).
- **BI-recommended automated actions** (with explicit opt-in per recommendation category), moving select low-risk categories (e.g., supplier-switch suggestions) from advisory-only (CBR-9) toward one-click-execute, once trust in recommendation quality is established over several BI cycles.
- **Multi-channel expansion beyond eBay/storefront** (e.g., a third marketplace) — the `ProductListing`/`channel` enum and Watcher architecture are designed to add a channel value without restructuring (additive, not redesign), but no additional channel is scoped in this document.

---

*End of document. This PRD should be read alongside [`flipflop-master-prd.md`](./flipflop-master-prd.md) (as-built system) and [`customer-experience-platform-prd.md`](./customer-experience-platform-prd.md) (fulfilment-stage schema this document references rather than repeats).*
