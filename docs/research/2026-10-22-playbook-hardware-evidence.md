# Playbook hardware and workload evidence — 22 October 2026

**Status:** Research and proposed validation; not approved specifications or customer performance claims. **Observed:** 22 October 2026, Europe/London. **Scope:** All eight current segments, with Student Hybrid, Business & Office and Family & Home reviewed first. No live catalogue, offers, source definitions or publication rules changed.

The current cell identities and specifications come from [Current Curated Playbook](../playbook/current-curated-playbook.md). Product constraints come from [catalogue rules](../product/catalogues-playbooks-and-fulfilment.md). These define the baseline, not evidence that every selected part is purchasable or compatible. The recommendations below are product architecture judgements derived from the cited software requirements; they are not measured performance findings.

## Evidence register

All URLs below were consulted through live search on the observation date. Search extracts establish the limited facts stated here; complete version-specific requirements must be recaptured before approving an exact system. No FlipFlop system was benchmarked in this research.

| ID | Primary source | Verified source fact | What it does not prove |
|---|---|---|---|
| E1 | [Microsoft Windows 11 specifications](https://www.microsoft.com/en-us/windows/windows-11-specifications) | Windows 11 minimum memory is 4GB. Copilot+ is a separate hardware class requiring a qualifying NPU above 40 TOPS, with additional requirements. | That minimum RAM delivers a good multitasking experience; that any CPU branded AI supports every Copilot+ experience. |
| E2 | [Microsoft Office suites requirements](https://support.microsoft.com/en-us/office/system-requirements/office-suites-for-enterprise-business-education-and-government) | Microsoft lists 4GB RAM for supported Windows Office configurations. | That heavy Excel models or concurrent meetings/browser use have the same needs as launching Office. |
| E3 | [AMD Ryzen AI 5 340](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-5-340.html) and [AMD announcement](https://ir.amd.com/news-events/press-releases/detail/1232/amd-announces-expanded-consumer-and-commercial-ai-pc-portfolio-at-ces) | AI 5 340 is a mobile-class part with Radeon 840M, six cores/twelve threads and up to 50 NPU TOPS. | A retail socketed desktop CPU or a verified complete mini-PC BOM. |
| E4 | [ASUS NUC 14 Pro UK specifications](https://www.asus.com/uk/displays-desktops/nucs/nuc-mini-pcs/asus-nuc-14-pro/techspec/) | NUC 14 Pro configurations use Intel processors, including Core Ultra. | Compatibility of an AMD AI 5 340 with a NUC 14 Pro mainboard or chassis assembly. |
| E5 | [AMD Ryzen 5 5600G specifications](https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-5-5600g.html) | Six cores/twelve threads, AM4, DDR4 up to 3200 MT/s, integrated Radeon graphics, PCIe 3.0. | PCIe 4.0 operation simply because the installed SSD is marketed as Gen4; measured gaming suitability. |
| E6 | [Adobe Premiere technical requirements](https://helpx.adobe.com/premiere/desktop/get-started/technical-requirements/adobe-premiere-pro-technical-requirements.html) | Adobe recommends 32GB or more RAM for 4K and above and 8GB GPU memory in the referenced requirements. | Every codec, effect chain or 8K workflow running smoothly; export speed on a selected BOM. |
| E7 | [Blender requirements](https://www.blender.org/download/requirements/) | Recommended configuration includes eight CPU cores, 32GB RAM and 8GB VRAM. GPU rendering has separate backend requirements. | Scene fit, render time, plugin compatibility or equivalence across GPU vendors. |
| E8 | [Autodesk AutoCAD 2026 requirements](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/System-requirements-for-AutoCAD-2026-including-Specialized-Toolsets.html) | Recommends 32GB RAM and an 8GB graphics device; large datasets and 3D modelling have higher, workstation-oriented requirements. | Certification for every engineering course, CAD application or consumer GPU. |
| E9 | [Docker Desktop Windows installation requirements](https://docs.docker.com/desktop/setup/install/windows-install/) | Requires 8GB system RAM, supported OS and virtualisation. Windows containers require Professional/Enterprise; Home permits Linux containers through the supported route. | That 8GB accommodates a browser, IDE, several databases and many containers; that all development needs a dedicated GPU. |
| E10 | [Ollama FAQ, official repository](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) | Available memory limits concurrent model loading. Context and parallel execution increase memory requirements. | A guaranteed model size or token rate based solely on nominal GPU memory. |
| E11 | [Epic Fortnite requirements](https://www.epicgames.com/help/c-37599050/c-32343914/a16548002?lang=en-US) | Recommended requirements include 16GB RAM and NVMe storage; Epic quality specifies materially higher graphics than minimum. | An FPS result at any specific resolution or preset. |
| E12 | [Intel Resizable BAR guidance](https://www.intel.com/content/www/us/en/support/articles/000090831/graphics.html) and [Arc B-series reference guide](https://cdrdv2-public.intel.com/839907/Intel%20Arc%20B-Series%20Graphics%20Quick%20Reference%20Guide%20V1.1.pdf) | Arc B580 has 12GB memory; Intel documents enabling/checking Resizable BAR for Arc. | That installing a B580 alone establishes a satisfactory gaming or AI software experience. |
| E13 | [NVIDIA RTX 5090 specifications](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/) | Reference RTX 5090 has 32GB memory and 575W total graphics power. | Board-partner dimensions, actual total system consumption, quiet operation or universal 4K frame rates. |

## Priority segments: customer jobs and tier value

### Student Hybrid — FF-STU-01/02/03

**Core job:** documents, research, calls, browser work, coding and occasional media. Gaming and CAD are distinct optional requirements, not prerequisites for being a student. E1/E2 support a functional software floor well below the current 32GB baseline; retaining 16–32GB as a practical proposal needs a multitasking test, not a claim that Office demands it.

- **Budget:** an integrated-graphics, 16–32GB RAM, 512GB–1TB SSD proposal can serve general study. Current 32GB/1TB is headroom, not evidence that NPU capability is necessary. Position the benefit as compact study workspace after measuring noise and footprint. Validate university-required apps and exam/proctoring software against the exact OS/architecture.
- **Mid-range:** the current 32GB/2TB plus B580 proposes a combined study/gaming machine. Explain the spending as gaming and storage capability. Offer an iGPU branch for students who do not game. ReBAR, current driver, individual games and the exact display target need testing (E12).
- **High-end:** 64GB plus a 16GB NVIDIA GPU is a specialist design/engineering/media route. E6–E8 justify checking project memory, GPU APIs and application certification; they do not justify automatically recommending it to every student. A course-specific intake should precede this recommendation.

**Immediate evidence blocker:** Campus AI Mini mixes an AMD mobile APU/OEM mainboard with an ASUS NUC 14 Pro-style description. E3/E4 do not establish that assembly. Replace the descriptive hybrid with one exact complete OEM SKU, or a fully specified socketed desktop proposal. Price the former as a complete system so included RAM/SSD/PSU/Windows are not counted twice. Do not imply a laptop: transportable mini-PC still needs mains power, display and peripherals.

**NPU judgement:** make an NPU a requirement only for an identified, supported local application feature. Cloud chat and ordinary study work do not become faster merely because a machine has a 50 TOPS label. Copilot+ branding needs whole-system eligibility checks (E1/E3).

### Business & Office — FF-BOF-01/02/03

**Core job:** responsive Office, accounting, browser/SaaS, calls and the required number of displays. E2 supplies a launch floor, not a heavy-workbook sizing rule. A dedicated gaming GPU should default to absent.

- **Budget:** current 5600G/32GB/1TB can be a test candidate for general office. E5 confirms integrated graphics and PCIe 3.0. A Gen4 SSD may be installed but must not be sold as operating at Gen4 speed without platform evidence. Check actual motherboard display sockets and simultaneous resolution/refresh, not just CPU graphics presence.
- **Mid-range:** justify cost through measured spreadsheet/recalculation performance, sustained multitasking, display connectivity, serviceability, acoustic performance and additional storage. The current 32GB→32GB transition offers no RAM-capacity improvement. A newer CPU or DDR generation alone is weak customer value without a workload result.
- **High-end:** current compact Ryzen AI 7/64GB is a different form-factor proposition, not a demonstrated performance step above the mid-range desktop. Require an exact OEM system, memory configuration, sustained power limits, display ports, warranty and service information. Premium can mean small/quiet/managed, but those must be evidenced. Move demanding data-analysis users to a workload-sized workstation rather than calling every executive workload high-end.

**OS proposal:** retain Pro where required for business management/security features or Windows containers. Document the actual feature requirement and legitimate licence. Do not imply Home cannot run ordinary Office or Linux containers (E9). Backup destination, restore testing and customer identity/licence ownership are operational needs, not reasons to add a GPU.

### Family & Home — FF-FAM-01/02/03

**Core job:** homework, browsing, calls, media and family photo storage. Gaming is an optional household requirement. Current Mid-range and High-end materially change the proposition into gaming machines.

- **Budget:** integrated graphics, 16–32GB RAM and 1TB SSD is a sensible proposal to test. Current 5600G's graphics capability is a hardware fact (E5), not proof of a specific game/settings target.
- **Mid-range:** prioritise additional usable photo capacity, convenient connectivity, quiet operation and practical serviceability. Retain the current 16GB discrete GPU only when the household selects meaningful gaming. Do not make families pay for a 1440p gaming target they did not ask for.
- **High-end:** distinguish a premium shared/home-office/photo desktop from a gaming variant. 64GB and RX 9070 need a stated workload; home video/photo work may warrant them but is not automatically present. 4TB is capacity, not data protection. Recommend a separately costed backup/restore service or destination rather than implying that one large SSD is a family archive.

**Commercial implication:** Student, Office and Family tiers may reasonably share a physical base platform while differing in setup and evidenced workload headroom. Maintain separate cell requirements and economics. Do not invent extra hardware merely to force a price ladder.

## Remaining five segments

| Segment | Budget benefit proposal | Mid-range benefit proposal | High-end benefit proposal | Main caveat and required evidence |
|---|---|---|---|---|
| Great-value Gaming, FF-GVG-01/02/03 | Efficient 1080p gaming at recorded settings | 1440p target with more GPU capacity and storage | Higher refresh or selected 4K titles after testing | E11 shows settings matter. Current resolution/FPS language is authored intent. Measure average and 1% low frame rates on the complete system; distinguish native rendering from upscaling/frame generation. |
| High-performance Gaming, FF-HPG-01/02/03 | Strong 1440p candidate | Higher graphics quality/refresh and an optional aesthetic premium | Workload-specific 4K/VR candidate with premium GPU | E13 establishes a large thermal/power requirement, not universal performance. Separate showcase-case spend from measured performance. Confirm exact headset/game, connector/PSU guidance, GPU dimensions and sustained noise. Avoid “no-compromise” blanket claims. |
| Content Creation, FF-CCR-01/02/03 | Defined 1080p/4K project workflow, measured export and memory use | Larger projects, faster effects/rendering or more media capacity | Large scenes, demanding footage and substantial project capacity | E6/E7 support RAM/VRAM priorities. Existing 64GB budget is a proposal above Adobe's general 4K recommendation. Capture codec, bit depth, chroma, effects and application version; 8K alone is not a sizing specification. |
| AI Workstation, FF-AIW-01/02/03 | Validated small/quantised local inference on exact 16GB GPU | Larger memory-fit workloads on exact 32GB AMD stack | Explicit 48GB workloads, ECC/expansion and sustained service use | E10 requires model/quantisation/context/concurrency accounting. AMD ROCm compatibility is a separate version/OS/library gate; “32GB” does not prove a CUDA application runs. Multi-GPU memory is not automatically one pool. CPU RAM does not become VRAM. |
| Software Development, FF-SWD-01/02/03 | IDE, Linux containers and ordinary local services | More parallel build/container/VM capacity | Larger reproducible builds and heavier VM/test workloads | E9 supports virtualisation and OS checks. Current 64GB plus B580 budget is substantial; offer an iGPU/no-dGPU proposal for web development. A faster GPU is valuable only for selected graphics/local-AI workloads; measure compile/test times and RAM pressure. |

## Architecture and form-factor checks before committing a proposal

1. **Exact identity:** distinguish socketed desktop CPU, mobile soldered APU, complete OEM PC, barebones kit and reference-board description. An OEM mainboard is not interchangeable with an arbitrary case. Require exact part numbers for integrated systems and included items.
2. **Whole-system fit:** motherboard form factor, BIOS CPU support, cooler socket/radiator and clearance, GPU length/thickness, PSU dimensions/connectors, cable bend clearance, airflow and display outputs. Never infer these from shared component-family photos.
3. **Memory:** distinguish system RAM, dedicated VRAM and shared iGPU allocation. Record actual supported module configuration and speed. Four DIMMs at an advertised overclock speed are not a stability guarantee; validate the exact CPU/board/memory combination.
4. **Specialist software:** application and version, GPU backend, driver, OS and architecture are explicit. CUDA, ROCm, Intel acceleration and NPU execution are separate ecosystems. One nominal capability tier cannot silently substitute across them.
5. **Compact premium:** measure footprint, idle/load noise, wall power and long-run performance. “Quiet”, “low-noise” and “continuous inference” are claims requiring measurements; an included compact cooler does not prove them.
6. **Capacity and resilience:** separate boot/application, active project and backup needs. Additional internal SSDs can improve workflow or capacity; they do not by themselves establish backup or recovery.

## Proposed validation pack — none executed in this research

| Segment | Reproducible test | Record before accepting a customer claim |
|---|---|---|
| Student | Representative research tabs, call, document and IDE simultaneously; optional course CAD project | Versions, exact fixture, peak RAM, responsiveness, fan noise; course app install/feature pass; external display result |
| Office | Anonymised representative workbook recalculation plus meeting/browser; dual-display workday and sleep/wake | Recalc duration, errors, memory pressure, output resolutions/refresh, stability, acoustic method |
| Family | Several user accounts; homework/call/media/photo import; optional named games | Import duration, supported media playback and dropped frames, account behaviour; actual backup and restore result |
| Both Gaming segments | Named esports and demanding game set at 1080p/1440p/4K as appropriate, three repeated runs after warm-up | Game/driver/BIOS versions, preset, native/upscaling/frame-generation modes separately, average/1% low, power/temperature/noise |
| Creation | Licensed representative footage/effects and Blender scene; repeat export/render | App/codec/project details, timeline behaviour, export time, peak RAM/VRAM, output correctness, sustained stability |
| AI | Fixed model hash/quantisation, prompt/context, concurrency and runtime; model-load and repeated generation | Full GPU/CPU offload split, peak memory, time to first token, prefill/generation rate, OOM/error outcomes and power |
| Development | Fixed repository revision/dependencies; cold/warm build/test with declared containers/VMs | Command and fixture hashes, elapsed time, CPU/RAM/storage pressure, pass/fail, OS/container backend |

Set pass thresholds against the chosen customer job before running tests. No benchmark percentage, FPS, token rate, “equal or better” substitution, or tier performance ranking has been verified here. Supplier price, availability, VAT, complete-PC comparison prices and commercial contribution also remain outside this hardware evidence file.
