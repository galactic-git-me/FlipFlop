# Product image standard

Decision: 14 October 2026. Applies to direct and indirect product publishing.

Keep the highest-resolution uncropped original byte-for-byte. Derivatives are
separate assets; original downloads and build photography remain available.
Preserve colour, lighting, RGB presentation and complete-case framing. Use a
consistent shoot angle and neutral background; resizing does not improve
lighting or create detail missing from a low-resolution source.

| Use | Default | Treatment |
| --- | --- | --- |
| eBay, Google Shopping, Facebook Marketplace, Gumtree, OnBuy, Vinted | 1600 × 1600, 1:1 | Complete photograph, no stretch or product crop |
| Amazon | 1600 × 1600, 1:1 | Pure-white background and strong product coverage; explicit review required |
| Etsy | 3000 × 2250, 4:3 | Product frame contained in the central square so thumbnail crops remain safe |
| Website product cards | 1600 × 1600, 1:1 | Square card; contain the complete image |
| Website hero / banner | 1920 × 1080, 16:9 derivative | Original and flexible product-page galleries retained |
| Social product photographs | 1080 × 1350, 4:5 | Preserve full product frame |

The renderer uses deterministic containment, EXIF orientation and sRGB colour
handling. It never paints a promotional sticker or watermark onto a channel
photograph. Website stickers remain separate, evidence-based UI elements.
Amazon trims empty white margins, but does not pretend a room photograph has
a pure-white background just because white padding was added. Supply a clean
white-background photograph/cutout and confirm its background and framing in
the review. Performance/specification cards are website/report assets rather
than primary product photographs.

## Publishing workflow

### Curated catalogue listing photos

In Curated Builds → Listing Images, all captured photos and video clips for an
approved exact product match are included automatically, including public media
from an exactly linked build or component listing. Newly captured media is
included when available; there is no per-photo or per-video approval step.
Product-match approval remains separate to prevent media from the wrong product
being attached to a Playbook component. In Catalogue → 3D Assets, choose one to
four captured photos as model references. Generated models still require the
normal model review and approval before they can be published.
The picker combines captured bestseller, scored-listing, observation and
catalogue-listing media for the same product, plus our linked build photographs
and video clips (including originals in the build-owned Media folder). Private
dispatch evidence and generated specification/registration cards are excluded.
Duplicate URLs are shown once.
This does not fetch an uncaptured retailer gallery or approve product identity.

### Build photographs

1. Upload originals in the build's Media tab. All format variants are prepared.
2. Choose **Preview channel photographs** to inspect/download individual formats.
3. Review clean photography and, for Amazon, background/product coverage.
4. Cross-listing's **Review & submit** previews the selected channel variants
   before submission. API eBay drafts, publishing and revision, Amazon,
   scheduled relisting and product social media use the shared derivatives.
5. Each source content hash and policy version identify its immutable outputs.
   New source content requires a fresh review. Low-resolution enlargement is
   disclosed rather than described as additional photographic detail.

Preview and approval endpoints require operator access and restrict their
inputs to that build's original product photographs. Original bytes and
derivatives live under `data/uploads/channel-images/<sha256>/`; approvals and
dimensions are recorded in the manifest. Remote downloads are bounded and
private-network URLs and build-private evidence paths are rejected.

The website API exposes `card_photo_url` and `website_hero_url` for prepared
assets, with original-photo fallback. No external listing is published by
image generation or preview. Social connectors remain fixture/sandbox
connectors; prepared images do not imply a live social integration. Channels
without adapters use downloadable assets/assisted publication. Production
deployment and external delivery remain separate validation gates.

## Verification on 14 October 2026

Authenticated DEV browser walkthrough covered photo preview, clean-photo
approval, selecting eBay alone and submitting a named Sandbox test build.
The resulting [Sandbox listing 110591158452](https://sandbox.ebay.com/itm/110591158452)
is externally visible with its photograph loaded. The seller Inventory API
returned its hosted eBay image URL; that image returned HTTP 200 at 1600 x 1600.
eBay publishing uploads reviewed derivatives through the current Media API,
with a seller-token-scoped expiry cache. Connection status checks the actual
configured listing environment.

DEV derivative URLs are not automatically deployed to the production website
(the tested public URL returned 404). Amazon submission now checks public
image bytes and dimensions before contacting the listing API. Amazon's UK
account/app authorization check currently returns 403. Production deployment
and Amazon publication have therefore not been verified.

Storefront ESLint is now configured. With Node 24, the six image-related files
pass lint and TypeScript passes. The full source scan fails with 140 errors
and 84 warnings; its report is `FlipFlop.shop/output/lint-baseline.json`.
The subsequent storefront cleanup resolved all 140 source errors without
disabling lint rules. Full lint now reports zero errors; remaining warnings
are recorded in `FlipFlop.shop/output/lint-current.json`.

## Source guidance

These are presentation standards, not promises of search ranking rewards.

- [eBay photograph guidance](https://www.ebay.com/sellercenter/listings/photo-tips): recommends 1600 × 1600.
- [Amazon image requirements](https://sellercentral.amazon.com/help/hub/reference/external/G1881): white background and product coverage.
- [Google image guidance](https://support.google.com/merchants/answer/6324350?hl=en): recommends around 1500 × 1500 or larger.
- [Etsy image guidance](https://help.etsy.com/hc/en-us/articles/115015663347-Requirements-and-Best-Practices-for-Images-in-Your-Etsy-Shop): landscape or square first image; sufficiently large originals.
