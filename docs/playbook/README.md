# Playbook and 3D asset working references

**Last reviewed:** 2026-10-24
**Authority:** Product rules live in [`../product/catalogues-playbooks-and-fulfilment.md`](../product/catalogues-playbooks-and-fulfilment.md). These files are operational references derived from current source data and do not replace live approval, compatibility, pricing, stock, or delivery checks.

## Current simple Playbook

The owner replaced the autonomous-demand implementation with a captured-data workflow on 23 October. The [generated Playbook](generated-simple/playbook.md) contains the saved DEV suggestions, Amazon demand anchors, linked supplier offers, pricing basis and missing parts. Amazon top ten per hardware category (NVMe/SATA separately) define the range; cases include all eligible products ranked in the Amazon top 100. Each bestseller retains its Amazon listing URL and ASIN. A validated shared CPK connects the Amazon anchor to exact cross-vendor observations; when metadata is missing, supplier CPK metadata must validate against both product titles before it is attached to the ASIN. Required gaps are filled from existing UK retailer captures, with their source URLs retained. Sealed mini-PC templates have been replaced by serviceable Student Budget and Office High-end desktop configurations. Suggested prices use matching complete-PC sold evidence, then component sold prices, then full recorded cost plus 10% profit on cost. Unknown postage defaults to £0 when buying components and £15 when selling a build; recorded charges take precedence. Source/experiment reviews do not gate these suggestions. Publication remains separate.

Rebuild locally with `cd flipflop-api` then `.venv/Scripts/python.exe scripts/rebuild_simple_playbook.py --apply --require-complete`. This uses stored data, makes no provider requests and updates pending proposals only.

Use `--cells FF-HPG-03 FF-CCR-03` to recalculate only named cells; exported reports and completeness checks still cover all 24. Supplier linking compares exact identities across CPKs, preserves recorded product URLs and rejects known-unavailable alternate offers. Required-range repair revisits oversized RAM, compares GPU board options within the authored family/VRAM requirement, and costs server-memory quantities in full. Enterprise retains Threadripper and 256GB ECC RDIMM by owner preference; that platform choice does not establish unmeasured AI throughput or concurrent-user guarantees.

## Build reference by Playbook cell

[`current-curated-playbook.md`](current-curated-playbook.md) lists the 24 current Curated-for-you builds: eight customer/use-case types crossed with Budget, Mid-range, and High-end. It includes each cell's build name and selected component specifications, followed by a deduplicated list of the distinct component specifications used across those builds.

Made-by-you uses the same Playbook customer/use-case and budget matrix to guide recommendations, software choices, and compatibility. It is intentionally not a second fixed-build list: customers start with an empty build and assemble it from the same Curated catalogue. Ready-to-Ship remains the complete-build sourcing workflow and is assessed against a chosen Playbook cell when proposed or entered.

The current component list is a planning inventory, not a request to create one model for every text row. Exact catalogue variants determine the real asset workload, and one shared asset is used when a variant appears in both Curated and Custom.

## Find what is waiting for a 3D asset

In the admin tool, open **Catalogue → Curated 3D assets** or **Catalogue → Custom 3D assets**. Each view shows active variants, captured listing photos and videos, supplier-description and saved customer-copy coverage, existing shared asset state, and variants still waiting. Use **Show missing…** to focus on gaps, expand a component row to inspect its saved media/copy, and use **Upload GLB** or **Upload / replace GLB** to add a model. A shared variant uses the same asset in both catalogue views. Uploading creates a version for review; it does not by itself approve provenance, scale, or customer activation.

The **Model approval** queue only lists uploaded GLB candidates. If it is empty, use **Open component asset inventory** to see the catalogue products that still need media or models.

The current implementation is [`../product/implementation-status.md`](../product/implementation-status.md), under **Shared catalogue 3D asset queue**. The detailed candidate inventory and shared-library rule are in [`shared-3d-asset-requirements.md`](shared-3d-asset-requirements.md).

## Prepare photos and models from the Playbook

In the Playbook, choose **Photos & 3D models** on a build cell. The overlay contains the selected build components, case choices and upsells, including pending-review variants and products shared with the from-scratch builder. Choose references and generate drafts in the first step; inspect, approve, confirm rights and scale, and publish models in the second. Closing the overlay reloads the Playbook snapshot; use the existing proposal refresh if its stored assessment is stale.

Both steps reuse the catalogue generation and model-review workspaces. The standalone catalogue queue remains available as a shared inventory and now includes pending-review products. The main **Photos & 3D models** navigation opens the Playbook asset slice. Model publication does not approve a catalogue product or publish the build itself. Existing review batches may span builds; the overlay shows the full batch and warns when other products are included.

## MVP matrix reset — 20 October 2026

The default Playbook is a single matrix. Open **Operating rules** once to set budget ceilings and enable bounded automatic publication. Empty ceilings keep those cells paused; the header reports whether scheduled source refresh is actually registered in this environment.

For routine work use **Approve photos** or **Approve models** in a cell. The photo panel includes only its selected physical base components, not software or unselected alternatives. Choose 1–4 photos and click **Approve photos & generate model**. The saved choice is sent unchanged; the browser returns as soon as the persisted generation job is accepted. Return to review the finished model and explicitly confirm rights/scale before publication. Media decisions queue an automatic captured-fact rebuild. No generated model is approved on the owner's behalf.

Builds may use approved product photos before a model is published. Missing/conflicting supplier, engineering or licensing evidence still pauses sale. Advanced diagnostics retain the previous operational pages for engineering investigation. The previous overlay description above is historical where it describes separate steps or unselected options.

## Main-photo approval grid — 21 October 2026

Open **Photos & 3D models** for the shared Curated/Custom main-photo grid. Use **Select all shown**, deselect incorrect products, then **Approve selected photos**. Approval is shared across every segment using that exact component. Broken photos are skipped; server-side validation rejects a changed main photo. This action does not create or replace a 3D model. Open **3D model inventory** from the grid for a clear list of existing models, missing models and running tasks. Manual photo tools are under Advanced. This replaces the routine per-cell photo approval instructions above.


### Single Curated range and photo gallery — 21 October 2026

Curated now supplies both Playbook builds and the empty from-scratch builder. The former Custom administration route redirects to the shared approval grid. The range is top ten per hardware category (NVMe and SATA separately), all eligible cases in Amazon's top 100, plus recorded Playbook requirements. Each card shows its Amazon source main photo and a scrollable captured-photo strip; choosing a thumbnail selects the picture for shared approval. Automatic Qwen photo selection is retired. See the canonical catalogue rules and shared asset requirements for refresh and cache behavior.
