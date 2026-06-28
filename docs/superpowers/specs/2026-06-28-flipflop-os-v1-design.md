# FlipFlopOS v1.0 Design

**Status:** Design Phase  
**Date:** 2026-06-28  
**Model:** Hybrid Made-to-Order + Speculative Inventory  

---

# Executive Summary

FlipFlopOS is a complete operating system for PC flipping businesses. v1.0 launches with:

1. **Customer storefront** — 3D configurator, budget-to-specs, real-time pricing
2. **Quote engine** — Component sourcing, instant quotes, full payment upfront
3. **Order management** — Build tracking from payment to delivery
4. **Demand intelligence** — Tracks what customers configure
5. **Playbook validator** — AI reviews playbooks against live demand + market data, suggests profitable builds
6. **Sourcing optimization** — Integrated vendor feeds, margin tracking, gem identification

All built on existing infrastructure (vendor scrapers, market feeds, LLM integration). Architecture adapted from pc-flipper codebase.

---

# Core Philosophy

**Budget-first → Specs → 3D Configure → Quote → Pay → Build → Ship**

Everything else (demand tracking, playbook validation, sourcing) is **background intelligence** feeding strategic decisions.

---

# Part 1: Customer Experience (Storefront)

## 1.1 Entry Point: Budget Selection

Customer lands on FlipFlop → sees hero section promoting 3D configurator.

Clicks **"Build Your PC"** → asked: **"What's your budget?"**

Options: £800 | £1200 | £1500 | £2000 | £3000 | Custom

System then asks: **"What's it for?"** (Optional, improves recommendations)
- Gaming
- Workstation
- Content Creation
- General Purpose

## 1.2 The 3D Configurator

**Input:** Budget + use case  
**System does:** Recommends balanced spec (CPU/GPU/RAM/SSD combo)

**UI shows:**
- 3D model of recommended build (Meshy AI models from 2D product images)
- Component list (each with interactive card)
- Real-time total price (updates as they configure)
- Stock status indicator per component:
  - 🟢 **In stock** — Ships in 2 days
  - 🟡 **Sourcing** — Ships in 4-5 days
  - 🔴 **Unavailable** — Suggest alternative

When customer selects an out-of-stock component:
- Show reason (lead time / not available)
- Offer 2-3 alternatives with pricing delta
  - "RTX 4090 (10 week wait) → Try RTX 4080 instead? Saves £280, ships in 3 days"

3D model updates in real-time as they swap components.

## 1.3 Quote View (Pre-Purchase)

Customer clicks **"Get Quote"** → sees breakdown:

**Summary:**
- Estimated cost: £XXX
- Estimated delivery: X days
- Your price: £XXX (full price)
- Button: **"Confirm & Pay"**

**Detailed breakdown** (expandable):
- Component costs (base price + shipping + tax per item)
- Labor estimate (X hours @ £XX/hr)
- Overhead allocation (XX%)
- Total landed cost
- Margin (hidden from customer)

## 1.4 Payment & Order Confirmation

Customer pays full price → order created immediately.

**Confirmation email to customer:**
- Order ID
- Build specs
- Delivery timeline (e.g., "Ready to ship in 5 days")
- Build status dashboard link (tracking page)

**Internal system:**
- Order marked as "Sourcing"
- Sourcing engine triggered
- You get notification with recommended vendors + prices

---

# Part 2: Operator Experience (Admin/Sourcing)

## 2.1 Orders Dashboard

List of active orders by stage:
- Awaiting Sourcing (new orders, ready to source)
- Parts Ordered (awaiting delivery)
- Building (in progress)
- QA (testing)
- Ready to Ship
- Shipped
- Completed

Each order card shows:
- Customer name + order ID
- Specs (CPU/GPU/RAM/case)
- Total profit (customer price - cost)
- Timeline (promised delivery date)
- Current blocker (if any)

## 2.2 Sourcing Workflow

When order moves to "Awaiting Sourcing":

**System recommends:**
- Best vendor for each component (price + delivery time)
- Total parts cost
- Margin at this vendor combo
- Lead time (parts arrival date)

**You approve:**
- Accept recommendation → parts auto-ordered, or
- Override (pick different vendors) → custom order created, or
- Check inventory (if component in stock, mark as on-hand)

**Status tracking:**
- Parts ordered → awaiting delivery
- Parts arrive → mark received
- All parts arrived → move to "Building"

## 2.3 Build Tracker

Once all parts arrive:
- Create build ticket
- Photo checklist (CPU installed ✓, GPU installed ✓, RAM installed ✓, etc.)
- Time tracking (started/ended)
- Notes
- QA checklist (stress test, temps, boot time, etc.)
- Final photos (gallery for customer)
- Move to "Ready to Ship" when done

## 2.4 Shipping & Delivery

Once QA passes:
- Generate shipping label
- Send tracking email to customer
- Mark as "Shipped"
- Customer receives + leaves rating
- Mark as "Completed"

---

# Part 3: Strategic Intelligence (Playbook Validator)

## 3.1 The Validator Screen

**Purpose:** AI reviews playbooks against live demand + market data, suggests new profitable builds.

**Location:** Admin dashboard, separate section: **"Strategic Intelligence"**

### Input Data (Auto-collected):

**Demand Data** (from configurator):
- Last 30 days customer configurations
- Budget distribution (% choosing £800, £1200, £1500, £2000+)
- Use case distribution (% gaming, workstation, etc.)
- Most popular component swaps
- Bounce rate (customers who start but don't quote)

**Playbook Data:**
- Current playbooks (e.g., "RTX 4070 Gaming £1500", "Ryzen 5 Budget £800")
- Historical performance (which playbooks sell fastest, highest margin)

**Market Data:**
- Current component prices (from vendor feeds)
- Market selling prices (eBay, Amazon, Overclockers current listings)
- Used market prices (eBay sold listings for similar specs)
- Market demand (search volume, price trends)

**Catalog Data:**
- All available components (CPUs, GPUs, RAM, SSDs, PSUs, Coolers, Fans, Cases)
- Current pricing per vendor
- Stock status

### LLM Prompt:

"You are a PC flipping strategist. I'm giving you:
1. Customer demand data (what people are actually building)
2. Current playbooks (my pre-built configs)
3. Market data (what similar builds sell for)
4. Component catalog with pricing

Please:
- Validate each playbook: Is it still aligned with current demand?
- Identify any playbooks that are outdated (low demand for that spec)
- Suggest 3-5 NEW high-profit builds based on:
  - Current demand patterns
  - High margin opportunities
  - Strong resale potential
  - Fast-selling specs in the market

For each suggestion, provide:
- Spec (CPU, GPU, RAM, SSD, PSU, Cooler, Case)
- Component costs (each line item + total)
- Current market selling price (what this build sells for today)
- Used market price (resale value)
- Recommended retail price (with your target margin)
- Estimated profit per unit
- Expected sell-through speed (days to sell)
- Market demand (high/medium/low)"

### Output (Validator Results):

**Playbook Validation:**
```
✓ RTX 4070 Gaming (£1500) — Still aligned with demand
  Current demand: 35% of gaming builds
  Current margin: 18%
  Sell-through: 4 days avg
  Status: KEEP

⚠ RTX 3070 Gaming (£1000) — Demand declining
  Current demand: 8% (was 20% last month)
  Margin: 12%
  Status: DEPRECATE (recommend replacing with RTX 4060 variant)

✗ Workstation Pro (£3500) — No recent demand
  Current demand: 0% (no orders in 30 days)
  Status: RETIRE
```

**New Build Suggestions:**
```
1. RTX 4060 Budget Gaming (£899)
   Specs: Ryzen 5 5600X | RTX 4060 | 16GB DDR4 | 512GB SSD
   Component costs: £580
   Market selling price: £999 (current listings)
   Used market price: £720
   Recommended price: £899 (margin 35%)
   Est. profit: £319/unit
   Expected demand: HIGH (15+ builds/month based on search trends)
   Sell-through: 3 days avg

2. Ryzen 7 Workstation (£1799)
   Specs: Ryzen 7 5700X | RTX 4070 | 32GB DDR5 | 1TB SSD
   Component costs: £1080
   Market selling price: £1999 (current listings)
   Used market price: £1400
   Recommended price: £1799 (margin 40%)
   Est. profit: £719/unit
   Expected demand: MEDIUM (8-10 builds/month)
   Sell-through: 7 days avg

[3-5 more suggestions...]
```

## 3.2 Your Action on Validator Output

You review the suggestions and decide:

**For validated playbooks:**
- ✓ Keep it (no action)
- ⚠ Adjust specs (swap component to improve margin)
- ✗ Retire it (stop offering)

**For new suggestions:**
- ✓ Add to playbooks (make it available as preset)
- ⚠ Test it (add to inventory, see if it sells)
- ✗ Reject (margin not good enough, or market timing wrong)

When you add a new build to playbooks:
- It appears in the configurator as a "pre-built template" option
- Customers can buy as-is or customize
- Demand tracking starts immediately

---

# Part 4: Sourcing Optimization

## 4.1 Vendor Feed Integration

**Existing system** (reused):
- Vendor scrapers (Amazon, eBay, Scan, CCL, Currys, etc.)
- Market pricing feeds (eBay sold data, Amazon pricing)
- Gem identification (flagging good deals)

**New integration:**
- When order arrives, sourcing engine searches feeds for best price/lead-time combo
- Recommends vendor for each component
- You approve or override
- Parts auto-ordered or you order manually

## 4.2 Inventory Strategy

**Made-to-order primary:**
- Customer pays → you source → you build
- Float zero capital

**Speculative secondary** (funded by profits):
- Gem scoring flags bargains (good deals on high-demand components)
- You buy bargains when margin permits
- Stock high-confidence components to reduce customer lead times (RTX 4070, Ryzen 5 5600X, etc.)
- Sell from inventory when customer configures matching spec
- Use profit to reinvest in next bargain

Sourcing engine tracks:
- Current inventory (what you own, cost, age)
- Inventory velocity (how fast it turns)
- Recommend what to buy next based on demand

---

# Part 5: Data Model

## Core Entities

### Customer
- Name, email, phone, address (billing + shipping)
- Order history

### Order
- Customer (FK)
- Order ID, date, status (sourcing/building/qa/shipped/completed)
- Specs (CPU, GPU, Motherboard, RAM, SSD, PSU, Case, Cooler, Fans)
- Customer price (paid)
- Component costs (actual)
- Labor hours
- Profit calculated
- Delivery timeline (promised vs actual)
- Rating (1-5, collected post-delivery)

### Playbook (Pre-built Config Template)
- Name (e.g., "RTX 4070 Gaming")
- Specs (component list)
- Target budget
- Target customer (gaming/workstation/etc)
- Current market price (auto-updated)
- Historical demand (% of customer configurations)
- Historical margin (avg profit)
- Performance (avg days to sell)
- Status (active/deprecated/retired)

### Component Catalogue
- Component ID
- Category (CPU, GPU, Motherboard, RAM, SSD, PSU, Case, Cooler, Fans)
- Manufacturer, model, variant
- Current vendor prices (Amazon, eBay, Scan, etc — auto-updated)
- Stock status (in stock / lead time)
- Market price (what it's selling for)
- Used market price (resale)
- Demand (search volume, market trends)

### Vendor Feed
- Vendor name (Amazon, eBay, Scan, etc)
- Component SKU
- Price
- Stock status
- Lead time
- Link
- Last updated

### Inventory (Your Stock)
- Component (FK to Catalogue)
- Quantity on hand
- Purchase price
- Date acquired
- Status (available / allocated / sold)

### Demand Data
- Date
- Budget chosen
- Use case
- Components configured (spec)
- Quote generated (yes/no)
- Converted to order (yes/no)
- Time spent configuring (minutes)

---

# Part 6: Integration with Existing Systems

## What We Reuse from pc-flipper:

1. **Database structure** (Alembic migrations, SQLAlchemy ORM)
2. **Vendor scrapers** (Temu, Amazon, eBay, Scan, etc. feeds)
3. **Market pricing feeds** (eBay benchmarks, pricing history)
4. **Gem identification algorithm** (deal scoring)
5. **LLM integration** (Claude API for recommendations, analysis)
6. **UI patterns** (sidebar, cards, tables, forms)

## What We Build New:

1. **3D Configurator** (Three.js + Meshy AI models)
2. **Quote Engine** (real-time pricing, spec → price)
3. **Playbook Validator Screen** (LLM-powered strategy tool)
4. **Order Management** (from payment to delivery)
5. **Demand Tracking** (collect customer config data)
6. **Storefront** (customer-facing separate from admin)

## Architecture:

```
flipflop-api (FastAPI backend, reuses existing code)
  ├── /inventory — component catalogue (existing + adapted)
  ├── /quotes — quote engine (new)
  ├── /orders — order management (new)
  ├── /sourcing — vendor feeds + recommendations (existing + adapted)
  ├── /playbooks — playbook CRUD + validator (new)
  ├── /demand — demand tracking (new)
  └── /vendor-feeds — market pricing (existing)

flipflop-storefront (Next.js, customer-facing)
  ├── 3D Configurator (budget → specs → 3D → quote → pay)
  ├── Order tracking dashboard (customers see status)
  └── Build gallery (pre-built playbooks as presets)

flipflop-admin (Next.js, operator-facing)
  ├── Orders dashboard (sourcing → building → shipped)
  ├── Build tracker (photos, checklist, QA)
  ├── Strategic Intelligence (playbook validator results)
  ├── Inventory management (what you own)
  └── Sourcing recommendations (next parts to buy)
```

---

# Part 7: Success Criteria

A successful v1.0 launch means:

1. **Customer can order** — Budget → configure in 3D → quote → pay in < 5 minutes
2. **You can build profitably** — Quote margin visible, cost tracking accurate, actual profit matches estimate
3. **Sourcing is efficient** — Vendors found automatically, parts ordered in bulk to reduce lead time
4. **Playbooks guide strategy** — Validator tells you which builds are hot and which are dead
5. **Demand drives inventory** — You buy specs that customers actually want
6. **Cash flow is positive** — Customer pays upfront, you source on their dime, profit reinvests into speculative buys

---

# Part 8: Out of Scope (v1.0)

- Advertising engine (data collection framework in place for v1.1)
- Customer portal (order history, build customization after purchase)
- Multi-user team management (you're the operator)
- Shipping automation (label generation yes, carrier APIs later)
- Advanced analytics (KPI dashboard comes in v1.1)
- Returns/refunds (policy defined, manual process)

---

# Questions for Approval

✓ **Storefront layout:** Option C (custom priority) — approved  
✓ **3D models:** Meshy AI from 2D images — approved  
✓ **Configuration flow:** Budget-first — approved  
✓ **Inventory handling:** Transparency + alternatives — approved  
✓ **Pricing:** Live total, detailed breakdown at quote — approved  
✓ **Payment:** Full upfront — approved  
✓ **Playbook validator:** Core v1.0 feature — approved  

---

# Next Steps (If Design Approved)

1. Spec self-review (read through, check for contradictions/gaps)
2. You review spec file
3. Invoke writing-plans skill to create implementation plan
4. Begin implementation

