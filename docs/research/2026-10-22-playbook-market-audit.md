# Playbook complete-PC market and outlier audit

Observed: 2026-10-22. Status: verified source/data inspection; methodology below is proposed. No implementation, price, database or live-offer changes. Saved operational snapshots are historical evidence, not a fresh availability check.

## Finding

The current Playbook review path has meaningful protection against invented prices, but it does **not** yet establish statistically robust market ranges. It separates sold/active samples, binds evidence to a selected BOM, requires human specification attestation and requires eight sold observations for its P75 approval. It lacks comprehensive configuration, transaction-price, regional, availability and outlier validation. The saved candidate population is unsuitable for any market cap.

The older general pricing engine is a separate concern: `compute_price_floor` is cost times 1.10 (10% markup, only 9.09% margin before other costs), and recalculation assigns active used asking-price median to `sold_comp_target`. Neither behaviour should become the new specification system's contribution or sold-evidence contract. Sources: [pricing_engine.py](../../flipflop-api/app/services/pricing_engine.py#L32), [manual recalculation](../../flipflop-api/app/services/pricing_engine.py#L196), [flip recalculation](../../flipflop-api/app/services/pricing_engine.py#L270).

## What the code actually does

- [playbook_market.py:24](../../flipflop-api/app/services/playbook_market.py#L24): fingerprints definition and component identities/titles; invalidates approval on mismatch or evidence older than 30 days. This protects selection consistency, not supplier availability or the age of an underlying sale.
- [candidate:74](../../flipflop-api/app/services/playbook_market.py#L74): requires exact eBay URL, title, matching condition, finite positive item price and known nonnegative postage; title keyword blockers for defective/incomplete builds.
- [core_spec_blockers:116](../../flipflop-api/app/services/playbook_market.py#L116): CPU/GPU model anchors, RAM/storage capacity text and PC/desktop/computer/workstation title anchor. Remaining specification is a reviewer attestation, not machine-verified compatibility. RAM and storage capacity matches are not role-bound; a capacity elsewhere in a title can satisfy a match. Architecture, memory generation/module type, GPU VRAM, internal storage role, OS, warranty, PSU and acoustics are not established by this check.
- [collect:188](../../flipflop-api/app/services/playbook_market.py#L188): direct sold fetch then browser fallback; NEW active search; within-kind exact-listing-ID deduplication. Candidate rows retain normalized totals and blockers, not complete provider responses or page captures.
- [decide:247](../../flipflop-api/app/services/playbook_market.py#L247): rejects stale/mismatched batch, blocked selections, duplicate listing ID across sold and active; requires exact-build confirmation and eight sold observations. This requirement applies to every approval through this function even though the error describes a High-end cap. [summarize:51](../../flipflop-api/app/services/playbook_market.py#L51) computes separate medians and linearly interpolated sold P75; it performs no statistical outlier check.
- [extension ingest:68](../../flipflop-api/app/services/playbook_extension.py#L68): vendor/host validation, GBP check, sold-results URL and sold-marker check, hidden Best Offer blocker; merges only same-BOM observations younger than one day. Vendor/path hashing ignores query parameters, which can conflate distinct configured variants. Retains last 300 candidate rows; previous snapshots remain separate records.
- [direct sold extraction:156](../../flipflop-api/app/gem_radar/adapters/sold_comps.py#L156): explicit sold label, pound symbol and single-price text required; requested condition copied to result, without inspecting actual condition. No accepted-offer flag is extracted. `sold_at` is collection time; actual date is only free text. Price cutoff is normally GBP3–3000, overridden to GBP10000 for Playbook collection; these are collection limits, not evidence-based outlier thresholds. The parser docstring mentions excluding auctions, but this extraction function has no explicit auction test.
- [Browse search:230](../../flipflop-api/app/services/ebay_browse.py#L230): GBP, positive/range price constraints, accessory and defective-condition filters; returns delivery-known flag, condition and Best Offer status. Missing currency defaults to GBP; product location, tax/fee context and availability are not returned. Unknown shipping defaults to zero internally, but the Playbook candidate layer blocks it. Do not rely on generic component medians to inherit that stronger block.

## Exclusion coverage matrix

“Partial” means the category is not guaranteed excluded; a reviewer may identify it, but the stored automated checks do not prove exclusion.

| Requested category | Current Playbook handling | Gap / required evidence |
|---|---|---|
| Components and accessories | Partial: Browse accessory filter; full-PC and core-title anchors | A component title containing PC and model/capacity terms can pass; require detail-page complete-system classification and included parts |
| Bundles / incomplete PCs | Partial: bundle/barebone/parts only/no gpu blockers | Other bundle language, missing OS/storage, optional GPU and peripherals need structured inclusion list; integrated-graphics builds must not be misclassified |
| Faulty, untested, repair only | Partial: faulty/broken/spares/repair title words and Browse defect conditions | “Untested”, intermittent defects and description-only faults not comprehensively checked |
| Wrong condition | Partial: exact normalized condition comparison | Sold adapter writes requested condition rather than actual condition; active snapshots demonstrate search filter alone is insufficient |
| Wrong currencies | Partial: explicit extension GBP and Browse GBP; sold pound symbol | Missing Browse currency treated as GBP; converted display currency does not establish original currency or fees |
| Wrong regions | Not guaranteed | UK host is not UK stock/location or UK delivered destination; capture origin, destination, import costs and delivery coverage |
| Wrong specification | Partial: CPU/GPU/title capacities plus human attestation | Require full configuration and role-specific constraints; CPU benchmark alone cannot establish architecture/software fit |
| Configurable starting prices | Not automatically excluded | Capture selected variant and configuration-specific delivered price; no priced variant means contextual evidence only |
| Duplicate observations | Partial: exact eBay ID within kind; approval rejects same ID across kinds | Cross-vendor duplicates and repeated batches are not globally deduplicated; retailer path hash can merge variants |
| Relisted physical items | Not guaranteed | Different listing IDs survive; cluster seller, images, description, configuration and timeline, retain uncertainty |
| Unavailable products | Not automatically excluded | Detail-page stock/purchasability and lead time must be captured |
| Stale evidence | Partial: 30-day batch expiry, BOM binding; one-day extension merge | Actual sale date is unparsed; fresh scraping of an old sale refreshes observation time, not transaction recency |
| Hidden accepted Best Offers | Extension blocks enabled Best Offer on sold | Direct sold parser does not capture it; a sold label alone is insufficient. An enabled-offer flag is conservative, not proof an offer was accepted |
| Missing delivery | Blocked by Playbook candidate if unknown | Supplier postage cannot be replaced by the GBP20 outbound allowance; confirm comparable destination |
| Missing fees / VAT context | Not automatically excluded | Capture displayed fee basis, buyer protection, VAT inclusion and recoverability; listing display is not seller payout |
| Statistical outliers | None in Playbook summary | Older engine truncates at an index near P90, without semantic grouping, lower-tail check or adequate sample requirement |

## Concrete saved-data evidence

Recomputed directly from [pricing-deep-dive.json](../../flipflop-api/tmp/pricing-deep-dive.json), `market.*.evidence.candidates`:

| Measurement | Count |
|---|---:|
| Latest saved cell batches | 24 |
| Candidate observations across batches | 3,874 |
| Distinct stored candidate IDs across batches | 544 |
| Sold observations | 0 |
| Eligible observations (empty blocker list) | 0 |
| Non-null delivered total | 21 |
| Missing item price or postage blocker | 3,853 |
| Missing exact storage-capacity title evidence | 3,829 |
| Missing exact RAM-capacity title evidence | 3,823 |
| Missing complete-PC title evidence | 3,445 |
| Incomplete/defective keyword blocker | 33 |

Blocker counts overlap. The 544 IDs are not verified unique physical products. Repeated source cards across cells explain why 3,874 is not a market sample size. No median, P75, demand or price ceiling can be inferred from this population.

Example from `playbook:1:cell:FF-GVG-03`: “GAMING PC / AMD Ryzen 9850X3D / RTX 5080 / 6TB M.2 SSD / 128GB DDR5 RAM”, GBP2579, is blocked for wrong GPU/RAM/storage versus selected BOM. Another “White Gaming PC Ryzen 7 9850X3D RX 9070 XT 32GB DDR5 1TB Gen5”, GBP2299, is blocked for GPU suffix and storage. These are specification exclusions, not statistical outliers.

[Fresh search snapshot](../../flipflop-api/tmp/fresh-pc-market-probes.json) contains 15 / 15 / 8 active results for 5600G, 7800X3D/9060XT and 9950X/5090 queries. Respectively 4 / 1 / 1 are “OPENED – NEVER USED”; 32 of 38 are NEW. All three sold probes report unavailable/no comps, which is not zero demand.

- 5600G query: GBP589.99 title advertises 16–32GB and 512GB–1TB; priced configuration unresolved. GBP539.99 XUM entries explicitly show 16GB/256GB despite 32GB query. GBP451.96 CyberPower entry is a bundle with 8GB and opened condition.
- 9060XT query: results include 9070XT, 5080 and 5070Ti; GBP2094.99 entry explicitly says 9060XT **8GB**, whereas a 16GB requirement cannot be inferred from GPU family text. GBP2034.99 title offers 16/32/64GB RAM, so its headline cannot establish a 32GB total.
- 5090 query: three different same-seller titles imply 9950X3D/5090/128GB/2TB at GBP2042, GBP2299 and GBP2457. They require detail-page configuration/availability scrutiny. Their low price alone is not evidence of fraud, a valid sale, or permission to delete them. Other entries are 5080 or 32GB RAM and must be semantically separated first.

These examples are captured asks, not independently reverified current offers. See [pricing deep dive](../plans/2026-10-22-playbook-pricing-deep-dive.md) for inspected sold pages, including hidden accepted offers and ambiguous buyer-protection/storage context.

## Proposed reproducible methodology: `complete-pc-market/1.0.0`

1. Preserve immutable raw fetch/page evidence with source URL, observation UTC, original listing/item/variant ID, query, provider version, content hash, selected configuration and source status. Scrub session identifiers and credentials. Preserve unavailable/error responses as collection status, never numeric observations. Keep normalized records and review decisions separate from raw evidence.
2. Require explicit product completeness, condition, region/destination, actual configuration, availability, item amount/currency, applicable delivery/fees/VAT basis, observed and sale timestamps. Unknown critical fields become `context_only` with reason codes; never silently impute zero. Keep sold, active, accepted-offer-unknown and own completed-sale reconciliation distinct.
3. Partition by workload-compatible architecture, component/capability band, condition, channel/region, warranty/service and comparable total basis. Exact and adjacent configurations get separate groups. Adjacent adjustments require independent evidence and visible uncertainty, never a guessed GPU benchmark-to-pound conversion. Do not pool workstation ECC/professional capabilities with gaming merely because CPU/GPU scores are higher.
4. Deduplicate exact item/variant and observation events. For repeat active sightings, use latest in-window observation and retain history. Link possible relists by seller/images/configuration/time; count uncertain clusters conservatively as one item, disclose ambiguity. Different units of a retailer model can be distinct sales only with transaction-level evidence. Preserve the deduplication graph and canonical IDs.
5. Freshness proposal: active offers checked within 7 days for research; reverify within 24 hours before any later publication approval. Sold transactions within 30 days; extend to 90 only as a separately labelled historical cohort with regime/availability check. Observation freshness and transaction freshness are separate. Do not merge old sales into a “current” range by fetching them today.
6. Sample policy, proposed rather than statistically universal: n=0 means unknown; n=1–4 list individual verified observations only; n=5–7 report descriptive median/min/max with low confidence and no automatic cap; n>=8 permits descriptive median/IQR/P75 and diagnostic flags only after comparability checks. Retain current eight-sold minimum as a minimum gate, not proof of sufficiency or permission to mix asks. Fewer than three independent seller/item clusters or material seller concentration lowers confidence. Small or biased non-random marketplace samples never gain a calibrated confidence interval simply from n.
7. For n>=8 compute Q1/Q3 with fixed linear interpolation, IQR, median and MAD. Flag below Q1−1.5*IQR or above Q3+1.5*IQR; additionally flag absolute modified z=0.67448975*(price−median)/MAD >3.5 when MAD>0. Thresholds are diagnostics, not deletion instructions. If MAD=0, do not divide; use IQR flag if nonzero, otherwise report repeated prices and manually inspect deviations. State exact quantile algorithm and penny rounding. Review flagged listings for configuration, service and supply explanations; keep valid extremes. Publish all-eligible and reviewed-cohort sensitivity summaries if an exclusion materially changes the conclusion.
8. Every exclusion stores record ID, reason code, source evidence, actor/time and rule version. Statistical flags store cohort membership, n, computed thresholds and disposition. Retain excluded raw records. No removal based on desired selling price or own margin. An unexplained extreme remains pending review rather than silently removed.
9. Publish sold and active panels separately: candidate/eligible/dedup/retained n, distinct sellers, oldest/newest transaction and observation dates, median, Q1/Q3/IQR, observed min/max, flagged count, exclusions, source/coverage limitations, methodology/spec versions and confidence. A price range is an empirical descriptor, not guaranteed willingness to pay or a mathematically justified maximum. Saved approval must cite observation IDs and reproducible calculation input hash.
10. Compare an evidenced complete-PC price scenario with full landed-cost contribution floor, channel fees, allowances and reserves. Recommend 12% target and hard 10% minimum only for analysis; stricter existing policy needs owner decision. If no overlap, re-source, redesign or withhold. Never discard cheaper competitors to manufacture overlap. Do not substitute legacy `cost*1.10` for full contribution arithmetic.

## Validation and implementation boundary

Verified by reading source and existing focused tests, and by read-only Python aggregation of snapshots. Existing [market tests](../../flipflop-api/tests/test_playbook_market.py) cover condition/postage blocking, sold/active separation, eight-item P75, suffix/capacity checks, BOM freshness and approval persistence. This audit did not run tests or independently reproduce provider fetches; no new code was introduced.

Next implementation should first repair detail/configuration capture and transaction semantics, then add reproducible deduplication/cohort diagnostics. Outlier sophistication cannot rescue component cards, unknown totals or hidden accepted offers. Automated research may prepare proposed evidence/spec revisions; approval, purchasing and publication remain separate owner-controlled actions.
