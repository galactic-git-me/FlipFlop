Master Product Requirements Document • Version 1.0 • 22 October 2026

Status: Proposed specification. Existing implementations, source entitlements, channel integrations and exact business rules require repository discovery and validation.

# 1. Executive intent

Build one autonomous subsystem that senses demand, maintains the product/build playbook, recommends and justifies full-build prices, executes permitted changes, and learns from results. Replace the existing admin Demand pages with an evidence-first decision cockpit. This subsystem owns the recommendations and lifecycle of the playbook, while the order, inventory, listing and checkout services remain authoritative for their respective transactions.

# 2. Goals and measurable outcomes

- Continuously identify commercially attractive UK PC configurations by budget, buyer persona and delivery option.

- Create, maintain, retire, reactivate and evolve playbook archetypes and component constraints from observed demand.

- Publish auditable full-build recommended prices and channel/delivery variants with floor, target, stretch and confidence.

- Combine external market evidence with first-party traffic, enquiries, orders, cancellations, returns and realised profit across every selling channel.

- Explain each playbook and price change, measure impact, and reverse harmful changes safely.

# 3. Scope and boundaries

IN: demand ingestion; entity resolution; opportunity discovery; playbook versioning; compatibility checks; complete-build price recommendation; experiments; guarded automation; admin redesign; alerts; provenance; backtesting. OUT: unapproved purchases, commitments to suppliers, direct marketplace scraping in breach of terms, autonomous modification of live orders, and inventing availability or competitor transactions.

# 4. Data source contract

| Source                      | Signal                                                                                                      | Integration rule                                                                                                  |
|-----------------------------|-------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| Steam Hardware Survey       | Installed base and directional changes in GPU, CPU, RAM, display resolution                                 | Reuse existing feed; monthly snapshot; geography/sample caveats                                                   |
| Google Trends               | Search demand and momentum for components/build keywords                                                    | Reuse existing feed; UK geo; relative-index caveat                                                                |
| PC Atlas                    | UK used-component completed-sale distributions                                                              | Validate permission, coverage and provenance before automated ingestion                                           |
| PCPartPicker                | Compatibility, completed-build configurations, price signals                                                | Prefer authorised interfaces; community-selection bias                                                            |
| eBay Product Research       | Historical aggregate sold-price, demand, sell-through and competitive signals                               | Check account entitlement and official export/API terms; no assumed automated access                              |
| eBay Sold Listings          | Individual completed-sale comparable PCs and parts, including sold date, condition, configuration and price | Distinct pipeline from Product Research; distinguish asking vs sold vs accepted offer; authorised collection only |
| flipflop owned website      | Build views, qualified views, configuration interactions, saves, leads, carts, conversion                   | Event schema, bot filtering, session attribution, consent                                                         |
| All external sales channels | Listings, impressions where accessible, watchers, offers, orders, returns, net revenue and time to sale     | Connector per channel; explicit missing metrics; no false equivalence                                             |
| Suppliers and sourcing      | Live landed component costs, stock, lead times, condition and delivery                                      | Timestamp quotes, supplier trust and actual purchasability                                                        |

Every record carries source_id, collection_method, observed_at, event_at, geography, currency, condition, item identity, confidence, rights status and deduplication key. A source can be visible for manual research yet blocked from automated collection until legal/technical access is approved.

# 5. Canonical entities and event model

- ComponentModel / ComponentOffer / ComponentSale: model identity, variant, condition, seller, currency, postage, fees, source and time.

- BuildArchetype / BuildRevision / BuildVariant: persona, budget, minimum specs, allowed substitutions, benchmark targets, aesthetics, delivery class, status.

- ComparableBuildSale: parsed CPU/GPU/RAM/storage/case, condition, warranty, completed price, postage, confidence, source URL and exclusions.

- MarketSignal / DemandObservation: normalized popularity, search trend, supply, transaction velocity, sample size and uncertainty.

- CustomerEvent / ChannelListing / OrderLine / Return: pseudonymous identity, channel, attribution, funnel stage, transaction state and contribution.

- PriceRecommendation / PriceEvidence / PlaybookProposal / ChangeDecision / Experiment / Outcome: immutable versioned decision chain.

Normalize manufacturer aliases and generations, avoid double-counting cross-posted sales, and maintain UK VAT, fees and returns as explicit ledger inputs. Do not merge listings and sales, or equate search interest with conversion.

# 6. Demand and opportunity engine

Daily ingest, validate and reconcile. Weekly recompute demand by price band, persona, platform, CPU/GPU pairing and delivery type. Monthly strategic review tests whether the playbook shape remains appropriate. Evaluate trends over multiple windows, separate installed-base popularity from current purchase intent, and apply sample-size and recency weighting. Surface conflicting signals rather than averaging them away.

Opportunity score: expected sell-through and contribution potential adjusted for sourcing availability, compatibility, risk, channel fit and evidence confidence. Weights are configurable, versioned and calibrated on actual flipflop outcomes, not fixed as universal truth.

# 7. Autonomous playbook lifecycle

States: DISCOVERED → CANDIDATE → VALIDATED → ACTIVE → WATCH → RETIRE_PENDING → RETIRED, with REACTIVATED where justified. Proposed edits include new archetype, spec minimum change, substitute change, target budget shift, variant/channel activation, price update and retirement. Each proposal includes before/after diff, evidence, estimated financial impact, uncertainty, affected listings and rollback.

| Action class                                                                             | Default execution                                               |
|------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| Low-risk evidence refresh / draft candidate                                              | Autonomous                                                      |
| Price adjustment inside approved floor/ceiling and change-rate guardrails                | Autonomous only after dry run and connector checks              |
| New build archetype or material spec/budget shift                                        | Approval until calibrated track record permits policy expansion |
| Retirement of live SKU, margin-floor override, supplier purchase, refund or order change | Human approval / separate authorised workflow                   |

Never auto-change a live order. Freeze changes during anomalies, stale feeds, data integrity failures, price volatility or channel connector incidents. Every automated action has policy version, idempotency key, audit log, notification and rollback mechanism.

# 8. Full-build pricing engine: mandatory core capability

For every BuildRevision × channel × delivery mode × condition, calculate an explainable price recommendation using both bottom-up economics and top-down market comparables. The engine must price complete PCs, not merely sum component resale values.

Landed build cost = component acquisition + component shipping + consumables + assembly/test labour + packaging + outbound courier + expected warranty/return allowance + attributable variable overhead. Channel proceeds = customer price less included VAT (when applicable), marketplace/payment fees, promotions and seller-funded shipping; contribution = channel proceeds less landed build cost and other transaction-variable costs. Apply consistent treatment to VAT, postage and fees without double counting. Profit calculations must specify whether amounts are ex-VAT and the applicable VAT scheme.

Produce: minimum viable price (hard floor), recommended target, stretch price, expected net proceeds, gross profit, contribution margin, ROI, expected time to sale, confidence, competitor positioning, and evidence links. A price below hard floor must never auto-publish. Price ranges must not imply statistically rigorous intervals unless calibrated.

Market comparable selection: prioritise recent UK sold complete-PC transactions with equivalent GPU/CPU performance tier, RAM, storage, condition, aesthetics, warranty and delivery; discount weak matches, bundles, defective stock and suspicious sales. Report sample count, age, dispersion and exclusions. When direct comparables are sparse, triangulate from component sales and benchmarks and explicitly downgrade confidence.

Pricing decision rule: propose a target within the commercially defensible market band, above contribution and margin floors, subject to sell-through target and sourcing feasibility. If no feasible price satisfies both demand and economics, recommend DO_NOT_BUILD or INVESTIGATE, not a fabricated profitable price. Apply distinct marketplace fees and customer-facing delivery promises for Fast Track (3 working days; £49 surcharge policy), Standard (5 working days target), and Flexible (tracked ETA, no fixed promise). Verify whether the £49 surcharge covers incremental fulfilment costs before publication.

# 9. Continuous experimentation and feedback

Track price exposure, impressions, qualified product views, add-to-cart, enquiries, offers, completed sales, realised margin, returns and time-to-sale. Segment by channel and source; control for stock availability, seasonality, ad campaigns, promotions and listing quality. Use bounded price experiments where traffic supports them; otherwise rely on cautious observational evidence. Compare expected vs realised margin and sell-through, and automatically create corrective proposals.

# 10. Admin Demand experience: complete redesign

| Page                  | Primary question and widgets                                                                                                                             |
|-----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Demand Command Centre | What changed, why, and what should we do? KPI strip, signal freshness, top 5 opportunities/risks, playbook changes, pending approvals.                   |
| Market Radar          | UK demand by GPU/CPU, RAM, budget, persona and channel; trends, sold-price bands, velocity, confidence, source disagreement.                             |
| Playbook Evolution    | Coverage heatmap of price band × persona × delivery; active/candidate/retired builds; gap analysis; before/after revision timeline.                      |
| Build Pricing Lab     | Choose archetype and channel; floor/target/stretch, contribution waterfall, sold comparable table, sensitivity, pricing justification, publish controls. |
| First-Party Demand    | Cross-channel funnel and cohort performance; product views → enquiries → sales → returns; margin and time to sale.                                       |
| Autonomy & Decisions  | Proposal queue, autonomous changes, policy/guardrail status, approvals, experiment outcomes, rollback and audit.                                         |
| Source Health         | Feed health, coverage, permissions, missingness, dedupe rate, source freshness, collection cost and reconciliation issues.                               |

Design: dark, high-density but legible operations UI, clear axis labels and legends, unsmoothed time series, side-by-side market vs flipflop metrics, visible sample sizes and last-updated times. Every insight opens a drill-down with evidence, recommended action, expected impact, confidence and decision history. No vanity-only charts.

# 11. Example insight cards and decisions

- “32GB demand strengthening”: Steam installed-base trend + own conversion lift; recommend upgrading default RAM only where contribution remains positive.

- “£700–£850 gap”: UK sold-PC velocity strong, flipflop has no active archetype; propose candidate with target spec and price.

- “RTX 3070 margin compression”: comparable sale median falls while sourcing cost holds; recommend repricing, substitution or retirement.

- “Strong views, weak sales”: separate price, listing quality, availability and shipping friction before changing the playbook.

- “eBay demand diverges from website”: preserve channel-specific price and variant recommendations instead of forcing one global price.

# 12. Functional requirements and acceptance criteria

| ID    | Requirement / acceptance                                                                                                        |
|-------|---------------------------------------------------------------------------------------------------------------------------------|
| FR-01 | Inventory existing Steam/Trends feeds and admin Demand implementation; migrate without duplicate ingestion.                     |
| FR-02 | All seven external categories above represented in source registry; each has access mode, freshness, coverage and legal status. |
| FR-03 | eBay sold-item observations and Product Research aggregates are separate typed datasets and independently auditable.            |
| FR-04 | All-channel first-party metrics ingest with channel identity and no fabricated unavailable fields.                              |
| FR-05 | Every active playbook build receives a price recommendation or explicit insufficient-evidence/block reason.                     |
| FR-06 | Each recommendation shows sold comparables, unit economics, target, floor, stretch, confidence and rationale.                   |
| FR-07 | A recommendation below policy margin floor cannot auto-publish; failed source checks halt changes.                              |
| FR-08 | Weekly review creates ranked proposals; monthly review evaluates overall playbook coverage and retirement.                      |
| FR-09 | Every applied change has before/after snapshot, actor, policy, evidence and reversible revision.                                |
| FR-10 | Admin drill-down connects each insight to source evidence, playbook change and observed outcome.                                |
| FR-11 | Channel/delivery price outputs honour fee schedules, delivery costs and customer promises.                                      |
| FR-12 | Backtest decisions on historical snapshots before enabling unattended write actions.                                            |

# 13. System architecture

Connectors → raw immutable snapshots → normalization/entity resolution → data quality and source rights gate → feature store / demand mart → demand inference + comparable retrieval → playbook optimizer + pricing engine → policy/approval gate → versioned playbook and listing adapters → outcome monitor. Use job orchestration, dead-letter queue, incremental sync, retries, idempotent writes and observability. Prefer deterministic arithmetic for financial calculations; use LLMs only for extraction, hypothesis generation and natural-language explanations, with evidence validation.

# 14. Cadence and triggers

| Frequency    | Action                                                                                             |
|--------------|----------------------------------------------------------------------------------------------------|
| Event-driven | Capture views, leads, orders, cancellations, returns and listing changes.                          |
| Daily        | Refresh authorised feeds, costs, comparable sales and pricing exception alerts.                    |
| Weekly       | Evaluate archetype coverage, score opportunities, create proposals and bounded changes.            |
| Monthly      | Strategic playbook reshape, segment mix review, score calibration and retire/reactivate decisions. |
| On anomaly   | Pause automation, alert operator and retain last-known-good recommendations.                       |

# 15. Non-functional and governance

- Reproducible pricing: same evidence snapshot + policy version yields same deterministic financial output.

- Data provenance and licence compliance, UK GDPR considerations, privacy-minimised tracking and retention policy.

- Role-based approval, audit, emergency stop, dry-run, rollback, rate limits and financial exposure caps.

- Source freshness thresholds per dataset; degrade confidence or block execution on staleness.

- Monitoring: ingestion success, entity match accuracy, pricing drift, margin violations, conversion impact and false-positive proposals.

- No public price publication until channel taxes, fees, delivery and stock have been validated.

# 16. Phased delivery and exit gates

| Phase                   | Deliverable / exit gate                                                                                                                   |
|-------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| 0\. Discovery           | Audit current repo, playbook schema, Steam/Trends feeds, Demand pages, channels and pricing rules; source access assessment.              |
| 1\. Evidence foundation | Canonical schema, eBay Sold distinct from Product Research, source registry, first-party event model, comparable matching; quality tests. |
| 2\. Pricing engine      | Deterministic cost/profit calculations, sold-PC comp engine, floor/target/stretch, explainability; golden test fixtures.                  |
| 3\. Admin redesign      | New seven-page decision cockpit with provenance and pricing lab; user acceptance.                                                         |
| 4\. Assisted evolution  | Weekly proposals, approval flow, backtests, versioned revisions and outcome monitoring.                                                   |
| 5\. Guarded autonomy    | Enable low-risk bounded actions with pause/rollback; prove no floor violations and measurable improvement.                                |

# 17. Golden test scenarios

- High Steam popularity but falling eBay completed-sale demand: no automatic demand-upgrade recommendation.

- Popular build but all viable channel prices below contribution floor: DO_NOT_BUILD.

- Strong Google Trends signal with low sample size of sold PCs: INVESTIGATE, not auto-publish.

- eBay accepted-offer price differs from original listing price: use verified realised price only.

- One cross-posted PC sold on two sources: deduplicate or explicitly flag uncertainty.

- Price recommendation differs between eBay and own site due to channel fees: both retain separate evidence and profit calculation.

- A sold-PC comparable missing CPU details: lower match confidence; do not treat as exact.

- Source stale or licensing unavailable: show missing-source status and suspend dependent autonomy.

- Stock cost rises between recommendation and publication: reprice atomically or block.

- Existing live listing retired by optimizer: require approval and protect active customer orders.

# 18. Open decisions before implementation

- Inspect actual current playbook ownership and API contracts, rather than assume a new source of truth.

- Confirm each external source’s permitted access, export formats and automation rights.

- Define canonical VAT treatment, labour costing, warranty reserve, fee tables and margin floor by channel.

- Define per-channel attribution and whether marketplace impressions/watchers are obtainable.

- Set budget-band definitions, persona taxonomy, source freshness SLAs and minimum comparable sample thresholds.

- Set autonomy policy: price-change bounds, maximum daily edits, approval roles, freeze conditions and rollback triggers.

# 19. Reference resources

https://store.steampowered.com/hwsurvey/

https://trends.google.com/trends/

https://pcatlas.co.uk/

https://uk.pcpartpicker.com/

https://www.ebay.co.uk/

https://www.ebay.co.uk/sellercentre/selling/how-to-sell/research

Source inclusion is a product requirement, not a representation that unrestricted machine access has been verified.
