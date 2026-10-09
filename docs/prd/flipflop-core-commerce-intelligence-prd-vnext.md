# FlipFlop Core Commerce & Intelligence Platform --- PRD vNext

**Status:** Proposed architecture update\
**Purpose:** Extend the existing FlipFlop platform. Existing inventory,
catalogue, playbooks, builds, pricing, MES and customer data remain
sources of truth; this PRD evolves curated builds from fixed BOMs into a
dynamic Playbook-led service.

## 1. Product thesis

FlipFlop should not decide months in advance which exact motherboard,
GPU and SSD every customer will buy. It should know **who the customer
is, what they need, what minimum machine satisfies them, what
improvements are worthwhile, how quickly they need it, how to source it
today, and what price is commercially viable**.

Core loop:

**Requirements → Playbook → Performance Envelope → Recommendation Engine
→ Procurement Plans → Pricing/Market Gate → Delivery Options → Payment →
Procurement → Build/QA → Delivery → Upgrade lifecycle**

The customer funds made-to-order procurement after checkout, reducing
FlipFlop's inventory-capital requirement.

## 2. Product principles

1.  Requirements first, components second.
2.  Playbooks define capabilities and minimums, not rigid BOMs.
3.  No silent reduction below Playbook minimums.
4.  New, refurbished and used condition must always be explicit.
5.  Honest advice beats upselling.
6.  Priority sells speed/queue priority; Flexible trades certainty of
    timing for sourcing freedom/value.
7.  Pricing protects real contribution, not a simplistic "parts + 20%".
8.  AI may interpret/explain; deterministic services own compatibility,
    arithmetic, price, stock, payment and order state.

## 3. Playbook Service

Segments remain: - Great-value Gaming - High-performance Gaming -
Student Hybrid - Business & Office - Content Creation - AI Workstation -
Software Development - Family & Home

Budget/Mid/High tiers become starting **performance profiles**, not
fixed products.

### Inputs

Common inputs include primary/secondary use, budget/ceiling, longevity,
urgency, workloads, storage, connectivity, noise, physical constraints,
aesthetics, upgradeability, reusable hardware, condition preference and
finance preference. Each segment adds only relevant questions.

### Output: Performance Envelope

Each recommendation produces versioned hard minimums, preferred targets
and stretch targets for: - CPU performance/class/cores; - GPU
performance/VRAM/compute; - RAM capacity/generation/speed; - storage
capacity/performance/endurance; - motherboard features/expansion; - PSU
capacity/quality/efficiency; - cooling/thermal/acoustic needs; - case
compatibility/aesthetic constraints; - networking; - OS/software; -
upgradeability.

The Playbook also outputs an **explainable budget strategy**, e.g. "For
your 1440p games, more GPU delivers more useful performance than moving
to a premium CPU, so we put more of your budget into graphics."

### Anti-upsell rule

If a requested upgrade is poor value for the stated workload, show its
cost and practical benefit and recommend the better allocation. The
customer keeps final choice.

## 4. Recommendation Engine

Pipeline: 1. Normalize answers/free text. 2. Select Playbook + workload
overlays. 3. Establish hard requirements. 4. Create Performance
Envelope. 5. Generate up to three sensible performance plans. 6. Query
current procurement availability. 7. Price each fulfilment plan. 8.
Compare with live market references. 9. reject technically/commercially
invalid candidates. 10. Return explainable options.

Possible outputs: - **Save:** lowest-cost option still meeting
requirements. - **Recommended:** best balance. - **Stretch:** extra
spend only where benefit is material. - **Ready-to-Ship Match:**
existing inventory that fits. - **Upgrade Existing PC:** where retaining
hardware is materially better value.

Do not manufacture three options if only one is sensible.

## 5. Fulfilment modes

### Priority / Fast Track

**Customer target:** 3 working days for eligible made-to-order builds.\
**Supplier pool:** Amazon + Overclockers UK only.\
**Default premium:** +£49, configurable.

Show only when stock, delivery cutoffs, supplier confidence and workshop
capacity support the promise. Priority means rapid sourcing **and
build-queue priority**.

### Standard

**Customer target:** 5 working days for eligible made-to-order builds.\
**Supplier pool:** all approved retail suppliers.\
Optimise landed cost while maintaining quality and delivery confidence.

### Flexible

**Customer promise:** no false fixed delivery date. Customer sees
sourcing progress and an evolving estimated delivery range.\
**Supplier pool:** all approved sources, including retail plus eBay,
Vinted and Gumtree where integration/terms permit.

Condition policies: - `NEW_ONLY` - `NEW_OR_REFURBISHED` - `USED_ALLOWED`

Non-new parts require explicit customer consent and condition/warranty
disclosure.

Every Flexible order has a maximum sourcing window, target saving,
escalation checkpoints, substitution policy and cancellation/refund
rules. It must never become indefinite bargain hunting.

### Ready to Ship

Completed FlipFlop inventory. Target next-working-day dispatch where
cutoff/payment/courier constraints permit. Ready-to-Ship stock
participates in normal Playbook recommendations.

### Upgrade Fast Track

Upgrade/Transformation orders may buy workshop priority when intake
status, parts and capacity support it. Premium independently
configurable.

## 6. Procurement Optimiser

For each envelope, construct compliant BOMs and minimise:

`total landed cost + expected risk cost + delivery penalty`

subject to compatibility, Playbook minimums, condition policy, supplier
policy, delivery constraint, quality rules, stock confidence,
aesthetics, budget and minimum margin.

**Landed cost** includes item price, VAT treatment, supplier delivery,
marketplace fees/protection, import/customs if relevant, required
accessories and build consumables.

Maintain supplier scores for stock accuracy, successful orders,
lateness, cancellation, returns/warranty, price competitiveness and
marketplace reputation.

## 7. Dynamic Pricing Engine

### True cost

`TrueCost = LandedParts + BuildLabour + Packaging + OutboundDelivery + PaymentCost + WarrantyReserve + ReturnsReserve + ExpectedFailureCost + AllocatedOverhead + OtherVariableCosts`

Support both: - minimum £ contribution/order; - minimum contribution
margin %.

These can vary by price band, condition, product and fulfilment mode.

### Market intelligence

Use separate condition-aware datasets for new active, new sold,
refurbished active/sold and used active/sold. Include comparable
complete PCs and major-retailer pricing. Active asking prices must never
be treated as sold evidence.

Produce market low/weighted median/high, confidence, sample size,
freshness and estimated days-to-sell where possible.

### Offerability gate

A configuration is sellable only when its required margin price is
commercially credible against the market. If not: 1. seek a cheaper
compliant BOM; 2. try Flexible; 3. offer a different performance plan;
4. recommend Upgrade Existing PC; 5. mark **not commercially offerable
today**.

Never fix margin by secretly degrading the specification.

### Fulfilment pricing

-   Priority = viable rapid-source cost + required margin + configurable
    priority premium.
-   Standard = viable approved-retail cost + required margin.
-   Flexible = customer-facing committed ceiling/quote under a defined
    sourcing policy, with no uncapped post-payment increase without
    approval.
-   Ready-to-Ship = inventory cost basis + transformation cost + market
    gate + required contribution.

Every checkout creates a versioned `PriceQuoteSnapshot` with envelope,
BOM assumptions, supplier prices/timestamps, market references, cost
stack, margin, condition policy, fulfilment mode, ETA and expiry.

## 8. Gem Hunter

Gem Hunter is a **supply intelligence service**, not a side feature.

Search approved sources for undervalued complete PCs/components. Score
using: - all-in acquisition cost; - condition-specific market value; -
harvest value; - transformation/upgrades; - conservative resale; -
fees/logistics; - expected net contribution; - profit velocity; -
seller/source risk; - compatibility with current Playbook demand; -
estimated days-to-sell.

Every Gem card shows acquisition price, all-in cost, required work,
conservative resale, gross/net contribution, max-buy price, confidence,
risks and urgency.

Possible outcomes: 1. **Ready-to-Ship candidate**; 2. **approved
component-harvest candidate** where customer condition policy permits;
3. **market/demand signal**; 4. **ignore**.

Gem Hunter must respect a configurable speculative-capital budget and
must not autonomously purchase outside explicit authority.

## 9. Upgrade & Transformation Service

First-class Playbook outcome for customers whose existing PC can
economically meet their goals.

Flow: 1. capture current PC/spec/photos/system report; 2. capture
desired outcome/budget; 3. identify reusable parts; 4. diagnose
bottlenecks; 5. return **KEEP / UPGRADE / OPTIONAL / DON'T SPEND HERE /
TRANSFORM**; 6. quote Standard/Fast Track; 7. intake and physically
validate; 8. obtain approval for material discrepancies; 9.
upgrade/case-transplant/cable-manage/clean; 10. QA/benchmark; 11. return
with before/after report.

Potential work: CPU/platform, GPU, RAM, storage, PSU, cooling/noise,
networking, case transplant, ARGB, cleaning, OS refresh.

The system must be able to say **"this is not worth upgrading."**

## 10. Payments & customer finance

Implement a provider-agnostic payment abstraction supporting card/wallet
plus eligible UK instalment/BNPL/finance providers, including
Klarna-style solutions where commercially/legal/provider eligibility
permits.

FlipFlop must not imply it is the lender unless legally structured to be
one. Provider rules govern eligibility, disclosures, credit decisions
and refund mechanics.

Product/checkout UX may show provider-compliant indicative instalments.
Procurement begins only after payment reaches the configured
**safe-to-procure** state.

Refund/cancellation logic must map cleanly back through the original
provider, including Flexible orders.

## 11. Order orchestration

Core states:

`QUOTE → PAYMENT_PENDING → PAID → PROCUREMENT_PLANNING → SOURCING → PARTS_ORDERED → IN_TRANSIT → PARTS_RECEIVED → BUILD_QUEUED → BUILDING → QA/BURN_IN → READY_TO_SHIP → SHIPPED → DELIVERED → AFTERCARE`

Exception states include `CUSTOMER_APPROVAL_REQUIRED`, `SUPPLIER_DELAY`,
`SUBSTITUTION_REQUIRED`, `INTAKE_VALIDATION`, `CANCELLED`,
`REFUND_PENDING`, `RETURN/RMA`.

Flexible customer view: **Finding your parts → Parts secured → Coming to
FlipFlop → Building → Testing → Ready → On its way**, with current
ETA/range and explanations for changes.

## 12. Internal application modules

-   **Control Room:** orders, deadlines, Fast Track risk, exceptions.
-   **Playbook Studio:** version/test rules and envelopes.
-   **Recommendation Inspector:** replay decisions and explanations.
-   **Procurement Desk:** BOMs, suppliers, substitutions, landed costs.
-   **Pricing Desk:** market refs, cost stack, margin and quote
    snapshots.
-   **Gem Hunter:** opportunity feed and max-buy decisions.
-   **Build/MES:** existing QA, provisioning, benchmarks, photography,
    packaging.
-   **Upgrade Desk:** intake, bottlenecks, work orders, return
    logistics.
-   **Customer Portal:** tracking, approvals, build identity,
    benchmark/warranty data.

## 13. Core data concepts

`CustomerRequirement`, `Playbook`, `PlaybookVersion`,
`PerformanceEnvelope`, `Recommendation`, `RecommendationOption`,
`ApprovedSKU`, `SupplierOffer`, `SupplierScore`, `ProcurementPlan`,
`ConditionPolicy`, `MarketReference`, `CostStack`, `PriceQuoteSnapshot`,
`FulfilmentMode`, `Order`, `OrderEvent`, `Build`, `GemOpportunity`,
`UpgradeAssessment`, `CustomerOwnedComponent`, `Payment`,
`FinanceProviderSession`, `ApprovalRequest`.

Important decisions must be versioned and replayable.

## 14. AI boundaries

AI may interpret free text, classify listings, explain recommendations,
summarise evidence and draft communications.

Deterministic services own compatibility, arithmetic, pricing, margin
floors, payment state, stock/reservations, condition rules and order
state. AI may not invent prices, stock, benchmarks, delivery promises or
finance eligibility.

## 15. KPIs

Commercial: conversion, contribution/order, margin %,
Priority/Standard/Flexible mix, Ready-to-Ship match rate, finance take
rate, procurement saving, quote failures, sourcing failures, on-time
rate, warranty/returns cost, Gem realised-vs-forecast profit, Upgrade
contribution.

Trust: explanation engagement, anti-upsell acceptance, substitution
approval, clarity ratings, pre-sale support contacts,
promised-vs-delivered spec mismatch (target zero).

## 16. Delivery phases

**Phase 1:** dynamic Playbooks, envelopes, Recommendation Engine,
approved SKUs, explanations.\
**Phase 2:** procurement/pricing, Priority Amazon+Overclockers, Standard
retail pool, market/margin gates, quote snapshots.\
**Phase 3:** Flexible, condition policies, dynamic ETA,
eBay/Vinted/Gumtree where permitted, Gem Hunter, Ready-to-Ship
matching.\
**Phase 4:** payment abstraction, instalment/BNPL provider(s), refunds
and safe-to-procure gate.\
**Phase 5:** Upgrade & Transformation, intake, Fast Track, before/after
evidence.

## 17. Acceptance criteria

The release is acceptable when: - requirements create a versioned
envelope without fixed SKUs; - changing market stock can produce a
different compliant BOM; - Priority uses Amazon/Overclockers only and is
eligibility-gated; - Standard uses approved retailers; - Flexible can
use the broader approved universe and provides tracking/ETA rather than
a false fixed promise; - used/refurbished parts cannot enter a new-only
order; - every quote passes true-cost and minimum-contribution gates; -
market pricing can suppress an uneconomic build; - Gem Hunter calculates
all-in cost, upgrades, resale, net contribution and max-buy; -
Ready-to-Ship inventory participates in Playbook recommendations; -
payment is safe before procurement; - Upgrade Service can recommend
doing nothing; - recommendations explain why the customer's money is
allocated as it is; - material decisions can be audited/replayed.

## 18. North star

FlipFlop's core intellectual property becomes a service that answers:

> **What does this customer actually need, and what is the smartest
> honest way to deliver it today?**
