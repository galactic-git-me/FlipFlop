> Current rule, 21 October 2026: cases alone have individualized images/models.
> All other hardware uses shared representative family media. Historical specification
> lists below identify products, not separate model-generation requirements. Cached
> drafts and active FINAL models are reused; generation never starts on photo approval.

# Shared 3D asset requirements

**Source:** `flipflop-api/data/curated_build_definitions.json` via [`current-curated-playbook.md`](current-curated-playbook.md)
**Status:** Current selected-build specifications; not a list of confirmed missing files
**Distinct selected component specifications:** 101, excluding operating systems

The current Playbook reference contains one deduplicated list of the component specifications selected across its 24 cells. It does not include saved two-option cell upgrades because those are stored separately and are not present in the definitions JSON. The list is useful for planning asset production, but generic specifications (for example, a capacity/interface-only SSD) may map to multiple exact catalogue products.

## Where to see what is waiting

The **Photos & 3D models** navigation now opens `/catalogue/3d-assets`: a main-photo
approval grid for the single Curated catalogue. Only cases have individual media;
other hardware is grouped by representative family (AMD Ryzen/Intel CPUs, GPU
manufacturer, RAM manufacturer, storage interface, motherboard manufacturer and cooler type). Each card shows the captured main photo with its title
overlaid and whether a 3D model exists. Choose **Select all shown**, deselect any
incorrect cards, then **Approve selected photos**. Search, catalogue, category and
approval filters narrow the selection. The browser checks selected images load
before saving; broken images are skipped. The server checks each submitted photo
still belongs to the available gallery and records approval across all family members (exact listing aliases for cases).
The grid uses `/api/assets-3d/catalogue/photo-queue`, which loads both catalogues
with a bounded set of database queries rather than loading every product gallery
and diagnostic history. Main photos fall back to the captured ASIN/scored-listing
photo where a catalogue listing has no image of its own.

Photo approval preserves existing model references, tasks and GLB files. It does
not start a paid generation job. Subsequent automatic model preparation uses the
approved main photo directly, bypassing repeated Qwen photo selection. The linked
**3D model inventory** distinguishes existing drafts, published models, running
tasks, missing models and failures. Detailed photo tools remain under Advanced.

The live admin queues show active catalogue variants and their actual shared 3D asset state:

- Catalogue → [Curated 3D assets](../../flipflop-admin/app/catalogue/3d-assets/page.tsx) (`/catalogue/3d-assets?catalogue=curated`)
- The from-scratch builder uses the same Curated assets; there is no separate Custom catalogue.

Each queue includes cases/families waiting for an asset, existing assets, and a shared `.glb` upload control. If one catalogue variant is tagged into both catalogues, both views resolve to the same versioned asset. Uploading does not approve rights, validate scale, or activate an asset for customers.

For exact catalogue variants, the queue shows captured Amazon, Overclockers and
other linked listing photos and videos as thumbnails. Captured listing media is
included automatically; operators do not approve individual photos or videos.
They choose one to four photos as model references for **Generate draft model**.
The published model must match that chosen reference set; the customer gallery
keeps the captured listing photos and videos.
The separate Cases → 3D Assets priority queue uses the same distinction while
reviewing case sourcing evidence: any number of candidate photos can be
approved as listing photos, with a separate one-to-four-photo selection for
Meshy generation. YouTube candidates are reviewed from selectable thumbnails,
and the compact Overclockers strip on each case row has its own scroll arrows.
The Playbook photo workspace also offers a DEV-only automatic preparation
workflow. Local Qwen reviews the captured images, selects one clear photo of the
exact physical component, and the app sends that single original photo to
Meshy's image-to-3D API with PBR texturing and GLB output enabled. It does not
edit the source or generate alternate views. The listing gallery remains
unchanged. The existing asset cache shares the resulting component model across
segments; each new component requires at most one active generation, and a
finished GLB remains a draft for model, scale, rights, and publication review.
The workflow requires local Qwen and `MESHY_API_KEY`; Meshy credits are used
only after an operator starts preparation from the Playbook.
Generated drafts enter a one-asset model review batch and still require model,
scale, commercial-use, redistribution, and publication approval. Changing the
approved model reference set makes an older model ineligible for storefront use
until a new matching model version is published. Storefront catalogue and
configurator APIs withhold a variant unless the selected model references match
the source photos of its active FINAL exact-variant model; category placeholders
cannot substitute.

The live queue—not this static candidate inventory—is authoritative for which exact variants already have a model. The upload endpoint checks GLB v2 container length, chunk boundaries, and first-chunk glTF 2.0 asset metadata before storing an upload.

## Case fan reconstruction in review

The 3D asset review page shows the source photos saved on the selected asset version. For case assets, **RGB fan layout** can scan one saved source photo or the case's separately labelled current approved photo set for bright coloured ring candidates. Detection is a visual starting point: reviewers can change the case face, fan positions, sizes, and RGB program in the Three.js preview, add or remove fans, and save the layout to that asset version. Saved fan layout metadata drives the review editor's procedural fan overlay; it does not edit the source GLB file. The asset still requires the normal model, scale, provenance, and publication checks.

## Candidate list

See the **Distinct 3D asset candidates from selected builds** table in [`current-curated-playbook.md`](current-curated-playbook.md). It deduplicates the component specifications by type and name and lists how many cells use each one.


### Single Curated catalogue and manual photo gallery (21 October 2026)

This supersedes the earlier Qwen photo-selection experiment and the separate Custom catalogue. Open **Photos & 3D models** (`/catalogue/3d-assets`). Each exact physical product appears once, including storage shared between primary and secondary slots. Its source main photo is initially shown with the title overlaid; the scrollable horizontal thumbnail strip includes all captured exact-listing images. Clicking a thumbnail changes the large photo and selects the component for approval. The operator chooses hardware-only images without retail packaging. Select all shown, deselect unsuitable cards, then approve the selected images. No image contents are represented as automatically verified.

Approvals accept the exact selected captured-gallery URL, share it across segment aliases and both build journeys, and retain existing model references, jobs and GLBs. Broken selected images are skipped. No Qwen or Meshy requests start from the approval grid. The retired hardware-photo endpoint returns 410 so older open pages cannot start new Qwen selection requests.

The range follows the top-ten-per-category/all-cases/recorded-Playbook-exception policy in the canonical product rules. Successful source captures reconcile membership and enqueue a bounded Playbook rebuild. Out-of-range products retain reusable photo/model records but are not active catalogue choices.

The trash icon permanently removes the entire product from the catalogue and all segment aliases, not just its displayed photo. A durable exclusion and historical records are retained to prevent re-import and preserve order history.

API: `GET /api/assets-3d/catalogue/photo-queue`, `POST /api/assets-3d/catalogue/approve-main-photos` with selected captured URLs, and `DELETE /api/assets-3d/catalogue/components/{variant_id}`. All require admin authentication.


### Google image search on component cards

The picture icon beside the trash icon opens a modal with Google image results for a shortened product title. The search phrase can be edited. Selecting a result downloads the original validated JPEG/PNG/WebP to `flipflop-api/data/uploads/catalogue-photos/`, served without authentication under `/api/uploads/catalogue-photos/`, and selects that saved URL in the shared grid. The operator then approves the selected photo using the normal bulk approval action. Existing model references and GLBs are retained. DEV URLs are local; production URLs use the public shop API.

Images are named by their SHA-256 content hash, written atomically, and reused on repeat selections. Only IDs from this component's recorded search results may be imported. Downloads use the existing public-HTTPS image downloader with private-network rejection, redirect checks, timeout and a 15 MB limit, followed by raster type/dimension validation. The origin URL, source page, selecting operator and time are retained. Search results are cached per product/query for 12 hours. No Qwen or Meshy calls start from this action.

Configure `SERPER_API_KEY` on the API to retrieve Google results through Serper. Legacy `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` are supported only for projects that still have access. The legacy Google project returns 403 (no Custom Search JSON API access). Serper is now configured for development; the live app endpoint returned 20 Google image results for the NZXT H3 Flow case. Download/selection and deduplication were checked with isolated fixtures and a rollback-only database transaction. Keys remain server-side.

Google photo selection downloads the original within eight seconds, then tries only that result's preview within six seconds if necessary. Both copies must pass the same public-network and raster-photo validation. Download errors stay visible outside the modal's scroll area; the modal closes only after a confirmed saved URL. Selection persists to every family member and remains subject to the normal photo approval.

APNX Creator C1 ChromaFlair is an owner-requested curated case exception. The listing's curated_range_pin records its role and reason so ranking reconciliation preserves membership. This grants no stock, compatibility, photo, model or sales approval.

The main 3D model inventory now offers Generate model directly beside a missing case/family model when its main photo is approved and the server is DEV. The action uses the existing durable auto-prepare endpoint, which submits the approved single photo to Meshy, records progress, and protects existing family models/tasks against duplication. It uses Meshy credits only after the operator clicks; missing photo approvals link back to the grid.

The Approve 3D models button opens the original /components-3d-review viewer workspace. The left-hand grid includes approved-photo case/family components with no model, alongside registered models. Select a missing item to see its approved reference photo and Generate 3D model action inside the viewer workspace. Generation polls in the background and the saved GLB replaces the placeholder for visual/rights/scale review. Placeholder cards are UI-only and cannot be approved or published as real model assets. Explicit batch/asset/case links remain supported.


In the viewer approval workspace, checkboxes select multiple approved-photo case/family cards for model generation. Select all shown and Clear selection control the selection; Queue selected models submits each chosen component to the existing durable generation endpoint. Each job uses its single approved photo, not a combined multi-component image. The app shows submission progress, removes accepted jobs from the selection, retains failed selections with errors, and polls per-item generation status. Keep the page open until all selected jobs are submitted; accepted work continues server-side. The operation uses Meshy credits only after the queue button is clicked. Existing models and active family jobs are skipped by the UI and rechecked under server locks.


The viewer includes a collapsible Meshy model queue showing the app's submitted catalogue jobs, per-model status and percentage, errors and review links. It refreshes recorded provider progress every five seconds, retains last-known data on refresh failure, and distinguishes submission, Meshy waiting/generation, local GLB saving and ready-for-approval stages. Batch submission sends each request without waiting for its generation to finish; accepted jobs run asynchronously in parallel subject to Meshy's account concurrency limits. The queue does not enumerate unrelated tasks created directly in the Meshy account.

Owned image files (including Google photos saved to DEV localhost) are sent to Meshy as validated base64 image data for geometry and texture guidance. External providers must never receive a localhost URL as an image download location. Approved source URLs remain in provenance; encoded transport payloads are not stored in catalogue review JSON. Missing local files fail before submitting a paid task.


Recovery fixes, 22 October 2026: explicit Meshy NoMorePendingTasks/429 responses wait ten seconds and retry for up to five minutes, reporting QUEUED while no provider task exists. Other rejections and uncertain network submissions are not automatically re-posted. Timed-out polls with a task ID resume that same provider task. A stale capacity-wait record can be safely resumed because the provider explicitly rejected it before task creation. Saved approved raster photos at 100px or larger are accepted without resizing; the separate original-CDN quality threshold does not reject an already approved 225px local photo. The recovery script checks the shared model cache before each submission and processes at most two owner-reported jobs concurrently.


Failed jobs in the Meshy queue table have a per-row Retry button. It shows Retrying while submitting and reports success/errors in that row. Existing timed-out tasks and completed-task save failures use the saved task ID; active jobs and saved models cannot be duplicated through this button. Retrying a genuinely failed generation can use Meshy credits.


The approval workspace shows one interactive 3D model at a time with the existing review controls. Select a component from the left-hand grid or use Previous/Next to change models. The viewer shows a spinner while waiting/downloading/preparing the model, a real download percentage where supplied, and a readable failure state. Lighting remains the single white camera-mounted light.

Visual approval clicks enter a browser-session queue and immediately advance to the next undecided model. Saves run sequentially in the background without blocking further reviews; counts distinguish pending, saved and failed approvals. Failures retain the model and notes with a Retry approval button. Keep the page open until pending saves finish; closing the tab warns while requests remain. Publishing is disabled while approvals are pending. Rights, scale checks and publication remain separate.

After the current GLB loads, the viewer predownloads the next undecided model, skipping queued approvals. One upcoming GLB is retained in memory and its download is reused when selected; geometry parsing and GPU setup happen when opened. Changing the upcoming target or leaving the workspace cancels speculative downloads. Failed predownloads fall back to the normal loader.

Single-action model approval: Approve confirms the owner review, usage rights and scale and atomically sets that model FINAL and active, replacing the previous model with the same registry identity. Separate checkboxes and batch publication are no longer required in the viewer. Unapprove and unpublish resets the model to an inactive draft, clears its review confirmations and schedules a Playbook refresh. Existing approved models can be unapproved and approved again to publish through this flow.

Refresh queue dismisses completed and failed generation entries from the current workspace view and refreshes active jobs. Automatic polling keeps dismissed job versions hidden; a new attempt or changed status is visible again. This does not delete models or provider history.
