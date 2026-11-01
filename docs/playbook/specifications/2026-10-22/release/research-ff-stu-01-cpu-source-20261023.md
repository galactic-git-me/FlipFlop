# FF-STU-01 CPU source recheck

Observed: 2026-10-23 (web pages opened directly; UK retail pages; no account or order activity).

Scope: resolve the standalone CPU sourcing lead for FF-STU-01, whose draft profile specifies a Ryzen 5 5600G, integrated Radeon graphics, and an MSI B550M PRO-VDH WIFI motherboard. This is source research only. It does not alter the catalogue, BOM, approval state, runtime definitions, or storefront.

## Verified from first-party sources

- AMD identifies the Ryzen 5 5600G as a boxed AM4 desktop CPU with 6 cores/12 threads, base/boost clocks of 3.9/4.4 GHz, 65 W default TDP, Radeon graphics (7 graphics cores at 1900 MHz), and a bundled Wraith Stealth cooler. Its boxed part number is **100-100000252BOX**. [AMD product specification](https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-5-5600g.html)
- PC Upgrade's live product page names the exact boxed part number **100-100000252BOX**, condition new, marks it **In Stock**, and lists **£164.39 including VAT** (£136.99 excluding VAT). The same page identifies the AM4 socket, integrated Radeon graphics, and included Wraith Stealth. This is a valid current retailer lead for the selected CPU, not a landed BOM cost. [PC Upgrade product page](https://www.pcupgrade.co.uk/components/cpu-processors/amd-ryzen-5-5600g-3-9ghz-6-core-socket-am4-cpu/)
- PC Upgrade's delivery policy states that most UK orders processed before 3 pm on working days ship the same day and most UK addresses receive them the next working day. It says non-mainland destinations can incur extra charges/delay; its published rate text gives the method (flat rate up to 10 kg) but no numeric rate. Therefore neither the exact postage nor the exact destination ETA is established. [PC Upgrade delivery policy](https://www.pcupgrade.co.uk/delivery-policy/)
- MSI's manufacturer page identifies the exact proposed board, **B550M PRO-VDH WIFI**, as supporting Ryzen 5000 desktop processors and advertises a Flash BIOS Button that can update BIOS without installing a CPU, memory, or graphics card. MSI support notes that CPU model support can depend on BIOS. [MSI board page](https://www.msi.com/Motherboard/B550M-PRO-VDH-WIFI.html), [MSI CPU compatibility guidance](https://www.msi.com/support/technical_details/MB_CPU_Upgrade_Installation)
- MSI's support page currently exposes BIOS package **7C95v2P2**, dated 2026-08-31, for this board. The support content available in this research view does not expose a model-level 5600G minimum-BIOS row. [MSI board support page](https://www.msi.com/Motherboard/B550M-PRO-VDH-WIFI/support)

## Not verified

- Exact 5600G minimum BIOS for the board's specific hardware revision, and the BIOS actually installed on any unit intended for the build. The retailer's generic advice is to update B550 to the latest BIOS; it is not a model-specific compatibility record. The physical revision and production source of the motherboard also remain unspecified in this CPU investigation.
- Numeric CPU postage, postcode-specific delivery cost, and a guaranteed fulfilment/delivery date. General next-working-day policy is not an order-specific promise.
- A product record linking this exact source to the FlipFlop CPU catalogue role. The just-observed retailer stock does not itself change the automated readiness result.
- The exact assembled build's workload, stability, dual-display, thermals, noise, or other proposed acceptance evidence.

## Disposition

The earlier statement that no viable standalone supplier listing was available is superseded for sourcing research: PC Upgrade presently advertises the precise new boxed 5600G SKU at £164.39 inc VAT and in stock. Treat it as a **current source lead**, not a qualified or approved CPU selection. Refresh/import it through the normal evidence path, determine numeric freight for the intended destination, and confirm the board revision plus the 5600G-supporting BIOS before this component can clear compatibility and landed-cost gates. Do not substitute another CPU or publish the cell from this note.

### Direct observations from other retailer pages

- AWD-IT's direct page showed the same 5600G family at £159.99 including VAT but **Out of stock**; it is not a purchasable alternative at this observation. [AWD-IT product page](https://www.awd-it.co.uk/amd-ryzen-5-5600g-six-core-4-4ghz-cpu-radeon-vega-7-graphics-processor-socket-am4.html)
- Box's direct listing showed £151.99 and **Out Of Stock**. [Box product page](https://box.co.uk/100-100000252box-amd-ryzen-5-5600g-zen-3-processor)

These pages support only their displayed stock/price state; no basket, account, checkout, or purchase was attempted.
