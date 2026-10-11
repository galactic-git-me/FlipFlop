# RGB vendor integration review

**Reviewed:** 2026-09-30  
**Purpose:** Decide how to fulfil the proposed FlipFlop-branded RGB setup across ASUS, MSI, and GIGABYTE systems.  
**Status:** Architecture guidance only; no adapter or hardware write is approved by this review.

## Finding

The motherboard vendors expose separate lighting ecosystems and SDKs: [ASUS Aura SDK](https://www.asus.com/campaign/aura/us/SDK.php), [MSI Mystic Light SDK](https://www.msi.com/Landing/mystic-light-rgb-gaming-pc/download), and [GIGABYTE RGB Fusion SDK](https://www.gigabyte.com/mb/rgb/sdk). Their SDK descriptions identify their own compatible vendor products and control paths. The available official materials do not define a common profile file format or promise that a saved Aura profile can be imported into Mystic Light or RGB Fusion.

Therefore, copying a profile file from an ASUS workstation to MSI/GIGABYTE is not a dependable implementation strategy. A similar visual result might be recreated, but it requires explicit mapping of the intended effect to the target ecosystem and exact supported hardware.

## Recommended implementation boundary

1. Store a reviewed FlipFlop *effect intent* independently of vendor files: palette, effect family, speed/brightness where meaningful, intended zones, and a stable profile version.
2. Resolve the exact motherboard/controller and connected-device support from the built specification and an operator hardware check.
3. Use a vendor-specific reviewed adapter to map the intent to that vendor's supported controls. Unsupported zones/effects must produce a visible `needs_review` result; do not silently approximate.
4. Keep the RGB checklist operator-managed until each adapter has documented licensing/distribution rights, official source/version provenance, a tested exact-board compatibility matrix, recovery/reset steps, and supervised physical-hardware acceptance.
5. Record the result and operator note. If no approved exact-hardware profile exists, record `not configured`; never report success merely because a vendor utility was installed.

Do not bundle SDK binaries or let the LLM generate or execute lighting commands. The LLM may draft a customer-friendly explanation from reviewed evidence; deterministic adapters and an explicit operator confirmation own all device writes.

## Primary sources

- ASUS, [Aura SDK](https://www.asus.com/campaign/aura/us/SDK.php), describes an SDK for the Aura Sync-capable ecosystem.
- MSI, [Mystic Light SDK for developers](https://www.msi.com/Landing/mystic-light-rgb-gaming-pc/download), describes control of MSI lighting-capable products and its developer toolkit.
- GIGABYTE, [RGB Fusion SDK](https://www.gigabyte.com/mb/rgb/sdk), describes an SDK for RGB Fusion motherboard lighting control.

These pages support the separation of vendor-specific control surfaces. They do not prove support for a particular motherboard revision, accessory, effect, binary redistribution, or an adapter implementation.
