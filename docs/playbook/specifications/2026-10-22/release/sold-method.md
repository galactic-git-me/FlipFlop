# eBay sold collection — 22 October 2026

Use the sibling `FlipFlopXtension` signed-in Chrome workflow. Direct server requests returned HTTP 403 and are not a substitute for this workflow.

Source implementation: `src/background/scan-orchestrator.ts`, `src/lib/search-defs.ts`, `src/content/ebay-extractor.ts`. Search parameters: `_sacat=179`, `LH_Sold=1`, `LH_Complete=1`, `LH_BIN=1`, `_sop=12`, `LH_PrefLoc=1`, and the encoded CPU/GPU/workstation query. The extension bounds collection to three pages/200 items, deduplicates listing IDs and throttles scans. Preserve those limits when running automated collection.

The 22 October research used signed-in Chrome and the same filters/selectors. These manually transcribed public card observations are research evidence, not a completed extension ingestion or verified transaction export. Listing detail, selected configuration and motherboard remain unverified. No account/session data is stored here.

## Observations

| Item | Public sold card | Displayed price | Delivery | Qualification |
|---|---|---:|---:|---|
| [267654324225](https://www.ebay.co.uk/itm/267654324225) | 9600X / RX 9060 XT / 32GB DDR5 / 1TB NVMe / WiFi / Windows; new; sold 4 September | £1,484.00 | Free | Historical (48 days); GPU VRAM and motherboard unknown; no Best Offer flag observed |
| [396841543022](https://www.ebay.co.uk/itm/396841543022) | 9600X / RTX 5060 Ti 16GB / 32GB / 2TB; new; sold 18 October | £1,229–£1,759 | Free | Exclude: configurable range, different GPU from query |
| [398242096450](https://www.ebay.co.uk/itm/398242096450) | 9600X / RX 9060 XT 16GB; used; sold 11 August | £873.70 | Unknown | Exclude: used, accepted Best Offer, historical |
| [267752254729](https://www.ebay.co.uk/itm/267752254729) | 9600X / RX 9070 XT / 32GB / 1TB; new; sold 5 September | £1,332.70 | £5.00 | Exclude from realised-price calculation: Best Offer flag; historical; different GPU |
| [327272614673](https://www.ebay.co.uk/itm/327272614673) | XUM Titan 5600G / 16GB / 256GB / Windows 11; new; sold 7 October | £427.99 | Free | Exclude from realised-price calculation: Best Offer flag |
| [256013461601](https://www.ebay.co.uk/itm/256013461601) | 5600G / 16GB / 480GB; new; sold 16 September | £479.95 | £19.95 | Historical (36 days), different storage; no Best Offer flag observed |
| [405839499692](https://www.ebay.co.uk/itm/405839499692) | 5600G / 16–32GB / 512GB–1TB / WiFi 6 / Windows 11 Pro; new; sold 13 September | £529.99–£619.99 | Free | Exclude: configurable range; historical |

The exact `R9700 workstation pc` query returned zero exact results; eBay's fewer-word matches are not R9700 sold evidence. None of the above establishes a current, exact matched-build sold median. Do not calculate one from these rows.

## Extraction correction

Current eBay `s-card` markup places delivery and Best Offer text in primary attribute rows. Existing selectors missed those terms. The development extractor now reads those rows, recognises condition after promotional text, and joins all price spans to detect ranges. The Playbook ingestion contract now carries `priceIsRange` / `price_is_range` and blocks ranges. Unknown delivery stays unknown. A displayed Best Offer amount is not the accepted amount.

Verified: three new commercial-row regression cases plus existing current-price/condition cases (13 passed), TypeScript check and development extension build. The installed LIVE extension was not updated. Backend integration tests remain unverified: the mandated isolated PostgreSQL runner cannot create its temporary database with the configured local role. Do not bypass that test guard or claim a successful end-to-end ingestion.

This correction applies to Playbook market ingestion. The general sold-comps path needs separate review before its stored rows can be treated as clean realised-price evidence.


## Resumed collection, evening of 22 October 2026

The signed-in Chrome session remained usable. A separate headed collector also completed authentication and returned 60 sold-card candidates for `Ryzen 5600G 32GB 1TB desktop PC`. This restores access, not evidence quality. The qualified export is [sold-browser-candidates-20261022-evening.json](sold-browser-candidates-20261022-evening.json); its per-row blockers prevent research candidates being mistaken for approved transaction prices. The original collector output remains in `flipflop-api/output/playbook-sold-resume-20261022T192658Z.json`.

A separately inspected [14-listing research subset](sold-research-20261022-evening.json) covers integrated baseline and gaming comparisons. Two detail pages were checked. The search card for [127940525246](https://www.ebay.co.uk/itm/127940525246) says New and sold 22 October at GBP1849 with free delivery, but its description explicitly includes used Corsair RAM and mixed new/open-box/pre-owned components. Exclude it from an all-new-build cohort. Its stated motherboard is Gigabyte B650 EAGLE AX WIFI6E, GPU ASUS Prime RX9070XT 16GB, storage Transcend 1TB Gen4 NVMe and PSU SAMA G750 GOLD. Windows activation does not establish licence provenance. The seller is private and accepts no returns.

[297475566131](https://www.ebay.co.uk/itm/297475566131) is a separate adjacent configuration: Gladiator Colosseum 9800X3D/RX9070XT/32GB/2TB, search-card sold date 21 October and displayed GBP2062.92/free delivery. Detail confirms New, business seller laptopsdirectltd and out of stock. Motherboard, full parts, warranty and historical transaction amount still require verification. A listing showing three sold units is counted once, never as three verified equal-price sales.

No exact-new-build median is justified. No Playbook definitions, prices, approvals or database rows changed. Next: capture actual card condition, all price spans, primary delivery/offer attributes and exact-match versus fewer-word section before using the legacy adapter for ingestion; retain date-window checks, then inspect complete descriptions and service terms for remaining candidates. The corrected extension workflow remains the preferred ingestion path.


## Collector and approval corrections, continuing publication loop

The shared sold parser now observes actual card condition, reads primary delivery rows, rejects hidden Best Offers and split ranges. Playbook ingestion rejects missing, future and >30-day sale dates. Approval rechecks the transaction date even for old saved candidates, and newly approved market summaries retain transaction dates so they expire with the sales window. Legacy market summaries without transaction-date evidence no longer satisfy the market gate; collect and review again.

Fresh bounded collection across 9600X/9060XT, 7800X3D/9070 and 9950X/5090 returned 86 fixed-price matching-condition candidates before exact-title, age and detailed component/service qualification. None establishes an exact current all-new cohort sufficient for publication. The 5600G pass returned no parsed cards, which is a collection limitation rather than proof of no demand. Search-model mismatches, configuration ranges and the detail-confirmed mixed-condition PC are retained with blockers in the research exports.

Amazon source discovery also had a brand-heading parsing defect: newer cards have brand-only h2 headings before the linked product heading. The parser now extracts the linked product identity and matching URL. A real Chromium fixture exercises both new and legacy card layouts. Corrected search exports and exact-page offer captures are retained separately.

Verification checkpoint: 56 focused tests pass through the mandatory isolated PostgreSQL runner after applying the complete migration chain. Additional deterministic source identity, sold-date, selection and pricing-guidance checks pass, as does the Chromium fixture for new and legacy Amazon headings. Both archived specification schemas validate. The test server is stopped. These checks establish software behaviour; no final offer is approved, no workload measurement is invented, and no production deployment occurred. The publication goal remains active.
