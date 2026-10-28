# SoldComps eBay UK research capture — RTX 4060 gaming PCs

- Captured: 2026-10-23 16:47 UTC
- Provider: SoldComps dashboard, account flipflop
- Query: `gaming PC RTX 4060`
- Marketplace filter: `ebay.co.uk (UK)` (verified selected in the dashboard before search and in the results filter)
- Search results: 240 records, 240 exported; eBay indicated 400 matching results overall
- Provider quota: 1 of 100 monthly requests used after this query
- Export: [soldcomps-ebay-uk-gaming-pc-rtx4060-20261023.json](soldcomps-ebay-uk-gaming-pc-rtx4060-20261023.json)
- Source page: https://sold-comps.com/dashboard/search

## What the capture contains

The export contains individual listing identifiers and UK item URLs, titles, condition, sale and postage amounts, dates, seller feedback, and a `bestOfferAccepted` flag. All 240 returned rows use GBP. Their sale dates range from 2026-03-06 to 2026-10-23. The first 240 are the provider's returned page; the dashboard reports 400 matches on eBay.

A date-only screen finds 145 records dated 2026-09-23 through 2026-10-23. This is a discovery set, not a comparable sample. The search is broad and the returned titles include RTX 5060 and RTX 4060 Ti machines, accessories/bundles, incomplete systems, mixed GPU claims, and listings with too little specification to match a sellable build. Across the full export, 43 records flag `bestOfferAccepted`; their displayed sold amount is not necessarily the accepted transaction amount.

## Decision use

Do not calculate or publish a single sold median from this search. It does not establish equivalent CPU/GPU/RAM/storage/condition, complete-system contents, Windows licence, or delivery basis for a candidate Playbook cell. Preserve the raw provider rows as source research; only individually reviewed, complete system transactions can move into the PRD's `complete_pc_sale` evidence contract. Keep the sale amount and postage separate. Exclude accepted-offer rows from exact-price calculations unless the actual accepted amount is independently available.

The export is stored as local research input. It has not been imported into the production demand evidence store: that path requires a current source permission grant, and the repository currently fails closed without one. The capture itself does not approve automated collection, commercial reuse, or publication rights.
