# Playbook owner review — 26 October 2026

**Purpose:** current DEV proposal and release-gate summary. This is not a publication approval.

## Update — 26 October 2026, 09:56 UTC

The supplier-review page now fetches the latest proposal revision immediately before recording a source review. If the proposal changed while the page was open, it refreshes the displayed evidence and requires a new review instead of submitting a stale revision. Missing supplier postage is costed at £0.00 and visibly labelled as a cost fallback; captured postage remains intact. Uncaptured supplier arrival uses the existing vendor estimate.

The prioritized automatic rebuild has completed. The latest audit is [`audit-live-supplier-fallback-20261026-final28`](./audit-live-supplier-fallback-20261026-final28/README.md): 24 proposals across 8 segments, 24 complete BOMs, 24 compatibility checks passed, 0 ready for approval and 0 published prices. All 87 uncaptured-postage cases carry the £0.00 assumption while remaining marked as unverified postage. The refreshed Fast Track explanation now identifies supplier arrival time exceeding the end-to-end commitment, instead of incorrectly claiming the evidence is missing. The review screen was reloaded and showed 24 builds and 46 supplier records available for review.

This update supersedes the time-sensitive supplier counts, prices and blockers in the earlier snapshot below; use the linked final27 audit for current release status. No supplier facts, licence sources, build prices or storefront products were approved or published by this update.

## Current state

- The live source refresh and post-refresh strict rebuild both completed. The refreshed DEV catalogue produced **24/24 complete hardware BOMs** across all 8 segments; all 24 pass the current compatibility gate.
- The source refresh scraped **700 Amazon bestseller rows across 8 hardware categories**, matched 384, with zero category errors. Exact supplier capture attempted 64 offers: 20 captured, 43 unresolved, and 1 retained; 14 Amazon pages showed no active seller offer and 29 did not expose one selected GBP price.
- **0/24 proposals are ready for approval**; no build has an approved or public selling price. Nothing was published.
- All 24 proposals still block on Windows licence-source review. Gamers Outlet has 2 fresh captured Windows offers, but 0 reviewed and 0 enabled. The refresh incorrectly still called the retired RoyalCDKeys discovery source, which returned HTTP 429; it did not discover Office products.
- The current proposals contain additional stale/unknown stock blockers: Titan (storage); Goddard, Odyssey, Rhode Island, Protostar, Prometheus and Galaxy (storage); Odyssey, Rhode Island, Prometheus (RAM); Enterprise (case and storage). Protostar RAM also has non-new evidence.
- The proposal BOMs have approved photos for all selected listings. Nine distinct proposed products lack FINAL 3D models; current product rules allow eligible builds to proceed with approved photos. This is not the current publication blocker.
- Only 2/24 builds have all three delivery modes priced. Standard is priced for the draft BOMs; Fast Track and Flex availability depends on verified stock/ETA and a genuine saving. No customer price is approved.

## Current price proposals

These are draft estimates only. “Captured-data recommendation” uses the owner-requested market/cost hierarchy; “Standard quote” is the separate commercial operating-cost policy. Prices can change when stale parts are replaced and supplier facts are reviewed.

| Cell | Build | Captured-data recommendation | Standard quote | Current blockers |
|---|---|---:|---:|---|
| FF-GVG-01 | Galileo | £1442.83 | £1454.87 | os: review the exact software licence source before publication |
| FF-GVG-02 | Cerritos | £2487.08 | £2575.50 | os: review the exact software licence source before publication |
| FF-GVG-03 | Voyager | £3091.19 | £3330.56 | os: review the exact software licence source before publication |
| FF-HPG-01 | Columbus | £2579.75 | £2630.35 | os: review the exact software licence source before publication |
| FF-HPG-02 | Defiant | £2901.85 | £3005.79 | os: review the exact software licence source before publication |
| FF-HPG-03 | Titan | £13341.19 | £14394.43 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: storage (listing not confirmed active; stock unknown); Standard delivery quote unavailable |
| FF-STU-01 | Copernicus | £1641.33 | £1655.64 | os: review the exact software licence source before publication |
| FF-STU-02 | Equinox | £2221.30 | £2299.80 | os: review the exact software licence source before publication |
| FF-STU-03 | Discovery | £4392.80 | £4739.59 | os: review the exact software licence source before publication |
| FF-BOF-01 | Hawking | £2050.39 | £2069.36 | os: review the exact software licence source before publication |
| FF-BOF-02 | Reliant | £1791.70 | £1858.65 | os: review the exact software licence source before publication |
| FF-BOF-03 | Excelsior | £2599.50 | £2800.06 | os: review the exact software licence source before publication |
| FF-CCR-01 | Goddard | £3506.08 | £3545.97 | os: review the exact software licence source before publication |
| FF-CCR-02 | Stargazer | £4780.76 | £4959.40 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: storage (listing not confirmed active; stock unknown); Standard delivery quote unavailable |
| FF-CCR-03 | Odyssey | £16163.34 | £17439.36 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: ram (source capture missing or stale), storage (listing not confirmed active; stock unknown); Standard delivery quote unavailable |
| FF-AIW-01 | Chaffee | £3440.42 | £3569.23 | os: review the exact software licence source before publication |
| FF-AIW-02 | Rhode Island | £7671.91 | £7958.60 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: ram (source capture missing or stale), storage (listing not confirmed active; stock unknown); Standard delivery quote unavailable |
| FF-AIW-03 | Enterprise | £35049.58 | £37811.91 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: case (listing not confirmed active; stock unavailable), storage (listing not confirmed active; stock unknown); Standard delivery quote unavailable |
| FF-SWD-01 | Sakharov | £3039.80 | £3070.04 | os: review the exact software licence source before publication |
| FF-SWD-02 | Protostar | £4506.94 | £4515.64 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: ram (source capture missing or stale; listing not confirmed active; stock unknown), storage (listing not confirmed active; stock unknown); Replace non-new supplier offers for: ram; Standard delivery quote unavailable |
| FF-SWD-03 | Prometheus | £8641.69 | £9323.91 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: ram (source capture missing or stale), storage (listing not confirmed active; stock unknown); Standard delivery quote unavailable |
| FF-FAM-01 | Cochrane | £2048.57 | £2067.50 | os: review the exact software licence source before publication |
| FF-FAM-02 | Grissom | £2487.08 | £2575.50 | os: review the exact software licence source before publication |
| FF-FAM-03 | Galaxy | £4176.87 | £4501.93 | os: review the exact software licence source before publication; Refresh exact supplier stock evidence for: storage (listing not confirmed active; stock unknown); Standard delivery quote unavailable |

## Evidence that needs action

### Supplier listings

The audit lists **27 distinct hardware supplier products** across **105 proposal appearances**. Refresh and review exact model/variant, new condition, stock, item price, postage and ETA. Continue the automatic replacement pass for out-of-stock items, but keep a build blocked when no fresh in-stock compatible alternative exists. The £0 buying-postage fallback is a cost assumption, not evidence that supplier postage is free.

### Windows software source

The two Gamers Outlet Windows product captures remain disabled pending source review. The seller page and captured price do not establish commercial resale rights. Keep the keys disabled until the exact licence channel, entitlement and resale basis are supported by acceptable documentation. The refresh should use the chosen Gamers Outlet source instead of calling RoyalCDKeys. Office Professional Plus and Office Standard are not yet captured in this catalogue.

### Build approval and customer flow

1. Refresh or replace each stale/unavailable supplier offer with an exact current new offer and rerun the proposal rebuild.
2. Resolve the Windows licence path and review the exact offers; no licence can be represented as approved from price capture alone.
3. Review supplier evidence and the exact BOMs; rebuild the owner-approved draft prices after evidence changes.
4. Verify the customer-facing build pages and exact-configuration checkout in DEV/test mode after the user approves the exact price and configuration.
5. Publish only the exact builds and prices the owner approves.

## Verification

- Durable source-refresh job `34c6c929-f185-4ae8-af92-2d91c3eb773f`: succeeded; 24 cells rebuilt; 0 ready for approval; no publication.
- Strict post-refresh rebuild command: `flipflop-api/.venv/Scripts/python.exe scripts/rebuild_simple_playbook.py --apply --require-complete --output ../docs/playbook/generated-simple` — succeeded; 24 cells, 24 priced draft recommendations, 8 segments, zero provider requests during the local rebuild, not published.
- Fresh live readiness audit: [`audit-live-servers-up-20261026-final23`](./audit-live-servers-up-20261026-final23/README.md). It reports 24/24 complete hardware proposals, 24/24 compatibility verified, 0/24 ready for approval and 0 public prices.
- All 77 active approved 3D model media checks returned HTTP 200. The saved supplier screenshots/captures are not blanket-verified or approved by this report.
- Paid checkout and customer purchase flow remain unverified because no build has an approved/public price. The isolated pytest runner remains blocked by the local PostgreSQL role’s missing `CREATE DATABASE` privilege; focused supplier-offer regression checks passed when called directly.

## Source decision still required

Current DEV data is sufficient to review draft BOMs and estimates, but **the Playbook is not ready for publication**. The remaining licence approval and supplier fact reviews require accepted evidence and an owner decision; current stale stock selections also need fresh replacements before their prices can be trusted.
