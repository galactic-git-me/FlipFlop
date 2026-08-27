# Curated Builds and 3D Rollout Plan

## Product structure

Keep the eight customer purposes as the primary choices:

1. Great-value Gaming
2. High-performance Gaming
3. Student Hybrid
4. Business & Office
5. Content Creation
6. AI Workstation
7. Software Development
8. Family & Home

Each purpose has three curated configurations: **Value**, **Balanced**, and
**Performance**. These are 24 maintained configurations, but the storefront
does not present 24 equal cards. It asks for purpose and all-in budget, selects
the strongest configuration within that ceiling, and offers the adjacent tier
as a clearly priced alternative.

The all-in budget includes case, components, assembly, packaging, warranty
reserve, insured delivery, payment costs, and target margin. When no tier fits,
the storefront explains the shortfall and offers the nearest honest option; it
must not silently exceed the customer's budget.

## Delivery phases

### 1. Restore the live catalogue

- Diagnose the production database/API failures currently returning HTTP 500.
- Apply and verify outstanding migrations and curated seed data.
- Make public API tests require successful responses rather than accepting 500.
- Verify playbooks, products, showcase builds, and cases from the public domain.

### 2. Implement budget routing

- Add tier identity and all-in minimum/recommended/maximum budget metadata.
- Calculate live sell prices from component cost, fulfilment, warranty, and margin.
- Add a public recommendation endpoint taking purpose and budget.
- Return recommended, lower-cost, and step-up configurations with explanations.
- Add analytics for entered budget, recommendation, step-up, and abandonment.

### 3. Enforce ten-model approval batches

- Generate or import candidates without activating them.
- Claim at most ten candidates into an immutable review batch.
- Record an explicit approve or reject decision for every candidate.
- Require provenance, redistribution rights, scale, orientation, pivot, file-size,
  texture, and visual-quality checks for approved candidates.
- Allow publication only after all candidates in the batch have decisions.
- Activate approved models atomically; retain rejected models for audit/revision.

### 4. Build the review experience

- Show one batch of ten with interactive 3D previews and source references.
- Provide approve, reject, revision notes, and next/previous navigation.
- Show validation and rights failures beside each candidate.
- Display batch progress and require a final explicit **Publish approved models**
  action. Approval alone does not publish.

### 5. Produce the asset library

#### Case sourcing funnel

Start with the **top 30 cases by catalogue rank**. Freeze a ranked snapshot for
the campaign so cases do not move between approval batches while marketplace
rankings change. Preserve rank and all source evidence in the asset record.

For every case, use this order and stop at the first commercially usable source:

1. Search the manufacturer's product, support, press, and download pages for an
   official GLB, GLTF, FBX, OBJ, STEP, CAD, BIM, or downloadable 3D model.
2. Search reputable third-party model/CAD libraries for an exact case model,
   recording creator, licence, commercial-use rights, redistribution rights,
   source URL, and required attribution. A downloadable model is not assumed to
   be legally publishable.
3. Search for official and high-quality product imagery: front, rear, both side
   panels, three-quarter angles, top, interior, and important I/O/details.
4. Search YouTube for official showcases, reviews, unboxings, teardowns, and
   full rotations. Record video URLs and timestamps for useful viewpoints.
5. If no publishable exact 3D model exists, feed the best consistent multi-angle
   image set to Meshy.ai. Video frames may fill missing angles, but should not
   replace clean manufacturer photos when those exist.
6. Download the generated candidate, preserve the raw output, clean and optimise
   it, produce a web GLB, and validate appearance, dimensions, scale, orientation,
   pivot, textures, polygon count, and file size.
7. Put the candidate into the next ten-model owner-review batch. It remains
   unpublished until explicitly approved and the completed batch is published.

Use one evidence manifest per case containing all searches attempted—including
unsuccessful searches—source URLs, image/video references, licence conclusions,
Meshy job/version information, validation results, and revision history. This
prevents repeatedly searching the same dead ends and gives every public model an
auditable provenance trail.

#### Batch order

Initial order:

1. One web-ready model for each highest-priority component family.
2. Ranked cases 1–10 (approval batch 1).
3. Remaining component-family coverage.
4. Ranked cases 11–20 (approval batch 2).
5. Ranked cases 21–30 (approval batch 3).
6. Exact popular-product models where a generic family representation is no
   longer sufficient.

Work stops at the end of every generated batch until the owner reviews all ten.

### 6. Storefront integration and release

- Resolve only active, approved assets through the public asset API.
- Use exact → family-generic → category-generic → UI-placeholder fallback.
- Verify desktop/mobile loading, graceful failure, accessibility, and performance.
- Run end-to-end tests from budget entry through configuration and checkout.
- Release behind a feature flag, monitor errors and conversion, then expand.

## Definition of done

- All eight purposes have three commercially valid, budget-routed tiers.
- The live public APIs return successful, non-empty, schema-valid responses.
- No model can reach the storefront without owner batch approval and validation.
- Component families and the first 20–30 priority cases have approved web assets.
- Storefront recommendations never exceed the customer's stated all-in budget
  unless the customer explicitly selects a labelled step-up option.
