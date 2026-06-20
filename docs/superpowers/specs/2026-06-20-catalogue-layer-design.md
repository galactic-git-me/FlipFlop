# Catalogue Layer — Design Spec

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Add a catalogue layer to FlipFlop that curates inventory into a structured, customer-facing product catalogue — powering the future customer website with live-priced, playbook-aligned build configurations.

**Architecture:** Three new DB tables extend the existing Listing/Playbook models. The hourly scrape run gains four new steps. A new "Catalogue" section in the FlipFlop admin provides review and management. Public API endpoints serve the customer site with zero auth.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Next.js/TypeScript (admin frontend), PostgreSQL (existing DB).

---

## 1. Context

FlipFlop currently scrapes eBay listings, scores them as gems, and tracks flips. The customer website (a separate Next.js site, Subsystem 3) needs a structured catalogue of curated components and cases to power a build configurator. This spec covers the FlipFlop-side changes only — the customer site is a separate subsystem.

The catalogue layer sits between raw inventory and the customer-facing site:

```
Hourly scrape → Listings → Gem detection → Auto-publish → Review queue → Active catalogue → /api/public/*
```

---

## 2. Core Concepts

### Playbook Slots
Each playbook defines which component types are available as customer choices. The seven slot types are:

| Slot | Type key | Customer-visible on |
|------|----------|-------------------|
| Processor | `cpu` | All playbooks |
| Graphics Card | `gpu` | Gaming, AI, Creative, Build-Your-Own only |
| Memory | `ram` | All playbooks |
| Storage | `storage` | All playbooks |
| Cooling | `cooling` | Gaming, AI, Creative, Build-Your-Own only |
| Operating System | `os` | All playbooks |

Slots not marked customer-visible for a playbook are still fulfilled — the system picks the best-value gem automatically. The customer never sees that choice.

**Note: Case is not a slot.** Cases are sourced from `case_catalogue` (admin-managed, not scraped) and are always customer-visible on every playbook. The case selector on the customer site calls `/api/public/cases` directly, independent of the slot/variant system.

### Tiers
Each playbook offers three preset starting configurations — not a gate, but a starting point the customer can then customise:

- **Budget tier** (gem score 40–65)
- **Mid tier** (gem score 65–80)  
- **High tier** (gem score 80–100)

Tier names are playbook-specific and stored as JSON on the slot. Examples:
- Gaming Rig: Starter / Battle-Ready / Beast Mode
- AI Machine: Foundation / Accelerator / Powerhouse  
- Creative Studio: Essentials / Professional / Elite
- Home Office Station: Basic / Balanced / Premium
- Generic: Budget / Mid-Range / High End

### Publishing Workflow
Gems are auto-published to the catalogue when they cross a score threshold and match a defined slot. Admin reviews auto-published items daily and approves or rejects. Approved variants go live on the customer site immediately.

### Freshness
The catalogue is never more than 2 hours stale. Variants that disappear from eBay are auto-hidden after 2 consecutive missed scrape runs. If a listing reappears within 24 hours it is automatically reinstated.

### Pricing
Display price = current scrape price × 1.15, rounded up to the nearest £5. Recalculated every hourly run. The 15% buffer absorbs price fluctuations over a typical 7-day build window.

---

## 3. Data Model

### New table: `playbook_slots`

```python
class PlaybookSlot(Base):
    __tablename__ = "playbook_slots"

    id: int (PK)
    playbook_id: int → Playbook.id (FK, cascade delete)
    slot_type: str  # cpu | gpu | ram | storage | cooling | os  (case is NOT a slot — see case_catalogue)
    is_customer_visible: bool  # False = system picks best gem, not shown to customer
    tier_names: dict  # {"budget": "Starter", "mid": "Battle-Ready", "high": "Beast Mode"}
    score_band_budget: list[int]  # [40, 65]
    score_band_mid: list[int]     # [65, 80]
    score_band_high: list[int]    # [80, 100]
    created_at: str
    updated_at: str
```

Unique constraint: `(playbook_id, slot_type)`.

### New table: `catalogue_variants`

```python
class CatalogueVariant(Base):
    __tablename__ = "catalogue_variants"

    id: int (PK)
    listing_id: int → Listing.id (FK)
    slot_id: int → PlaybookSlot.id (FK)
    status: str  # pending_review | active | hidden | rejected
    display_price: float   # scrape_price × 1.15, rounded to £5
    tier: str              # budget | mid | high (derived from gem score at publish time)
    consecutive_misses: int  # default 0; auto-hide at 2
    last_seen_at: str
    auto_published_at: str
    reviewed_at: str | None
    reviewed_by: str | None  # admin identifier
    reject_reason: str | None
```

Index on `(slot_id, status)` for fast catalogue reads.

### New table: `case_catalogue`

```python
class CaseCatalogue(Base):
    __tablename__ = "case_catalogue"

    id: int (PK)
    name: str            # "O11 Dynamic EVO"
    brand: str           # "Lian Li"
    form_factor: str     # atx | matx | itx
    images: list[str]    # manufacturer photo URLs
    rrp_gbp: float
    is_transparent_panel: bool  # True for glass-side cases (majority)
    status: str          # active | hidden
    notes: str | None
    created_at: str
    updated_at: str
```

Cases are admin-managed only. No scraping. No freshness logic needed.

---

## 4. Scrape Run Additions

Four new steps added to the existing hourly scrape pipeline, executed after gem detection:

### Step A — Auto-publish
For every listing newly detected as a gem (gem_score ≥ 40 — the minimum of the budget score band, configurable via slot settings):
1. Determine `component_type` from existing classifier
2. Find matching `PlaybookSlot` records for that component type
3. Determine tier from gem score band
4. If no existing `CatalogueVariant` for this `(listing_id, slot_id)`:
   - Create variant with `status=pending_review`
   - Set `display_price = ceil(listing.price * 1.15 / 5) * 5`
   - Set `tier` from score band
   - Set `auto_published_at = now()`

### Step B — Freshness check
For every `CatalogueVariant` with `status=active` or `status=pending_review`:
1. Check if `listing_id` was seen in this run's scrape results
2. If not seen: `consecutive_misses += 1`
3. If `consecutive_misses >= 2`: `status = hidden`
4. If seen: `consecutive_misses = 0`, `last_seen_at = now()`
5. If `status=hidden` and listing seen again within 24h of hiding: `status = active`, `consecutive_misses = 0`

### Step C — Price update
For every `CatalogueVariant` with `status=active`:
1. Fetch current `listing.price`
2. `display_price = ceil(listing.price * 1.15 / 5) * 5`
3. Update record (no admin action needed)

### Step D — Review digest
Once per day at 08:00:
1. Count `CatalogueVariant` records with `status=pending_review`
2. If count > 0: emit alert via existing `emit_alert()` system
3. Alert message: "Catalogue review: {count} new variants awaiting approval"

---

## 5. API Endpoints

### Admin endpoints (existing auth, `/api/catalogue/`)

```
GET    /api/catalogue/review-queue
       → list of pending_review variants, newest first
       → includes listing detail (title, price, gem_score, component_type)
       → includes slot detail (playbook name, slot_type, tier)

POST   /api/catalogue/variants/{id}/approve
       → status = active, reviewed_at = now()

POST   /api/catalogue/variants/{id}/reject
       body: { reason: str }
       → status = rejected, reject_reason saved

POST   /api/catalogue/variants/approve-all
       → approves all pending_review in one call

GET    /api/catalogue/variants
       → all variants with filters: status, playbook_id, slot_type, tier

GET    /api/catalogue/cases
       → all cases (admin view, includes hidden)

POST   /api/catalogue/cases
       body: CaseCatalogueCreate

PATCH  /api/catalogue/cases/{id}
       body: CaseCatalogueUpdate (partial)
```

### Public endpoints (no auth, `/api/public/`)

```
GET    /api/public/playbooks
       → active playbooks only
       → includes slot definitions and tier_names per slot
       → excludes internal fields (gem scores, pricing multipliers)

GET    /api/public/playbooks/{id}/slots
       → customer-visible slots only (is_customer_visible=True)
       → per slot: available active variants grouped by tier
       → each variant: display_price, component title, key specs only
       → excludes hidden/rejected/pending variants

GET    /api/public/cases
       → active cases only
       → full image list, form_factor, is_transparent_panel
```

Public endpoints are read-only. No mutations from the customer site. Rate-limited to 60 req/min per IP.

---

## 6. Admin UI

A new **Catalogue** section added to the FlipFlop sidebar with four sub-pages:

### Review Queue (landing page)
- Badge on sidebar nav showing pending count
- Table: component name | playbook + slot + tier | display price | gem score | Approve / Reject buttons
- Bulk "Approve All" button
- Reject requires a reason (dropdown: "Price too high", "Wrong category", "Duplicate", "Other")

### Component Variants
- Full list of all variants filterable by: status | playbook | slot type | tier
- Inline status toggle (active ↔ hidden) for manual override
- Shows consecutive_misses counter and last_seen_at for freshness visibility

### Case Catalogue
- Grid of cases with thumbnail, name, brand, form factor, status
- "Add Case" form: name, brand, form factor, image URLs (paste from manufacturer), RRP, transparent panel toggle
- Edit / hide / show per case

### Slot Configuration
- Per-playbook table matching the slot mapping from design
- Toggle is_customer_visible per slot per playbook
- Edit tier_names and score bands per slot
- Seeded on first deploy with defaults from this spec

---

## 7. Out of Scope

- Customer-facing website (Subsystem 3)
- AI image generation pipeline (Subsystem 2)
- Order management / Stripe (Subsystem 4)
- Case scraping (cases are admin-managed only)
- Warranty upsell (revisit after 20+ builds)
- Multi-currency pricing

---

## 8. Success Criteria

- Hourly scrape run completes with all 4 new steps in under 60 additional seconds
- Admin can action the full review queue in under 2 minutes
- Public endpoints return accurate catalogue data within 2 hours of a listing disappearing from eBay
- Zero customer-facing downtime when variants go hidden (they simply no longer appear as options)
- All new endpoints covered by integration tests
