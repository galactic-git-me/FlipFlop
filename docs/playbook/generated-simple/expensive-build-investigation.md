# Titan, Odyssey and Enterprise pricing investigation

**Corrections completed in DEV, 24 October 2026:** Titan £12,836.94; Odyssey £15,406.57; Enterprise £35,973.90. Enterprise retains Threadripper and 256GB ECC RDIMM at the owner's explicit request. The investigation below records the original baseline; see the completed corrections at the end.

24 October 2026. Read-only inspection of the latest pending DEV proposals for the three cells, current pricing code and supplier pages. No prices, components or proposals changed.

| Build | Recorded parts incl. buying postage | Current cost-floor suggestion | Main cost drivers |
|---|---:|---:|---|
| Titan | £13,662.45 | £18,654.15 | RTX 5090 about £9,960.83; 128GB RAM £2,199 |
| Odyssey | £14,249.01 | £19,453.10 | Same GPU and RAM; two 4TB SSDs |
| Enterprise | £27,178.20 | £37,063.62 | 256GB RDIMM £11,999.96; RTX 6000 Ada £7,675; Threadripper £3,409.33 |

These are deterministic cost-floor calculations from the current saved components, not validated complete-PC market valuations. Read-time prices can change as new captures arrive.

## Findings

1. **Titan and Odyssey are dominated by the selected Amazon RTX 5090 asking price.** Stored Scan captures contain £4,599.98 and Computer Orbit £4,399 for a Ventus 5090, but these rows have different CPKs and no commercial-source URL, so the current supplier-offer join cannot use them. Computer Orbit is also outside this particular offer index. `same_product()` only accepts identical normalized titles, embedded exact MPNs, or normalized CPU names: it cannot reliably reconcile differently worded GPU titles without an MPN. This is a supplier coverage/identity limitation, not evidence that a cheaper GPU is currently purchasable.
2. **Current supplier checks do not support replacing the GPU with the historical cheap quotes.** The exact Scan Ventus page currently shows Notify Me without an item price. Overclockers currently shows £10,800 and Out of Stock. Search-engine snapshots showing £4,199.99–£4,559.99 were older and contradicted the opened pages; they were not used as current offers.
3. **Titan has more RAM than its authored requirement.** Its definition asks for 64GB (2×32GB); the selected catalogue option is 128GB (2×64GB) at £2,199. Minimum-capacity matching plus the limited priced range admits the larger kit. Odyssey requires 128GB, so its capacity is intentional, but its supplier selection still needs comparison.
4. **Enterprise's RAM arithmetic is correct but commercially poor.** Four 64GB Micron RDIMMs at £2,999.99 each produce £11,999.96. The exact Scan product page currently confirms that unit price. It is not a fourfold duplication or decimal error. The authored requirement is 256GB; the selected arrangement is 4×64GB rather than the template's 8×32GB. A cheaper 64GB *total* kit is not an equivalent substitute for 256GB. Module arrangement and memory bandwidth should be assessed before changing the configuration.
5. **Enterprise is inherently an expensive specification.** A Threadripper PRO/WRX90 platform, 256GB registered memory and 48GB professional GPU account for most of its cost. A dedicated single-user local-AI machine does not automatically need this platform; the intended model, concurrency and expansion requirements should justify it.
6. **Operating allowances amplify expensive parts.** The pricing function adds 10% of parts as overhead, £36.20 fixed allowances, payment fees 3.15%, warranty reserve 5%, returns reserve 2%, then solves for 10% profit on total cost. Consequently the final suggestion is about 36.5% above parts, not simply parts × 1.10. Enterprise alone carries £2,717.82 allocated overhead. The arithmetic matches the implemented policy; the large cash profit in the heatmap is mostly a consequence of high costs.

## Recommended correction

- Restore Titan's 64GB target using a priced compatible kit; compare Odyssey's required 128GB across suppliers.
- Reconcile exact GPU identities across stored captures using manufacturer model/MPN and retain traceable supplier product URLs. Compare current stock and prices before treating old cheap captures as alternatives.
- Compare equivalent 256GB RDIMM configurations for Enterprise and reassess whether the Threadripper platform is necessary for its intended workload. Do not silently reduce its capability just to lower the price.
- Recalculate pending suggestions after those sourcing/specification changes. Do not invent replacement costs or alter customer checkout prices from this investigation.

## Source checks

- [Scan exact Micron 64GB RDIMM](https://www.scan.co.uk/products/64gb-micron-mtc40f2046s1rc56br-ddr5-5600-rdimm): £2,999.99, in stock; page also lists £5.48 delivery (the existing captured offer has unknown postage).
- [Scan exact MSI RTX 5090 Ventus](https://www.scan.co.uk/products/msi-nvidia-geforce-rtx-5090-ventus-3x-oc-32gb-gddr7-ray-tracing-graphics-card-21760-core-2437-mhz): Notify Me; no current item price exposed.
- [Overclockers exact MSI RTX 5090 Ventus](https://www.overclockers.co.uk/msi-geforce-rtx-5090-ventus-3x-oc-32gb-gddr7-pci-express-graphics-card/GRA-MSI-04859.html): £10,800, out of stock.

The current Amazon kit page was inaccessible through the research tool, so its £2,199 remains a stored observation rather than independently refreshed evidence.

## Completed corrections

| Build | Previous suggestion | Final suggestion | Reduction |
|---|---:|---:|---:|
| Titan | £18,654.15 | £12,836.94 | £5,817.21 |
| Odyssey | £19,453.10 | £15,406.57 | £4,046.53 |
| Enterprise | £37,063.62 | £35,973.90 | £1,089.72 |

- Titan now selects a recorded Crucial 64GB (2×32GB) DDR5-6000 CL40 kit at £739.99 rather than the £2,199 128GB kit. Capacity is corrected; CL30 performance is not claimed for this CL40 kit.
- Titan and Odyssey select a Zotac RTX 5090 Solid OC 32GB at £6,989.99. The existing product parser captured that exact price and InStock structured offer from the supplier page on 24 October; the capture is retained in `sourcing-repair/zotac-current-capture.json`. This is an explicit alternative board meeting the authored GPU-family/VRAM requirement, not an assertion that different manufacturers' cards are the same exact product. Remaining exact-card clearances remain assembly checks.
- Two cheaper Palit product URLs returned HTTP 404, including the initially selected £5,899.99 and £5,999.99 alternatives. They were marked unavailable in DEV with new observations and preserved price history. The final saved suggestions do not use them.
- Enterprise retains the PRO 7975WX, WRX90 motherboard, 256GB ECC RDIMM, RTX 6000 Ada 48GB, large chassis and TR5 cooler. Memory is now eight 32GB Silicon Power DDR5-4800 RDIMMs at £1,399.99 each (£11,199.92 total), rather than four £2,999.99 64GB Micron DIMMs. Capacity is unchanged; module count and full quantity costs are explicit. The advertised module speed changes from 5600 to 4800; BIOS/QVL/SPD settings and sustained performance still need assembly validation.
- Threadripper remains the owner's preferred expandable workstation platform. The current single-GPU model-fitting requirement alone does not establish a need for it or prove team concurrency. Its workstation memory architecture and expansion are deliberate platform choices; no unmeasured multi-user latency or throughput promise is made.
- Exact MSI Ventus board identities now match across CPKs and differently worded titles without merging different cards. Same-listing historical URLs can be recovered without reusing historical prices. Newer captures of the same supplier product supersede older catalogue prices even when prices rise; equal prices prefer the newer evidence. Current available captures outrank stale asks, and known-unavailable alternatives are deprioritised/excluded appropriately.
- The range-gap logic revisits oversized RAM, compares GPU boards within the required family/VRAM specification, recognises RDIMM-only titles and ranks server memory using the complete required quantity. A focused `--cells` rebuild can update named proposals while validating/exporting all 24 cells.
- All 24 suggestions were saved with complete costs, no detected planning-check errors and the existing 10% profit-on-total-cost floor. Rebuilds use stored data and publish no customer offers. The pre-change DEV backup is in `sourcing-repair/before-dev-rebuild.json`; supplier availability changes have separate recovery snapshots and receipts there.

Final component costs: Titan £9,391.61; Odyssey £11,278.17; Enterprise £26,378.16. These remain planning suggestions, not physical performance qualification or checkout publication.
