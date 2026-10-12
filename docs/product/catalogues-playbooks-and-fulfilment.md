# Playbooks, catalogues and fulfilment

**Status:** Current product rules  
**Last reviewed:** 2026-09-29  
**Customer-safe:** No; use the support knowledge base for customer answers

## Playbook model

Each Playbook cell is one customer/use-case row crossed with one budget tier: Budget, Mid-range, or High-end. A recommendation matches when its components meet the cell's hard requirements and its CPU/GPU capability is in an equal-or-better benchmark tier. Exact model matching is not required.

The same equal-or-better rule applies to:

- Curated-for-you candidate builds;
- Ready-to-Ship matching;
- potential flips proposed as complete builds;
- flip-derived components where those components are permitted;
- AI review of manually entered or uploaded Ready-to-Ship builds.

Every cell owns two reviewed upgrades. Regeneration first identifies valid upgrade possibilities, then selects the two most appropriate based on useful benefit, popularity, and price spread. Storefront runtime code presents those authored choices; it does not invent unreviewed upsells. The two upgrades are a total per customer-type × budget cell, not two upgrades for each component category. The source draft may contain a broader possibility list; that list is not a customer-facing offer until the selection is explicitly recorded and reviewed. Popularity and price-point inputs must be evidenced, and an upgrade with no usable evidence remains a candidate rather than being silently ranked as popular.

For CPU and GPU upgrades, the proposed model must have stored benchmark records for both the cell's `from_sku` baseline and the proposed `to_sku`. Compare gaming cells using gaming score, creator/workstation/AI cells using workstation score, and other cells using overall score; use overall score only when that use-case score is absent. Equal scores qualify. Missing scores or a lower proposed score block approval. The saved choice retains both models, scores, metric, and benchmark sources as review evidence.

Made-by-you customers declare Budget, Mid-range, or High-end in the custom studio. That choice identifies the software Playbook cell used for their recommended installation list; it is not inferred from the final component total. The declared tier travels with shared/exported builds, cart, payment metadata and order snapshot so normal payment confirmation and Stripe webhook recovery resolve the same reviewed software profile. If a cell has no separately reviewed software profile, use that customer type's reviewed default and retain the declared tier in the order record.

## Three catalogues

| Catalogue | Extension/listing tag rule | Used by | Meaning |
|---|---|---|---|
| Complete | no catalogue tag | Ready-to-Ship sourcing and AI proposals | Whole approved catalogue plus permitted complete-PC opportunities |
| Curated | `curated`; search terms may additionally target `top10bestsellers` | Curated-for-you | Narrow reviewed range for pre-designed builds; each cell publishes at most two selected upgrades in total |
| Custom | `custom`; search terms may additionally target `allbestsellers` | Made-by-you | Wider compatible range for customer-led configuration |

`curated` and `custom` are listing/catalogue tags. Phrases such as `top10bestsellers` and `allbestsellers` describe what the FlipFlopXtension search settings should attach those tags to; they are not interchangeable tag names.

## Product and sourcing rules

| Product | Customer choice | Catalogue | Flip components | Auctions, eBay and Vinted |
|---|---|---|---|---|
| Ready-to-Ship | Sold as built | Complete | Allowed | Allowed when approved and commercially viable |
| Curated-for-you | Approved choices and two selected upgrades per Playbook cell | Curated | Flexible delivery only | Flexible delivery only |
| Made-by-you | Broad compatible choices with active advice | Custom | Flexible delivery only | Flexible delivery only |

Vinted, eBay marketplace listings, and eBay auctions are excluded from rapid/standard made-to-order sourcing. They default to the slowest supplier group and may be used only for Flexible delivery after condition, seller, payment protection, and expected-arrival checks.

## Delivery evidence and defaults

Supplier delivery logic uses this precedence:

1. A listing-specific estimated delivery date or range captured by the scraper.
2. A marketplace/carrier estimate derived from structured listing evidence.
3. An administrator override for the listing or vendor.
4. Vendor default.

Amazon Prime status should be scraped when it is visible and reliable. Prime listings receive the rapid default; non-Prime Amazon listings use Amazon's configured default. All ordinary vendors default to the three-day supplier group. Vinted, eBay marketplace, and auctions default to seven days. Defaults are assumptions and must remain distinguishable from scraped evidence.

Supplier arrival groups do not equal the customer delivery promise. The latter also includes procurement, workshop capacity, build, QA, packing, and courier time.

## Customer delivery modes

| Mode | Intended customer target | Sourcing rule |
|---|---|---|
| Ready-to-Ship | Next-working-day dispatch when eligible | Completed stock only |
| Fast Track | About 3 working days for eligible made-to-order builds | Rapid supplier group plus workshop priority |
| Standard | About 5 working days for eligible made-to-order builds | Approved retail suppliers |
| Flexible | Indicative range, initially around 10 working days | Broad approved sources, including permitted marketplace/auction sources |

Display a date/range based on current evidence. Never silently turn a vendor default into a guaranteed customer delivery date. Changes in evidence update the order estimate and generate a customer-visible explanation.

## Recommendation behaviour

For Ready-to-Ship and Curated-for-you, explain the Playbook cell and workload, and where the build budget is concentrated when that evidence exists. Ready-to-Ship listings may state their saved cell assignment, but must not claim a verified performance match unless the reviewed match evidence is available; point customers to the exact specification and measured results. Curated-for-you may explain the authored use case, pre-approved core and explicitly offered customizations. For Made-by-you, continuously review the customer's choices. A dedicated GPU is optional only when the selected Playbook explicitly says it is not required; such GPUs start unselected, can be added deliberately, and remain subject to physical fit and power checks. If an Office customer adds a GPU that does not materially improve their stated use, explain the limited benefit and suggest reallocating money to RAM, CPU, storage, or savings as appropriate without changing the build. Recommendations may appear in the build flow and in Hermes, but messages must be based on persisted Playbook and build evidence.

AI may explain and rank evidence. Deterministic services own compatibility, benchmark comparisons, catalogue eligibility, price arithmetic, stock, delivery eligibility, and order state.
