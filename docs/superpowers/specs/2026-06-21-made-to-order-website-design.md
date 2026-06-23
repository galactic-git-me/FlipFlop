# Made-to-Order Website — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Build a customer-facing made-to-order PC configurator (flipflop.co.uk) that reads live from the FlipFlop catalogue, takes Stripe payments, auto-schedules builds on an internal calendar, and tracks component deliveries via an LLM-powered email parser.

**Architecture:** Three subsystems — (1) a new `pc-flipper-customer/` Next.js app (the storefront), (2) order management + intelligent build scheduler in the existing backend + new admin pages, (3) a delivery tracker that polls Gmail/IMAP and uses Claude to extract delivery status. All three read from the catalogue API already built.

**Tech Stack:** Next.js 14 App Router / TypeScript / Tailwind (customer site), Python / FastAPI / SQLAlchemy 2.0 async (backend additions), Stripe Checkout (payments), IMAP + Claude API (delivery tracker), PostgreSQL (existing DB).

**Design note:** Visual design (colours, typography, component library) to be produced in Google Stitch before implementation begins. The spec defines pages, behaviour, and data — not pixel-level UI.

**Implementation order:** This spec should be executed as three separate implementation plans in sequence:
1. **Storefront** — `pc-flipper-customer/` Next.js app (Section 2)
2. **Orders & Build Scheduler** — backend tables, endpoints, Stripe, admin calendar (Section 3)
3. **Delivery Tracker** — IMAP poller, LLM extraction, scheduler integration (Section 4)

Each plan depends on the previous one being deployed.

---

## 1. Context

FlipFlop scrapes eBay for gem PC components, curates them through a catalogue layer (playbook slots, variants, cases), and exposes a public API at `/api/public/*`. This spec covers the customer-facing side: a storefront that turns that live catalogue into made-to-order PC builds.

```
/api/public/* (existing)
       ↓
pc-flipper-customer/   →   Stripe Checkout   →   Order confirmed
                                                       ↓
                                            Build Scheduler
                                            (auto-assigns build date,
                                             optimises calendar,
                                             re-runs on every change)
                                                       ↓
                                            IMAP email poller
                                                       ↓
                                            Claude → component arrival date
                                                       ↓
                                            Re-run scheduler if late
```

---

## 2. Customer Storefront (`pc-flipper-customer/`)

### 2.1 Pages

#### `/` — Landing page
- Hero section with FlipFlop brand and one-line value proposition
- Playbook cards grid: one card per active playbook
- Each card shows: playbook name, one-liner description, tier names (read from `tier_names` on slots), "from £X" (estimated budget-tier total: sum of the cheapest active variant per customer-visible slot in budget tier, plus lowest-RRP case + postage)
- Clicking a card navigates to `/configure/[slug]`
- Static playbook descriptions stored in a local config file (not in DB)

#### `/configure/[slug]` — Configurator
On load:
1. Fetch `/api/public/playbooks` to resolve slug → playbook ID
2. Fetch `/api/public/playbooks/[id]/slots` to get slots + variants grouped by tier
3. Fetch `/api/public/cases` for case options
4. Fetch `/api/public/checkout-config` for postage, insurance rate, fast-track fee, delivery day ranges
5. Auto-select mid tier for all customer-visible slots

**Tier picker:** three buttons (budget / mid / high) using playbook-specific tier names from slot data. Selecting a tier re-selects the highest gem-score active variant for each slot in that tier.

**Slot list:** one row per customer-visible slot showing: slot label, selected component name, tier badge, display price, "swap" button. Non-customer-visible slots are fulfilled automatically (not shown).

**Swap modal:** opens on "swap" click. Shows all active variants for that slot across all tiers, sorted by gem score descending. Each card shows: component name, gem score, display price, price delta vs current selection, tier badge. Clicking a card selects it and closes modal.

**Case picker:** separate section below slots. Grid of available cases from `/api/public/cases`. Shows: image (if available), name, brand, form factor, RRP. One selected at a time.

**Build summary panel (sticky):**
- Line items:
  1. Each selected component with price
  2. Case with price
  3. Postage: £XX (static, from config)
  4. Insurance: £XX (calculated as `insurance_rate_pct` % of components + case subtotal, rounded to nearest £0.50)
  5. Fast-track (if selected): +£XX
- **Total** line
- **Fast-track toggle:** "Fast-track my build — 2–3 working days (+£49)" checkbox. When selected, updates total and changes delivery estimate.
- **Delivery estimate** (below total): "Estimated delivery: 3–5 working days" (standard) or "Estimated delivery: 2–3 working days" (fast-track). This is static text from config — not a specific date.
- **"Order Now" button** → POST to `/api/orders/checkout`, redirect to Stripe Checkout

**URL:** `/configure/[slug]?tier=budget|mid|high` — tier pre-selection via query param (for marketing links).

#### `/order/[reference]` — Order confirmation
- Shown after Stripe redirects back (success_url)
- Fetches order details from `/api/orders/[reference]` (public endpoint, keyed by human reference)
- Shows: build summary, delivery address, estimated delivery range (e.g. "Expected within 3–5 working days of payment"), reference number
- "Questions? Email us at hello@flipflop.co.uk"

### 2.2 Tech notes
- No auth on any customer page — fully public
- All data fetched server-side (Next.js Server Components) for SEO and speed; swap modal and fast-track toggle state managed client-side
- Stripe Checkout hosted page handles card details — no PCI scope on our server
- `BACKEND_URL` env var for server-side fetches; Next.js rewrite proxies `/api/*` for any client-side calls

---

## 3. Order Management & Build Scheduler

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
components_subtotal_gbp: float   # sum of variant display prices + case RRP
postage_gbp: float               # snapshotted from config at order time
insurance_gbp: float             # snapshotted (calculated) at order time
fast_track_fee_gbp: float        # 0 if standard, config fast_track_fee_gbp if priority
total_gbp: float                 # sum of all above
is_fast_track: bool              # True = priority build
stripe_session_id: str
stripe_payment_intent_id: str (nullable)
status: str                      # pending_payment | confirmed | building | paused | shipped | cancelled
build_status: str (nullable)     # scheduled | in_progress | paused | completed
scheduled_build_date: date (nullable)  # assigned by scheduler
delivery_promise_min: date (nullable)  # order_confirmed_date + delivery_days_min (working days)
delivery_promise_max: date (nullable)  # order_confirmed_date + delivery_days_max (working days)
component_ready_date: date (nullable)  # estimated date all components will be in hand
created_at: datetime
updated_at: datetime
```

#### `build_settings`
Single row — all values admin-configurable via `/api/admin/build-settings`.

```python
id: int (PK)
builds_per_day: int              # default 2
standard_days_min: int           # default 3
standard_days_max: int           # default 5
fast_track_days_min: int         # default 2
fast_track_days_max: int         # default 3
fast_track_fee_gbp: float        # default 49.00
postage_gbp: float               # default 12.00
insurance_rate_pct: float        # default 1.5  (% of components+case subtotal)
component_arrival_estimate_days: int  # default 1 (working days after order confirmation)
updated_at: datetime
```

### 3.2 Build Scheduler

The scheduler is a pure function `run_build_scheduler()` called any time the build plan needs re-optimising:
- New order confirmed (Stripe webhook)
- Order cancelled
- Order upgraded to fast-track
- Component arrival estimate changes (delivery tracker update)
- Admin manually triggers re-schedule

#### Algorithm

```
Input: all orders with status in (confirmed, building, paused)
Settings: builds_per_day, working days only (Mon–Fri)

1. SORT orders by priority:
   a. is_fast_track DESC (fast-track first)
   b. delivery_promise_min ASC (tightest deadline first within same priority tier)

2. BUILD the calendar slot list:
   - Generate working days starting from tomorrow
   - Each day has `builds_per_day` slots
   - Skip days where component_ready_date > day (components not in yet)

3. ASSIGN scheduled_build_date:
   - Walk sorted orders; assign each to the earliest available slot
     where day >= order.component_ready_date
   - Store assigned date on order

4. CHECK interruption (called after each new fast-track order):
   - "Currently working on" = order with scheduled_build_date == today
     AND build_status in (in_progress, scheduled)
   - If that order is NOT fast-track and the new order IS fast-track:
     a. Mark current order build_status = paused, status = paused
     b. Re-run step 3 giving today's remaining slot to the fast-track order
   - If current order IS fast-track: do not interrupt; re-optimise future slots only

5. CALCULATE traffic light per order:
   - build_done_date = scheduled_build_date + 1 working day (shipping day)
   - GREEN  if build_done_date <= delivery_promise_min
   - AMBER  if delivery_promise_min < build_done_date <= delivery_promise_max
   - RED    if build_done_date > delivery_promise_max

6. CALCULATE delay reasons (for traffic light hover tooltip):
   For each non-green order, identify contributing delays:
   - "Component X: estimated arrival {date} → delays build by N working day(s)"
   - "Build queue full until {date} → delays build by N working day(s)"
   - "Total overrun: {N} working day(s) past promised window"
```

#### "Currently working on" derivation
- No manual "start" button needed
- `scheduled_build_date == today` → that order is considered in progress
- If `build_status == paused`: interrupted, show flashing on calendar
- Scheduler never marks a build in_progress explicitly — status is derived from date + build_status field

### 3.3 New backend endpoints

#### `GET /api/public/checkout-config`
Returns static values needed by the storefront to calculate totals and show delivery estimates. No auth required.

```json
{
  "postage_gbp": 12.00,
  "insurance_rate_pct": 1.5,
  "fast_track_fee_gbp": 49.00,
  "standard_days_min": 3,
  "standard_days_max": 5,
  "fast_track_days_min": 2,
  "fast_track_days_max": 3
}
```

#### `POST /api/orders/checkout`
Body:
```json
{
  "playbook_id": 1,
  "build_config": {"cpu": {"variant_id": 42, "name": "...", "display_price": 125}, ...},
  "case": {"id": 7, "name": "...", "rrp": 95},
  "customer_name": "Jane Smith",
  "customer_email": "jane@example.com",
  "delivery_address": {"line1": "...", "city": "...", "postcode": "SW1A 1AA", "country": "GB"},
  "is_fast_track": false
}
```

Validates:
- All variant IDs in build_config are active
- Case ID is active
- is_fast_track is boolean

Calculates at server (not trusted from client):
- `components_subtotal_gbp` = sum of variant display_prices + case rrp
- `postage_gbp`, `insurance_gbp`, `fast_track_fee_gbp` from current `build_settings`
- `total_gbp` = sum of all

Creates:
- `orders` row with status `pending_payment`
- Stripe Checkout session with line items:
  1. "FlipFlop {playbook_name} Build" — components_subtotal_gbp
  2. "Postage" — postage_gbp
  3. "Build Insurance" — insurance_gbp
  4. "Fast-track Build" — fast_track_fee_gbp (omitted if 0)
- `success_url` = `/order/{reference}`, `cancel_url` = `/configure/[slug]`

Returns: `{stripe_url, reference}`

#### `POST /api/stripe/webhook`
Handles `checkout.session.completed`:
1. Find order by stripe_session_id
2. Set status → `confirmed`, build_status → `scheduled`
3. Set `component_ready_date` = today + `component_arrival_estimate_days` working days
4. Set `delivery_promise_min` / `delivery_promise_max` from settings + today
5. Call `run_build_scheduler()` to assign `scheduled_build_date` and re-optimise all
6. Send confirmation email (SMTP): reference, build summary, "Estimated delivery: X–Y working days"

#### `GET /api/orders/[reference]` (public)
Returns order for confirmation page. Keyed by human reference.

#### Admin endpoints (auth required)
- `GET /api/admin/orders` — list all orders, filterable by status / build_status / date
- `PATCH /api/admin/orders/[id]` — update status (building → shipped, or cancel)
- `GET /api/admin/build-settings` — return current build_settings row
- `PATCH /api/admin/build-settings` — update any field; calls `run_build_scheduler()` after save
- `POST /api/admin/orders/[id]/reschedule` — manually trigger scheduler for one order
- `POST /api/admin/scheduler/run` — manually trigger full `run_build_scheduler()`

### 3.4 Admin pages in `pc-flipper`

#### Build Calendar (`/orders/calendar`)

Day-by-day view (rolling 30 working days, scrollable):
- Each day column shows up to `builds_per_day` build slots
- Each build card shows:
  - Customer name + reference
  - Playbook name
  - **Gold background** if `is_fast_track`
  - **Traffic light dot** (green / amber / red — see scheduler algorithm)
  - **Flashing border** if `build_status == paused` (interrupted, need to stop and switch)
  - Hover on traffic light dot → tooltip showing delay breakdown (see algorithm step 6)
- If today has a paused build AND a fast-track build: the fast-track is shown at top, paused shows flashing below it
- Sidebar panel: current `build_settings` (builds_per_day, delivery ranges, postage, insurance rate, fast-track fee) with inline edit + "Save & Re-schedule" button

#### Orders (`/orders`)
Table: reference, customer name, playbook, total, is_fast_track badge, status, build_status, scheduled_build_date, traffic light, delivery promise range.
Click to expand: full build config, delivery address, delivery events timeline, re-schedule button.
Status can be advanced (building → shipped, cancel) from this view.

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
7. After processing, for each affected order:
   - Recalculate `component_ready_date` = max(estimated_arrival across all linked delivery_events)
   - If `component_ready_date` changed: call `run_build_scheduler()` to re-optimise all builds
   - If any order flips to RED: emit alert (`code="BUILD_AT_RISK"`, severity="warning")

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

**Linking to orders:** for each confirmed/building/paused order, extract component names from build_config. If ≥1 component name appears (case-insensitive, partial match) in the email body, link the event to that order. If multiple orders match, link to the most recently created. Unmatched events stored with order_id = null for manual review.

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
created_at: datetime
```

#### `delivery_email_config`
```python
id: int (PK)
imap_host: str
imap_user: str
last_polled_at: datetime (nullable)
is_enabled: bool
```
Single row. Password stored in env var only, never in DB.

### 4.3 Admin page in `pc-flipper`

#### Deliveries (`/orders/deliveries`)
Grouped by order (only confirmed/building/paused orders shown):
- Order reference, customer name, scheduled build date, traffic light status, delivery promise range
- Per-component row: component name, latest delivery status, estimated arrival, retailer
- Unlinked events section at bottom for manual assignment
- "Mark as arrived" button per component (manual override — sets confirmed_arrival = today, triggers `run_build_scheduler()`)

---

## 5. Environment Variables (new)

| Variable | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe API key (backend) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signature verification |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe publishable key (customer site) |
| `BACKEND_URL` | FlipFlop backend URL (customer site server-side fetches) |
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
- Inventory reservation before payment (abandoned checkouts don't affect schedule)
- Carrier API integrations (static postage + email LLM tracking covers this)
- Multiple currencies (GBP only)
- VAT receipts (manual for now)
- Weekend or bank holiday awareness beyond Mon–Fri working day counting
