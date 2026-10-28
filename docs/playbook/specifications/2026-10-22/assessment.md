# Assessment and owner decisions

> **Current implementation — 23 October 2026:** the replacement simple Playbook has 24 complete, priced planning builds across all eight segments. [Open the completed Playbook](../../generated-simple/playbook.md) or the signed-in DEV matrix at http://localhost:4312/pc-builder. Supplier links, quantities, cost/profit assumptions and planning compatibility checks are included. Physical assembly checks and customer publication remain separate. The research assessment below is historical and does not gate these suggestions.


Draft 0.2.0, 22 October 2026. Complete review coverage means every existing cell has a disposition;
it does not mean every proposed build is verified, sourceable or approved for sale.

## Approved dimension model

The owner approved **customer use case × capability tier**, replacing spending bands as the second
dimension. Shared column levels are Essential, Enhanced and Advanced; the customer sees a specific
benefit-led profile name for their use case. Budget is a separate customer constraint. Selling price
is established after workload qualification, balanced component selection, complete channel costs
and comparable market evidence. Select the least expensive viable offer meeting the customer's needs.
If none fits their budget, explain the shortfall or offer an explicitly reduced capability; do not
silently weaken the promised workload or sell below the approved contribution floor.

This approves the model, not every proposed tier name, hardware choice, test threshold, withdrawal,
merge, margin change or price. Existing IDs and legacy Budget/Mid-range/High-end mappings are retained;
runtime migration is not implemented. In the assessment below those old names refer to the previous
spending tiers and historical snapshots. The generated matrix uses the capability names.

AI profiles illustrate the distinction:

| Level / proposed name | Useful customer outcome | Evidence needed before promising it |
|---|---|---|
| Essential / Personal AI | One person uses a responsive private text assistant | Exact licensed model/hash, runtime, quality fixture, context, memory fit and measured latency/throughput |
| Enhanced / Advanced AI workspace | More capable text work plus a validated image-understanding workflow | Named task quality improvement, vision encoder/model fit, supported backend, text/image coexistence and measured performance |
| Advanced / Team AI server | Several people use supported local AI concurrently | Pinned model and per-request context, simultaneous-user load test, per-user speed, latency and sustained stability |

The draft proposes one interactive request for Essential/Enhanced and three for Advanced; these are
test hypotheses, not tested capacity. Model download count, resident model count and concurrent requests
are separate. A small validated multimodal model may also run in Essential: image understanding is not
inherently exclusive to Enhanced. Model parameters, VRAM, TOPS and hardware cost are not quality scores.
No local frontier-model capability, cloud service or automatic multi-GPU memory pooling is promised.

## First: Student, Business and Family

Student Hybrid needs an affordable study computer and a separate study-plus-gaming proposition.
Mobility means a laptop: a mini PC still needs power, screen and peripherals. Do not describe one as
a portable substitute. Remove the default NPU premium unless a named supported application needs it.
Propose a serviceable integrated-graphics mATX base, explicitly changing the authored compact architecture;
retain a separately quoted exact OEM mini-PC alternative only after owner approval. A desktop is never
an automatic replacement for an integrated OEM board/LPDDR/adapter assembly. High-end engineering
coursework belongs in an application-qualified Creator recommendation; withhold the generic student tier.

Business & Office should prioritise quiet operation, two actual display outputs, recoverability and
appropriate Windows licensing. A dedicated GPU and flagship chipset do not improve bookkeeping.
Budget and Mid-range have a defensible distinction only for measured larger spreadsheets and concurrent
applications, plus modern serviceable platform longevity. An executive title, NPU or aluminium enclosure
does not justify High-end. Withhold it; offer a size preference or route genuine compute workloads elsewhere.

Family & Home Budget shares hardware with Office Budget but keeps Home software and setup.
Mid-range adds real gaming capability, preferably sharing the Great-value Gaming BOM. Storage capacity
is not backup: preserve separate backup/restore acceptance. Withhold High-end: 4K media playback does
not justify an expensive gaming GPU, and heavy gaming or editing already has a clearer home.

## Remaining segments

Great-value Gaming Budget/Mid-range have clear 1080p/1440p purposes. High-end overlaps High-performance
Gaming Budget. Retain both identifiers but propose merging the overlapping offer, preserving customer
entry points and history rather than maintaining two independent BOMs. High-performance Mid-range may
serve 4K raster gaming; High-end remains quote-only until a named high-refresh/RT workload supports
its substantial price. Styling belongs in an optional case choice after the MVP, not a CPU/GPU tier claim.

Creation must distinguish 1080p/light 4K with proxies, routine 4K production, and measured heavy VFX/3D.
No one GPU guarantees all codecs, CAD certification or 8K workflows. Development starts with integrated
graphics; containers do not inherently need a GPU. Higher tiers buy measured concurrency and compile
throughput. Local AI is a separate optional workload, not a compulsory developer tax.

AI tiers are defined by a pinned model/runtime/context/concurrency and usable memory, not a GPU score.
Propose CUDA-based entry by default for the supported application set, but retain AMD/ROCm as a
separately validated architecture branch for Mid-range. This is an owner decision: the current R9700
cannot silently become an RTX5090. High-end stays quote-only; 48GB single-card memory and ECC/platform
requirements must be preserved if promised. Multi-GPU does not automatically pool VRAM.

## Commercial conclusion

No cell has a verified complete landed replacement BOM and matched delivered market sample in this
review. Proposed price envelopes are experiments, not observed market ranges. Component ceilings are
reverse calculations of affordable procurement, not supplier quotes. All cells remain commercially blocked.
The saved 22 October operational costs are carried separately, including four incomplete builds; they
must not be represented as costs of the redesigned defaults. Current snapshot Student Budget exceeds
Mid-range by £1,843.84. The matrix reports this inversion; it does not repair it by increasing prices.

Current code `commercial_pilot_policy.py:6-11` sets minimum contribution/margin of £60/10%, £100/12%,
£175/15%. Recommend 12% target and 10% absolute minimum for analysis, while retaining those stricter
approved floors and any cell-specific absolute targets until explicitly changed. At price P, simplified
contribution is `0.8985P - 1.10L - 41.20`; L includes evidenced supplier postage. This assumes current
3.15% payment, 5% warranty, 2% returns and 10% landed-parts overhead allowances, zero owner labour,
£20 outbound fallback, £15 separate insurance, £6 packaging and £0.20 fixed fee. Use exact Decimal
rounding and both margin and absolute contribution gates before any quote. £20 is not supplier postage.
Do not apply this direct-card scenario to eBay or claim personal earnings. VAT rate zero here means the
current non-registered scenario, not zero-rated goods; registration requires a net-VAT model review.

## Prioritised owner decisions

1. Approve or reject the three withheld generic High-end tiers (Student, Office, Family), plus the
   Great-value High-end/Performance Budget merge. Keep historical IDs regardless of outcome.
2. Approve the Student Budget architecture redesign; require an exact assembled OEM product if compact
   architecture remains essential. Decide whether Office Mid-range has enough demand to retain.
3. Decide whether 12% target/10% minimum replaces current Mid/High floors and absolute profit targets.
   Until then, the stricter existing rules win. Confirm channel fee mix and accounting/VAT assumptions.
4. Approve explicit workload fixture definitions and proposed thresholds, particularly game suites,
   creator codecs/plugins, AI model licences/context and the ROCm/CUDA support boundary.
5. Authorise an exact retail basket and matched competitor quotation pass for retained cells, starting
   Office/Family Budget and Student Budget. Do not buy anything. If cost exceeds ceilings, re-source,
   redesign or withhold; do not relax PSU, licensing or warranty standards to fill the matrix.
6. After those gates, review a separate implementation proposal for selector constraints and market
   collection defects. This research does not modify either implementation.

Verified: canonical documents and current source inspected; existing public evidence and fresh primary
research linked; structural and arithmetic checks recorded. Proposed: all replacement defaults, performance
thresholds, tier dispositions, price experiments, review cadence and outlier policy. Blocked: sourceable
landed BOMs, valid comparable ranges and customer offer approval. Unknown: real demand, acceptance
pass rates, acoustics/thermals, realised costs and margins. No physical build or new sales test performed.


## Owner-approved scope update, specification 0.2.1

On 22 October the owner explicitly approved withholding generic Advanced Student, Office and Family offers, sharing the overlapping Great-value Advanced / Performance Essential BOM while retaining both IDs/entry points, and redesigning Student Essential as a serviceable integrated-graphics desktop. These dispositions are settled for the reconstructed draft. All 24 historical IDs remain. The prior 0.2.0 specification, schema and evidence register are archived in `history/0.2.0.json`. Exact SKUs, cost/market prices, acceptance results and runtime publication remain gated. The numbered decision list above is historical for these scope points.

## Superseded implementation scope — 23 October 2026

The owner cancelled the autonomous-demand PRD implementation and replaced it with the simple top-ten Amazon catalogue → stored supplier offers → segment builds → sold-price/cost-plus-10 pricing flow. See the [generated Playbook](../../generated-simple/playbook.md) for the current DEV suggestions. This research specification no longer gates catalogue inclusion or price suggestions.

## DEV checkpoint — 25 October 2026, 20:03 UTC

The saved Playbook again contains **24 complete hardware BOMs and 24 draft prices**. The current generated Markdown and JSON include exact selected products, source captures, supplier-postage assumptions, software-source review flags, compatibility reviews and publication blockers. **0/24 cells are ready for publication approval; none was published.** A complete planning price does not certify supplier stock, licensing or physical fit.

Rebuild `2ac6ed8f-108c-421e-84fd-d88f5b15275b` completed successfully through the durable rebuild queue. Proposal calculation now saves before local Qwen reviews. A separate scheduled worker claims up to three pending reviews, releases the database connection during inference, saves each matching result independently, retries unavailable responses after fifteen minutes and recovers abandoned claims after six minutes. This prevents the model queue from holding the proposal transaction open. Unsupported model verdicts and omitted physical relationships are recorded as insufficient evidence.

Curated component membership now uses the same 24-hour freshness window as supplier evidence. This repaired five builds that lost specialty parts because a separate two-hour catalogue window hid their still-current captures. Freshness recovery preserves pending review status and cannot automatically approve an unreviewed software source. The repair was limited to Curated variants and saved a status backup under `output/playbook-priority-rebuild-20261025/`.

The APNX C1 supplier match resolves its exact Overclockers SKU and product page rather than the old search URL. Unknown inbound delivery remains an explicitly assumed £0, never a zero component price or a claim of verified free shipping. Exact captured Windows licence candidates can be costed provisionally while their source review remains a publication blocker. Fresh boxed-OEM Overclockers alternatives were captured separately for source selection; they have not been substituted or purchased.

Verified: Python syntax compilation, successful durable DEV rebuild, persisted proposal/source snapshots, all 24 exported hardware BOMs and prices, and enabled one-minute rebuild/compatibility schedules. Remaining work: source-backed fit measurements and CPU/BIOS support, eligible current supplier condition/arrival evidence, software-source selection/review, and final commercial publication checks. Physical assembly and customer checkout were not verified in this checkpoint.

### 25 October: draft validation decoupled from publication
- Draft rebuilds now validate fresh exact-source engineering facts with automatic publication disabled; absent measurements remain unknown and unrelated draft values are not certified.
- Applied the documented Standard-only matrix profile to eight segments with automatic publication explicitly disabled; prior pricing models backed up under output/playbook-priority-rebuild-20261025/before-standard-only-profile.json.
- Corrected preparation to retain separate primary and secondary storage roles for the same listing. Focused deterministic checks pass; full rebuild verification remains in progress.
- Exact refresh of the two selected RoyalCDKeys listings returned HTTP 429; retained older captures remain stale, not freshly verified.

### Software vendor replacement: Gamers Outlet
CD-Keys.uk is disabled in DEV and replaced by Gamers Outlet. Extension DEV now captures exact Windows 11 Home, Pro and Office 2024 Professional Plus products, converting EUR to GBP using dated ECB evidence. Office Standard remains a targeted discovery search because no perpetual Standard product was found; Microsoft 365 Business Standard is not substituted. Live source JSON-LD fixtures and deterministic conversion checks passed, as did extension type checking and DEV packaging. Installed browser reload and actual scan ingestion are not yet verified. This does not approve licence rights or publish offers.

### Active publication preparation: 25 October late checkpoint
- Verified completed rebuild: 24 complete hardware BOMs; builds with non-new supplier blockers reduced from 17 to 4 by fresh/new source preference.
- Galileo now passes motherboard/case fit, GPU length, PSU format, storage interface/mounting/slot count and GPU eight-pin connector checks. The new-condition cooler selection changed to Thermalright Peerless Assassin 120 SE; ARCTIC evidence is not reused for it.
- DEV model gateway 11435 was absent while 11434/11436 existed. Started a DEV-only recovery listener through shared 11434 without restarting production. Listener startup succeeded; upstream /api/tags timed out, so inference remains unverified. Recovery logs: output/playbook-priority-rebuild-20261025/dev-gateway-recovery.*.log. Nested recovery traffic enters the shared gateway as other-priority work; normal DEV priority requires restoration of the main listener during a separately coordinated gateway restart.
- A follow-up rebuild is still running. No customer publication was performed. No Gamers Outlet observations were present at the last check.

### Qwen recovery and remaining supplier captures
Owner explicitly approved restarting local model services. The standard gateway restart succeeded: engine 11433, DEV 11435 and production 11436 responded; shared queue again advertises one GPU-only generation and normal priorities. Saved compatibility reviews completed for FF-GVG-01/02/03 at 22:06 UTC, confirming inference and persistence resumed.
Refreshed the exact Amazon CPU14937 and motherboard15034; selected offers remain used. Added exact AWD-IT product-page support using canonical identity, the main product VAT-inclusive final price and structured stock metadata. Fresh workstation motherboard17229 capture succeeded at £1243.73; no new-condition evidence was invented. Fixed null availability parsing and verified nearby recommendation prices cannot become selected costs.
Added Thermalright Peerless Assassin120SE base-model official socket and155mm height facts. Missing RAM clearance remains unknown; ARCTIC measurements are not reused. Focused checks and Python compilation passed. A further rebuild was requested for the changed evidence; no publication performed.

### Catalogue-driven extension product searches
The existing authenticated search feed now includes current active curated component identities. Stored-data verification returned146 deduplicated searches:4 selected products with supplier gaps,41 other selected products and101 other catalogue products. It excludes software and inactive/hidden listings. Extension sync applies both component and complete-build feeds, rereading settings after fetch. Successful sync disables unchanged legacy generated terms and obsolete managed component terms while preserving custom/edited queries, disabled identities and manual-only choices. Existing scan windows are retained; other catalogue parts run daily after success. No source scan or customer publication is triggered by the feed itself. Type checking, DEV build and a cross-contract fixture using the actual backend feed passed; installed browser sync remains unverified.

### Listing processing performance
Live model gateway reported20–21 queued requests with single GPU generation. The ingestion log showed canonical product extraction calls during a30.2-second32-identity batch. A deterministic repro proved two concurrent identical titles made two model requests. Added bounded exact-input extraction reuse:512 entries, one-hour successful-result lifetime,30-second empty-result backoff and shared in-flight tasks. Cache key includes title/category/condition, provider tiers, routing flags and timeout. Cached values are copied so caller mutations cannot corrupt identities. The repro now makes one call, sequential reuse makes no extra call and differing conditions stay separate. Python compilation passed. Live end-to-end throughput improvement remains unmeasured; no GPU concurrency or identity validation was relaxed.

### Simplified compatibility and Windows connection implemented
Implemented the owner's basic Playbook gate across proposals, source-backed LLM review and curated checkout: CPU/socket, RAM generation, GPU/motherboard expansion interface and motherboard/case form factor. Missing workshop measurements become warnings; known incompatibilities remain errors. Custom/Made-by-you retains strict fit validation. Focused checks cover workshop-only unknowns, RAM mismatch, GPU interface mismatch, known oversized GPU and LLM's four source-cited relationships. Galileo's stored proposal passed all four basic checks.
Captured exact Gamers Outlet Home/Pro product pages and dated ECB conversion directly, linked new DEV listings17448/17449 to existing OS slots as pending-review candidates (£3.34/£4.68), and exposed both through software source review. Supplier's OEM and Global claims are retained; licence resale rights remain explicitly unverified. No supplier approval or publication was invented. Scan/CCL direct requests for a new Galileo motherboard returned403 and did not establish stock. Full24-cell stored-data rebuild completed; subsequent Galileo refresh is underway for fresh Windows costs.
