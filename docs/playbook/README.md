# Playbook and 3D asset working references

**Last reviewed:** 2026-09-30  
**Authority:** Product rules live in [`../product/catalogues-playbooks-and-fulfilment.md`](../product/catalogues-playbooks-and-fulfilment.md). These files are operational references derived from current source data and do not replace live approval, compatibility, pricing, stock, or delivery checks.

## Build reference by Playbook cell

[`current-curated-playbook.md`](current-curated-playbook.md) lists the 24 current Curated-for-you builds: eight customer/use-case types crossed with Budget, Mid-range, and High-end. It includes each cell's build name and selected component specifications, followed by a deduplicated list of the distinct component specifications used across those builds.

Made-by-you uses the same Playbook customer/use-case and budget matrix to guide recommendations, software choices, and compatibility. It is intentionally not a second fixed-build list: customers assemble a compatible build from the broader Custom Catalogue. Ready-to-Ship remains the complete-build sourcing workflow and is assessed against a chosen Playbook cell when proposed or entered.

The current component list is a planning inventory, not a request to create one model for every text row. Exact catalogue variants determine the real asset workload, and one shared asset is used when a variant appears in both Curated and Custom.

## Find what is waiting for a 3D asset

In the admin tool, open **Catalogue → Curated 3D assets** or **Catalogue → Custom 3D assets**. Each view shows active variants, existing shared asset state, and variants still waiting. Use the **Upload GLB** or **Upload / replace GLB** button on the component row/card to upload a `.glb` file. A shared variant uses the same asset in both catalogue views. Uploading creates a version for review; it does not by itself approve provenance, scale, or customer activation.

The current implementation is [`../product/implementation-status.md`](../product/implementation-status.md), under **Shared catalogue 3D asset queue**. The detailed candidate inventory and shared-library rule are in [`shared-3d-asset-requirements.md`](shared-3d-asset-requirements.md).
