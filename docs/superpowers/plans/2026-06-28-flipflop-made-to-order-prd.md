# FlipFlop Made-to-Order PRD

## Revised Vision: Order-Driven PC Build Business

**Version:** 2.0 (Made-to-Order Model)

**Status:** Strategy Document

---

# Executive Summary

FlipFlop pivots from speculative inventory trading to **made-to-order PC building**.

The business model shifts:

**Before:**
```
Buy cheap → Hope to sell → Profit (if lucky)
```

**After:**
```
Customer orders → Quote cost → Source parts → Build → Deliver → Profit (guaranteed)
```

This eliminates inventory risk, improves cash flow, and lets you scale without tying up capital in dead stock.

---

# Philosophy

## The Core Problem with Speculative Flipping

- £2000 of inventory sitting on shelves earning nothing
- Dead stock (3x RTX 3070s nobody wants) blocks cash
- Guessing what customers want = wasted buys
- Small team can't hunt deals AND manage inventory AND find buyers

## The Made-to-Order Advantage

- **Zero inventory risk** — customer commits first
- **Guaranteed sales** — build what's ordered, not hope
- **Predictable cash flow** — know money is coming
- **Lower capital needs** — scale by orders, not inventory
- **Operational simplicity** — clear workflow, no chaos

## Still Buy Smart

You're not abandoning deal-hunting. But you buy *strategically*:

- High-confidence components (popular GPUs, RAM, PSUs)
- Only when you have customer demand or reliable forecast
- To reduce lead time, not carry risk
- To capture bulk discounts when margin allows

---

# Core Design Principles

## Every Order is a Project

A customer order is not inventory management.

It's a mini-project with:
- Clear specs
- Customer budget
- Build deadline
- Profit target
- Fulfillment pipeline

---

## Margin is Transparent

Every order must show:
- Customer price
- Cost of goods (inventory + purchases)
- Labor + overhead
- Profit
- ROI

No guessing. No "I think I made money."

---

## Lead Time Wins Sales

A competitor takes 3 weeks.

You deliver in 5 days.

That's worth premium pricing.

The system tracks lead time for every component.

---

## Inventory is Tactical

Speculative buying is optional.

Strategic buying is essential.

Example:

Customer orders gaming PC, budget £1200.

You have:
- RTX 4070 (in stock)
- Ryzen 7 5700X (in stock)
- 32GB RAM (need to buy)
- SSD (need to buy)

You **only buy RAM and SSD**.

Inventory accelerates builds, not creates them.

---

# Product Modules

---

# Module 1: Order Management

**The heart of the system.**

Every customer interaction becomes an order.

## Order States

```
Quote Requested
  ↓
Quote Provided
  ↓
Quote Accepted (Order Created)
  ↓
Sourcing (buying parts)
  ↓
Parts Arrived
  ↓
Building
  ↓
Testing & QA
  ↓
Ready to Ship
  ↓
Shipped
  ↓
Delivered
  ↓
Invoice & Profit Recorded
```

## Order Fields

**Customer**
- Name
- Email
- Phone
- Address (delivery + billing)
- Previous orders (for upsell)

**Specs**
- Use Case (gaming, workstation, streaming, etc.)
- Budget
- Preferred Components (if specified)
- Special Requests (cable management, RGB, silence, etc.)

**Build**
- CPU
- GPU
- Motherboard
- RAM
- SSD/HDD
- PSU
- Case
- Cooler
- Other components
- Customizations

**Financials**
- Customer Price
- Cost of Goods (inventory + new purchases)
- Labor Cost (hours × hourly rate)
- Overhead Allocation
- Profit
- Profit Margin %
- ROI

**Timeline**
- Order Date
- Quote Date
- Delivery Date (promised)
- Delivery Date (actual)
- Days to Deliver

**Status Tracking**
- Current stage
- Next milestone
- Blockers (waiting for part, QA issue, etc.)

---

# Module 2: Quote Engine

**Converts customer requests into buildable specs and pricing.**

## Input

Customer says:
> "I need a gaming PC under £1000 for 1080p 144Hz gaming"

## Process

Engine determines:

1. **Feasible spec** for budget (RTX 4060, Ryzen 5 5600X, 16GB RAM, etc.)

2. **Check inventory:**
   - GPU: Have it? ✓ Cost: £250 (landed cost)
   - CPU: Have it? ✓ Cost: £180
   - RAM: Have it? ✗ Must buy: £70
   - SSD: Have it? ✓ Cost: £60
   - Rest: Have it? ✓ Cost: £280

3. **Calculate cost:**
   - Inventory items: £250 + £180 + £60 + £280 = £770
   - New purchases: £70
   - Labor: 3 hours × £25/hr = £75
   - Overhead (10%): £91.50
   - **Total Cost: £1,006.50**

4. **Set price and margin:**
   - Desired margin: 20%
   - Price: £1,206.50 + (£1,206.50 × 0.20) = **£1,447.80**

5. **Deliver quote:**
   - "I can build this for £1,447.80, deliver in 7 days"
   - Show breakdown (optional for transparency)
   - Show why this config (performance, value, etc.)

---

# Module 3: Sourcing Engine

**Finds the cheapest, fastest way to get missing parts.**

When quote engine identifies needed parts:

1. **Check suppliers:**
   - Amazon Prime (fast, known prices)
   - eBay (cheap, variable speed)
   - Scan.co.uk (trusted, mid-range)
   - CCL Electronics (bulk discounts)
   - Currys (stock reliable)

2. **Calculate total cost:**
   - Base price
   - Shipping
   - Tax
   - Delivery time
   - Risk (will it arrive in time?)

3. **Recommend:**
   - Best price
   - Best speed
   - Best balance (fast enough + cheap enough)

4. **Auto-buy or notify:**
   - If margin allows: auto-purchase
   - Otherwise: notify you to approve/decline

---

# Module 4: Inventory (Strategic Layer)

**Not speculative. Tactical.**

Tracks what you own that reduces lead time.

## Strategic Stock

**High-confidence items:**
- Popular GPUs (RTX 4060, 4070, etc.)
- Common CPUs (Ryzen 5 5600X, i5-13600K, etc.)
- Standard RAM (DDR5 32GB kits)
- Popular SSDs (Samsung 990 Pro, etc.)
- Good PSUs (Corsair RM 850x, etc.)

**Rationale:**
- Every build uses at least one
- 3-4 day lead time from suppliers (too slow)
- Markup sufficient to justify storage
- Low risk of obsolescence

## Stock Rules

1. **Never buy speculatively** — only when:
   - You have customer orders needing it, OR
   - Market discount is >30% AND supply is 3+ months, OR
   - Bulk discount pays for storage

2. **Track age** — components >6 months old get discounted/sold

3. **Optimal quantities:**
   - 2-3 of each high-confidence item
   - Enough to deliver 1-2 orders while supplier restocks
   - Never 5+ of anything (too much capital)

---

# Module 5: Build Tracker

**Manages active builds from order to delivery.**

## Per-Build View

- Customer name & contact
- Spec (what to build)
- Current stage (sourcing / building / testing / shipping)
- Parts checklist (✓ arrived / ✗ waiting / ⚠ delayed)
- Build photos (progress tracking)
- Test results (passes / failures)
- Cost tracking (running total)
- Timeline (promised vs actual)
- Blockers (what's holding it up)

## Dashboard

- Active builds (current count)
- Builds by stage (funnel view)
- Late builds (need attention)
- Bottlenecks (waiting for part X)
- Ready to ship (next to fulfil)

---

# Module 6: Margin Optimizer

**Ensures every order is profitable.**

Tracks:

- Customer price vs cost
- Profit per order
- Profit margin %
- Profit per hour (labor efficiency)
- ROI (profit ÷ capital invested)

Alerts:

- Orders below 15% margin
- Orders taking too long (labor creep)
- Repeat customers (offer loyalty discount, track retention)

---

# Module 7: Supplier Management

**Tracks vendors and their reliability.**

Per supplier:
- Average delivery time
- Average price
- Reliability (% on-time, % correct)
- Shipping cost
- Returns/issue rate
- Preferred for (GPUs, CPUs, etc.)

When sourcing, prefer reliable/fast vendors even if slightly more expensive.

---

# Module 8: Customer Relationship

**Repeat customers = sustainable business.**

Track:
- Customer history (previous orders)
- Preferences (RGB? Quiet? Fast?)
- Satisfaction (manual rating after delivery)
- Repeat rate
- Referrals

Use to:
- Personalize quotes
- Anticipate needs
- Upsell intelligently
- Build loyalty

---

# Module 9: Analytics Dashboard

**KPIs that matter for made-to-order:**

**Volume**
- Orders this month
- Avg order value
- Orders by use case

**Profitability**
- Avg profit per order
- Avg margin %
- Total profit (month/year)
- Profit by build type (gaming vs workstation)

**Efficiency**
- Avg build time (hours)
- Profit per hour
- Days to deliver (promised vs actual)
- On-time delivery %

**Cash Flow**
- Capital in inventory (should be low)
- Monthly revenue
- Days cash on hand

**Customer**
- Repeat customer %
- Avg rating
- Referral %
- Customer lifetime value

---

# Module 10: Pricing Intelligence

**Smart pricing for different customer segments.**

Examples:

**Budget Gaming (£800-1200)**
- Mid-range GPU (RTX 4060)
- Good CPU (Ryzen 5)
- 16GB RAM
- Target margin: 18% (volume play)

**Premium Gaming (£2000+)**
- High-end GPU (RTX 4080)
- High-end CPU (Ryzen 7 7800X3D)
- 32GB DDR5
- Target margin: 25% (less price-sensitive)

**Workstation (£3000+)**
- Pro GPU (RTX 5000)
- High core CPU
- 64GB+ RAM
- Target margin: 20% (specialist, low volume)

System recommends pricing based on customer segment.

---

# Workflow Example

## Day 1: Customer Inquiry

Customer emails:
> "Hi, I need a PC for 1440p gaming, budget around £1500. Can you build one?"

---

## System Flow

**Step 1: Create Quote Request**
- Customer details logged
- Use case: 1440p gaming
- Budget: £1500
- Timeline: ASAP

**Step 2: Quote Engine Calculates**
- Spec: RTX 4070, Ryzen 7 5800X, 32GB DDR5, 1TB SSD, 850W PSU
- Inventory check:
  - GPU (have): £320 cost
  - CPU (have): £180 cost
  - RAM (don't have): £140 to buy
  - SSD (have): £80 cost
  - PSU (have): £120 cost
  - Case + cooler (have): £100 cost
- Total cost: £940
- Labor (3.5 hrs): £87.50
- Overhead: £102
- **Total: £1,129.50**

**Step 3: Price & Profit**
- Sell price: £1,589 (40% margin)
- Profit: £459.50
- ROI: 41%
- Delivery: 7 days (RAM ships in 2 days, build 3 days, test 1 day, ship 1 day)

**Step 4: Send Quote**
Email customer:
> "Here's your 1440p gaming PC. Build cost £1,589. Delivers in 7 days. Full specs and warranty included."

---

## Day 2: Customer Accepts

**Step 1: Create Order**
- Status: Sourcing
- Payment captured (or 50% deposit)

**Step 2: Auto-Source**
- RAM auto-purchased (margin allows it)
- Confirmation: "Parts ordered, estimated arrival 3 days"

---

## Day 4: Parts Arrive

**Step 1: Inventory Updated**
- RAM logged as received
- All components available
- Status: Building

**Step 2: Build Begins**
- Photo checklist (CPU installed ✓, GPU installed ✓, etc.)
- Time tracking (started 2pm, building 3.5 hours expected)

---

## Day 5: Testing

**Step 1: Stress Test**
- GPU load test (pass)
- RAM test (pass)
- Thermals (pass)
- Boot speed (25 seconds - acceptable)

**Step 2: QA Sign-off**
- Status: Ready to Ship
- Photo gallery for customer

---

## Day 6: Ship

- Pack carefully (foam, cable management)
- Get tracking
- Email customer tracking link
- Status: Shipped

---

## Day 7: Delivered

- Customer confirms arrival
- Status: Delivered
- Profit recorded: £459.50
- Customer rating: (requested via email)

---

# MVP Roadmap (Made-to-Order)

## Version 0.1 (Foundation)

- ✅ Order management (create, track, deliver)
- ✅ Quote engine (budget → spec → price)
- ✅ Inventory (what you own, costs)
- ✅ Build tracker (stages, checklists)
- ✅ Manual sourcing (you approve each buy)

**Deliverable:** Customer can order → you quote → you build → you ship

---

## Version 0.2 (Automation)

- Automated sourcing (system recommends suppliers)
- Auto-buy for approved vendors
- Parts checklist with photos
- QA checklist
- Customer notification emails (order → building → shipped → delivered)

**Deliverable:** Less manual email back-and-forth

---

## Version 0.3 (Intelligence)

- Supplier management (track delivery times, prices, reliability)
- Pricing recommendations by segment
- Customer history & repeat order discounts
- Profit alerts (flag low-margin orders)

**Deliverable:** Smarter pricing, better supplier choices

---

## Version 0.4 (Analytics)

- KPI dashboard (orders, profit, efficiency)
- Customer satisfaction tracking
- Profitability by build type
- Lead time optimization

**Deliverable:** Data-driven decisions

---

## Version 0.5 (Strategic Inventory)

- Smart stock recommendations (buy only high-confidence items)
- Demand forecasting (if I build 5 gaming PCs a month, I need Y GPUs in stock)
- Inventory optimization (don't tie up capital)

**Deliverable:** Inventory serves orders, not vice versa

---

## Version 0.6 (Customer Portal)

- Customers can order directly (no email back-and-forth)
- Real-time build tracking
- Photo gallery as build progresses
- Customer feedback/rating

**Deliverable:** Professionalized customer experience

---

## Version 0.7+ (Future)

- Multi-location tracking (if you expand)
- Team assignment (assign builds to team members)
- Shipping integrations (automated label generation)
- Accounting integrations (export for tax)
- AI purchasing advisor ("buy GPU X now, market will go up 3 weeks")

---

# Key Differences from Original PRD

| Original PRD | Made-to-Order |
|---|---|
| Inventory-first | Order-first |
| Buy then find customer | Customer orders, then source |
| Speculative buying | Strategic buying |
| Hope to sell | Guaranteed to sell |
| Cash locked in inventory | Cash flows predictably |
| Complex (hunt deals, manage stock, find buyers) | Simple (quote, source, build, deliver) |
| Scales with capital | Scales with customers |
| Gem Score, Opportunity Engine | Quote Engine, Sourcing Engine |
| Deal Hunter needed | Strategic stock rules |

---

# Success Metrics

A successful made-to-order FlipFlop user should:

1. **Never hold dead stock**
   - Everything built is sold
   - Inventory is 95%+ turnover

2. **Predictable profit**
   - Know margin before building
   - Profit = customer price − cost
   - No surprises

3. **Cash flow positive**
   - Customer pays (or deposits) before building
   - Money in before money out
   - Working capital grows with volume, not linearly with inventory

4. **Repeatable process**
   - Quote → Source → Build → Test → Ship
   - Consistent delivery time
   - Customer satisfaction >4.5/5

5. **Scalable without capital**
   - Profit from order 1 funds part of order 2
   - Don't need £50k inventory to make £10k profit
   - Can grow to 10 builds/month without proportional capital increase

If FlipFlop can deliver these, it's evolved from a deal-hunting tool into a **business operating system for made-to-order PC builders**.

---

# Implementation Notes

## Keep from Original PRD
- Inventory module (now tactical instead of speculative)
- Cost engine (still needed for build costing)
- UI/UX patterns (inventory page, builds page)

## Remove from Original PRD
- Deal Hunter (no longer needed)
- Gem Score (no longer relevant)
- Opportunity Engine (no longer relevant)
- Voucher Optimizer (too niche)
- AI Purchasing Advisor (replaced by Quote Engine)

## Add New
- Order management (customer orders, quotes)
- Quote engine (budget → buildable spec)
- Sourcing engine (find parts, best price/speed)
- Customer management (repeat orders, satisfaction)
- Analytics dashboard (order volume, profit, efficiency)
- Supplier tracking (reliability, delivery time)

