# Made-to-Order Website — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Build a customer-facing made-to-order PC configurator (flipflop.co.uk) that reads live from the FlipFlop catalogue, takes Stripe payments, manages build slot capacity, and tracks component deliveries via an LLM-powered email parser.

**Architecture:** Three subsystems — (1) a new `pc-flipper-customer/` Next.js app (the storefront), (2) order & capacity management in the existing backend + new admin pages, (3) a delivery tracker that polls Gmail/IMAP and uses Claude to extract delivery status. All three read from the catalogue API already built.

**Tech Stack:** Next.js 14 App Router / TypeScript / Tailwind (customer site), Python / FastAPI / SQLAlchemy 2.0 async (backend additions), Stripe Checkout (payments), IMAP + Claude API (delivery tracker), PostgreSQL (existing DB).

**Design note:** Visual design (colours, typography, component library) to be produced in Google Stitch before implementation begins. The spec defines pages, behaviour, and data — not pixel-level UI.

**Implementation order:** This spec should be executed as three separate implementation plans in sequence:
1. **Storefront** — `pc-flipper-customer/` Next.js app (Section 2)
2. **Orders & Capacity** — backend tables, endpoints, Stripe, admin pages (Section 3)
3. **Delivery Tracker** — IMAP poller, LLM extraction, delivery admin page (Section 4)

Each plan depends on the previous one being deployed.

---

## 1. Context

FlipFlop scrapes eBay for gem PC components, curates them through a catalogue layer (playbook slots, variants, cases), and exposes a public API at `/api/public/*`. This spec covers the customer-facing side: a storefront that turns that live catalogue into made-to-order PC builds.

```
/api/public/* (existing)
       ↓
pc-flipper-customer/   →   Stripe Checkout   →   Order confirmed
                                                       ↓
                                            Auto-assign build slot
                                                       ↓
                                            IMAP email poller
                                                       ↓
                                            Claude → delivery status
                                                       ↓
                                            Risk flag if delayed
```

---

## 2. Customer Storefront (`pc-flipper-customer/`)

### 2.1 Pages

#### `/` — Landing page
- Hero section with FlipFlop brand and one-line value proposition
- Playbook cards grid: one card per active playbook
- Each card shows: playbook name, one-liner description, tier names (read from `tier_names` on slots), "from £X" (estimated budget-tier total: sum of the cheapest active variant per customer-visible slot in budget tier, plus lowest-RRP case)
- Clicking a card navigates to `/configure/[slug]`
- Static playbook descriptions stored in a local config file (not in DB)

#### `/configure/[slug]` — Configurator
On load:
1. Fetch `/api/public/playbooks` to resolve slug → playbook ID
2. Fetch `/api/public/playbooks/[id]/slots` to get slots + variants grouped by tier
3. Fetch `/api/public/cases` for case options
4. Fetch `/api/orders/slots` (new endpoint) for available build weeks
5. Auto-select mid tier for all customer-visible slots

**Tier picker:** three buttons (budget / mid / high) using playbook-specific tier names from slot data. Selecting a tier re-selects the highest gem-score active variant for each slot in that tier.

**Slot list:** one row per customer-visible slot showing: slot label, selected component name, tier badge, display price, "swap" button. Non-customer-visible slots are fulfilled automatically (not shown).

**Swap modal:** opens on "swap" click. Shows all active variants for that slot across all tiers, sorted by gem score descending. Each card shows: component name, gem score, PassMark score, key spec (VRAM for GPU, capacity for RAM/storage, core count for CPU), display price, price delta vs current selection, tier badge. Current selection highlighted. Clicking a card selects it and closes modal.

**Case picker:** separate section below slots. Grid of available cases from `/api/public/cases`. Shows: image (if available), name, brand, form factor, RRP. One selected at a time.

**Build summary panel (sticky):**
- Line items: each selected component + case with price
- Total (sum of display prices + case RRP)
- Available build weeks: show next 3 weeks with slots remaining, customer picks one
- "Order Now" button → POST to `/api/orders/checkout`, redirect to Stripe

**URL:** `/configure/[slug]?tier=budget|mid|high` — tier pre-selection via query param (for marketing links).

#### `/order/[id]` — Order confirmation
- Shown after Stripe redirects back
- Fetches order details from `/api/orders/[id]` (public, by reference ID not internal ID)
- Shows: build summary, assigned build week, delivery address, reference number
- "Questions? Email us at hello@flipflop.co.uk"

### 2.2 Tech notes
- No auth on any customer page — fully public
- All data fetched server-side (Next.js Server Components) for SEO and speed, swap modal state managed client-side
- Stripe Checkout hosted page handles card details — no PCI scope on our server
- `NEXT_PUBLIC_API_URL` env var pointing to the FlipFlop backend

---

## 3. Order & Capacity Management

### 3.1 New DB tables

#### `orders`
```python
id: int (PK)
reference: str  # human-readable e.g. "FF-2026-0042" — shown to customer
playbook_id: int → Playbook.id
playbook_name: str  # snapshot at order time
build_config: JSON  # {slot_type: {variant_id, name, display_price}, case: {id, name, rrp}}
customer_name: str
customer_email: str
delivery_address: JSON  # {line1, line2, city, postcode, country}
total_gbp: float
stripe_session_id: str
stripe_payment_intent_id: str (nullable)
status: str  # pending_payment | confirmed | building | shipped | cancelled
assigned_build_week: str (nullable)  # ISO week "2026-W27"
estimated_arrival_date: date (nullable)  # latest component arrival across all tracked deliveries
delivery_at_risk: bool  # True if estimated_arrival_date >= build week start
created_at: str
updated_at: str
```

#### `build_capacity`
```python
id: int (PK)
default_per_week: int  # applies to all weeks with no override
created_at: str
updated_at: str
```
Single row — seeded with `default_per_week = 3`.

#### `build_capacity_overrides`
```python
id: int (PK)
week: str  # ISO week "2026-W27"
max_builds: int (nullable)  # null = week closed
note: str (nullable)  # e.g. "holiday"
created_at: str
```

### 3.2 New backend endpoints

#### `GET /api/orders/slots`
Returns next 8 calendar weeks with availability.
For each week:
- capacity = override.max_builds if override exists, else default_per_week (null override = 0)
- booked = count of confirmed/building orders with assigned_build_week = that week
- available = capacity − booked
- earliest_eligible = today + 5 working days (replaced by delivery tracker later)
Returns only weeks where available > 0 AND week_start_date ≥ earliest_eligible.

```json
[
  {"week": "2026-W27", "week_start": "2026-06-29", "available": 2, "capacity": 3},
  {"week": "2026-W28", "week_start": "2026-07-06", "available": 3, "capacity": 3}
]
```

#### `POST /api/orders/checkout`
Body: `{playbook_id, build_config, customer_name, customer_email, delivery_address, chosen_week}`

Validates:
- All variant IDs in build_config are active
- chosen_week still has capacity

Creates:
- `orders` row with status `pending_payment`
- Stripe Checkout session with line items matching build_config
- `success_url` = `/order/{reference}`, `cancel_url` = `/configure/[slug]`

Returns: `{stripe_url, reference}`

Slot is NOT reserved until payment confirmed — abandoned checkouts don't block capacity.

#### `POST /api/stripe/webhook`
Handles `checkout.session.completed`:
1. Find order by stripe_session_id
2. Set status → `confirmed`
3. Auto-assign build week: earliest week where available > 0 AND week_start ≥ today + 5 working days (re-checks live in case chosen_week filled up)
4. Send confirmation email (SMTP): order reference, build summary, assigned build week

#### `GET /api/orders/[reference]` (public)
Returns order details for confirmation page. Keyed by human reference, not internal ID.

#### Admin endpoints (auth required, under `/api/admin/`)
- `GET /api/admin/orders` — list all orders, filterable by status/week
- `PATCH /api/admin/orders/[id]` — update status (building, shipped, cancelled)
- `GET /api/admin/capacity` — current default + all overrides
- `PATCH /api/admin/capacity/default` — update default_per_week
- `PUT /api/admin/capacity/overrides/[week]` — set or remove week override

### 3.3 New admin pages in `pc-flipper`

#### Build Calendar (`/orders/calendar`)
Week-by-week view (rolling 12 weeks):
- Each week shows: capacity bar (booked/total), list of confirmed orders for that week, risk flags
- Click a week to set override capacity or close it (with optional note)
- Closed weeks shown in red, at-risk orders highlighted amber

#### Orders (`/orders`)
Table of all orders: reference, customer name, playbook, total, status, build week, risk flag.
Click to expand: full build config, delivery address, delivery events timeline.
Status can be advanced (confirmed → building → shipped) from this page.

---

## 4. Delivery Tracker

### 4.1 How it works

Hourly APScheduler job `poll_delivery_emails`:
1. Connects to inbox via IMAP (credentials in env vars `IMAP_HOST`, `IMAP_USER`, `IMAP_PASS`)
2. Fetches unseen emails from last 48 hours
3. For each email: checks subject against delivery keyword list
4. Matching emails → Claude API with prompt (see below)
5. Stores result as `delivery_event`
6. Attempts to link to an order by fuzzy-matching component names in email body
7. After processing, re-evaluates `estimated_arrival_date` and `delivery_at_risk` on affected orders

**Delivery keyword list (subject pattern match):**
`dispatched`, `shipped`, `out for delivery`, `delivered`, `your order`, `tracking`, `parcel`, `on its way`, `delivery update`, `expected delivery`

**Claude prompt:**
```
Extract delivery information from this email. Return JSON only:
{
  "retailer": "name of sender/retailer",
  "item_description": "what was ordered",
  "status": "dispatched|in_transit|out_for_delivery|delivered|delayed|unknown",
  "estimated_arrival": "YYYY-MM-DD or null",
  "confirmed_arrival": "YYYY-MM-DD or null",
  "notes": "any relevant detail e.g. delay reason"
}

Email subject: {subject}
Email body: {body}
```

**Linking to orders:** for each confirmed/building order, extract component names from build_config. If ≥1 component name appears (case-insensitive, partial match) in the email body, link the event to that order. If multiple orders match, link to the most recently created. Unmatched events stored with order_id = null for manual review.

**Risk flag logic:** after processing each batch, for every confirmed/building order:
- `estimated_arrival_date` = max(estimated_arrival across all linked delivery_events)
- `delivery_at_risk` = estimated_arrival_date ≥ build_week_start_date
- If newly at-risk: emit alert via existing alert system (`code="BUILD_AT_RISK"`, severity="warning")

### 4.2 New DB tables

#### `delivery_events`
```python
id: int (PK)
order_id: int (nullable) → orders.id
email_uid: str  # IMAP UID, prevents re-processing
email_subject: str
retailer: str (nullable)
item_description: str (nullable)
status: str  # dispatched|in_transit|out_for_delivery|delivered|delayed|unknown
estimated_arrival: date (nullable)
confirmed_arrival: date (nullable)
notes: str (nullable)
raw_email_snippet: str  # first 2000 chars, for debugging
created_at: str
```

#### `delivery_email_config`
```python
id: int (PK)
imap_host: str
imap_user: str
last_polled_at: str (nullable)
is_enabled: bool
```
Single row. Password stored in env var only, never in DB.

### 4.3 New admin page in `pc-flipper`

#### Deliveries (`/orders/deliveries`)
Grouped by order (only confirmed/building orders shown):
- Order reference, customer name, build week, risk flag banner if at risk
- Per-component row: component name, latest delivery status, estimated arrival, retailer
- Unlinked events section at bottom for manual assignment
- "Mark as arrived" button per component (manual override, sets confirmed_arrival = today)

---

## 5. Environment Variables (new)

| Variable | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe API key (backend) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signature verification |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe publishable key (customer site) |
| `NEXT_PUBLIC_API_URL` | FlipFlop backend URL (customer site) |
| `IMAP_HOST` | Email server hostname |
| `IMAP_USER` | Email address to poll |
| `IMAP_PASS` | Email password / app password |
| `SMTP_HOST` | For order confirmation emails |
| `SMTP_USER` | |
| `SMTP_PASS` | |
| `SMTP_FROM` | e.g. orders@flipflop.co.uk |

---

## 6. Out of Scope

- Customer accounts / login (no auth on storefront)
- Returns / refunds (handled manually)
- Inventory reservation before payment (abandoned carts don't block slots)
- Carrier API integrations (email LLM parsing covers this)
- Multiple currencies (GBP only)
- VAT receipts (manual for now)
