# Commercial engine: proposals for approval

**Prepared:** 13 October 2026  
**Decision status:** User approved the operating model and development/staging pilot on 13 October 2026. This does not enable checkout, establish missing business facts or approve production deployment.  
**Scope:** Close the commercial gaps around the implemented core-build quotes, checkout and readiness tooling. This is a decision pack; planned capabilities below are not represented as implemented.

## Recommended first approval

Approve the operating model, the provisional guardrails below, and a development/staging pilot on one fully sourced new-condition core build. Approve automatic evidence refresh and recommendation generation within these boundaries. Keep live publication, new business rules and production rollout as separate decisions. Actual supplier prices, provider charges, VAT treatment and workshop throughput must be populated from business records; approval of this document does not establish those facts.

## 1. Customer proposition and delivery policy

**Proposed copy:** “Same PC. Choose your price and pace.” Fast Track: “Pay more for priority sourcing and build turnaround.” Standard: “A balanced price and delivery estimate.” Flexible: “Get our lowest available price for this build when you can wait longer.” Show the actual total, saving versus Standard and evidence-backed working-day estimate together, before payment. Include standard outbound postage and chosen insurance in the total; do not add them again at checkout.

**Proposed planning bands:** Fast Track 3–7 working days, Standard 7–14, Flexible 14–28. These are provisional ceilings for planning, not promises to publish. Actual supplier lead time + queue + assembly/QA/packing + courier must fit the approved ceiling. The current quote engine does not delay a build artificially to create a saving; its Flexible saving must come from a genuinely cheaper eligible sourcing/cost route. Hide an unavailable mode and explain why. Fast Track must be faster and cost more than the current Standard offer; Flexible must cost less. Do not promise a guaranteed date until operations can support one.

**Approved pilot decision:** Wording and planning bands, subject to measured workshop validation. If a build has no economic Flexible route, permit only the modes it can honestly support.

## 2. Segment economics and complete pricing

Each cell owns its exact BOM, mode costs, contribution floors and comparison evidence. Suggested initial **net-revenue contribution** floors after component costs, labour, packaging, courier, insurance, payment fees, warranty/returns reserves and allocated overhead:

| Budget tier | Minimum GBP contribution | Minimum net-revenue contribution margin |
|---|---:|---:|
| Budget | £60 | 10% |
| Mid-range | £100 | 12% |
| Premium | £175 | 15% |

Use the greater resulting price floor, across every mode. These are trial hypotheses, not validated economics; map actual canonical tiers explicitly before population. Segments describe customer workload and may need different labour, support and failure assumptions even at the same tier.

**Proposed Fast Track premium:** Start assessment at the greater of £35 or 5% of the Standard gross total, in addition to any higher sourcing/operating costs. The current contract stores a fixed GBP premium; a percentage proposal must first be converted into a reviewed policy amount, not silently interpreted by the solver. **Proposed Flexible goal:** £25 or 3% below Standard, whichever is greater, only when genuine cost savings fund it and floors still pass. A smaller real saving can be offered with its exact amount; never subsidise it invisibly.

Retain the existing minimum 5% warranty reserve. Proposed initial returns allowance: 2% of gross selling price, to be calibrated from realised outcomes. Record payment rates and fixed charges from the merchant account, VAT treatment from the business's confirmed position, and courier/insurance/labour/overhead from actual costs. Do not use a tax assumption, unknown fee or unknown insurance charge as zero. Prevent double-counting reserves between quote economics and accounting allocations.

**Approved pilot decision:** Trial floors, premium and saving goals, and provisional returns allowance. Actual operating inputs remain evidence requirements. Pilot assessment may recommend higher floors or no offer when the market does not support profitable pricing.

## 3. Upsells and configuration changes

**Proposal:** Start with RAM/storage upgrades and explicitly priced preparation services already supported by the catalogue. A hardware change uses a complete replacement configuration: remove the displaced part, add the chosen part, recheck compatibility, exact source, stock, delivery and all three full-build economics. Never add a retail price difference to an accepted core quote without rechecking the entire build. Services require an approved scope, labour/licence cost, exclusions and fulfilment time. Unknown or unavailable upsells are hidden from purchase with an honest explanation where relevant.

**Approved pilot decision:** This initial upsell scope. **Implementation gap:** Core checkout currently requires the exact reviewed configuration; general upsell quote composition and accepted-contract snapshots still need implementation and tests. Until then, unsupported changes cannot reuse the core commercial quote.

## 4. Promotions

**Proposal:** Recommend promotions only for profitable cells with fresh evidence and spare workshop capacity. Rank by demand, qualified impressions, conversion opportunity, current contribution and capacity. Use supplier sold activity as a labelled demand proxy, not our own sales. Do not treat missing sales or search coverage as zero demand.

Initial pilot: at most 5% off, at most seven days, one promotion per order, no stacking. Recompute the complete discounted quote and all reserves; never cross either contribution floor, remove a real Flexible saving, or misstate the Fast Track relationship. Prefer targeting a cell or service with measurable headroom over blanket segment discounts. Any claimed previous price must have a defensible recorded history; otherwise show only the current offer and scope.

**Approved pilot decision:** Limits and recommendation-first promotion selection. **Implementation gap:** Versioned promotion rules, eligibility, budget counters, redemption/checkout verification and outcome tracking.

## 5. Supplier identity, stock and evidence population

**Proposal:** Use the readiness page at `/playbooks/commercial` to select actual catalogue components and a case, save an incomplete draft, inspect exact linked collector observations, explicitly review stock/fees/risk/confidence and import evidence. Catalogue RRP and title similarity are not procurement evidence. Catalogue-local keys keep unrelated variants separate; cross-supplier pooling requires an approved canonical SKU/ASIN/MPN mapping with condition and variation checked.

Only import original observation times and prices. A newer unavailable observation must invalidate that listing's older availability regardless of supplier casing or capture channel. If all suitable sources disappear, pause the affected purchasable option; retain the Playbook, audit history and accepted customer contracts. A substitute requires compatibility and commercial review, not an automatic title match.

**Approved pilot decision:** Exact identity and fail-closed availability rules. **Implementation gap:** Existing raw collector observations do not establish explicit stock confirmation. Extend supported collectors with source-backed stock states (`available`, `unavailable`, `unknown`) and provenance before automatic positive-stock ingestion. The current reviewed importer is the bootstrap bridge, not an autonomous collector.

## 6. Sold-market, search, bestsellers and trends

**Proposal:** Keep two separate evidence flows. Procurement/fulfilment evidence determines whether we can sell the exact build at its quoted price. Demand evidence recommends which Playbooks, options, content and promotions deserve attention.

For complete-PC market comparisons, require documented comparable specification/condition/geography, realised sold price, observation time and source. Retain the current minimum three samples/30-day freshness as hard minimums; target ten comparable observations per cell, with three to nine labelled low confidence and reviewed manually. Component medians and Amazon bestseller ranks cannot replace a complete-PC sold price. A source must actually expose dependable sold data; no invented sales estimates.

Store Google/search signals by query, geography, period, source and capture time; Amazon rank/category movements as ordinal rank histories; vendor sold counts as proxies; our impressions, selections, abandoned checkout, orders, returns, realised margin and delivery outcomes as first-party measures. Normalise within each source and record coverage; do not add raw ranks, search volumes and orders together.

**Proposed trend trigger:** Four consecutive weekly increases and a 25% increase in a comparable four-week demand measure, supported by at least two independent sources. A new product launch or sparse emerging query may trigger a labelled research proposal earlier, but never automatic BOM publication. Draft the affected cell, suggested compatible components, content angle, expected economics and supporting links for review.

**Approved pilot decision:** Source separation, confidence policy and initial trend trigger. **Implementation gap:** Connected feed coverage audit, durable normalised demand/sold snapshots, trend detection and evidence-linked proposals. Existing holdings must be inventoried before adding paid feeds. No paid subscription is authorised by this proposal.

## 7. Background automation and bounded repricing

**Proposal:** Reconcile immediately after a completed source scan and at least hourly; refresh workshop evidence daily and after a material workload change; refresh market comparisons weekly and demand/trend proposals weekly. The hourly job does not make a stale collector observation fresh. Supplier and workshop evidence retain the current 24-hour expiry; sold comparisons retain 30-day expiry. Recommend tighter expiry later for volatile sources based on measured update reliability.

Start with recommendations only. After a successful pilot and explicit approval, allow automatic changes to **unaccepted quotes** within ±3% and £25 of the last approved price, whichever bound is tighter, and only when all price floors, market limits, delivery relationships and approved rules pass. Cumulative movement is measured from the approved anchor; repeated small changes cannot bypass review. Larger moves create a proposal and can pause unsafe offers rather than retaining an uneconomic price. Accepted quotes/orders remain immutable.

Use idempotent jobs, bounded retries/backoff, per-source concurrency limits, durable run records and an admin alert after repeated failure. Report last attempt, last success, original source time, cell coverage, stale/withdrawn options and pending proposals. Use deterministic code for arithmetic, freshness and stock gates; optional LLMs may explain evidence or draft content, with no authority to invent observations or publish prices.

**Approved pilot decision:** Cadence and eventual limits; recommendation-only operation first. **Implementation gap:** Scheduler/scan hooks, stock-aware ingestion, run-health screen, automatic offer invalidation and bounded publication policy.

## 8. Workshop readiness and learning

**Proposal:** Initially record a reviewed daily assessment of outstanding work, procurement blockers, available staffing and measured assembly/QA/packing throughput. Derive available capacity after committed work; the quote engine separately subtracts live holds. No customer build-slot assignment. Use estimated end-to-end working days, not an unsupported calendar promise.

Track quoted versus actual cost, promised versus actual delivery, contribution, conversion, cancellation, return and warranty cost by cell, mode and cohort. Produce monthly calibration proposals; keep small samples labelled. Start with one controlled change at a time and explicit approval for economic policy changes. Do not train on vendor sold proxies as if they were FlipFlop conversions. Keep explainable versions and rollback for future unaccepted quotes.

**Approved pilot decision:** Manual-to-measured capacity path and monthly reviewed learning. **Implementation gap:** Workload-derived capacity, first-party event joins, realised-cost reconciliation and calibration proposal generation. Until reliable measures exist, keep owner-reviewed capacity and rules.

## Delivery order and release gates

1. Finish and validate readiness/draft/import tooling; populate one real cell in development/staging using reviewed inputs.
2. Implement explicit collector stock and exact canonical supplier mappings, scheduled reconciliation and run health. Prove stale/negative evidence withdraws an offer.
3. Add full configuration/upsell quote composition and promotion enforcement, including accepted-contract and payment recovery tests.
4. Add sold/demand evidence adapters, trend/content proposals and monthly calibration; then assess bounded automatic repricing for approval.
5. Validate the storefront entry journey, total, mode, payment sandbox, confirmation/webhook recovery and operational delivery evidence. Present the pilot results before production enablement.

A safe rollout can ship in stages, but the overall autonomous commercial-engine requirement remains partial until stages 2–4 work against real sources. Approving proposals authorises agreed implementation, not production deployment, fabricated inputs or external spending.
