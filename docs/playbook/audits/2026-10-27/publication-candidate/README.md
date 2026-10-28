# Playbook publication candidate — 27 October 2026

DEV only. The owner authorized catalogue and source approvals and instructed that Windows keys remain with the original Gamers Outlet supplier. No customer offer or selling price was published.

Current machine-readable status is in [summary.json](summary.json). The exact selected BOM, supplier links, compatibility checks and price assumptions are in [playbook.md](playbook.md) and [playbook.json](playbook.json). [standard-prices.csv](standard-prices.csv) separates the Standard commercial quote and estimated contribution from draft pricing guidance.

The final DEV audit has 24/24 complete BOMs, 24/24 deterministic compatibility checks passed, and 24/24 proposals without publication blockers. All 219 selected component entries have eligible Standard and Flexible sources. Fast Track currently has evidence for 27 software entries only, so no complete Fast Track build is offered. Flexible clears the existing genuine-saving gate on one build; the other Flexible quotes are withheld rather than advertising an unverified saving. These mode gaps remain explicit.

## Repairs

- Approved the current Curated hardware candidates under the owner's explicit instruction, retaining deleted/rejected exclusions and role validation. Approval backup: `tmp/playbook-approved-20261027/catalogue-before.json`.
- Filled premium PSU and workstation requirements from captured current supplier offers. Enterprise retains a Threadripper PRO platform, 256GB ECC RDIMM, RTX 6000 Ada and separate internal storage devices.
- Verified the 9975WX replacement against AMD specifications and same-source CPU Mark comparisons; verified WRX90 and SSI-EEB relationships against ASRock and Lian Li specifications.
- Fixed stale exact CPU choices suppressing benchmark-qualified in-stock alternatives, missing RAM-kit title recognition, repeated enumeration of unresolved fit pairs, and shared asset queries loading full catalogue payloads.
- Fixed the original Gamers Outlet integration across supplier identity, explicit source review, software-channel pricing, digital delivery and the shared catalogue. The original Home and Pro source URLs are preserved. Source approval does not claim independently verified entitlement or activation on a physical customer PC.
- Preserved supplier unit evidence for separately procured RDIMMs. Commercial policies explicitly cost all required units; Enterprise's eight-module cost is included in pricing and operating overhead.
- Carried the customer pace choice through policy, per-component source tables, quotes, checkout snapshots and storefront wording. Flexible has no deadline or promised date; Fast Track and Standard retain source, workshop and courier timing checks.
- Linked and approved the exact retail Sparkle B580 TITAN OC source and secondary Kingston NV3 4TB storage options, removing the remaining Standard supplier-timing failures.
- Required separate listing identities for the two storage slots and repaired a broken case photo using a matching model/colour source image.

## Verification limits

The four focused deterministic contract scripts pass. The commercial quote tests (20) and mocked quote adapter tests (10) pass. Seven targeted existing CPU/RAM/manufacturer regression checks pass. An additional exploratory run of the no-fixture requirement functions passed 17 and failed 9; the broader existing suite is not claimed green. Several of those fixtures encode superseded expectations for source-cost fallback and compatibility scope. The five customer-pace regressions and seven admin review component tests pass. Admin and storefront TypeScript checks pass; targeted lint has no errors (two existing storefront accessibility warnings). The loaded admin matrix and sourcing columns and the customer delivery policy were verified in the browser. Full pytest isolation, paid checkout, physical assembly, activation and production deployment were not performed.

The local LLM advisory cross-check returned gateway errors during this run. Deterministic publication compatibility is recorded separately; a model response is never used to invent missing source facts.

## Primary references

- [AMD Threadripper PRO 9975WX](https://www.amd.com/en/products/processors/workstations/ryzen-threadripper/9000-wx-series/amd-ryzen-threadripper-pro-9975wx.html)
- [PassMark 9975WX / 7975WX comparison](https://www.cpubenchmark.net/compare/6799vs5729/AMD-Ryzen-Threadripper-PRO-9975WX-vs-AMD-Ryzen-Threadripper-PRO-7975WX)
- [ASRock WRX90 WS EVO](https://www.asrock.com/mb/AMD/WRX90%20WS%20EVO/index.asp)
- [Lian Li LANCOOL 217 INF](https://lian-li.com/product/lancool-217-inf/)
- [MSI HERALD BE6500](https://uk.msi.com/Networking/HERALD-BE6500-WiFi-7-PCIe-Card/Specification)
- [AMD Ryzen 7 9800X3D](https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9800x3d.html)
