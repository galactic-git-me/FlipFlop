# Market coverage and Super Gem eligibility audit

The largest immediately recoverable gap is a repeat-ingestion defect: live listing observations are refreshed, but their comparable-price rows are not. A read-only replay increases market-reference coverage from 293 to 822 of 2,795 identified active listings. References backed by at least three comparables increase from 233 to 521. This is measurable coverage recovery, not a forecast of additional Gems.

Audit performed on 13 September 2026 against the configured **local PostgreSQL `pcflipper` database on 127.0.0.1**, plus the current repository. No production query or database mutation was performed. Its 24-hour active population is 5,426 scored listings, different from the screenshot's 18,999; these figures must not be presented as an exact recount of that screen. The latest stored score is 12 September 2026 at 22:54 UTC. The local population may reflect snapshot timing and subsequent local ingestion.

## Measured coverage

| Measure | Local result |
|---|---:|
| All historical scored listings | 64,821 |
| Active scored listings, observed within 24 hours | 5,426 |
| Active listings with a canonical product key (CPK) | 2,795 (51.5%) |
| Active listings with a stored market sample | 294 (5.4% of active; 10.5% of identified) |
| Active insufficient-data listings | 2,480 |
| Of those, no-comparables | 2,430 |
| Active identity-failed / identity-pending | 2,423 / 28 |
| Active Gems / Super Gems | 9 / 4 |
| Sold observation rows | 119,194 |
| Distinct sold URLs, stripping query strings | 9,441 |
| Sold rows lacking a CPK | 47,064 (39.5%) |
| Fresh active-price rows, across the historical price table | 1,170 of 33,586 |

The historical catalogue corroborates the category imbalance: stored market references exist for 1,424/5,662 CPUs, 380/6,837 motherboards, 288/3,230 GPUs, 142/2,670 RAM listings, 144/3,382 SSDs, 179/3,067 coolers, 66/1,132 PSUs, and 15/2,602 cases. These are historical, not current-market availability rates.

## 1. Fix live price freshness first

In `app/api/gem_radar.py:2384`, a repeat listing takes one of two branches: unchanged prices call `touch_observation`; changed prices call `record_observation`. If a CPK exists, both branches then skip extraction and continue. Neither calls `upsert_listing_price`.

In `app/gem_radar/phase2_runner.py:118`, active comparable prices are accepted only when `gem_radar_cpk_listing_price.updated_at` is within 14 days. The documented assumption in `cpk_market.py` that every re-sighting refreshes this clock is therefore false on this ingestion path.

Consequences measured on identified active listings:

- 2,534 of 2,795 have price rows older than 14 days, despite being seen within 24 hours.
- 991 have a stored comparable price that differs from the latest observed delivered price.
- There are no missing price rows in that active identified subset: expiry and stale values dominate here.

**Proposed repair:** on every valid fixed-price re-sighting, reuse the CPK and upsert the current delivered price and its observation time. This needs no extra identity-model call. Recompute affected aggregates in batches. Backfill using genuine recent observations; do not refresh every historical row to today.

Read-only replay with existing robust filtering, same-condition separation and subject exclusion:

| Market-reference result for 2,795 identified active listings | Current price rows | Prices from latest observations within 14 days |
|---|---:|---:|
| Any accepted market reference | 293 | 822 |
| Reference with at least 3 comparables | 233 | 521 |
| Accepted reference, fewer than 3 comparables | 60 | 301 |

The replay's 293 versus 294 stored references reflects recomputation at the audit time rather than reuse of earlier scoring facts. The simulation does not rerun identity, profitability, demand velocity, or final deal classification. Some recovered references are fixed-retailer context only; those do not satisfy the minimum sample gate. Existing CPK quality remains a limitation. Active-cohort construction is based on observation-linked price rows; exceptional orphan price rows are not modelled.

Examples gaining a reference include Gigabyte B550 EAGLE, Gigabyte B760M D3HP DDR4, Intel i5-9500, and Noctua NH-D15 chromax.black. Recovery is not limited to obscure products.

## 2. Repair the identity system before attempting a broad sold backfill

Phase 2 joins sold observations by exact CPK and condition. The sold ingestion resolver instead derives a normalised model-text key and only accepts an exact, unique match across CPKs (`benchmarks.py:223`). Ambiguity is correctly rejected there.

Of the unmapped sold rows:

| Existing alias outcome | Rows |
|---|---:|
| Exactly one candidate CPK | 75 |
| Multiple candidate CPKs | 27,514 |
| No candidate CPK | 19,475 |

Attaching the 75 unique matches in memory added **zero additional active market references** in this replay. Merely filling NULL keys will not close this gap.

Concrete examples:

- `RX6800XT16GB` matches both AMD and XFX identities; 1,008 sold rows are unmapped. The sold key has lost board-partner information.
- `RX9060XT` matches several board partners and both `rx9060-xt` and `rx-9060-xt` spellings. It also omits VRAM capacity, which must not be guessed.
- `16GBDDR4` spans brands and lacks enough kit/speed detail for exact pricing.
- `RADEONR9` is a family, not a sufficiently identified GPU.

CPKs hash category, brand and model. Cosmetic model variation and inconsistent manufacturer/board-partner naming therefore split evidence, while underspecified models can wrongly pool variants. `canonical_variant_model` adds selected capacity, VRAM and radiator tokens but is not a complete product ontology.

**Proposed repair:** introduce a versioned canonical product record with validated aliases. Prefer GTIN/MPN/catalog identifiers, then deterministic category parsers, and retain model-assisted extraction as a fallback. Distinguish chip manufacturer from board partner. Preserve CPU suffixes; motherboard DDR generation/Wi-Fi/revision; RAM capacity, module count, generation and speed; SSD capacity; GPU VRAM; PSU series and wattage; cooler size; case variant.

Keep exact SKU and comparable product-family relationships separate. A validated broader family can support labelled research context, but should not silently inherit exact-SKU confidence. Ambiguous legacy sold rows need original listing identity evidence; the sold table currently lacks title, MPN and variant fields, so some cannot be repaired from this table alone.

There is also an asymmetry to fix: `cpk_pipeline.py:151` backfills model aliases to NULL sold CPKs without the uniqueness check used by `_get_cpk_for_match_key`. Reuse one resolver across all writers. Already-mapped rows need validation too, not just NULL repair.

## 3. Identity failures include obvious components

A deterministic sample of 20 active identity failures includes “GIGABYTE B760 DS3H DDR5 Motherboard”, “Intel Core i5 14400F SRN3R CPU Processor LGA 1700”, and a Corsair Vengeance kit with the full MPN `CMK32GX4M2E3200C16`. It also includes irrelevant or unusable input such as “CompareQuick viewOffer”.

This proves that the missing-identity population is not entirely accessories or unrecognisable products. It does not establish the exact recoverable proportion or whether each failure came from extraction, service availability, old data, or validation.

**Proposed repair:** record reason codes for missing input, unsupported product, extraction timeout/service failure, invalid schema, ambiguous identity, and genuine exclusion. Retry transient failures separately. Add deterministic recognisers for clear CPU models and full MPNs. Audit stratified samples by vendor/category before a broad identity backfill; keep accessories and unsuitable legacy hardware excluded.

## 4. Count unique sold evidence, not repeated sightings

119,194 sold rows reduce to 9,441 distinct URL strings after stripping query parameters: about 12.6 observations per URL. That is not 119,194 independent sales. Nor is the URL count a final canonical sale count, because URL forms can differ.

`submit_sold_comps` inserts on each submission. The robust market scorer deduplicates URLs, but the targeted enrichment endpoint uses `COUNT(*)` and stops nominating cohorts at five rows. Repeated sightings can therefore suppress enrichment while still failing the scorer's three-unique-comparable requirement.

**Proposed repair:** persist canonical marketplace/item ID, sale timestamp when available, observed timestamp, condition, title/identifiers and price provenance. Upsert repeated observations; compute usable cohort size with the same deduplication and filtering as the scorer. Keep observation freshness distinct from the actual sale date. Current lookback uses scrape time, so repeated scrapes do not prove a sale happened recently.

## 5. Direct research at the remaining gaps

`sold_comp_targets` (`app/api/gem_radar.py:2100`) only selects `INSUFFICIENT_DATA`, requires at least two aggregate price observations, at least a 10% discount, fewer than five sold rows, and returns three targets by default, maximum five.

This excludes both:

- `EVIDENCE_LIMITED_DEAL`, whose economics already look promising: 23 active examples in this local snapshot.
- True singleton/no-market products that cannot meet the existing-price gate.

Its aggregate price source also combines conditions and evidence types, unlike Phase 2's condition-specific robust cohorts. That can distort enrichment priority.

**Proposed repair:** maintain a bounded queue per canonical product and condition. Prioritise promising evidence-limited deals, then high-reuse cohorts needing one or two more unique comps, then a limited discovery budget for singleton products. Rank by plausible economic upside, number of affected active listings, inventory need, and expected research cost. Use the scored cohort's actual usable unique count and same-condition reference. Preserve exact target identity through collection and record why returned comps were rejected.

The external extension implementation was not located in this repository during this audit, so actual target-request cadence and rejection rates remain unverified. Instrument those before increasing collection volume.

## 6. Make the dashboard reconcile

The “M Prices” gauge counts CPK aggregate rows with at least two observations (`app/api/gem_radar.py:344`). That aggregate can include sold, active, Amazon and scan rows. Phase 2 instead uses condition-specific, deduplicated, leave-one-out robust evidence with a three-comparable policy, plus limited retailer context. These are different metrics.

The no-CPK branch constructs `OpportunityResult` without setting evidence status (`phase2_runner.py:281`), leaving the default `CLASSIFIABLE`. The database consequently contains 34,630 historical `IDENTITY_FAILED` rows labelled `CLASSIFIABLE`. The vendor chart lacks classification buckets for identity-failed/pending, while the table deliberately omits average and evidence-limited deals (`flipflop-admin/app/sourcing/page.tsx:1453`). Totals cannot be reconciled by simply adding the displayed columns.

**Proposed repair:** expose one additive funnel: observed → valid component → identity resolved → reference available → sufficient comparable evidence → profitable → Gem/Super Gem. Show identity pending/failed explicitly. Track evidence basis separately from deal quality. Split “no comparables” into no raw matches, condition mismatch, stale-only, too few unique matches, rejected outliers, and unresolved identity. The present diagnosis can label a failed sparse sold cohort “no comparables” merely because active count is zero.

## Delivery order and acceptance criteria

1. **Freshness repair and bounded backfill.** Regression-test unchanged and changed-price re-sightings, delivered-price handling, and continued exclusion of genuinely stale rows. Repeat the read-only replay on a production snapshot before applying a migration. Expected benefit already measured locally: +529 references, of which the net increase with at least three comparables is 288.
2. **Evidence accounting and dashboard correction.** Ensure every displayed vendor total reconciles; identity failures never say classifiable; repeated sold sightings cannot satisfy the target quota.
3. **Versioned identity reconciliation.** Produce reviewable exact-alias merge proposals with variant-conflict checks, then rebuild dependent prices and scores. Use a labelled positive/negative product-pair sample to check false matches. Do not treat all 47,064 unmapped rows as recoverable.
4. **Targeted collection.** Include promising evidence-limited deals and a controlled singleton budget. Measure newly classifiable products per research job, not rows scraped.
5. **Re-score and measure opportunity yield.** Report changes in evidence coverage, false-match rate, profit-qualified candidates, and final Gems separately.

No recommendation here requires lowering Super Gem thresholds. The current scorer already permits active-market estimates through economics/evidence gates, but Gems additionally require liquidity (45 for Gem, 60 for Super Gem under the loaded policy). Additional active prices alone may therefore leave a promising item evidence-limited. Sold/demand evidence remains a separate bottleneck. One active Super Gem currently has condition-uncertain evidence, so condition-policy consistency should also be checked during validation.

## Reproducibility

Run from `flipflop-api`:

```powershell
.venv/Scripts/python.exe scripts/audit_market_coverage_readonly.py
```

The script sets the database transaction read-only, loads the configured scoring policy, and writes `tmp/market-coverage-audit.json`. It performs no enrichment calls or scoring writes. The replay exercises the repository's existing robust market functions; it is an analytical scenario, not a production fix or end-to-end scoring test. The only files added by this investigation are the audit script, this report, and local output artifacts.

## Implementation status

The first implementation slice is now applied in code and the local database migration is at head:

- live repeat sightings refresh CPK listing prices;
- sold observations retain bounded canonical item IDs and identity evidence;
- repeated sold items are updated instead of inserted again;
- ambiguous sold-to-CPK backfills are rejected;
- enrichment targets include evidence-limited deals and count distinct sold items;
- identity failures receive `IDENTITY_UNCERTAIN` evidence status and are visible in the sourcing dashboard;
- migration `20260913_0001_sold_observation_identity` adds the sold identity fields;
- migration `20260913_0002_identity_proposals` adds the durable reconciliation queue;
- deterministic proposal generation and apply scripts are available, with a local 1,000-row preview producing 713 ambiguous and 287 unresolved proposals and zero automatic merges;
- the safe unique-alias backfill ran locally and mapped 22 sold observations from one unambiguous normalized key; ambiguous keys such as RX6800XT16GB and RX9060XT remain untouched;
- scoring tests now match the loaded 8.5/7.5/6.5 classification boundaries and the three-comparable minimum policy.

The implementation intentionally does not auto-merge the 27,514 ambiguous sold rows. Product-level alias proposals still require review or stronger identifiers (GTIN/MPN/catalog IDs) to avoid corrupting comparable cohorts.

### Identity reconciliation queue

The review queue is available through
`flipflop-api/scripts/propose_identity_reconciliation.py`. It reads sold
observations with no CPK and the distinct CPK catalog, then stores one
auditable proposal per sold observation in
`gem_radar_identity_proposals`. Exact GTIN/MPN/model matches are surfaced with
high confidence; title/model matches are conservative; conflicting and
unresolved rows retain their candidate list and evidence. The command never
updates `gem_radar_sold_observations.cpk`.

Run a bounded preview first:

```powershell
cd flipflop-api
$env:PYTHONPATH = '.'
python scripts/propose_identity_reconciliation.py --limit 5000 --dry-run
```

After reviewing the counts, persist that same bounded batch by omitting
`--dry-run`. Approved proposals can then be applied by a separate review
operation. The deterministic apply step is:

```powershell
python scripts/apply_identity_proposals.py --limit 5000 --dry-run
python scripts/apply_identity_proposals.py --limit 5000
```

It only applies `exact_identifier` proposals at confidence 0.95 or higher;
ambiguous and title-only proposals must not be auto-merged.
