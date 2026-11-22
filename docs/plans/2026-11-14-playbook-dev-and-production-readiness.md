# Playbook DEV validation and production readiness

**Readiness:** Not ready; evidence review and proposal repairs are required
**Latest audit:** 14 November 2026, 18:21 UTC
**Audited environment:** local DEV API (`127.0.0.1:4311`) and its local database; API reports branch `dev`, commit `cc50bbd635782e3e13ea724ad730b30c3a9340e9`, and a dirty source tree. This is not proof of the remote customer-facing DEV site or production.
**Audit output:** `flipflop-api/output/playbook-readiness-2026-11-14-refresh/README.md` and `readiness.json`.

## Latest refresh — 14 November 2026, 18:21 UTC

- The proposal-only rebuild saved **24 draft cells** from stored data, calculated complete component costs for **20/24**, made **0 provider requests**, and **did not publish**. Four cells still lack complete cost inputs; the optional `--require-complete` gate correctly failed before the successful draft-only rerun.
- The fresh readiness audit still finds **0/24 approval-ready**, **0/24 public prices**, **0/24 approved selling prices**, and **0/24 with all three delivery prices**. The 20 draft cost calculations are not approved or customer-visible prices.
- Hardware remains complete in **20/24** cells; **4** have missing required roles, **3** lack separate secondary storage, and compatibility is verified in **17/24**. The audit reports **55** motherboard facts and **11** product-engineering suggestions awaiting operator review.
- The supplier evidence filter currently finds **3 distinct products** suitable for review across **20 proposal appearances**. This remains a narrow subset of the sourcing options available; the supplier captures have not been operator-approved, and no proposal is ready for approval. Refresh exact listing, stock, postage, and arrival evidence for each chosen part in Admin.
- Media is still clear: **96** approved active models returned HTTP 200, with no proposal photo-approval or final-model blockers.
- The local API is healthy and serves **8 Playbooks**, but `/api/public/curated-builds` returns **0 builds**. The local Admin route still redirects to `/login?reason=session_missing`, so I could not perform the authenticated supplier, compatibility, licence, or price approvals.
- No production action was taken. The checkout remains dirty, so it is not a release candidate.

## Historical check — 14 November 2026, 15:03 UTC

## Previous audit result — rechecked at 15:03 UTC

- There are 24 proposals across 8 active segments. **0/24 are ready for approval**, **0/24 have public or approved selling prices**, and **0/24 have all three delivery prices**.
- Hardware is complete for 20/24. Four proposals still lack required roles: Discovery (motherboard), Reliant (motherboard), Enterprise (CPU, PSU, RAM and second storage), and Protostar (motherboard). Three proposals also lack a separate secondary storage device.
- Compatibility is verified for 17/24. The remaining seven still need exact source facts or compatible component choices.
- Media is not a current blocker: 96 active approved models were checked through the local API and returned HTTP 200; the proposal audit found no missing photo approvals or final models.
- Three exact supplier observations were previously imported into DEV procurement evidence: MSI B550M PRO-VDH WIFI motherboard (£109.99); ASUS TUF B850-PLUS WIFI motherboard (£185.99); Corsair FRAME 4000D RS case (£89.99). Those evidence imports did not approve component proposals, selling prices, or publication.
- The current generated-proposal feed exposes four distinct listings (23 proposal appearances) meeting the audit's basic source-review filter: MSI B550M PRO-VDH WIFI (£109.99; in stock; 4 working days), ASRock Arc B580 Challenger (£514.49; dispatch estimate 4–5 days), Lian Li Lancool 207 (£74.99; one left in stock), and Corsair FRAME 4000D RS (£89.99; in stock; 3 working days). These source rows were observed around 04:33–04:35 UTC, and the exact Amazon pages describe first-order free-delivery eligibility for some offers. The automated filter is not an operator review: confirm seller, stock, conditional postage and delivery timing in Admin before treating any offer as accepted. The count fell from 5 listings/37 appearances at 06:26 to 4/23 at 15:03, without changing the overall price or readiness totals.
- There are 55 motherboard facts awaiting review (17 AI-generated, 25 listing-title, 13 manufacturer captures) and 11 exact-product engineering suggestions (3 cases, 5 cooling, 2 motherboards, 1 PSU).
- Two Windows licence offers are priced and marked source-reviewed, but there are **0 fresh captures** and **0 customer-enabled offers**. A fresh source check and resale/transfer-rights decision remain necessary.
- Several proposals also need fresh stock/price evidence. Resolve missing roles with exact supported products; do not use a fuzzy substitute.
- The API returns all 8 Playbooks from `/api/public/playbooks`, but `/api/public/curated-builds` is empty. Local storefront `/products` renders correctly; choosing “Browse all curated builds” shows “No curated builds are available right now.” No customer Playbook or checkout flow can be validated until at least one exact offer is approved and published in DEV.
- At 15:03 UTC, the local API health endpoint returned `ok`, `/products` on port 4313 returned HTTP 200, and the public curated-builds API returned 0 builds. The HTTP response alone does not verify the rendered customer UI. The authenticated Admin commercial route redirects to `/login?reason=session_missing`.
- The scheduled rebuild that began at 06:13 UTC succeeded at 06:17 UTC. The 15:03 audit is read-only; no variants or builds were published. The Admin review route still redirects to `/login?reason=session_missing`.
- The separate MVP-autonomy endpoint still reports `mode=standard`, 0/24 enabled policies, and 8 High-end cells without budget ceilings. Keep that distinct from the requested Fast Track, Standard and Flexible customer modes; it must not silently override the chosen three-mode offer.

## Additional supplier spot-check — 14 November 2026

An independent spot-check found a direct UK retailer offer for the exact Lian Li LANCOOL 207 (MPN LAN207RX) at £81.99 inc VAT, marked in stock with free delivery; express delivery is £9.99. The product page does not state an arrival estimate, so this does not satisfy the Playbook's delivery-timing gate without a checkout or retailer confirmation. The separate Direct Computers page for the same MPN is marked unavailable and must not be used as an in-stock offer. For the ASRock Arc B580 Challenger (MPN B580 CL 12GO), a comparison listing showed £254.75, in stock, free delivery and three working days at PCHUB, but the retailer's own product page and live offer could not be verified. These external alternatives remain unapproved; they are separate from the four Amazon offer captures listed in the current audit.

## Owner actions, in order

1. Sign in to Admin, then open **Playbooks → Commercial → Supplier listings** (`/playbooks/commercial?area=suppliers`). Start with the exact CPU, RAM and PSU rows flagged stale or unavailable. Search the exact part number/model across the available retailer offers; capture a current exact listing and verify seller, condition, stock, item price, postage and delivery date. The automated filter currently surfaces only three distinct products for review, so this review must include sourcing additional exact offers where available. I could not submit these operator reviews because the local Admin session redirects to login.
2. In **Compatibility**, review the 55 motherboard facts and 11 product-engineering suggestions against their linked exact evidence. Rebuild, then verify each impacted proposal. Resolve the four missing BOMs and the three missing secondary-storage roles using exact requirement-matching products; do not substitute based only on similarity.
3. In **Software licences**, refresh the two Windows sources and review licence type, current offer terms and resale/transfer rights. A supplier’s claim does not establish independent resale entitlement. Keep customer enablement off unless those rights are evidenced.
4. Allow the scheduled supplier refresh/rebuild to run, then review price, stock, postage and arrival evidence for every chosen component. Amazon’s verification interstitial blocks exact capture for many pages; use another genuine exact supplier source where available, otherwise leave that component unavailable.
5. Review the generated Fast Track, Standard and Flexible selling prices and delivery timings against the existing pilot cost/margin rules. The current audit has 0/24 prices in every mode. Flexible must be supported by a genuine saving; do not enter a manual price. Keep these three customer paces separate from the disabled Standard-only MVP-autonomy switch.
6. Re-run the readiness audit after the evidence and proposal fixes. Require complete BOMs, verified compatibility, fresh source evidence, all three reviewed price/timing options, and zero publication blockers for each build selected for the pilot. Resolve High-end budget ceilings only if the separate MVP-autonomy policy is being enabled.
7. Once at least one build is genuinely approved and published in local DEV, validate `/products` and its exact build/configuration page, all supported paces, total and timing, availability, quote acceptance, sandbox payment, confirmation and webhook recovery. Record the build ID, source SHA and observed results.
8. Prepare a scoped release from reviewed changes while preserving the dirty worktree. Production remains a separate gate: the workflow requires a tag reachable from `main`, a merged production PR with passing checks, DEV schema attestation, and manual dispatch with the exact confirmation `DEPLOY-PRODUCTION`.

## Release decision

Do not publish from the current audit state. The customer-facing curated page is reachable but empty, and no Playbook checkout can be validated. Local app availability is verified; authenticated Admin review is not. The worktree contains unrelated user changes and deletions, so it is not a release candidate. The source refresh and proposal rebuild do not approve facts or publish builds. Re-run the read-only audit after owner reviews and the next scheduled refresh; production remains untouched.
