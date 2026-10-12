# Shared 3D asset requirements

**Source:** `flipflop-api/data/curated_build_definitions.json` via [`current-curated-playbook.md`](current-curated-playbook.md)
**Status:** Current selected-build specifications; not a list of confirmed missing files
**Distinct selected component specifications:** 101, excluding operating systems

The current Playbook reference contains one deduplicated list of the component specifications selected across its 24 cells. It does not include saved two-option cell upgrades because those are stored separately and are not present in the definitions JSON. The list is useful for planning asset production, but generic specifications (for example, a capacity/interface-only SSD) may map to multiple exact catalogue products.

## Where to see what is waiting

The live admin queues show active catalogue variants and their actual shared 3D asset state:

- Catalogue → [Curated 3D assets](../../flipflop-admin/app/catalogue/3d-assets/page.tsx) (`/catalogue/3d-assets?catalogue=curated`)
- Catalogue → Custom 3D assets (`/catalogue/3d-assets?catalogue=custom`)

Each queue includes variants waiting for an asset, existing assets, and a per-product `.glb` upload/replace control. If one catalogue variant is tagged into both catalogues, both views resolve to the same versioned asset. Uploading does not approve rights, validate scale, or activate an asset for customers.

The live queue—not this static candidate inventory—is authoritative for which exact variants already have a model. The upload endpoint checks GLB v2 container length, chunk boundaries, and first-chunk glTF 2.0 asset metadata before storing an upload.

## Case fan reconstruction in review

The 3D asset review page shows the source photos saved on the selected asset version. For case assets, **RGB fan layout** can scan one saved source photo or the case's separately labelled current approved photo set for bright coloured ring candidates. Detection is a visual starting point: reviewers can change the case face, fan positions, sizes, and RGB program in the Three.js preview, add or remove fans, and save the layout to that asset version. Saved fan layout metadata drives the review editor's procedural fan overlay; it does not edit the source GLB file. The asset still requires the normal model, scale, provenance, and publication checks.

## Candidate list

See the **Distinct 3D asset candidates from selected builds** table in [`current-curated-playbook.md`](current-curated-playbook.md). It deduplicates the component specifications by type and name and lists how many cells use each one.
