# Populate and maintain Playbook commercial policies

**Date:** 13 October 2026  
**Status:** Scheduled catalogue-owned proposal and source-review workflow active in DEV; owner source reviews and publication remain pending

See [commercial approval proposals](commercial-engine-approval-proposals.md) for concrete proposed rules and remaining implementation gaps.

## Start with one reviewed core build

The scheduled Playbook service prepares the full segment matrix from curated/custom catalogues and current source captures. It recalculates proposal prices, delivery fit, profit and upsell candidates automatically. It does not require you to create cell drafts or type supplier or selling prices. Start in `/playbooks/commercial` and review only the evidence or publication decisions that need an operator.

Use `/api/public/curated-builds` to identify the stable cell and parent Playbook IDs, `/api/public/playbooks/{playbook_id}/curated-slots?build_id={cell_id}` for current catalogue variants, and `/api/public/cases` for the case catalogue. Not every case/configuration returned by a public catalogue is necessarily approved for the chosen curated build; preserve existing eligibility checks.

## Inputs and ownership

| Input | Source | Maintenance |
|---|---|---|
| Exact BOM mapping | Reviewed catalogue variants and case; canonical supplier SKU/ASIN/MPN/product keys | Re-review when specification, case or eligible options change; never approve a fuzzy title match as exact identity |
| Profit and cost rules | Approved Playbook service rules and shared business settings, combined with exact catalogue item/postage costs | Service recalculates every proposal; an owner reviews generated prices, profit and any changed global business rule |
| Supplier observations | Existing collectors/listing evidence: exact item, condition, price, postage/fees, stock and delivery estimate | Append current observations after scans/changes; record out-of-stock explicitly |
| Sold-market comparison | Comparable complete-PC sold observations with matching condition and a documented sample | Refresh regularly; do not use a component median, Amazon rank or asking price as a complete-PC sold price |
| Workshop timing | Reviewed build/QA/packing allowance plus paid-order deadlines and parts readiness | Review timing assumptions; use the live Workshop Calendar to plan workload |

The customer selects delivery mode; they do not choose planning records or set commercial prices. Workshop build counts never limit concurrent sales or checkout. Use the live Workshop Calendar to prioritise paid Fast Track, Standard and Flexible orders by promised delivery and parts readiness.

## 1. Review generated prices and delivery rules

Do not enter per-cell operating costs, part prices, profit floors or delivery prices. The service reads current item and supplier-postage observations from the exact selected catalogue listings, adds its Playbook cost/margin rules, and reports Fast Track, Standard and Flexible price, profit and end-to-end timing. It leaves a mode unavailable when current supplier arrival, compatibility, required evidence or the genuine Flex saving fails.

The authenticated manual commercial-draft, supplier-evidence-entry and approve-prices routes are retired for this workflow. The admin proposal action rechecks the current generated revision, source evidence, compatibility and all three delivery modes server-side before it can publish. Changing a business-wide cost rule remains a separate owner policy change; it is not a field to maintain for every cell.

## 2. Capture real evidence

Scheduled catalogue capture adds exact, timestamped supplier-page observations and exposes their stock, price, postage and arrival evidence in the Playbook review queue. A person reviews new supplier facts before they become approved `SupplierOfferEvidence`; stale or inactive listings cannot be approved as available. After approval, scheduled reconciliation can refresh changed price/availability facts for that exact source without re-approving unchanged facts.

Manual supplier-offer entry is disabled. Scheduled collectors capture source facts; review exact current listings in the admin queue and select only evidence that matches the chosen catalogue product. The service records captured facts and applies the existing shared pricing rules. Do not type or infer missing stock, prices, postage, fees or delivery days.

The legacy `workshop-capacity-evidence` endpoint may record a planning estimate, but it is optional and cannot cap a sale. Do not enter a weekly build quota as checkout capacity. The Playbook's delivery estimate uses supplier arrival and reviewed build/QA/courier allowances; the live Workshop Calendar is the operator's daily workload view, ordered by customer deadline, paid delivery priority and parts readiness.

The current implementation requires approved supplier observations no older than 24 hours. Sold-market evidence requires at least three comparable sold observations and a timestamp no older than 30 days. These are minimum code gates, not proof that a sparse or poorly matched sample is commercially reliable. Review comparability, geography, condition, specification, sample period and outliers. Missing required supplier or commercial evidence keeps the affected offer unavailable; a missing workshop-count record does not.

Sold-market median/sample/provenance currently sit inside the versioned cell policy's `market` field; supplier and workshop observations are separate records. A market refresh therefore needs a new policy version through the guarded write path today. A future ingestion adapter should reference durable sold-market observations without silently rewriting reviewed business rules.

## 3. Assess before enabling

Use authenticated `POST /api/commerce-intelligence/playbook-quotes` with parent/cell identity; capacity evidence is optional. This works while checkout is disabled. Inspect each mode's full cost stack, contribution, market gate, delivery estimate and comparison against Standard. Check the result against the intended customer budget tier as well. Do not force a Flexible saving or an uneconomic premium just to display three options.

Exercise missing/stale evidence, unavailable stock and the exact selected component/case identity. Review the policy and evidence together; the definition hash alone does not verify supplier mapping or costs.

## 4. Enable the pilot in development/staging

After review, save the next policy version with `checkout_enabled: true`, retaining the current definition hash and complete mapping. Customer comparison uses `POST /api/payments/delivery-quotes` with the exact `PlaybookBuildConfig`. Verify the comparison before checkout, total charged with provider adapters/sandbox, selected delivery mode, confirmation and webhook recovery. Production enablement remains a separate release decision.

The current customer path supports new-condition, explicitly reviewed core configurations. Selecting a different case/component or legacy upgrade requires a matching reviewed commercial configuration; it cannot reuse the core quote. General upsell/custom configuration pricing is subsequent work.

## 5. Automate the ongoing refresh

The Playbook catalogue refresh and changed-fact rebuild are scheduled in normal DEV service startup. They collect current catalogue/source observations and recalculate pending proposals without publishing. New supplier and engineering facts still wait for operator review; approval triggers a recalculation. The `/playbooks/commercial` page monitors scheduler runs and presents separate proposal, supplier, compatibility, software and workshop-planning review areas. Routine refresh and rebuild are automatic and are not operator approval actions.

The next useful implementation is a bootstrap/readiness report plus ingestion adapters:

1. Read approved catalogue/cell mappings and existing observations; generate draft policies and a per-cell list of missing business inputs, unmapped parts, stale evidence and unavailable modes. Do not invent missing values or auto-approve fuzzy mappings.
2. Bridge existing scans into append-only supplier evidence using stable identities, timestamps and out-of-stock transitions. Reuse collected data before adding paid feeds or new scrapers.
3. Bridge comparable complete-PC sold observations into reviewed market snapshots; retain sample/provenance and distinguish weak coverage from zero demand.
4. Keep the live Workshop Calendar current from paid orders, promised delivery priority and parts readiness. Use it to plan daily work; do not translate a preferred weekly workload into a sales cap.
5. Continue scheduled reconciliation and event-driven proposal invalidation, recording last success, coverage, failures and stale cells. Keep rules authoring separate from observed prices/stock. Enable automatic repricing only within reviewed bounds, and retain accepted customer contracts unchanged.

Google/search demand, Amazon bestseller history and own conversion/margin/delivery outcomes should later guide cell/upsell/promotion proposals and calibration. They do not replace exact supplier cost/stock evidence or complete-build sold-price comparisons required for a sellable quote.

## Approved pilot progress

See [automation progress and current development gates](2026-10-13-commercial-automation-progress.md), [how to find each business input](commercial-inputs-explained.md), and the [latest 15 October DEV readiness audit](../../flipflop-api/output/dev-readiness-cont-20261015-193432/README.md). It is a read-only snapshot of the current database and serving API; it did not approve facts or change publication.


The audit still finds only 19 complete hardware drafts; five lack required roles: Copernicus, Hawking, Excelsior and Cochrane lack an eligible CPU proposal, while Enterprise lacks CPU, GPU, RAM and its second storage device. No proposal has verified compatibility, all three delivery prices or readiness for approval. Hawking and Cochrane have matching Ryzen 5 5600G variants only as hidden, ineligible fixed-catalogue records without fresh source capture; integrated graphics are part of the CPU and are not a separate required GPU. Do not substitute nearby parts for authored OEM or workstation requirements.

Operator queues now contain 37 distinct hardware listings (151 proposal appearances), 21 motherboard research suggestions, 93 exact-product engineering suggestions, five software offers, and 46 listings needing photo approval (209 build-role appearances). There are zero approved supplier-offer evidence records, zero source-reviewed/customer-enabled software offers, zero public prices, and zero published upsells. The audit found one approved active case model with both registry and storefront asset URLs returning HTTP 200. It also reports three cells missing separate storage devices and three missing dual-boot products.

The completed run spent 668 seconds on Amazon bestseller capture and 331 seconds on exact product capture; total duration was 17m14s. Exact listing captures run asynchronously in batches of three; their accumulated per-listing capture time was 968 seconds and queue wait was 9,540 seconds, so concurrency is active but not reducing the number of supplier pages that withhold a selected price or seller. A failed refresh with a retained last-good capture retries daily; new/unresolved listings retry hourly. A retained capture is not fresh cost evidence.

The pilot's £0 owner labour, £10 packaging, £15 separate-insurance allowance, 3.15% + £0.20 card-fee allowance, 5% warranty reserve and 2% returns allowance are documented owner-approved development assumptions. The configured £15 outbound courier fallback remains a planning allowance; a signed collection quote was not verified, so do not present it as a confirmed carrier cost. Current delivery limits are configured as 3/5/10 working days (Fast/Standard/Flex); the intended planning bands are 3–7/7–14/14–28 days. Resolve that mismatch before making those timelines customer promises. No policy was silently changed during this pass.

### Completed DEV refresh and readiness audit — 15 October 2026, 21:14


### Current live DEV audit and scheduler check — 15 October 2026, 21:30 BST

The current [read-only all-cell audit](../../flipflop-api/output/dev-readiness-continuation-current/README.md) confirms the same 24-cell readiness counts as the 21:14 audit: 19 complete hardware proposals, five missing required roles, zero compatibility-verified, zero complete three-mode prices, zero ready for approval, and no public prices or upsells. The live API health endpoint returns `ok`; its automation endpoint confirms catalogue refresh is enabled and registered, with the next run due at 22:00 BST. The latest durable scheduled attempt remains interrupted after an API restart at 20:56 BST; the manual run at 21:00 BST succeeded. This check did not start another refresh or change approvals/publication. Re-audit after the 22:00 scheduled cycle to verify unattended execution.

### Unattended scheduled refresh completed — 15 October 2026, 22:23 BST


### Unattended scheduled refresh completed — 15 October 2026, 23:21 BST


### Admin approval queue reachability verified — 15 October 2026, 23:25 BST


### Two-page category capture verified — 15 October 2026, 23:45 BST


### Second concurrent-capture run completed — 16 October 2026, 00:03 BST


### Current external compatibility-data gate — 16 October 2026, 00:10 BST

The successful run cached `access_denied` for all 158 Amazon Catalog Items attribute lookups; no request was made on the next cycle because those failures are backed off for seven days. The configured SP-API integration reaches the endpoint, but its present app authorization cannot read the catalogue attributes required to enrich exact products. Amazon documents the **Product Listing** role for Catalog Items operations; it must be requested/approved on the SP-API developer profile, selected for the registered application, and the seller authorization must include the updated role. See [Amazon's SP-API role mapping](https://developer-docs.amazon.com/sp-api/docs/roles-in-the-selling-partner-api). Until access is granted and a subsequent exact-ASIN lookup succeeds, scraped marketplace titles and retailer fields remain incomplete, all compatibility results remain unverified, and no proposal may be approved for sale. This is an external credential/authorization gate; do not replace it with model-generated specs. A fresh capture will be confirmed by `amazon_catalogue_attributes.captured > 0` and source URLs/attributes in the engineering review queue.
