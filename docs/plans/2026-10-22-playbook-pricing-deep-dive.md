# Playbook pricing and contribution analysis

Observed 22 October 2026. Read-only commercial investigation: no policy, selling price, catalogue selection or live publication was changed. Data reflects the operational-book snapshot captured during this run, not a guarantee that a supplier price remains valid.

## Decision

Do not approve the existing catalogue-wide prices. The arithmetic generally produces the configured 10%, 12% and 15% contribution margins correctly, but costs and specifications are not yet economically fit for every segment. Reducing margins alone does not solve the competitive gap. Fix procurement/selection first; use a market-supported price only when its complete cost permits at least 10% contribution.

For analysis I recommend a 10% hard floor and an initial 12% target, with higher margins only where comparable sales, service or product differentiation support them. This is a recommendation, not a policy change. Existing higher minimums remain in place.

## Evidence quality and collection

- Queried all 24 current operational cells, their cost allowances and the latest complete-PC market batch per cell. The 24 latest batches contain 3,874 candidate records in aggregate (not unique market listings), zero sold records, and zero records eligible under current complete-spec rules. Many are malformed retailer search cards with no usable price or component listings rather than complete PCs. This population cannot establish a sold median or market cap.
- Queried own manual-build realised-sale records: no positive `sale_price_actual` rows. This does not establish that no sales exist elsewhere, but this table cannot calibrate the displayed estimates to realised profit.
- Fresh direct sold searches for 5600G integrated, 7800X3D/9060XT, and 9950X/5090 builds received HTTP 403 in both eBay desktop and all-category passes. The browser fallback for 7800X3D/9060XT reached a sign-in requirement and returned no comps. This was not treated as zero market demand.
- Fresh active eBay collection returned 15, 15 and 8 records respectively. Search output includes wrong GPUs, wrong conditions and configurable base prices. It was inspected as candidate evidence, not pooled into a median.
- Public primary eBay sold detail pages and primary retailer pages supplied the bounded evidence below. Exact current matched sold samples remain insufficient to certify a sale price for every cell.

## What the displayed profit actually means

Current automatic allowances are: labour GBP 0; outbound delivery GBP 20; separate insurance GBP 15; packaging GBP 6; fixed payment fee GBP 0.20; overhead 10% of selected landed parts; payment fee 3.15% of the sale; warranty reserve 5%; returns reserve 2%. VAT rate is zero in the current policy. Supplier postage is included only when recorded; some estimates exclude unknown supplier postage. These are assumptions, not measured actual expenditure or realised take-home profit.

If L is fully known landed parts cost, the simplified current model is:

```
Fixed cost = 1.10 * L + 41.20
Contribution(P) = 0.8985 * P - Fixed cost
10% margin floor = Fixed cost / 0.7985
12% margin target = Fixed cost / 0.7785
15% margin target = Fixed cost / 0.7485
```

Each fee/reserve is rounded separately, so exact floors below use the production Decimal economics routine and penny increments, rather than just rounding the formula. Every reported 10% floor passed the >=10% check and failed it one penny below. These counterfactual floors isolate a 10% margin and do not preserve any separate higher absolute-profit target or existing higher tier minimum. They are analysis figures, not checkout quotes.

The estimate is already after the overhead allowance and reserves, but before personal tax and any unrecorded costs. Zero owner labour makes it unsuitable as a claim of fully paid owner earnings. The overhead proxy and reserves have no realised-sales calibration in the inspected records; do not simply delete them to manufacture a lower price. Replace them with measured amounts/rates when evidence is available.

Example: Cerritos GBP 2896.46 = parts GBP 2012.43 + overhead GBP 201.25 + fixed operating allowances GBP 41.20 + payment GBP 91.24 + warranty GBP 144.83 + returns GBP 57.93 + estimated contribution GBP 347.58. Its cost-only 10% floor is GBP 2823.92. Moving 12% to 10% saves about 2.5%; moving 15% to 10% saves about 6.3%. The large gap to competitors is not chiefly an excessive margin percentage.

## Current cost floor for every cell

All monetary values GBP. Current price is the Standard proposed price or admin estimate; it is not necessarily publishable. Unknown postage can make a floor provisional even with a complete selected BOM. Incomplete means no complete-price recommendation is possible.

| User type | Tier / build | Recorded parts subtotal | Current estimate | Estimated contribution | Cost-only 10% floor |
|---|---|---:|---:|---:|---:|
| Great-value Gaming | Budget / Galileo | 1026.87 | Incomplete | Unknown | Incomplete |
| Great-value Gaming | Mid-range / Cerritos | 2012.43 | 2896.46 | 347.58 | 2823.92 |
| Great-value Gaming | High-end / Voyager | 2219.30 | 3316.57 | 497.49 | 3108.88 |
| High-performance Gaming | Budget / Columbus | 2135.88 | 2993.96 | 299.40 | 2993.96 |
| High-performance Gaming | Mid-range / Defiant | 2330.84 | 3346.37 | 401.57 | 3262.56 |
| High-performance Gaming | High-end / Titan | 10804.78 | Incomplete | Unknown | Incomplete |
| Student Hybrid | Budget / Copernicus | 3223.95 | 4492.88 | 449.29 | 4492.88 |
| Student Hybrid | Mid-range / Equinox | 1837.31 | 2649.04 | 317.89 | 2582.68 |
| Student Hybrid | High-end / Discovery | 3832.32 | 5687.09 | 853.07 | 5330.96 |
| Business & Office | Budget / Hawking | 1526.61 | 2154.67 | 215.47 | 2154.67 |
| Business & Office | Mid-range / Reliant | 1645.19 | 2377.56 | 285.31 | 2317.99 |
| Business & Office | High-end / Excelsior | 3225.62 | 4795.46 | 719.32 | 4495.18 |
| Content Creation | Budget / Goddard | 3733.29 | 5194.54 | 519.46 | 5194.54 |
| Content Creation | Mid-range / Stargazer | 4777.09 | 6802.85 | 816.35 | 6632.46 |
| Content Creation | High-end / Odyssey | 12257.49 | Incomplete | Unknown | Incomplete |
| AI Workstation | Budget / Chaffee | 3878.10 | 5394.04 | 539.41 | 5394.04 |
| AI Workstation | Mid-range / Rhode Island | 11808.10 | 16737.48 | 2008.50 | 16318.26 |
| AI Workstation | High-end / Enterprise | 1265.11 | Incomplete | Unknown | Incomplete |
| Software Development | Budget / Sakharov | 3537.99 | 4925.49 | 492.55 | 4925.49 |
| Software Development | Mid-range / Protostar | 3522.98 | 5030.83 | 603.70 | 4904.83 |
| Software Development | High-end / Prometheus | 6307.47 | 9324.57 | 1398.69 | 8740.69 |
| Family & Home | Budget / Cochrane | 1524.94 | 2152.35 | 215.24 | 2152.35 |
| Family & Home | Mid-range / Grissom | 2032.43 | 2924.72 | 350.97 | 2851.47 |
| Family & Home | High-end / Galaxy | 4446.21 | 6589.26 | 988.39 | 6176.66 |

These are not ideal market prices. For example, the fact that Copernicus needs GBP 4492.88 to produce 10% on its selected costs does not mean a student PC is worth GBP 4492.88.

## Sold evidence: what can and cannot be inferred

| Primary record | Visible information | Treatment |
|---|---|---|
| [7800X3D / RTX4080 complete PC](https://www.ebay.co.uk/itm/278311327312) | Sold 28 August 2026; marked New; opened page GBP 1639.02 including GBP 39.02 buyer-protection fee, implying GBP 1600 underlying displayed item amount; postage unresolved | Historical adjacent-spec context only. Different GPU, private-seller protections and several weeks old. Not a 9060XT current matched sale. |
| [9950X3D / RTX5090 / 64GB complete PC](https://www.ebay.co.uk/itm/287147972869) | Sold 1 September 2026; marked New; business seller; GBP 6084.99 displayed; title says 4TB while item specifics expose conflicting storage fields | Historical premium-PC context only; not a clean exact current comparator and not an auditable seller-payout record. |
| [5600G / 16GB / 256GB+1TB PC](https://www.ebay.co.uk/itm/178148158600) | Sold 26 June; Used; GBP 363.59 displayed including buyer protection; Best Offer option shown; postage unclear | Excluded from pricing new builds and from a numeric sold median. |
| [7500X3D / RX9070 / 32GB PC](https://www.ebay.co.uk/itm/178304781639) | Sold 21 July; Used; GBP 1225.58 displayed; explicitly Best Offer accepted | Actual accepted amount is hidden; exclude as a known sold transaction price. |
| [9800X3D / RTX5090 complete PC](https://www.ebay.co.uk/itm/227481079543) | Sold 19 August; Used; GBP 4372.25 displayed; explicitly Best Offer accepted | Exclude as a known transaction price. |

A sold badge is evidence of a completed listing, not proof that the displayed asking figure equals the accepted offer or that payment, delivery and retention succeeded. Do not compute a market median from these heterogeneous examples or use an old single sold record as a present-day ceiling.

## Active market evidence and conditional price recommendations

See [the primary retailer evidence file](2026-10-22-retailer-pricing-evidence.md) for full product links and availability/configuration caveats. Proposed targets below are commercial hypotheses for corrected, explicitly specified builds, not validated replacement prices for today's selected BOMs.

| Corrected product proposition | Observed comparison | My provisional trial target | Maximum fully known landed parts budget at target, 10% margin, current allowances |
|---|---|---:|---:|
| Basic Office/Family: 5600G-class integrated graphics, 32GB, roughly 1TB, Windows | [New eBay 5600G/32GB/960GB](https://www.ebay.co.uk/itm/255983074208): API returned GBP 489.90 delivered; public page showed GBP 469.95 item amount with international destination, not a UK delivered total. One historic unit sold is shown, but historic realised price unknown. AWD 5600G headline GBP 469.99 with configuration unresolved. | GBP 549, conditional on matched configuration and a service proposition justifying the premium | GBP 361.07 |
| Entry gaming: 5600-class / RTX5050 / 32GB / 1TB | [Ozi 5600/5050/16GB/1TB](https://ozigaming.co.uk/shop/shadowviper-gaming-pc-amd-ryzen-5-5600-nvidia-rtx-5050-8gb-16gb-ddr4-ram-1tb-ssd/) GBP 899, with VAT/delivery not explicitly verified | GBP 999 for a costed 32GB version; 16GB-to-32GB upgrade cost must be evidenced | GBP 687.73 |
| Cerritos-like: 7800X3D / RX9060XT16 / 32GB / 2TB internal | [JS Computing Psyche](https://jscs.co.uk/product/psyche/) starts GBP 2149.99 with 32GB/1TB and six-year warranty; delivered/OS configuration unresolved | GBP 2299 only after a matched 2TB quote and warranty/service comparison; indicative, not a sold median | GBP 1631.41 |
| Premium 9950X / RTX5090 workstation with justified RAM/storage upgrades | [Workstation Specialists 64GB/2TB/Ubuntu](https://www.workstationspecialist.com/product/ws-ar-x8700-amd-ryzen-preconfigured-ai-workstation-5/) estimated GBP 7077.89 including VAT; availability/transport require quote | GBP 8499 is a low-confidence scenario for a correctly costed higher-RAM/internal-storage version, not an ideal price established by current evidence | GBP 6132.05 |

The landed-parts ceilings are `(0.7985 * target - 41.20) / 1.10`, before penny-rounding safety. Use a slightly lower procurement cap in practice. At a 12% target use 0.7785 instead of 0.7985. For example, at GBP 2299 the 12% parts ceiling is GBP 1589.61.

None of these targets is a licence to reprice the current selected BOM below its floor. At GBP 2299, today's Cerritos costs would lose approximately GBP 189.23 after the current allowances, before any missing costs. The recorded parts total must fall from GBP 2012.43 to about GBP 1631 or less to make a 10% margin at that target. Hawking currently has GBP 1526.61 of parts because it is no longer the basic authored 5600G proposition; changing its label/price to GBP 549 would not make it viable. Rhode Island's current GBP 11808.10 parts total also cannot support the GBP 8499 scenario.

For other cells there is not enough exact matched sold/active evidence to responsibly nominate a final ideal price. The all-cell table supplies a reproducible floor and identifies the gap; a complete price list without that evidence would be invented precision.

## Why selected costs are commercially wrong in some cells

1. **Overspecified RAM and capacity matching.** Copernicus's authored 32GB LPDDR5X compact system becomes desktop DDR5 128GB at GBP 2199. Budget Software Development also gets 128GB despite an authored 64GB requirement. Selection checks a minimum capacity, then freshness/ETA/rank ahead of cost. Architecture and exact memory family are not consistently preserved.
2. **Storage substitution.** Several internal NVMe requirements select an 8TB external USB SSD at GBP 819.99. Generic role plausibility and capacity are insufficient. This is a specification error independent of whether GBP 819.99 is a valid price for that external product.
3. **Workload-inappropriate GPU substitution.** AI Mid-range's authored professional AMD GPU becomes an RTX5090 at GBP 7499. A generic benchmark improvement does not prove professional capabilities, software compatibility or business value are equivalent.
4. **Genuinely expensive retail supply.** [Opened OcUK RTX5090 pages](https://www.overclockers.co.uk/pc-components/graphics-cards/nvidia-graphics-cards/nvidia-geforce-rtx-5090-graphics-cards?sort=price_asc) show ASUS Astral GBP 7499.99 and Zotac GBP 6989.99 inc VAT in stock. [32GB RAM category](https://www.overclockers.co.uk/pc-components/ram-computer-memory/ram-by-size/32gb-ram) shows KLEVV GBP 398.99 and TeamGroup GBP 499.99. The recorded price magnitudes are plausible; do not replace them with remembered historic prices. A small builder buying expensive retail parts may be unable to compete with a system builder's supply chain or existing stock.
5. **Unvalidated market collection.** Thousands of unpriced search cards or wrong products are not useful comparisons. Current market selection is too sparse/malformed to constrain the cost-plus proposals. Repair title/model/capacity extraction and capture the selected configuration on detail pages.
6. **Incomplete totals.** Galileo, Titan, Odyssey and Enterprise do not have complete costs; their partial subtotals must stay outside tier-price ordering and ideal-price comparisons.

## Channel economics and margin discipline

The 3.15% + GBP 0.20 allowance matches a cautious international-card headline. [Stripe's current UK pricing](https://stripe.com/gb/pricing) advertises 1.5% + GBP 0.20 for standard UK cards and 3.15% + GBP 0.20 for international cards. Account-specific pricing and method mix remain unverified. Using a lower evidenced domestic rate saves only roughly two percent of the required selling price; it does not cure an oversized BOM.

Do not reuse Stripe economics for eBay. [eBay's UK business fee schedule](https://www.ebay.co.uk/help/selling/fees-credits-invoices/store-selling-fees?id=4809) includes category-dependent final value fees, per-order charges, a 0.35% regulatory operating fee and possible promotion/international charges; listed fees exclude VAT. Exact category/account fees were not verified here. Some live parent strategies still reference eBay and legacy flipping targets, whereas the inspected automatic cost policy uses the common payment allowance. Require channel-specific cost and contribution before advertising profit on eBay.

Treat 10% as contribution after actual channel costs, risk reserves and operating allowance, not 10% markup on parts. For incomplete/stale supplier costs, confidence is provisional and no minimum-profit promise is justified. VAT remains the current configured zero rate for this analysis; a change in registration/accounting status requires a fresh model rather than comparing ex-VAT competitor headlines with VAT-inclusive costs.

## Recommended next implementation slice

- Tighten authored architecture, RAM type/form factor and internal storage/interface requirements; separate optional upsells from the cheapest adequate baseline.
- Rank economically adequate candidates within the required delivery commitment, instead of paying large premiums for an unnecessary one-day sourcing advantage.
- Repair complete-PC market collection and collect/review multiple recent sold and current active exact/adjacent configurations with explicit adjustments. Exclude hidden Best Offers, components, bundles, wrong conditions and unavailable configurable starting prices.
- Compute a price interval: lower bound from the full-cost >=10% floor; upper/target from credible recent matched sold evidence and available competitors. If there is no overlap, re-source/redesign or withhold the cell.
- Validate Budget < Mid-range < High-end for comparable complete delivered totals, and require a meaningful specification/value improvement. Flag inversions rather than inflating a higher tier to conceal bad selection.
- Show estimated contribution and margin together with the cost assumptions and missing costs; reserve 'realised profit' for completed-sale reconciliation.

## Validation and limits

The exact production Decimal fee/reserve arithmetic verified all 20 complete-cost 10% floor calculations, including the one-penny-below boundary. Four cells remain incomplete. No tests of purchasing, checkout, live repricing or publication were run because no such changes were made. No final price can be certified across all 24 cells while component assignments, supplier postage and matched sold evidence remain unresolved. Recommendations above are conditional and intentionally leave prices unchanged.

Source snapshots for this audit were saved under `flipflop-api/tmp/pricing-deep-dive.json`, `pricing-deep-dive-calculations.json`, `fresh-pc-market-probes.json` and `browser-sold-probe.json`. These contain public product/market observations and cost-policy data, not credentials. Related: [tier investigation](2026-10-22-playbook-tier-pricing-investigation.md).
