# Capability-led Playbook matrix — specification 0.2.1

Generated from specifications.json; edit that source and rerun render_validate.py.

Owner-approved direction: customer use case × capability tier. Budget filters suitable offers; selling prices are derived from validated costs and market evidence.

All acceptance thresholds are proposals, all replacement landed costs unknown, all cells blocked from sale.

## Customer benefits

| Customer use case | Essential | Enhanced | Advanced |
|---|---|---|---|
| Student Hybrid | **Study essentials** (FF-STU-01) — Documents, research, video calls and introductory coding on one responsive study desktop; draft_redesign | **Study and gaming** (FF-STU-02) — Study plus validated modern 1080p gaming and greater application concurrency; draft_retain | **Specialist coursework** (FF-STU-03) — Course-specific CAD or media work, routed to a qualified Creator profile; no generic offer proposed; withheld |
| Business & Office | **Everyday office** (FF-BOF-01) — Everyday office work, bookkeeping and video calls across two displays; draft_retain | **Demanding office** (FF-BOF-02) — Larger spreadsheets and more concurrent office applications, subject to measured improvement; draft_conditional | **Specialist business needs** (FF-BOF-03) — Specialist business analysis requires workload intake; no distinct general-office offer established; withheld |
| Family & Home | **Home essentials** (FF-FAM-01) — Shared homework, calls, photos and media with a tested recovery path; draft_retain | **Home and gaming** (FF-FAM-02) — Everyday household use plus modern 1080p gaming and additional active-photo storage; draft_conditional | **Specialist home workloads** (FF-FAM-03) — Specialist home editing or gaming routes to the corresponding profile; no extra general-home offer established; withheld |
| Great-value Gaming | **1080p play** (FF-GVG-01) — Validated native 1080p gaming on the approved title suite; draft_retain | **1440p play** (FF-GVG-02) — Validated native 1440p gaming plus a larger game library; draft_retain | **Fast 1440p play** (FF-GVG-03) — Faster 1440p play; proposed shared offer with High-performance Essential; shared_offer |
| High-performance Gaming | **High-refresh 1440p** (FF-HPG-01) — High-refresh 1440p play on the approved competitive game suite; draft_conditional | **4K gaming** (FF-HPG-02) — Validated 4K raster gaming and high-refresh CPU-limited play; draft_conditional | **Advanced 4K and VR** (FF-HPG-03) — Named advanced 4K ray-traced or VR experience; exact game/headset qualification required; draft_quote_only |
| Content Creation | **Everyday creation** (FF-CCR-01) — Photo work, 1080p editing and light 4K production using proxies; draft_retain | **4K production** (FF-CCR-02) — Routine native 4K editing, more simultaneous production work and faster measured renders; draft_conditional | **Large-scene production** (FF-CCR-03) — Larger GPU-resident scenes and demanding VFX/media projects qualified individually; draft_quote_only |
| AI Workstation | **Personal AI** (FF-AIW-01) — One person uses a responsive private text assistant; draft_conditional | **Advanced AI workspace** (FF-AIW-02) — One person uses a more capable assistant plus a validated image-understanding workflow; draft_conditional | **Team AI server** (FF-AIW-03) — Several people use local AI concurrently with bounded response times; draft_quote_only |
| Software Development | **Application development** (FF-SWD-01) — IDE, local databases and a small Linux-container application stack without a mandatory discrete GPU; draft_retain | **Parallel development** (FF-SWD-02) — More simultaneous containers or VMs and shorter measured builds; draft_conditional | **Local build and test lab** (FF-SWD-03) — A larger sustained local build/test lab with more resident VMs and measured compile improvement; draft_conditional |

## Candidate hardware and commercial status

Legacy labels are compatibility mappings only. Old price experiments remain in the source/history and do not define capability levels. No current selling price has been established.

| Cell | Use case / capability profile | Disposition | CPU / GPU | RAM / internal storage | Derived delivered price |
|---|---|---|---|---|---|
| FF-STU-01 | Student Hybrid / Study essentials | draft_redesign | Ryzen 5 5600G / Integrated Radeon | 16GB / 1TB | Not established |
| FF-STU-02 | Student Hybrid / Study and gaming | draft_retain | Ryzen 5 7600 / RTX 5060 Ti 16GB | 32GB / 1TB | Not established |
| FF-STU-03 | Student Hybrid / Specialist coursework | withheld | Ryzen 7 9700X / RTX 5060 Ti 16GB | 32GB / 2TB | Not established |
| FF-BOF-01 | Business & Office / Everyday office | draft_retain | Ryzen 5 5600G / Integrated Radeon | 16GB / 1TB | Not established |
| FF-BOF-02 | Business & Office / Demanding office | draft_conditional | Ryzen 5 8600G / Integrated Radeon 760M | 32GB / 1TB | Not established |
| FF-BOF-03 | Business & Office / Specialist business needs | withheld | Ryzen 5 8600G / Integrated Radeon 760M | 32GB / 2TB | Not established |
| FF-FAM-01 | Family & Home / Home essentials | draft_retain | Ryzen 5 5600G / Integrated Radeon | 16GB / 1TB | Not established |
| FF-FAM-02 | Family & Home / Home and gaming | draft_conditional | Ryzen 5 7600 / RTX 5060 Ti 16GB | 32GB / 2TB | Not established |
| FF-FAM-03 | Family & Home / Specialist home workloads | withheld | Ryzen 5 8600G / Integrated Radeon 760M | 32GB / 2TB | Not established |
| FF-GVG-01 | Great-value Gaming / 1080p play | draft_retain | Ryzen 5 5600 / RTX 5050 8GB | 16GB / 1TB | Not established |
| FF-GVG-02 | Great-value Gaming / 1440p play | draft_retain | Ryzen 5 7600 / Radeon RX 9060 XT 16GB | 32GB / 2TB | Not established |
| FF-GVG-03 | Great-value Gaming / Fast 1440p play | shared_offer | Ryzen 5 9600X / Radeon RX 9070 16GB | 32GB / 2TB | Not established |
| FF-HPG-01 | High-performance Gaming / High-refresh 1440p | draft_conditional | Ryzen 5 9600X / Radeon RX 9070 16GB | 32GB / 2TB | Not established |
| FF-HPG-02 | High-performance Gaming / 4K gaming | draft_conditional | Ryzen 7 9800X3D / Radeon RX 9070 XT 16GB | 32GB / 2TB | Not established |
| FF-HPG-03 | High-performance Gaming / Advanced 4K and VR | draft_quote_only | Ryzen 7 9800X3D / RTX 5090 32GB | 32GB / 2TB | Not established |
| FF-CCR-01 | Content Creation / Everyday creation | draft_retain | Ryzen 7 9700X / RTX 5060 Ti 16GB | 32GB / 2TB | Not established |
| FF-CCR-02 | Content Creation / 4K production | draft_conditional | Ryzen 9 9900X / RTX 5070 Ti 16GB | 64GB / 4TB | Not established |
| FF-CCR-03 | Content Creation / Large-scene production | draft_quote_only | Ryzen 9 9950X / RTX 5090 32GB | 128GB / 8TB | Not established |
| FF-AIW-01 | AI Workstation / Personal AI | draft_conditional | Ryzen 5 7600 / RTX 5060 Ti 16GB | 32GB / 2TB | Not established |
| FF-AIW-02 | AI Workstation / Advanced AI workspace | draft_conditional | Ryzen 9 9900X / Radeon AI PRO R9700 32GB | 64GB / 4TB | Not established |
| FF-AIW-03 | AI Workstation / Team AI server | draft_quote_only | Threadripper PRO 7975WX / RTX 6000 Ada 48GB | 256GB / 12TB | Not established |
| FF-SWD-01 | Software Development / Application development | draft_retain | Ryzen 5 8600G / Integrated Radeon 760M | 32GB / 1TB | Not established |
| FF-SWD-02 | Software Development / Parallel development | draft_conditional | Ryzen 9 9900X / CPU integrated display graphics | 64GB / 2TB | Not established |
| FF-SWD-03 | Software Development / Local build and test lab | draft_conditional | Ryzen 9 9950X / CPU integrated display graphics | 128GB / 4TB | Not established |

## FF-STU-01 — Student Hybrid / Study essentials

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_redesign**. Owner approved scope on 22 October 2026: Affordable study; remove unevidenced NPU requirement; exact SKU, price, workload promises and runtime publication remain gated.

Customer: General student: documents, research, video calls and introductory coding

Work: General student: documents, research, video calls and introductory coding.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Documents, research, video calls and introductory coding on one responsive study desktop

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 5600G; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Integrated Radeon; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 16GB DDR4 UDIMM; 2x8GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 1TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | MSI B550M PRO-VDH WIFI; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination

Optional upgrades: 32GB matched RAM only if workload needs it; Separately costed backup destination/service.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["549", "649"].

Existing selected-build snapshot (not this proposal): {"parts": "3223.95", "current": "4492.88", "profit": "449.29", "margin": "0.1000004451487687185057246132", "floor10": "4492.88", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "361.06", "0.12": "351.08"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Exact component specification and workload acceptance approval; scope disposition already approved. Review: 2026-10-22 → 2026-11-22.

## FF-STU-02 — Student Hybrid / Study and gaming

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_retain**. Discrete graphics and more concurrency; not a universal study requirement; recommendation only, current cell remains untouched.

Customer: Student who also plays modern games at 1080p

Work: Student who also plays modern games at 1080p.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Study plus validated modern 1080p gaming and greater application concurrency

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 7600; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5060 Ti 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 1TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination
- Pinned game suite: 1080p, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["1099", "1399"].

Existing selected-build snapshot (not this proposal): {"parts": "1837.31", "current": "2649.04", "profit": "317.89", "margin": "0.1200019629752665116419533114", "floor10": "2582.68", "gaps": ["gpu: supplier postage excluded because it is unknown"]}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "760.31", "0.12": "740.33"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-STU-03 — Student Hybrid / Specialist coursework

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **withheld**. Owner approved scope on 22 October 2026: Route to qualified Creator Budget; no generic student High-end need; exact SKU, price, workload promises and runtime publication remain gated.

Customer: Design/engineering student with course-specific applications

Work: Design/engineering student with course-specific applications.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Course-specific CAD or media work, routed to a qualified Creator profile; no generic offer proposed

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 7 9700X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5060 Ti 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: null.

Existing selected-build snapshot (not this proposal): {"parts": "3832.32", "current": "5687.09", "profit": "853.07", "margin": "0.1500011429395349818624287641", "floor10": "5330.96", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Exact component specification and workload acceptance approval; scope disposition already approved. Review: 2026-10-22 → 2026-11-22.

## FF-BOF-01 — Business & Office / Everyday office

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_retain**. Lowest balanced office machine with legitimate Pro licence; recommendation only, current cell remains untouched.

Customer: Small-business office, bookkeeping, browser SaaS and two displays

Work: Small-business office, bookkeeping, browser SaaS and two displays.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Everyday office work, bookkeeping and video calls across two displays

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 5600G; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Integrated Radeon; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 16GB DDR4 UDIMM; 2x8GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 1TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | MSI B550M PRO-VDH WIFI; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Pro; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination

Optional upgrades: 32GB matched RAM only if workload needs it; Separately costed backup destination/service.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["549", "649"].

Existing selected-build snapshot (not this proposal): {"parts": "1526.61", "current": "2154.67", "profit": "215.47", "margin": "0.1000013923245787057878932737", "floor10": "2154.67", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "361.06", "0.12": "351.08"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-BOF-02 — Business & Office / Demanding office

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_conditional**. More working memory and serviceable AM5 platform; require workload improvement; recommendation only, current cell remains untouched.

Customer: Large spreadsheet and concurrent office application user

Work: Large spreadsheet and concurrent office application user.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Larger spreadsheets and more concurrent office applications, subject to measured improvement

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 8600G; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Integrated Radeon 760M; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 1TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Pro; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination
- Demanding office benefit: Approved anonymised >=100MB workbook plus call/browser fixture: median full recalculation at least 20% faster than enabled Everyday office candidate across 3 runs, zero errors; exact formula/data fixture hash required

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["749", "949"].

Existing selected-build snapshot (not this proposal): {"parts": "1645.19", "current": "2377.56", "profit": "285.31", "margin": "0.1200011776779555510691633439", "floor10": "2317.99", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "506.25", "0.12": "492.63"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-BOF-03 — Business & Office / Specialist business needs

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **withheld**. Owner approved scope on 22 October 2026: Size/finish is a preference, not proof of an improved office workload tier; exact SKU, price, workload promises and runtime publication remain gated.

Customer: Premium office buyer; demanding data work needs separate workstation sizing

Work: Premium office buyer; demanding data work needs separate workstation sizing.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Specialist business analysis requires workload intake; no distinct general-office offer established

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 8600G; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Integrated Radeon 760M; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Pro; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: null.

Existing selected-build snapshot (not this proposal): {"parts": "3225.62", "current": "4795.46", "profit": "719.32", "margin": "0.1500002085305684960358338929", "floor10": "4495.18", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Exact component specification and workload acceptance approval; scope disposition already approved. Review: 2026-10-22 → 2026-11-22.

## FF-FAM-01 — Family & Home / Home essentials

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_retain**. Simple everyday family PC without gaming premium; recommendation only, current cell remains untouched.

Customer: Shared household homework, calls, photos and media

Work: Shared household homework, calls, photos and media.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Shared homework, calls, photos and media with a tested recovery path

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 5600G; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Integrated Radeon; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 16GB DDR4 UDIMM; 2x8GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 1TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | MSI B550M PRO-VDH WIFI; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination

Optional upgrades: 32GB matched RAM only if workload needs it; Separately costed backup destination/service.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["549", "649"].

Existing selected-build snapshot (not this proposal): {"parts": "1524.94", "current": "2152.35", "profit": "215.24", "margin": "0.1000023230422561386391618464", "floor10": "2152.35", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "361.06", "0.12": "351.08"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-FAM-02 — Family & Home / Home and gaming

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_conditional**. Gaming capability and more active-photo storage; share gaming hardware platform; recommendation only, current cell remains untouched.

Customer: Household explicitly requesting modern 1080p gaming

Work: Household explicitly requesting modern 1080p gaming.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Everyday household use plus modern 1080p gaming and additional active-photo storage

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 7600; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5060 Ti 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination
- Pinned game suite: 1080p, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["1199", "1499"].

Existing selected-build snapshot (not this proposal): {"parts": "2032.43", "current": "2924.72", "profit": "350.97", "margin": "0.1200012308870592740501654859", "floor10": "2851.47", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "832.91", "0.12": "811.11"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-FAM-03 — Family & Home / Specialist home workloads

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **withheld**. Owner approved scope on 22 October 2026: Use optional backup/storage or a qualified gaming/creator cell instead; exact SKU, price, workload promises and runtime publication remain gated.

Customer: Premium home media buyer

Work: Premium home media buyer.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Specialist home editing or gaming routes to the corresponding profile; no extra general-home offer established

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 8600G; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Integrated Radeon 760M; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Office/study fixture: 20 fixed browser tabs + 1080p call + document + 25MB workbook for 30min; zero app errors, p95 foreground switch <=1s, peak committed working set <=85% physical RAM
- Displays and recovery: Two simultaneous 1080p60 displays with verified physical outputs; 10 sleep/wake cycles pass; restore a 1GB test folder byte-identically to separate backup destination

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: null.

Existing selected-build snapshot (not this proposal): {"parts": "4446.21", "current": "6589.26", "profit": "988.39", "margin": "0.1500001517621098575560836877", "floor10": "6176.66", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Exact component specification and workload acceptance approval; scope disposition already approved. Review: 2026-10-22 → 2026-11-22.

## FF-GVG-01 — Great-value Gaming / 1080p play

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_retain**. Entry 1080p raster gaming; 32GB optional where measured; recommendation only, current cell remains untouched.

Customer: First gaming PC, esports and 1080p single-player games

Work: First gaming PC, esports and 1080p single-player games.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Validated native 1080p gaming on the approved title suite

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 5600; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5050 8GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 16GB DDR4 UDIMM; 2x8GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 1TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | MSI B550M PRO-VDH WIFI; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Pinned game suite: 1080p, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["899", "1099"].

Existing selected-build snapshot (not this proposal): {"parts": "1026.87", "current": null, "profit": null, "margin": null, "floor10": null, "gaps": ["gpu: supplier item price unknown", "gpu: supplier postage excluded because it is unknown"]}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "615.13", "0.12": "598.79"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-GVG-02 — Great-value Gaming / 1440p play

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_retain**. 1440p capability, VRAM and game-library capacity; recommendation only, current cell remains untouched.

Customer: Value-focused 1440p gamer

Work: Value-focused 1440p gamer.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Validated native 1440p gaming plus a larger game library

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 7600; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Radeon RX 9060 XT 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Pinned game suite: 1440p, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["1299", "1599"].

Existing selected-build snapshot (not this proposal): {"parts": "2012.43", "current": "2896.46", "profit": "347.58", "margin": "0.1200016571953349951319887035", "floor10": "2823.92", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "905.50", "0.12": "881.88"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-GVG-03 — Great-value Gaming / Fast 1440p play

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **shared_offer**. Owner approved scope on 22 October 2026: Merge into HPG Budget after comparison; avoid duplicate overlapping offers; exact SKU, price, workload promises and runtime publication remain gated. Share the FF-HPG-01 BOM and retain this customer entry point and ID.

Customer: Higher-refresh 1440p player

Work: Higher-refresh 1440p player.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Faster 1440p play; proposed shared offer with High-performance Essential

Architecture: socketed x86-64 desktop; ATX airflow tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 9600X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Radeon RX 9070 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM850e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Fractal Pop Air; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Pinned game suite: 1440p, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: null.

Existing selected-build snapshot (not this proposal): {"parts": "2219.30", "current": "3316.57", "profit": "497.49", "margin": "0.1500013568234652065236072207", "floor10": "3108.88", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Exact component specification and workload acceptance approval; scope disposition already approved. Review: 2026-10-22 → 2026-11-22.

## FF-HPG-01 — High-performance Gaming / High-refresh 1440p

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_conditional**. Owner approved scope on 22 October 2026: Higher native raster performance than GVG Mid; RT preference separately qualified; exact SKU, price, workload promises and runtime publication remain gated.

Customer: High-refresh 1440p raster gamer

Work: High-refresh 1440p raster gamer.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: High-refresh 1440p play on the approved competitive game suite

Architecture: socketed x86-64 desktop; ATX airflow tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 9600X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Radeon RX 9070 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM850e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Fractal Pop Air; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Pinned game suite: 1440p, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["1699", "2099"].

Existing selected-build snapshot (not this proposal): {"parts": "2135.88", "current": "2993.96", "profit": "299.40", "margin": "0.1000013360231933626367753744", "floor10": "2993.96", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "1195.86", "0.12": "1164.97"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Exact component specification and workload acceptance approval; scope disposition already approved. Review: 2026-10-22 → 2026-11-22.

## FF-HPG-02 — High-performance Gaming / 4K gaming

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_conditional**. Higher native rendering target and CPU headroom; aesthetics optional; recommendation only, current cell remains untouched.

Customer: 4K raster or CPU-limited high-refresh gamer

Work: 4K raster or CPU-limited high-refresh gamer.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Validated 4K raster gaming and high-refresh CPU-limited play

Architecture: socketed x86-64 desktop; ATX airflow tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 7 9800X3D; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Radeon RX 9070 XT 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM850e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Phantom Spirit 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Fractal Pop Air; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Pinned game suite: 4K, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["2199", "2799"].

Existing selected-build snapshot (not this proposal): {"parts": "2330.84", "current": "3346.37", "profit": "401.57", "margin": "0.1200016734551170372672477939", "floor10": "3262.56", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "1558.81", "0.12": "1518.83"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-HPG-03 — High-performance Gaming / Advanced 4K and VR

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **draft_quote_only**. Validate named game/headset benefit before expensive GPU; quote only; recommendation only, current cell remains untouched.

Customer: Specific 4K ray-traced high-refresh or VR customer

Work: Specific 4K ray-traced high-refresh or VR customer.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Named advanced 4K ray-traced or VR experience; exact game/headset qualification required

Architecture: socketed x86-64 desktop; ATX airflow tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 7 9800X3D; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5090 32GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM1200x; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Phantom Spirit 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Fractal Pop Air; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Pinned game suite: 4K, fixed high preset, RT off, native rendering, frame generation off; >=60 mean FPS and >=45 1% low in 3 repeats per title; HPG additionally >=120/90 in chosen esports fixture. Names/builds must be approved before testing

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: null.

Existing selected-build snapshot (not this proposal): {"parts": "10804.78", "current": null, "profit": null, "margin": null, "floor10": null, "gaps": ["psu: no selected catalogue component", "gpu: supplier postage excluded because it is unknown"]}

Affordable landed-parts ceilings at the lower trial price: {}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-CCR-01 — Content Creation / Everyday creation

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_retain**. Reliable entry production workflow; specific codecs checked; recommendation only, current cell remains untouched.

Customer: Photo, 1080p production and light 4K editor using proxies

Work: Photo, 1080p production and light 4K editor using proxies.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Photo work, 1080p editing and light 4K production using proxies

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 7 9700X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5060 Ti 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Creator fixture: 1080p/light-4K proxy 10-minute H.264 8-bit 4:2:0 30fps timeline with three defined effects: <=1% playback drops after cache warmup; export <=timeline duration; fixed Blender scene fits GPU without fallback. Higher bit depth/6K/8K and plugins need separate tests

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["1499", "1899"].

Existing selected-build snapshot (not this proposal): {"parts": "3733.29", "current": "5194.54", "profit": "519.46", "margin": "0.1000011550589657602020583151", "floor10": "5194.54", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "1050.68", "0.12": "1023.42"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-CCR-02 — Content Creation / 4K production

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_conditional**. More project concurrency and shorter measured renders; recommendation only, current cell remains untouched.

Customer: Working 4K editor and moderate Blender renderer

Work: Working 4K editor and moderate Blender renderer.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Routine native 4K editing, more simultaneous production work and faster measured renders

Architecture: socketed x86-64 desktop; ATX airflow tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 9 9900X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5070 Ti 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 64GB DDR5 UDIMM; 2x32GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 4TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM850e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Phantom Spirit 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Fractal Pop Air; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Creator fixture: 4K native 10-minute H.264 8-bit 4:2:0 30fps timeline with three defined effects: <=1% playback drops after cache warmup; export <=timeline duration; fixed Blender scene fits GPU without fallback. Higher bit depth/6K/8K and plugins need separate tests

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["2499", "3299"].

Existing selected-build snapshot (not this proposal): {"parts": "4777.09", "current": "6802.85", "profit": "816.35", "margin": "0.1200011759777152222965374806", "floor10": "6632.46", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "1776.59", "0.12": "1731.15"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-CCR-03 — Content Creation / Large-scene production

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **draft_quote_only**. More scene fit and sustained throughput; do not promise universal 8K; recommendation only, current cell remains untouched.

Customer: Heavy VFX, large Blender scenes or demanding footage with measured need

Work: Heavy VFX, large Blender scenes or demanding footage with measured need.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Larger GPU-resident scenes and demanding VFX/media projects qualified individually

Architecture: socketed x86-64 desktop; ATX airflow tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 9 9950X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5090 32GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 128GB DDR5 UDIMM; 2x64GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 4TB internal NVMe boot/project + 4TB internal NVMe scratch; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM1200x; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Phantom Spirit 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Fractal Pop Air; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Home; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Creator fixture: 4K native 10-minute H.264 8-bit 4:2:0 30fps timeline with three defined effects: <=1% playback drops after cache warmup; export <=timeline duration; fixed Blender scene fits GPU without fallback. Higher bit depth/6K/8K and plugins need separate tests

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: null.

Existing selected-build snapshot (not this proposal): {"parts": "12257.49", "current": null, "profit": null, "margin": null, "floor10": null, "gaps": ["psu: no selected catalogue component", "gpu: supplier postage excluded because it is unknown"]}

Affordable landed-parts ceilings at the lower trial price: {}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-AIW-01 — AI Workstation / Personal AI

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_conditional**. One person uses a responsive private text assistant; capability direction approved, exact service profile and hardware remain proposals.

Customer: One person uses a responsive private text assistant

Work: One person uses a responsive private text assistant.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: One person uses a responsive private text assistant

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 7600; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 5060 Ti 16GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | AMD boxed Wraith Stealth where included; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Ubuntu 24.04 LTS; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Capability-specific local inference under load: Pinned licensed model/hash, quantisation and runtime; 1 simultaneous request(s), 4096 context tokens each; >=10 generation tokens/s per request, p95 first token <=5s on 512-token prompt; 60 minutes with zero OOM and intended GPU residency. Model quality rubric must pass; no frontier-model promise.

AI service profile (proposed; no measured promise):

- customer_outcome: "One person uses a responsive private text assistant"
- modalities: ["text"]
- interactive_users: 1
- simultaneous_requests: 1
- resident_model_count: null
- model_size_guidance: "7-8B quantised text model candidate"
- model_id: null
- model_hash: null
- quantisation: null
- runtime_version: null
- model_licence: null
- context_tokens_per_request: 4096
- generation_tokens_per_second_per_request_min: 10
- first_token_seconds_p95_max: 5
- test_prompt_tokens: 512
- sustained_test_minutes: 60
- multimodal_test: "Not required for this profile; may be supported by an individually validated model"
- quality_evaluation: "Named held-out customer-task fixture, baseline comparison, scoring rubric and pass threshold remain to be approved; parameter count does not establish quality"
- all_thresholds_status: "proposed_not_measured"
- memory_gate: "Include weights, KV cache, vision encoder, context and concurrency; zero OOM, required GPU residency and validated backend"
- frontier_model_claim: false
- cloud_inference: "not included; separately disclosed service if ever offered"
- concurrency_note: "Downloaded models, resident models, simultaneous requests and users are distinct; more VRAM alone proves none of these"

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["1599", "2099"].

Existing selected-build snapshot (not this proposal): {"parts": "3878.10", "current": "5394.04", "profit": "539.41", "margin": "0.1000011123388035683828818474", "floor10": "5394.04", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "1123.27", "0.12": "1094.20"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes; Exact model/runtime/licence and quality evaluation; image fixture for Enhanced/Advanced; Verify proposed concurrency and latency on actual BOM; redesign if capacity is insufficient. Review: 2026-10-22 → 2026-11-22.

## FF-AIW-02 — AI Workstation / Advanced AI workspace

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_conditional**. One person uses a more capable assistant plus a validated image-understanding workflow; capability direction approved, exact service profile and hardware remain proposals.

Customer: One person uses a more capable assistant plus a validated image-understanding workflow

Work: One person uses a more capable assistant plus a validated image-understanding workflow.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: One person uses a more capable assistant plus a validated image-understanding workflow

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 9 9900X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Radeon AI PRO R9700 32GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 64GB DDR5 UDIMM; 2x32GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 4TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair RM650e; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Phantom Spirit 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Ubuntu 24.04 LTS; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Capability-specific local inference under load: Pinned licensed model/hash, quantisation and runtime; 1 simultaneous request(s), 4096 context tokens each; >=10 generation tokens/s per request, p95 first token <=5s on 512-token prompt; 60 minutes with zero OOM and intended GPU residency. Model quality rubric must pass; no frontier-model promise.
- Image understanding and text coexistence: Pin licensed 100-image fixture and task-specific quality threshold before approval; test latency and memory while text service remains active; no claim until model licence, backend, encoder fit and output quality pass

AI service profile (proposed; no measured promise):

- customer_outcome: "One person uses a more capable assistant plus a validated image-understanding workflow"
- modalities: ["text", "image_understanding"]
- interactive_users: 1
- simultaneous_requests: 1
- resident_model_count: null
- model_size_guidance: "20-32B quantised model candidate with separately validated vision profile"
- model_id: null
- model_hash: null
- quantisation: null
- runtime_version: null
- model_licence: null
- context_tokens_per_request: 4096
- generation_tokens_per_second_per_request_min: 10
- first_token_seconds_p95_max: 5
- test_prompt_tokens: 512
- sustained_test_minutes: 60
- multimodal_test: "Pin licensed 100-image fixture and task-specific quality threshold before approval; test latency and memory while text service remains active"
- quality_evaluation: "Named held-out customer-task fixture, baseline comparison, scoring rubric and pass threshold remain to be approved; parameter count does not establish quality"
- all_thresholds_status: "proposed_not_measured"
- memory_gate: "Include weights, KV cache, vision encoder, context and concurrency; zero OOM, required GPU residency and validated backend"
- frontier_model_claim: false
- cloud_inference: "not included; separately disclosed service if ever offered"
- concurrency_note: "Downloaded models, resident models, simultaneous requests and users are distinct; more VRAM alone proves none of these"

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["3499", "4999"].

Existing selected-build snapshot (not this proposal): {"parts": "11808.10", "current": "16737.48", "profit": "2008.50", "margin": "0.1200001433907613332472988765", "floor10": "16318.26", "gaps": ["gpu: supplier postage excluded because it is unknown"]}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "2502.50", "0.12": "2438.88"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes; Exact model/runtime/licence and quality evaluation; image fixture for Enhanced/Advanced; Verify proposed concurrency and latency on actual BOM; redesign if capacity is insufficient. Review: 2026-10-22 → 2026-11-22.

## FF-AIW-03 — AI Workstation / Team AI server

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **draft_quote_only**. Several people use local AI concurrently with bounded response times; capability direction approved, exact service profile and hardware remain proposals.

Customer: Several people use local AI concurrently with bounded response times

Work: Several people use local AI concurrently with bounded response times.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: Several people use local AI concurrently with bounded response times

Architecture: socketed x86-64 workstation; SSI-EEB full tower; exact board/case support pending.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Threadripper PRO 7975WX; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | RTX 6000 Ada 48GB; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 256GB DDR5 ECC RDIMM; 8x32GB validated kit; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 4TB internal NVMe boot + 8TB internal SATA data SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASUS Pro WS WRX90E-SAGE SE; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | Corsair AX1600i; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Noctua NH-U14S TR5-SP6; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Corsair 9000D Airflow; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Ubuntu 24.04 LTS; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Capability-specific local inference under load: Pinned licensed model/hash, quantisation and runtime; 3 simultaneous request(s), 4096 context tokens each; >=10 generation tokens/s per request, p95 first token <=5s on 512-token prompt; 60 minutes with zero OOM and intended GPU residency. Model quality rubric must pass; no frontier-model promise.
- Image understanding and text coexistence: Pin licensed 100-image fixture and task-specific quality threshold before approval; test latency and memory while text service remains active; no claim until model licence, backend, encoder fit and output quality pass

AI service profile (proposed; no measured promise):

- customer_outcome: "Several people use local AI concurrently with bounded response times"
- modalities: ["text", "image_understanding"]
- interactive_users: 3
- simultaneous_requests: 3
- resident_model_count: null
- model_size_guidance: "Explicitly selected model fitting validated dedicated memory under concurrent load"
- model_id: null
- model_hash: null
- quantisation: null
- runtime_version: null
- model_licence: null
- context_tokens_per_request: 4096
- generation_tokens_per_second_per_request_min: 10
- first_token_seconds_p95_max: 5
- test_prompt_tokens: 512
- sustained_test_minutes: 60
- multimodal_test: "Pin licensed 100-image fixture and task-specific quality threshold before approval; test latency and memory while text service remains active"
- quality_evaluation: "Named held-out customer-task fixture, baseline comparison, scoring rubric and pass threshold remain to be approved; parameter count does not establish quality"
- all_thresholds_status: "proposed_not_measured"
- memory_gate: "Include weights, KV cache, vision encoder, context and concurrency; zero OOM, required GPU residency and validated backend"
- frontier_model_claim: false
- cloud_inference: "not included; separately disclosed service if ever offered"
- concurrency_note: "Downloaded models, resident models, simultaneous requests and users are distinct; more VRAM alone proves none of these"

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: null.

Existing selected-build snapshot (not this proposal): {"parts": "1265.11", "current": null, "profit": null, "margin": null, "floor10": null, "gaps": ["cpu: no selected catalogue component", "gpu: no selected catalogue component", "psu: no selected catalogue component", "ram: no selected catalogue component", "storage_secondary: no selected catalogue component"]}

Affordable landed-parts ceilings at the lower trial price: {}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes; Exact model/runtime/licence and quality evaluation; image fixture for Enhanced/Advanced; Verify proposed concurrency and latency on actual BOM; redesign if capacity is insufficient. Review: 2026-10-22 → 2026-11-22.

## FF-SWD-01 — Software Development / Application development

Capability level: essential; legacy mapping: Budget (unchanged operational policy).

Disposition: **draft_retain**. Serviceable CPU/RAM-focused development; remove compulsory GPU; recommendation only, current cell remains untouched.

Customer: Web/application developer running IDE, databases and Linux containers

Work: Web/application developer running IDE, databases and Linux containers.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: IDE, local databases and a small Linux-container application stack without a mandatory discrete GPU

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 5 8600G; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | Integrated Radeon 760M; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 32GB DDR5 UDIMM; 2x16GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 1TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Assassin X 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Pro; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Reproducible developer fixture: 4 declared services plus IDE/test runner; zero OOM, peak resident memory <=85%; fixed cold/warm build commands and repo hash recorded. Mid/High must improve prior enabled tier cold build median by >=20% across 3 runs; absolute time target awaits fixture approval

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["899", "1199"].

Existing selected-build snapshot (not this proposal): {"parts": "3537.99", "current": "4925.49", "profit": "492.55", "margin": "0.1000002030254857892311221828", "floor10": "4925.49", "gaps": ["gpu: supplier postage excluded because it is unknown"]}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "615.13", "0.12": "598.79"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-SWD-02 — Software Development / Parallel development

Capability level: enhanced; legacy mapping: Mid-range (unchanged operational policy).

Disposition: **draft_conditional**. More build parallelism and resident VM capacity; no default AI GPU; recommendation only, current cell remains untouched.

Customer: Larger codebase builds and concurrent containers/VMs

Work: Larger codebase builds and concurrent containers/VMs.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: More simultaneous containers or VMs and shorter measured builds

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 9 9900X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | CPU integrated display graphics; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 64GB DDR5 UDIMM; 2x32GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 2TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Phantom Spirit 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Montech AIR 100; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Pro; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Reproducible developer fixture: 8 declared services plus IDE/test runner; zero OOM, peak resident memory <=85%; fixed cold/warm build commands and repo hash recorded. Mid/High must improve prior enabled tier cold build median by >=20% across 3 runs; absolute time target awaits fixture approval

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["1499", "1999"].

Existing selected-build snapshot (not this proposal): {"parts": "3522.98", "current": "5030.83", "profit": "603.70", "margin": "0.1200000795097429251236873438", "floor10": "4904.83", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "1050.68", "0.12": "1023.42"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.

## FF-SWD-03 — Software Development / Local build and test lab

Capability level: advanced; legacy mapping: High-end (unchanged operational policy).

Disposition: **draft_conditional**. Additional measured compile throughput and memory; local-AI upsell separate; recommendation only, current cell remains untouched.

Customer: Large parallel builds and sustained local VM/test lab

Work: Large parallel builds and sustained local VM/test lab.

Excludes: Unqualified CAD certification, heavy AI training and gaming promises outside specified fixture; Monitor/peripherals and paid application subscriptions not included; explicitly normalise competitor bundles.

Tier benefit: A larger sustained local build/test lab with more resident VMs and measured compile improvement

Architecture: socketed x86-64 desktop; serviceable mATX closed tower.

| Role | Current proposed product / permitted alternative | Quoted landed price |
|---|---|---|
| cpu | Ryzen 9 9950X; alternatives: Same socket, graphics/virtualisation features and passed workload fixture; no mobile/OEM substitution | Unknown |
| gpu | CPU integrated display graphics; alternatives: Same validated runtime/API, dedicated VRAM floor, codec/output capabilities and workload pass; no AMD/NVIDIA cross-swap without new specification review | Unknown |
| ram | 128GB DDR5 UDIMM; 2x64GB; alternatives: Same generation, UDIMM/RDIMM/ECC class and validated capacity/topology; no SO-DIMM/LPDDR substitution | Unknown |
| storage | 4TB internal NVMe PCIe SSD; alternatives: WD Blue SN580 or equivalent internal NVMe where exact capacity/endurance/fit supported; secondary SATA role stays SATA | Unknown |
| motherboard | ASRock B650M Pro RS WiFi; alternatives: Least-cost same-socket board with verified BIOS, display outputs, slots, VRM and required I/O; no premium chipset prerequisite | Unknown |
| psu | 450–550W independently reviewed Gold ATX unit; exact SKU open; alternatives: Independently reviewed Gold unit meeting exact GPU vendor power/transient/connectors and fit; wattage alone insufficient | Unknown |
| cooling | Thermalright Phantom Spirit 120 SE; alternatives: Socket/height/RAM-clearance compatible air cooler passing sustained thermal/noise test; AIO not inherently required | Unknown |
| case | Fractal Pop Air; alternatives: Least-cost compatible ventilated closed mATX/ATX case with included fans; no open mining/test frame | Unknown |
| os | Windows 11 Pro; alternatives: Reviewed supported Ubuntu option with customer app/driver confirmation; Windows edition and legitimate licence rights cannot silently change | Unknown |

Proposed acceptance (not measured):

- Common safety and sustained operation: 60-minute concurrent CPU/GPU or iGPU workload: zero errors, no shutdown or sustained thermal-limit throttling; memory test zero errors
- Acoustics: At 1m in <=25dBA ambient: <=30dBA idle and <=40dBA workload (<=45dBA for quote-only GPU workstation); exact method and meter recorded
- Reproducible developer fixture: 12 declared services plus IDE/test runner; zero OOM, peak resident memory <=85%; fixed cold/warm build commands and repo hash recorded. Mid/High must improve prior enabled tier cold build median by >=20% across 3 runs; absolute time target awaits fixture approval

Optional upgrades: Extra internal storage with separate backup plan; Workload-qualified memory/GPU upgrade; requires whole-system retest and repricing.

Substitution: All required capabilities AND exact compatibility must pass; benchmark score or larger capacity alone is insufficient; Cheapest adequate delivered candidate within required arrival window; do not buy unnecessary capacity to save one day; Preserve socket/form factor, memory class, drive role/interface, runtime/API, dedicated VRAM, licence and measured noise/power limits; OEM/mini-PC, ECC/professional GPU and Linux/Windows architecture changes require new spec review; never infer support from model family.

Commercial: blocked: exact component prices/postage/stock/licensing, workload results and matched delivered comparisons absent. Selling price is not established. Historical price experiments are unvalidated positioning assumptions, not market ranges or tier definitions.

Archived 0.1.0 price experiment: ["2299", "3099"].

Existing selected-build snapshot (not this proposal): {"parts": "6307.47", "current": "9324.57", "profit": "1398.69", "margin": "0.1500004825959802972147777324", "floor10": "8740.69", "gaps": []}

Affordable landed-parts ceilings at the lower trial price: {"0.10": "1631.41", "0.12": "1589.61"}; these are budgets, not supplier costs.

Evidence IDs: BASE, POLICY, FLOORS, SNAPSHOT, HW, RETAIL, MARKET-AUDIT, DESIGN, CAPABILITY-DECISION. Confidence: medium workload architecture; low product choice/commercial feasibility; no measured system performance.

Questions: Exact SKU/firmware/fit and landed supplier quotes; Approved workload fixtures and measured pass results; Matched complete delivered price and demand evidence; Owner approval of disposition and specification changes. Review: 2026-10-22 → 2026-11-22.
