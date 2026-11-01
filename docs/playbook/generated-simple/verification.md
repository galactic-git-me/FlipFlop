# Completed Playbook verification

- 24/24 complete, priced planning builds across eight segments; 24 pending proposals saved in local DEV.
- No missing component identities or item costs; no detected conflicts in the implemented planning checks.
- All suggested prices cover at least 10% profit on recorded total cost.
- Unknown buying postage defaults to £0; selling delivery defaults to £15; known charges are preserved.
- 140 shared hardware catalogue entries; 50 distinct hardware listing identities selected across the builds.
- All 165,988 sold observations retained; no provider search quota used by catalogue rebuilding.
- Standalone regression checks, API imports/health, admin TypeScript and targeted lint passed.
- Authenticated browser at http://localhost:4312/pc-builder verified 24/24 prices, the selected workstation's four memory modules, supplier links, postage defaults and planning checks. No login action was needed: the existing session uses localhost rather than 127.0.0.1.
- Browser proof: admin-playbook.png and admin-workstation-details.png.
- No checkout payment, customer publication, production deployment or physical assembly test was performed.

Primary specification references used for exact-model facts are retained in each exported component's manufacturer_facts.source_url. Physical BIOS/QVL, cable routing, remaining unrecorded clearances and thermal/noise tests remain explicit assembly notes. Planning completion does not claim a physical build or sale approval.

## Admin timeout recovery — 24 October 2026

- Reproduced the reported Console TimeoutError on the signed-in Sourcing Dashboard. Browser diagnostics showed progress requests starting every second while earlier requests were still pending, and listing/summary timeouts.
- Bounded progress requests and prevented overlapping batches, including effect reruns. Parsed each response body within its own failure boundary so a listing-body timeout preserves a successful queue response. Failed refreshes retain loaded values; the sourcing page displays a retry notice instead of escalating a handled refresh failure to the Next.js error overlay.
- Prevented overlapping Playbook book reads as well. Local DEV read returned 24 cells in 20.4 seconds; the authenticated browser subsequently displayed 24/24 priced suggestions without the timeout overlay. Backend response time under scanning load remains variable; these changes do not claim to optimise every database query.
- Standalone checks against the actual polling functions passed response-body timeout isolation, overlap prevention and recovery after failure. Admin TypeScript and targeted ESLint passed. Existing suites were not run, in accordance with the platform test strategy.
- Browser proof: admin-sourcing-recovered.png and admin-timeout-recovery.png. No provider calls, publication or production deployment were performed by this diagnosis.

## Customer needs in the matrix — 24 October 2026

The matrix comments now describe each customer's intended tasks and priorities, in first-person language, instead of repeating the pricing method and market-advice summary. All 24 cells have distinct copy in `flipflop-admin/lib/playbook-customer-needs.ts`. These are requirements, not benchmark guarantees. Pricing evidence remains in build details; hardware definitions, their hashes and stored prices are unchanged. TypeScript, targeted lint and a deterministic check covering all 24 cell IDs passed.

Authenticated browser verification found all 24 customer-needs comments rendered and the repeated pricing-method comment absent. Proof: admin-customer-needs.png.

## Estimated profit heatmap — 24 October 2026

The matrix uses a linear GBP profit scale across all builds: red at the lowest estimated profit, amber halfway between the minimum and maximum, and green at the highest. The legend shows those amounts. Each cell uses the same profit value for its shading and displayed figure; missing or invalid profits remain unshaded, and equal profits use amber. Colours compare cash profit per build, not profit percentage or approval status. TypeScript, targeted lint and standalone scale checks passed.

Authenticated browser verification found 24 shaded cells and a legend spanning £118.95–£3,369.42 in the observed snapshot. Text and legend were visually checked. Proof: admin-profit-heatmap.png.

## Heatmap metric selector — 24 October 2026

The heatmap has three selectable metrics: estimated profit (default), recommended price and sales volume. Switching metrics updates the scale and shading locally without another API request. Price uses the displayed approved price for live builds or suggested price for drafts, excluding partial parts costs. Sales volume uses distinct sold-listing URLs from the existing matching complete-PC comparison set captured within the last 90 days; active listings and component-sales counts are excluded. Missing evidence stays unshaded and explicitly says Not recorded. These captured counts do not claim total market sales. TypeScript, targeted lint and standalone checks of metric values, deduplication, live/draft selection and missing/zero values passed.

Browser verification exercised all three controls: profit and price each shaded 24 cells and changed the legend; sales volume showed all 24 as Not recorded and unshaded because the current response contains no matching complete-PC sales. Proof: admin-heatmap-selector.png and admin-heatmap-sales-volume.png.

## Profit colour refinement — 24 October 2026

Profit now uses only green, increasing background intensity from 6% at the lowest recorded profit to 40% at the highest. The legend uses the same scale. Recommended price and sales volume retain red–amber–green. Missing values remain unshaded. This supersedes the earlier red–amber–green profit styling. TypeScript, targeted lint and standalone checks of both palettes passed.

## Component cost in each cell — 24 October 2026

Each cell now shows Component cost above its suggested/customer price and estimated profit. It uses the existing recorded parts subtotal, including recorded buying postage and the £0 default for unknown buying postage; build operating allowances are excluded. Missing subtotals display Not recorded. No price calculation was changed. TypeScript and targeted lint passed.

## Completed sourcing corrections — 24 October 2026

Titan is 64GB DDR5; Titan and Odyssey now use the Zotac RTX 5090 Solid OC with an exact live £6,989.99 InStock capture. Two cheaper Palit URLs verified HTTP404 were marked unavailable without deleting history. Final suggestions: Titan £12,836.94, Odyssey £15,406.57, Enterprise £35,973.90. Enterprise retains Threadripper PRO 7975WX, WRX90, 256GB ECC RDIMM and 48GB Ada graphics; its RAM is eight priced 32GB modules instead of four expensive 64GB modules. See expensive-build-investigation.md for before/after prices and memory-speed trade-offs.

Strict DEV rebuilds and independent artifact checks passed all 24 cells, complete costs/roles, no planning-check errors, and profit at least 10% of total cost. Standalone checks cover cross-CPK exact board matching, variant/accessory exclusions, URL recovery, known-unavailable/current-stock ranking, newer same-product quote replacement, RDIMM recognition and quantity pricing. No existing test suite or production deployment was run. The range now has 155 hardware identities; 51 are selected across the 24 builds.

The authenticated browser verified the final three prices, Titan's 64GB, the two Zotac 5090 selections, and Enterprise's eight memory modules with Threadripper retained. Proof: admin-titan-sourcing-corrected.png and admin-enterprise-threadripper-retained.png. DEV had zero live segments and 166,752 sold observations at the final check; no sold data was removed.

### Inventory health lights — 24 October 2026
Each matrix cell now shows supplier hardware availability: green when all required parts have available stock evidence within 24 hours, amber for unknown/stale evidence, red for missing or unavailable parts. Expanded details identify affected components. Uses the selected supplier, includes secondary storage, excludes software and integrated GPU slots, and does not change publication gates or pricing. This is supplier availability, not workshop inventory or guaranteed order quantities.
Verified seven standalone deterministic cases and targeted ESLint. Existing running admin rendered all 24 lights; all currently amber with partial stock confirmation. Screenshot: admin-inventory-health.png. No provider requests or existing test suites run.

### 3D model indicators — 24 October 2026
Each matrix cell shows approved hardware model count and expandable component statuses: green when all required models are ready, amber for partial readiness or generation/review in progress, red when models are absent/failed. Software is excluded; missing hardware remains incomplete. Uses existing media readiness; no generation jobs or approval changes are triggered. Verified all 24 rendered indicators (one green, 23 amber), six standalone deterministic cases and targeted ESLint. Screenshot: admin-model-health.png.

### Build status indicators — 24 October 2026
Each cell shows green Live only when published, checkout-enabled and in stock; amber Ready when complete with no publication blockers and an available positive-priced Standard delivery offer; otherwise red Not live. Hover text explains readiness/blockers. This uses existing publication checks and changes no approval/publication state. Verified all 24 rendered cells (currently Not live), six standalone status checks and targeted ESLint. Screenshot: admin-live-status.png.
