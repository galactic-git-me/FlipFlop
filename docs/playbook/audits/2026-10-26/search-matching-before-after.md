# Search-page MPN matching: before and after

**DEV applied and verified:** direct-retailer MPN-linked products 8 → 46; all-source MPN-linked products 58 → 153. These are the MPN-identifiable cohort within a frozen 50,739-listing sample, not all existing title-based catalogue links.

Same frozen captures, exact manufacturer+MPN only; no detail-page data or new network captures. After is replay until a separate apply receipt exists.

Frozen sample: 50,739 listings. 1,612 eligible listings across 959 manufacturer+MPN products.

| Metric | Before | After replay | Change |
|---|---:|---:|---:|
| products_with_cross_source_links | 58 | 155 | +97 |
| products_with_all_observed_sources_linked | 45 | 155 | +110 |
| listings_in_cross_source_groups | 206 | 547 | +341 |
| cross_source_listing_pairs | 192 | 666 | +474 |
| amazon_products_linked_to_another_source | 11 | 48 | +37 |

Direct retailer-only comparison (excludes eBay and Google Shopping):

| Metric | Before | After replay |
|---|---:|---:|
| products_with_cross_source_links | 8 | 48 |
| products_with_all_observed_sources_linked | 7 | 48 |
| listings_in_cross_source_groups | 16 | 107 |
| cross_source_listing_pairs | 8 | 70 |
| amazon_products_linked_to_another_source | 2 | 26 |

## Limits

- MPN equality and variant consistency are the measurement evidence; this is not a manual precision audit.
- Title-only fallback links are retained but not counted as new confirmed MPN links.
- Existing captured titles often omit MPNs; extension improvements need a new results-page scan to measure their additional capture gain.
- No historical CPK is redirected wholesale: only individual evidenced source listings are planned.
- 41 individual conflicts and 9 conflicting part-code groups were excluded from reassignment.

## Applied and verified in DEV

Reconciled 1,568 listing identities; skipped 44 locked or concurrently changed rows. Recomputed 1,776 current-price aggregates. Original rows, price contributions and aggregate cache were backed up before writes. No historical CPK was redirected wholesale.

| Metric | Before | Verified after | Change |
|---|---:|---:|---:|
| products_with_cross_source_links | 58 | 153 | +95 |
| products_with_all_observed_sources_linked | 45 | 151 | +106 |
| listings_in_cross_source_groups | 206 | 538 | +332 |
| cross_source_listing_pairs | 192 | 646 | +454 |
| amazon_products_linked_to_another_source | 11 | 46 | +35 |

Direct retailer sources exclude eBay and Google Shopping:

| Metric | Before | Verified after |
|---|---:|---:|
| products_with_cross_source_links | 8 | 46 |
| products_with_all_observed_sources_linked | 7 | 46 |
| listings_in_cross_source_groups | 16 | 103 |
| cross_source_listing_pairs | 8 | 68 |
| amazon_products_linked_to_another_source | 2 | 24 |

## Implementation and checks

- Manufacturer plus exact MPN is resolved first from search captures, then existing source/ASIN aliases, then conservative legacy title/specification inference.
- MPN resolution now works on the existing CPK schema without the optional registry migration.
- Vendor IDs stay source aliases. Manufacturer-code suffixes are retained; code-encoded RAM/storage facts veto conflicting quantities or variants.
- Known retailer SKU/barcode values masquerading as mpn are rejected; captured barcode fields remain incidental evidence.
- Extension reads exact Computer Orbit handles/variants from inline search-page JSON, parses data without executing scripts, and refuses ambiguous multi-variant parents. No product-detail requests were added.
- Shared supplier-offer MPN keys include the manufacturer namespace; catalogue reconciliation uses the same resolver.
- DEV extension build and TypeScript checking passed; focused offline backend/extension checks cover the new identity rules. New captures from the installed extension have not yet been verified.
- Metrics measure the fixed snapshot cohort, not all catalogue products or manually verified matching precision. Detail-page barcode audit values were not injected into this matching experiment.
- Pending proposals, sold-history keys and pre-existing scored rows were not published or bulk rewritten by this identity repair.

## Extension activation boundary

`npm run build:dev` and `npx tsc --noEmit` passed. Nine focused extension checks and 25 focused backend checks passed. The rebuilt package is `C:\Users\mclar\CODING\FlipFlopXtension\dist\dev`.

Chrome extension-management navigation was rejected by the browser security policy (the tool permits HTTP/HTTPS only and explicitly prohibits workarounds). No reload was performed. Manually reload the existing DEV extension on `chrome://extensions` after its current scan finishes. This activates the additional search-page inline metadata capture. Do not load a second copy or replace LIVE.

The measured database gain above comes from captured search evidence already in DEV; additional gain from newly captured inline metadata needs a later results-page sweep and has not been claimed.
