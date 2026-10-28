# Galileo source evidence — 25 October 2026

These references inform the exact-model draft compatibility assessment. They do not assert a physical assembly test, installed BIOS version, approved supplier condition or publication approval.

| Component | Manufacturer evidence checked | Facts retained for the draft |
|---|---|---|
| AMD Ryzen 5 5600 | [AMD specifications](https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-5-5600.html) | AM4, 65W TDP, Ryzen 5000/Zen 3 identity. It must not be confused with a Zen 5 processor. |
| MSI B550M PRO-VDH WIFI | [MSI specifications](https://www.msi.com/Motherboard/B550M-PRO-VDH-WIFI/Specification) | AM4, micro-ATX, four DDR4 slots, two M.2 slots supporting 2242/2260/2280, four SATA ports. The captured retailer property saying one SATA port conflicts with the primary specification. Exact installed BIOS/CPU support still needs its own evidence. |
| Corsair CMK32GX4M2E3200C16 | [Corsair exact kit](https://www.corsair.com/uk/en/p/memory/cmk32gx4m2e3200c16/vengeance-lpx-32gb-2-x-16gb-ddr4-dram-3200mhz-c16-memory-kit-black-cmk32gx4m2e3200c16), [manufacturer datasheet hosted by distributor](https://www.littlebit.ch/media/productattach/l/1/l1124408.pdf) | Two 16GB DDR4 modules; 34mm module profile from the Corsair-authored datasheet. |
| ASUS DUAL-RTX5050-O8G | [ASUS exact board specifications](https://www.asus.com/ie/motherboards-components/graphics-cards/dual/dual-rtx5050-o8g/techspec/), [NVIDIA GPU reference specifications](https://www.nvidia.com/en-ph/geforce/graphics-cards/50-series/rtx-5050/) | ASUS board length 203mm, 8GB GDDR6, one 8-pin power connector, recommended system PSU 550W. NVIDIA lists reference GPU power of 130W; this is distinct from a measured whole-system load. |
| be quiet! System Power 11 750W | [Manufacturer specifications](https://www.bequiet.com/en/powersupply/5906) | 750W ATX, three PCIe 6+2 connectors and one 12V-2x6 connector. The retailer's conflicting 650W model-name property cannot establish an exact casing dimension. |
| ARCTIC Freezer 36 | [Manufacturer product page](https://www.arctic.de/Freezer-36-Black/ACFRE00123A), [base-model dimensional drawing](https://support.arctic.de/products/freezer-36/techdocs/Freezer%2036%20-%202D%20Drawing.pdf) | Recorded reference height 159mm. The base-model drawing gives separate AMD/Intel clearances; its different part number must be reconciled before treating those clearances as exact evidence for the selected black variant. |
| APNX C1 | [APNX specifications](https://www.apnx.com/product/c1/) | Recorded reference clearances: GPU 395mm, CPU cooler 166mm; supported ATX/micro-ATX/mini-ITX boards. The current selected case must be rechecked if sourcing chooses another model. |

## Data-flow repair

An original `catalogue_identity` supplier suggestion previously replaced the rich source capture with a synthetic price snapshot. The replacement dropped technical properties and exact observation provenance. The service now keeps the original capture and promotes only genuinely different stored supplier offers.

The regression command failed before the change and passed afterwards. A stored-data Galileo rebuild then confirmed 38 CPU, 47 motherboard, 10 RAM, 49 storage, 30 PSU and 31 cooler properties survived selection. Its model input includes the relevant captured fields and separate manufacturer reference facts. Manufacturer references remain distinguishable from reviewed engineering records.

Unknown inbound postage is represented as £0 with `postage_verified=false` and `postage_assumption=owner-approved-zero-fallback`; the component item price is preserved.

## Alternative Windows supply captured

Fresh exact Overclockers product-page captures at 19:52 UTC returned Home OEM DVD **KW9-00632 / SW-18J-MS, £129.95** and Pro OEM DVD **FQC-10528 / SW-18K-MS, £159.95**, both with structured in-stock offers. Buying postage was absent and therefore uses the separately labelled £0 fallback. The raw captures are in `output/playbook-priority-rebuild-20261025/boxed-windows-captures.json`.

These alternatives have not been purchased or substituted into the proposals. The owner's source preference was requested. The current RoyalCDKeys source remains provisional in draft costing. [Microsoft's OEM end-user terms](https://www.microsoft.com/content/dam/microsoft/usetm/documents/windows/11/oem-%28pre-installed%29/UseTerms_OEM_Windows_11_English.pdf) describe device licensing, transfer, activation and installer support; they do not by themselves establish FlipFlop's upstream system-builder distribution agreement.

## Automated evidence resolution update
Exact, field-level primary references are now used by draft deterministic fit checks for MSI B550M PRO-VDH WIFI, ASUS DUAL-RTX5050-O8G, APNX C1, Kingston NV3 2280, System Power 11 750W and Freezer 36. Generic family pages remain planning-only. Automated retailer discrepancies are recorded; conflicts with explicit human-reviewed records remain unresolved. Missing BIOS support, RAM dimensions and cable-clearance evidence are not invented. The exact ARCTIC Black drawing confirms ACFRE00123A RAM clearance: 43.9mm AMD / 42.9mm Intel; the shared check uses the conservative 42.9mm limit. The earlier Corsair-hosted-by-Littlebit document names the white W suffix; it is not promoted as exact black-SKU dimension approval.
Supplier selection now prioritises fresh in-stock new offers over cheaper used offers. Focused deterministic fixtures verify preference, stale-offer handling, exact manufacturer fields and retained conflicts. Full rebuild verification is in progress.
