# Cross-listing implementation note

## Current capability boundary

The admin cross-listing screen is intentionally backed by the existing `manual-builds` API. A build is the canonical product record; eBay listing IDs/status and storefront product IDs are channel identities. The screen never invents an external listing ID or URL.

| Channel | Current behaviour | Why |
| --- | --- | --- |
| eBay UK | API action reuses the existing seller OAuth and `post-to-ebay` backend operation. | eBay's Inventory API supports inventory items, offers, publish, update and withdraw operations. The existing account flow remains the only credential flow. |
| FlipFlop.shop | API action reuses `list-on-storefront` and links an existing product/build. | The direct storefront is an existing first-party API surface; cross-listing must not create a duplicate product. |
| OnBuy | Manual-assist pack with `manual_action_required`. | No OnBuy seller connection/API/feed is configured in this repository, so the app does not claim to publish. |
| Amazon | Manual-assist pack with `requires_approval`. | Amazon SP-API listing creation depends on seller authorization, the Product Listing role, marketplace/category requirements and identifiers. |
| Facebook Marketplace | Manual/catalog-assist pack. | The app does not automate personal Marketplace posting or authenticated scraping. A future implementation must use an approved business catalog/feed route. |
| Vinted | Manual-assist pack. | No approved seller integration is configured; consumer-account automation is intentionally not implemented. |

Official references used for these capability decisions:

- [eBay Inventory API](https://developer.ebay.com/api-docs/sell/inventory/overview.html)
- [Amazon Manage Product Listings with SP-API](https://developer-docs.amazon.com/sp-api/docs/manage-product-listings-guide)
- [Amazon SP-API onboarding](https://developer-docs.amazon.com/sp-api/docs/onboarding-overview)
- [OnBuy selling](https://www.onbuy.com/gb/sell/)

## What is implemented

- Sidebar navigation and `/cross-listing` admin page.
- Source refresh from existing build records, eBay listing state and storefront product state.
- Search, source/status filters, sorting, current-filter select-all and multi-select.
- Canonical listing normalisation with platform-safe channel capability adapters.
- Per-listing review/edit for title, description and price, with copied/transformed field summary.
- Explicit confirmation before calling an API destination.
- Batch result reporting with partial success preserved and manual-only results clearly labelled.
- Downloadable manual listing packs containing content, image URLs and manual steps.
- No fake published state, mock URLs, private-image hotlinking or personal-account marketplace automation.

## Remaining backend work before full production automation

The repository currently has no cross-listing persistence/job tables, channel connection records beyond the existing eBay OAuth state, sales-event reconciliation worker, customer/order/portal association workflow for non-eBay channels, notification store, or courier adapter contract. Those require backend migrations and provider credentials/approvals. The UI therefore reports the capability boundary instead of treating browser state as durable job state.

Before enabling additional API destinations, add durable idempotent records for batches/jobs/listings/events, provider request IDs, audit events, channel connections and manual-action tasks. Add scheduled order reconciliation/webhook receivers and the confirmed-sale transaction/lock before automatic cross-channel delisting is enabled.
