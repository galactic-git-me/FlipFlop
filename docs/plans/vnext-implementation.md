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

## Next implementation slices

1. Connect approved SKUs and compatibility rules; form compliant BOM candidates and ready-to-ship matches. Suppress recommendations when evidence is missing.
2. Add supplier offers, condition policies, landed costs, full cost stack, contribution floors, market evidence and immutable quote snapshots.
3. Gate Priority, Standard and Flexible by actual suppliers, stock, workshop capacity and sourcing policy. Add honest customer ETA ranges and approval events.
4. Connect payment safe-to-procure state, refunds, upgrade assessment and the customer tracking portal. Extend Gem Hunter scoring with all-in cost and max-buy evidence.

No vNext recommendation should be sold until the procurement, market, margin, fulfilment and payment gates above are complete and verified.
