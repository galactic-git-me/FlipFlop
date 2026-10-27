# Why captured vendor offers are missing from the Playbook

Audit date: 26 October 2026. Environment: local DEV PostgreSQL. Database probes were read-only. No account changes, purchases, supplier approvals or publication were performed.

## Finding

The low vendor counts are a confirmed identity and data-flow defect. The system has already captured retailer offers that the Playbook fails to attach to the corresponding Amazon bestseller. Additional scraping alone will not fix this.

The previous 90-product export showed 87 stored CPK values and only 22 products with another matched vendor. A populated CPK column does not establish that the key is correct or shared consistently. Several examples have fragmented keys; other keys incorrectly merge different variants.

This investigation traced three products from the Amazon observation through stored vendor observations, persisted CPK metadata, the supplier-offer index and the actual `same_product` function. It also opened vendor product pages to distinguish missing data from products that genuinely have retailer listings.

## Individual examples

| Amazon bestseller | Amazon ASIN / stored CPK | Evidence already present | Why it is missing |
|---|---|---|---|
| Samsung 990 PRO 2TB | `B0B9C4DKKG` / `5b6af37e88a55eef` | Scan `LN130047`, AWD-IT, Ebuyer and Overclockers have captured 2TB product candidates. Scan and AWD-IT expose manufacturer code `MZ-V9P2T0BW` on their product pages. | Scan/AWD use CPK `368752d4ec55daa9`; Ebuyer uses `74f4e755229f692e`; Overclockers uses `54033a100e32fa43`. Model text differs between `990-pro-2tb`, `990-pro-nvme-m2-ssd-2tb` and `990-pro`. The index does not bridge these identities. The real matcher returns false for the Amazon/Scan pair. Exact MPN/GTIN still needs to validate each individual variant before merging. |
| Kingston NV3 1TB M.2 2280 | `B0DBR3DZWG` / `171817f97851df4f` | Overclockers `STO-KNG-02942` was captured today with a direct product URL, £159.95 and available stock. Both titles contain `SNV3S/1000G`. The live product page also exposes that MPN and EAN `0740617344790`. Ebuyer has a page with the same MPN. | Overclockers/Ebuyer/Computer Orbit use `39f5e120c5269634`; AWD-IT's 2280 candidate uses `1d3b114dff95aeb7`. The Amazon metadata model contains descriptive wording while other records use `nv3-1tb`. The supplier matcher has no general exact-MPN index, so it rejects even the identical-MPN Overclockers pair. This is a definitive missed link. |
| Corsair Vengeance LPX DDR4 32GB, 2×16GB, 3200 CL16 | `B07RW6Z692` / `16881be5473c90f8` | Overclockers `MEM-CRS-08411` has a captured 32GB 2×16GB 3200 CL16 listing and direct product URL; Ebuyer has a corresponding spec-level candidate. | The Amazon key is also assigned to Vengeance RGB PRO, a different family. Overclockers uses `9bf92e72c4e5feca`; Ebuyer uses `48d311db95b94dcc`. The Ebuyer record's saved metadata incorrectly says 8GB/3600 despite its title saying 32GB/3200. The LPX vendor page needs its exact manufacturer part number captured before treating every spec-level candidate as the identical SKU. |

Vendor pages inspected:

- [Scan: Samsung 990 PRO 2TB, MZ-V9P2T0BW](https://www.scan.co.uk/products/2tb-samsung-990-pro-m2-2280-pcie-40-x4-nvme-ssd-mlc-3d-v-nand-7450mb-s-read-6900mb-s-write-pc-ps5).
- [AWD-IT: Samsung 990 PRO 2TB, MZ-V9P2T0BW](https://www.awd-it.co.uk/samsung-990-pro-2tb-ssd-pcie-4-0-nvme-m-2-solid-state-drive-mz-v9p2t0bw.html).
- [Overclockers: Kingston NV3, SNV3S/1000G](https://www.overclockers.co.uk/kingston-nv3-1tb-pci-e-4.0-nvme-m.2-solid-state-drive-snv3s-1000g/STO-KNG-02942.html).
- [Ebuyer: Kingston NV3 1TB](https://www.ebuyer.com/kingston-technology-nv3-1tb-internal-m2-ssd-732484). Its current page reports out of stock; that means retain its product link but exclude it from currently purchasable cheapest-offer selection.
- [Overclockers: Corsair Vengeance LPX 32GB 2×16GB 3200](https://www.overclockers.co.uk/corsair-vengeance-lpx-32gb-2x16gb-ddr4-c16-3200mhz-dual-channel-kit-black/MEM-CRS-08411.html).

## Confirmed causes

### 1. CPKs are derived from inconsistent product names

`app/gem_radar/cpk_extractor.py` and `cpk_pipeline.py` hash category, brand and normalized model text. Equivalent retailer descriptions can produce different model text and therefore different keys. Capacity and other variant fields are not consistently encoded in the model. Historical rows also contain CPK-column versus embedded-JSON-key disagreements.

The supplier index in `app/services/playbook_stored_offers.py` first joins the hash, then a metadata identity that still requires an equal normalized category/brand/model. For RAM and SSDs it lacks a general index on manufacturer part number or GTIN. CPU-specific model normalization already has a bridge; RAM/storage do not have an equivalent reliable bridge.

### 2. Invalid identities survive and propagate

`cpk_pipeline._valid_existing_cpk` checks broad completeness/accessory/bundle rules. A reproduction with a 32GB/3200 title and stored 8GB/3600 RAM metadata returns **true**. `_lookup_unique_catalog_alias` can reuse a generic model alias without checking the full RAM variant. Previously accepted records therefore survive later scans, and their aliases can seed further bad assignments.

Captured examples sharing CPK `9bf92e72c4e5feca` include LPX 32GB 2×16GB DDR4-3200, LPX 32GB 4×8GB DDR4-3200, and a DDR5-6400 listing. These require different product identities. Other audited catalogue metadata incorrectly identifies Thermalright coolers as AMD, Corsair RAM as “coral”, and a Lian Li PSU as Kolink “power-supply”.

The error therefore includes both false splits and false merges. Removing the current variant checks would inflate counts and mix incompatible prices.

### 3. Rescoring discards known product URLs

`phase2_runner.run_phase2_classification` reads the observation but constructs the scored URL using `fallback_listing_url` instead of carrying the captured product URL through. A direct reproduction for Scan `LN130047` produces `https://www.ebay.co.uk/itm/LN130047`.

The fallback URL templates omit Scan and Ebuyer; other retailers are often reduced to search URLs. The database contains Ebuyer-qualified listing IDs wrapped in eBay URLs and Overclockers product records whose scored URL is a search page. In some cases the exact URL survives in `commercial_source_evidence`; in others there is no usable product URL available to the Playbook lookup.

### 4. URL recovery and supplier indexing compound the identity failure

`stored_offers` only attempts historical/canonical URL recovery for requested CPKs or GPU-category observations. If an SSD/RAM already has the wrong CPK, it can miss that recovery step as well. Many retailer observations have null `category`, so they rely on their CPK metadata to be indexed correctly. Reconstructing an unverified URL from a title cannot establish current price or stock.

### 5. Search generation does not reliably target the exact SKU

The current component feed contains 192 terms and covers 85 of the 90 table products by an ASIN or CPK tag. Five have no such managed identity search. This is feed generation coverage; the installed browser's exact current configuration and completed per-vendor runs were not verified.

For the examples:

- Samsung 990 PRO's generated query is `Samsung 990 PRO NVMe M.2 SSD`: truncation at the comma removes its 2TB capacity.
- Corsair LPX's generated query contains the whole marketing title, timings, XMP/EXPO wording and the manufacturer code, rather than searching the manufacturer code first.
- Kingston's query retains its exact MPN, yet the recorded offer is still lost during matching. This proves query quality alone is not the central fix.

`playbook_extension.component_searches` also uses a `cpk` variable left from a preceding loop when choosing query formatting, instead of the current grouped row's `g['cpk']`. It limits managed searches to active catalogue variants, which can leave newly imported pending-review products without targeted supplier discovery.

## Required repair order

1. **Repair identity production and validation.** Prefer validated manufacturer+MPN or GTIN; use exact category-specific identity fields where identifiers are absent. RAM must preserve family, DDR generation, kit size, module count, speed and relevant variant fields. SSDs must preserve family, capacity, form factor and exact heatsink/SKU variants. Contradictory metadata must be rejected and re-resolved. Local LLM output supplies candidate fields, not unrestricted canonical names.
2. **Backfill the captured data.** Reconcile Amazon anchors and retailer observations to the same validated identity; repair both false splits and false merges. Recompute affected market aggregates after repair so old mixed buckets do not remain trusted. Keep an audit of old/new assignments and preserve source observations.
3. **Preserve source product URLs end to end.** Carry the captured URL into rescoring and catalogue materialisation. Give known retailers vendor-correct fallback search links for browsing only. Keep exact product links, search links and stock verification distinguishable.
4. **Use the corrected identity in Playbook supplier selection.** Gather all exact new-condition retailer offers for the chosen bestseller component, retain unavailable vendor links for visibility, and select the lowest fresh available delivered offer. Apply captured postage, then a saved vendor default, then £0 inbound fallback. Never substitute a zero component price.
5. **Repair managed discovery.** Search by MPN first, then a compact exact product/variant query; fix the grouped-CPK variable error. Ensure every in-range bestseller has supplier-discovery coverage before catalogue approval, while retaining active source-listing requirements and explicit scan states.
6. **Rerun the frozen 90-product comparison and rebuild.** Require the known Kingston exact-MPN miss to pass, Samsung exact-MPN offers to attach, and incompatible LPX/RGB/DDR/module-count variants to remain separate. Report per-product/per-vendor states: found and linked, found pending identity, found unavailable, scan failed, not yet searched, or no result. Then reprice and revalidate all affected build proposals.

## Publication implications

The 22/90 value is matched-offer coverage through a defective lookup, not evidence that the other products are absent from vendors. Current lowest-price and market-range outputs cannot be treated as complete cross-vendor comparisons until identities and contaminated aggregates are repaired.

Separately, the preceding build audit found only 87 of 190 hardware occurrences traceable to the strict current top-ten/top-100-case range. The assembler currently admits authored/pinned/historical exceptions; that must be reconciled with the owner's stated bestseller constraint before claiming all builds meet it. Windows-source review remains a publication blocker in all 24 saved proposals. Four builds also have RAM evidence/condition gaps, Enterprise has an unavailable case, and Prometheus has unresolved compatibility/search-limit work. Customer checkout and publication have not been verified; zero builds were live at the read-only build audit.

## Evidence and limits

- [Top-90 table](amazon-top10-supplier-table.md): captured prices and match coverage before repair.
- [Minimal function reproductions](vendor-link-reproduction.json): three rejected retailer pairs, contradictory RAM metadata accepted, and Scan's malformed fallback URL.
- [Retailer record trace](vendor-example-trace.json): captured URL versus scored/canonical URLs, source keys and metadata.
- [Managed feed audit](component-search-feed-audit.json): actual generated terms and missing identity coverage.
- [Full build-link audit](supplier-link-audit.json): selected hardware provenance, offer links and publication blockers.

The online checks establish that named product pages exist and expose the stated identifiers; search-index prices and stock can be older than the current page. No claim is made that every exact bestseller SKU is sold by every retailer. This investigation establishes concrete missed matches without requiring that assumption. Repair steps above are required work, not completed implementation.
