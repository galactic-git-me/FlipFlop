# Playbooks, catalogues and fulfilment

**Status:** Current product rules  
**Last reviewed:** 2026-10-22
**Customer-safe:** No; use the support knowledge base for customer answers

## Playbook model

**Customer delivery choice, owner instruction 27 October 2026:** the customer selects Fast Track, Standard or Flexible pace. The Playbook retains a sourcing option for every required component under each pace and prices the complete compatible build from those choices. Fast Track and Standard require supplier arrival plus workshop and courier time to meet their promises. Flexible has no delivery deadline or promised delivery date; supplier arrival estimates remain internal planning evidence. Missing eligible component sources make that pace unavailable with the exact gap shown. This supersedes the Standard-only MVP restriction and any fixed Flexible delivery ceiling. Hardware requirements, compatibility, source freshness, condition and profit rules apply to every pace.

**Owner-approved product direction, 22 October 2026:** the target matrix is customer use case ×
capability tier. Essential, Enhanced and Advanced are common column levels; each cell explains its
benefit using a use-case-specific name and measurable workload criteria. Customer budget is a filter,
not a definition of capability. Prices follow validated configuration, landed cost, channel economics
and comparable-market evidence. See [product strategy](./product-strategy.md) and the
[draft capability matrix](../playbook/specifications/2026-10-22/matrix.md).

The operational budget matrix, upgrade price rules and declared budget-tier software mapping below
describe the current implementation. They remain in force until an explicit migration. Legacy labels
are compatibility mappings, not the new customer proposition. No cell ID, order snapshot, profit floor,
budget ceiling, publication authority or current offer is changed by this product decision.

The admin operational home is one customer-type × budget matrix. Each cell shows its base build, Standard price, estimated contribution, delivery estimate and status. Photos and finished-model approvals open on that build. Previous operational pages are retained under Advanced diagnostics rather than being the everyday workflow.

**MVP reset approved 20 October 2026:** one base configuration and one selected case per cell; Standard delivery was the initial scope. The 27 October customer-pace instruction above supersedes that restriction: all three paces are assessed, with per-component source coverage and explicit eligibility. The single base configuration and case remain; upgrades retain their existing review rules. The owner can approve product photos in one shared catalogue grid: choose a captured listing photo, select all shown, deselect unsuitable cards, and approve the selection once per case or shared hardware family. Approval is reused across the single Curated catalogue, the from-scratch builder and every segment. The source main photo is shown initially with a horizontal thumbnail gallery; local Qwen is not used to select or approve photos. Automatic model preparation uses the owner-approved single photo without another selection gate. Existing model references and GLBs are preserved when photo approvals change. Finished-model customer publication still requires its recorded quality, scale and rights evidence. Once approved product photos exist, an otherwise eligible build may publish without a 3D model; the public model resolver still returns no model until a matching FINAL case or family asset has been explicitly approved and published. Software licences are not physical 3D subjects.

Routine collection, exact source-backed specification validation, supplier-cost reconciliation, compatibility checks and bounded publication are automated after one-time operating-rule setup. The Playbook publication compatibility gate is intentionally limited to the owner-approved checks: CPU socket and motherboard, GPU interface and motherboard when a discrete GPU is selected, RAM generation and motherboard, and motherboard form factor and case. A build without a discrete GPU must have integrated graphics. Cooler clearance, PSU length and cabling, total system power, BIOS revision, memory slot count, storage mounting and other assembly details stay in the workshop checklist rather than blocking a proposal. Each scheduled proposal also receives a local LLM cross-check of its exact selected BOM and the saved source evidence. Its result is stored against that evidence; the model cannot turn a missing or contradictory fact into a verified pass. Proposals are saved before model calls run. A scheduled worker claims up to three pending compatibility reviews each minute, releases its database connection during inference, and saves each result only if the physical evidence still matches. Unavailable responses retry after fifteen minutes; abandoned claims recover after six minutes. Price, postage and software-only changes reuse unchanged physical evidence. Rules record per-cell budget ceilings, the existing tier profit floors, a fixed published-price anchor and an allowed movement (10% default, at most 25%). Approved retail source hosts are Amazon UK, Overclockers, Gamers Outlet, retained RoyalCDKeys sources and official Ubuntu releases; inclusion never waives licence, condition, stock or fit checks. Missing budgets keep the affected cell paused. Unknown or contradictory facts remain exceptional system work; no source or model approval is invented. Pausing automatic publication preserves the MVP presentation and existing valid offers.

The detailed MVP implementation and verification limits are recorded in [implementation status](./implementation-status.md).

Admin pricing guidance (25 October 2026): a missing sale-ready Standard price can display an **Estimated minimum price** using selected supplier item costs, known postage and the existing Standard operating-cost, fee/reserve and margin policy. Unknown inbound supplier postage is costed at the owner-approved **£0 fallback** and must be labelled as an assumption; it is not verified free delivery. Missing components or missing item prices produce only a **Partial parts cost**, never a complete-PC selling price. The details list gaps and assumptions. These projections do not change offers, approved selling prices, budgets or checkout eligibility. For a High-end Standard draft, use reviewed complete-PC sold P75 evidence as a market cap when the required sample exists; when it does not, use the approved full-cost margin fallback and label the missing market evidence for owner review. If an available reviewed P75 is below the full-cost price, keep that proposal blocked for repricing.

When fresh, reviewed complete-PC comparisons match the selected BOM, the app automatically queues local-only LLM market-position advice in the background. It receives actual comparison titles, URLs and prices and chooses from deterministically computed price options at or above the provisional cost floor; unsupported prices and comparison IDs are rejected. Advice is cached by its specification, costs and evidence for 24 hours; failures back off for 15 minutes. Missing or stale comparisons remain visible as evidence gaps. The advice never publishes a build or supplies missing supplier facts. No cloud-model fallback is allowed for this task.


Each Playbook cell is one customer/use-case row crossed with one budget tier: Budget, Mid-range, or High-end. A recommendation matches when its components meet the cell's hard requirements and its CPU/GPU capability is in an equal-or-better benchmark tier. Exact model matching is not required.

The same equal-or-better rule applies to:

- Curated-for-you candidate builds;
- Ready-to-Ship matching;
- potential flips proposed as complete builds;
- flip-derived components where those components are permitted;
- AI review of manually entered or uploaded Ready-to-Ship builds.

Curated builds offer automatic component upgrades from the active curated catalogue. An upgrade is eligible only when its current market median is higher than the Playbook component it replaces, the listing and catalogue variant are active, the complete selected system passes compatibility checks, and the priced build total (including case, assembly and overhead) stays within 120% of that cell's `budget_max`. The server repeats these checks when evaluating and pricing a selection; client-supplied IDs or prices do not bypass them. Missing market median, stock, compatibility or segment budget evidence means the option is not offered. Saved admin-reviewed offers may still provide customer guidance, but they are not a prerequisite for an eligible upgrade.

Stored CPU/GPU benchmark evidence can help explain an upgrade's likely benefit when available. It is advisory and is not an eligibility gate for automatic upgrades; do not claim performance gains without matching benchmark evidence.

Made-by-you customers declare Budget, Mid-range, or High-end in the custom studio. That choice identifies the software Playbook cell used for their recommended installation list; it is not inferred from the final component total. The declared tier travels with shared/exported builds, cart, payment metadata and order snapshot so normal payment confirmation and Stripe webhook recovery resolve the same reviewed software profile. If a cell has no separately reviewed software profile, use that customer type's reviewed default and retain the declared tier in the order record.

## One component catalogue

**Owner instruction, 27 October 2026:** Windows keys remain with the original Gamers Outlet supplier and its existing Home/Pro product links. Rebuilds and source reviews must preserve that choice. Fix missing capture, approval and commercial integration checks against those offers; do not substitute another Windows vendor. A vendor change requires a new explicit owner instruction. This does not waive source freshness, edition or licence-source review.

An exact captured Windows licence on an active supplier listing may be included in a draft cost estimate while its catalogue source review is pending. The estimate identifies that licence cost as provisional. The catalogue variant remains unapproved and the proposal retains a publication blocker until the licence source is reviewed; draft costing does not establish activation eligibility or resale rights.

**Approved simplification, 21 October 2026:** Curated is the only component catalogue. Curated-for-you starts with a Playbook recommendation; Made-by-you starts with an empty 3D build and chooses from the same products. There is no separate Custom catalogue, independent component membership or Custom price list. Legacy API paths/columns remain only for compatibility and historical records.

The physical range contains the ten highest-ranked eligible Amazon UK products in each of CPU, motherboard, GPU, desktop RAM, NVMe SSD, SATA SSD, PSU and CPU cooler, plus every eligible actual PC case in the captured Amazon UK Best Sellers list. The ten-product quota applies to components, not cases. Accessories, spare parts and category mismatches are excluded before counting. NVMe and SATA have independent quotas; an ambiguous M.2 description does not establish its interface. Software/licences retain their separate approved sourcing rules and do not require physical-product photo approval.

An authored Playbook requirement that the normal range does not cover may add the best-ranked matching product outside the top ten. Record the cell, requirement, role and source rank as the exception reason; this may include a specialist AI component. An exact historical hardware identity can be retained as a requirement exception, but a historical price/rank is never current availability evidence. Inclusion does not prove compatibility or authorize sales. Compound storage requirements are evaluated separately for both drives.

Refresh reconciles membership rather than accumulating it. When a product falls outside the range it leaves the current catalogue unless it has a recorded requirement exception. Retain its listing, photo approval and cached model so it can return without duplicate generation, and preserve existing paid order snapshots. Deleted products remain excluded. If a source category cannot be refreshed, preserve its last known range and require current supplier evidence before sale.

Successful scheduled Amazon captures reconcile this range and enqueue a Playbook rebuild. The existing bounded maintenance loop re-evaluates compatibility, source availability, pricing, margin, approved media and publication rules. It may update eligible enabled cells; a ranking change never waives a blocker or changes a paid order. Missing photos remain owner work in the shared approval grid.

Fresh out-of-stock evidence also queues that rebuild. Candidate selection prioritises fresh, in-stock supplier evidence and excludes non-active catalogue variants. If a build component is out of stock or no longer active in the shared catalogue, and a different active product is selected, the proposal records the old part, replacement and source evidence, then rechecks complete-build compatibility, source freshness, price, margin, media and publication limits. The live cell is paused while its own current evidence is unsafe; a replacement is published only through the existing enabled bounded policy, otherwise it remains a reviewable proposal. Paid order snapshots are not rewritten.

Extension `curated`, `custom`, `top10bestsellers` and `allbestsellers` tags may remain historical/source metadata; they no longer independently assign catalogue membership. Ready-to-Ship sourcing remains a separate complete-PC/inventory workflow, not another component selection range.

## Product and sourcing rules

| Product | Customer choice | Catalogue | Flip components | Auctions, eBay and Vinted |
|---|---|---|---|---|
| Ready-to-Ship | Sold as built | Complete | Allowed | Allowed when approved and commercially viable |
| Curated-for-you | Playbook recommendation plus eligible automatic component upgrades | Curated | Flexible delivery only | Flexible delivery only |
| Made-by-you | Empty build with compatible choices from the shared range | Curated | Flexible delivery only | Flexible delivery only |

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

Delivery modes are separately costed offers for the same selected build, with Playbook-owned segment policies. Flexible must show a real saving against the contemporaneous Standard quote before it is promoted as the bargain choice. A longer estimate alone is not a saving. Fast Track requires both profitable pricing and evidenced end-to-end feasibility. Component condition, warranty and specification cannot silently change between modes. See [commercial engine requirements](./playbook-commercial-engine.md) for pricing, autonomous maintenance and acceptance criteria.

| Mode | Intended customer target | Sourcing rule |
|---|---|---|
| Ready-to-Ship | Next-working-day dispatch when eligible | Completed stock only |
| Fast Track | About 3 working days for eligible made-to-order builds | Rapid supplier group plus workshop priority |
| Standard | About 5 working days for eligible made-to-order builds | Approved retail suppliers |
| Flexible | No promised delivery date | Broad approved sources, including permitted marketplace/auction sources |

For Fast Track and Standard, display a date/range based on current evidence. Flexible has no promised delivery date. Never silently turn a vendor default into a guaranteed customer delivery date. Changes in evidence update the order estimate and generate a customer-visible explanation.

The storefront must present Fast Track, Standard, and Flexible as meaningful choices for the same eligible Playbook build: pay more for a faster, capacity-prioritised build, or select Flexible with no promised delivery date and any verified saving. Explain the price difference, any applicable target range, and sourcing/priority trade-off together before checkout. Do not imply that paying for Fast Track can bypass unavailable stock, supplier evidence, compatibility, or workshop capacity. Hide or disable a mode when its eligibility cannot be established, and explain why. Ready-to-Ship remains a separate completed-stock offer.

## Playbook commercial ownership and market learning

The Playbook is the commercial source of truth for each customer-type × budget-tier cell. It owns the approved core build, selectable upsells, their prices, and the price/eligibility rules for Fast Track, Standard, and Flexible. The same build may have different delivery-mode prices because supplier selection, procurement risk, workshop priority, and delivery cost differ. A price is publishable only when its current cost evidence covers parts, labour, packaging, payment fees, outbound delivery, insurance where offered, returns allowance, warranty reserve, expected failures, and overhead, and meets the approved margin floor for that segment and mode. Storefronts and checkout consume a versioned Playbook offer; they do not independently invent prices or eligibility.

Promotions are evaluated against the same complete cost and margin model for the affected segment and delivery mode. The system should recommend which cells, modes, or upsells can support a promotion and its maximum safe discount; it must withhold or flag promotions that breach the floor. A recommendation is not a published promotion until it passes the configured commercial rules and the required review gate. Price, promotion, or supplier changes must retain an auditable before/after record and update affected customer-facing offers consistently.

Keep the Playbook current through a scheduled, evidence-backed review loop. Candidate signals include FlipFlop storefront searches and conversion, orders and returns, observed supplier prices/availability and sales rank, Amazon Best Sellers data where collection and use are permitted, and Google search-interest data where an approved source is available. Treat supplier sold listings as a noisy demand proxy, not confirmed market-wide demand. Normalize sources by product identity, geography, time window, freshness, and confidence; do not combine incomparable observations as if they were equivalent. Detect emerging trends as candidates for review, then map them to customer use cases and capability needs rather than adding products solely because a ranking moved.

Automated analysis may propose Playbook content, component substitutions, upsells, segment price changes, delivery-mode price changes, and promotion opportunities. Deterministic checks own compatibility, active supply, full-cost calculation, margin floors, and publication eligibility. Preserve source evidence, confidence, and rationale with each recommendation. Stale or conflicting evidence must lead to a hold or review request, not an invented current price or stock claim. Keep an audit trail of accepted and rejected recommendations so outcomes can improve future ranking; historical outcomes can inform suggestions but cannot waive commercial or customer-safety rules. Changes that alter a live offer, customer promise, or price require the configured approval before publication.

## Recommendation behaviour

For Ready-to-Ship and Curated-for-you, explain the Playbook cell and workload, and where the build budget is concentrated when that evidence exists. Ready-to-Ship listings may state their saved cell assignment, but must not claim a verified performance match unless the reviewed match evidence is available; point customers to the exact specification and measured results. Curated-for-you may explain the authored use case, pre-approved core and explicitly offered customizations. For Made-by-you, continuously review the customer's choices. A dedicated GPU is optional only when the selected Playbook explicitly says it is not required; such GPUs start unselected, can be added deliberately, and remain subject to physical fit and power checks. If an Office customer adds a GPU that does not materially improve their stated use, explain the limited benefit and suggest reallocating money to RAM, CPU, storage, or savings as appropriate without changing the build. Recommendations may appear in the build flow and in Hermes, but messages must be based on persisted Playbook and build evidence.

AI may explain and rank evidence. Deterministic services own compatibility, benchmark comparisons, catalogue eligibility, price arithmetic, stock, delivery eligibility, and order state.

## Product selection and product guides

Curated and custom builds should show a large case chooser with form-factor filters, similar-case browsing, and an auto-advancing gallery that uses an approved 3D model when available and supplier photos otherwise. Case and component names open a product guide modal; the guide presents cached, source-grounded benefits and technical details, with upgrade copy tied to the selected build's actual baseline.

Generate guides for active Curated catalogue products, cases, and approved curated upgrade offers in resumable batches. On-demand generation fills missing or stale guides. Both paths may use configured local models and explicitly free model tiers only; never fall through to a paid provider. Treat scraped vendor text as untrusted source material and omit unsupported claims.

Product guides retain source-backed facts and an explicit baseline-to-target Playbook upgrade relationship. Without recorded evidence of an improvement, copy describes an alternative and makes no performance or compatibility claim. Only public catalogue identities are accepted by the public guide endpoint.

Every two minutes, maintenance creates/refreshes source-fact guides and enriches up to four guides through local/free LLM tiers. Cached hover reads do not wait for enrichment. Failures retain usable source guides, are recorded for retry, and are moved behind unattempted work. Newly encountered baseline comparisons receive an immediate source-based guide and are cached. Copy never grants supplier, compatibility, pricing or publication approval.


### Shared hardware media (21 October 2026)

Only PC cases have individualized approval images and 3D models. Other components use one representative photo/model per established family: AMD Ryzen or Intel CPUs; NVIDIA, AMD Radeon or Intel Arc GPUs; RAM manufacturer (shared across DDR generations); NVMe/SATA storage; motherboard manufacturer; cooler type/radiator size; standard ATX PSU. Family visuals do not claim exact SKU geometry or establish compatibility. Names, specifications, sourcing and fit checks remain product-specific.

The Photos & 3D models grid shows a card for each case and each hardware family, with the number of products sharing it. Approvals propagate across family members; newly ranked members inherit the approved family photo. Generation and uploads use the same family identity, durable job state and model cache. Existing files are retained and eligible published legacy models can be reused as representative family models. Photo approval does not start paid generation or waive finished-model quality/provenance/rights gates.

Profit floor: every commercial mode must target at least 10% contribution margin on net sales after supplier landed costs, operating costs, payment fees and warranty/returns reserves. Existing stricter tier targets (12% Mid-range, 15% High-end) remain. The deterministic engine also enforces this floor for legacy policy objects; policy validation rejects lower margins. Market advice is rechecked at the model-selected price using sale-dependent costs. The matrix displays the margin and separates supplier costs from operating allowances; an estimate cannot assert fully verified actual profitability while actual operating expenditure is unverified.

ASIN-based planning reconciliation (22 October 2026): Curated hardware identities remain eligible for draft selection when their linked variant is hidden or the supplier price is not yet captured. Rejected/deleted products remain excluded. Photo/model readiness no longer removes a product from the matching pool; media remains a separate publication check. OS roles bypass physical-media checks. A fresh exact-product offer is preferred as a complete observation over ranking/search-card estimates, even if their prices differ; known newer unavailability still blocks availability. Unknown costs, stock, delivery, fit or insufficient performance evidence remain explicit blockers and cannot authorize checkout.

The requirement exception pass now preserves GPU memory minima (8GB and 16GB versions do not cover the same requirement) and distinct storage identities for separately procured drives. Socket-labelled product properties and normalized socket spelling are usable for planning, while full engineering verification still gates publication. Scheduled source refresh also performs bounded exact Amazon searches for uncovered authored requirements, retaining actual ASIN/URL provenance as a pinned range exception; it does not invent bestseller rank or supplier evidence. Search attempts back off for six hours. Search matches stay pending and require separate exact-offer cost/stock/postage captures. Sold-market collection retries unavailable direct eBay collection through the existing authenticated-browser adapter; an active listing never counts as a completed sale.

Draft ordering prefers complete exact-offer evidence over token similarity once role requirements have been applied. PSU planning enforces the authored minimum labelled wattage. Source discovery rejects CPU/motherboard bundles, bulk-unit CPUs and generic fit-for motherboard products. A title explicitly stating integrated graphics may retain a draft CPU candidate without declaring its engineering reviewed; publication compatibility checks remain mandatory.

Exact-source engineering validation runs during draft rebuilds even when automatic publication is disabled. This does not enable publication or import commercial prices: those imports retain their existing enabled live-maintenance policy. Unknown or conflicting specifications still require further source evidence.


## Publication compatibility scope - owner decision, 25 October 2026

Playbook publication and curated checkout use CPU/motherboard socket support,
GPU/motherboard expansion-interface compatibility, RAM generation and
motherboard/case form-factor support. Missing assembly measurements, installed
BIOS state, RAM clearance, cable routing and detailed power allowance remain
workshop tasks rather than publication blockers. A known incompatibility remains
blocking, including a measured oversized component. Integrated-graphics builds
must establish graphics availability. The LLM review uses the same basic
relationships with source references; it cannot invent absent facts. The strict
Made-by-you/custom fit policy is unchanged. This changes compatibility scope,
not supplier condition, software entitlement, prices or publication authority.
