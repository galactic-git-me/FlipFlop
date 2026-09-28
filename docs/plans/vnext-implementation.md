# vNext implementation status

The two vNext PRDs in `docs/prd/` set the product direction. This file records delivered work and the remaining gates. Existing order, payment, catalogue, playbook, and MES data remain authoritative.

## Delivered foundation

- `POST /api/recommendations/envelope` accepts primary use, budget, condition policy and relevant workload answers.
- A deterministic service returns a version-labelled, SKU-free performance envelope with hard minimums, preferred memory/storage targets and customer-facing budget reasoning.
- Requirements and their resulting envelope are persisted in `recommendation_sessions` for replay; the migration is `vnext_20260926_05`.
- Pure pricing rules now enforce explicit non-new consent, Priority's Amazon/Overclockers supplier pool, Standard's retail-only pool, full true-cost and contribution floors, and a separate sold-market gate. They are not yet connected to live supplier or checkout data.
- Admin-only `/api/commerce-intelligence/price-assessment` and `/gem-assessment` endpoints expose review calculations without creating a customer quote or authorising a purchase. Gem assessment includes all-in costs, conservative resale, net contribution, profit velocity, max-buy and the speculative-capital ceiling.
- Admin-only `/api/commerce-intelligence/procurement-assessment` searches approved, stocked, recent candidate offers for a BOM that meets envelope minimums and explicit socket, memory, power and case compatibility checks. It fails closed when required evidence is missing or the exhaustive search would be too large.
- `UpgradeAssessment` persists customer-owned PC intake, expert advice, revisioned scope and explicit approval for material changes. The sibling storefront now has `/upgrade-my-pc` for authenticated submission, advice and approval. Photo/system-report links can be provided; direct file upload and workshop intake remain to be built.
- The admin app has an Upgrade Desk for reviewing submissions and publishing KEEP / UPGRADE / OPTIONAL / DON'T SPEND HERE / TRANSFORM advice.
- The sibling `FlipFlop.shop` storefront has a `/find-my-pc` guided route, a primary homepage CTA, and immediate access to the homepage without the blocking startup video.
- The endpoint is explicitly `requirements_only`: it cannot be used as a quote or to initiate checkout.

## Slice 1 — Playbook versioning and guided recommendation plans (complete)

- Playbook rules are versioned (`1.0`, `1.1`) and the active version is saved with each recommendation envelope for replay.
- The guided flow now captures relevant secondary uses, gaming resolution/refresh/focus, development workload, local-AI workload, content-creation workload, practical preferences and explicit condition policy.
- The deterministic reveal returns only the Save, Recommended and Stretch performance plans that have a concrete target difference. Stretch is omitted for a firm budget and is never treated as an automatic spend authorization.
- Each plan remains SKU-free and unpriced. The reveal states that stock, compatibility, cost and market checks are still required; this work does not make a recommendation purchasable.
- Earlier Playbook version `1.0` remains selectable for session replay and does not apply the new workload overlays.

## Slice 2 — Catalogue and Ready-to-Ship matching (implemented)

- Recommendation sessions now search active customer-visible catalogue entries by plan tier. Component BOM candidates require fresh (24-hour) active listings, explicit condition eligibility, reviewed engineering specs, every required component role, and a full compatibility pass. Candidate search is bounded and fails closed.
- The compatibility gate checks CPU/socket, memory generation, motherboard form factor, cooler support, case clearance, GPU fit and PSU reserve, then applies active catalogue compatibility rules. Missing specs or required slots suppress the BOM.
- Listed Ready-to-Ship prebuilt units are matched only when the unit is not reserved, its build is finalised, the selected condition policy allows its condition, and explicit component or performance evidence meets the hard minimums.
- Candidate results are saved with the recommendation session for replay. They do not include supplier stock, a price, delivery estimate or purchase authority.

## Next implementation slices

### Slice 3 — Supplier evidence and quote snapshots (admin-only foundation)

- Admins can append supplier offer observations with explicit source/reference, stock state, condition, full landed-cost inputs, capture time and delivery estimate.
- Quote assessment loads the persisted offer records, applies freshness, stock, supplier, delivery, condition-policy and fulfilment-mode gates, and requires exactly one eligible offer for every required BOM part.
- The calculation derives parts cost from the selected evidence, applies the full cost stack, contribution/margin floors and the existing sold-market freshness/sample/condition checks.
- Every assessment persists an immutable evidence and decision snapshot, including failed assessments. This is review tooling only: supplier ingestion is still manual, market evidence is still submitted by an admin, and no storefront, checkout or payment path consumes these snapshots.

### Slice 4 — Workshop capacity evidence (admin-only foundation)

- Admins can append week-specific capacity observations with a source/reference and observation time; historical evidence is retained.
- Admin-only read endpoints expose the capacity history and each quote's saved evidence and decision for review.
- Made-to-order quote assessments require a capacity record observed within 24 hours, with open slots for the current or a future ISO build week. Priority's supplier and delivery rules still apply on top of this gate.
- The capacity observation is copied into each quote snapshot. Assessments do not create an order or promise an ETA.

### Slice 5 — Short workshop holds (admin-only foundation)

- A passing, recent made-to-order quote snapshot can acquire one 15-minute hold for its build week. Capture, hold and release operations serialize on that week in Postgres, and the active-hold count cannot exceed the latest evidenced capacity.
- New capacity evidence supersedes earlier observations. The capacity value represents slots available to the quote-hold pool after existing booked work, before active quote holds are subtracted.
- A hold rechecks the latest capacity observation and the saved supplier and sold-market timestamps. Repeated requests for the same snapshot return its active hold; an expired or released hold requires a new assessment. Admin release records a reason, and hold/release events are retained.
- If a new capacity observation has fewer slots than active holds, the newest excess holds are released in the same locked transaction and the reason is recorded.
- These holds are internal planning state. They are not connected to order assignment, checkout or payment, and expiry does not trigger procurement.

### Remaining gates

1. Connect live supplier offer and stock feeds plus trusted sold-market evidence; reconcile feed identity and provenance before using data in customer flows. Existing build sold observations are tied to manual builds, and their `sold_at` field can contain retrieval time rather than a confirmed sale date.
2. Reconcile the legacy order slot model with current `Order` fields, then connect holds to payment-safe order assignment, approval events and honest customer ETA ranges.
3. Connect payment safe-to-procure state, refunds, upgrade assessment and the customer tracking portal. Extend Gem Hunter scoring with all-in cost and max-buy evidence.

No vNext recommendation should be sold until the procurement, market, margin, fulfilment and payment gates above are complete and verified.
