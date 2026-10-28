# SoldComps eBay UK search ledger — 23 October 2026

The SoldComps Basic account allows 100 requests/month. The dashboard shows **8/100 used** after the searches below. Every query used the dashboard's `ebay.co.uk (UK)` filter, and every exported item URL is on `www.ebay.co.uk`.

| # | Query | Results | Useful signal and disposition | Export / notes |
|---:|---|---:|---|---|
| 1 | `gaming PC RTX 4060` | 240 | Broad discovery only; mixes RTX 4060, 4060 Ti, other GPUs, bundles and incomplete units. 43/240 flag accepted offers with unknown actual amounts. | [JSON](soldcomps-ebay-uk-gaming-pc-rtx4060-20261023.json), [screening note](soldcomps-ebay-uk-gaming-pc-rtx4060-20261023.md) |
| 2 | `RTX 4060 i5 12400F gaming PC 16GB 1TB` | 14 | Two recent title-level non-offer matches, not enough for a representative sample or exact build validation. | [JSON](soldcomps-ebay-uk-rtx4060-i5-12400f-16gb-1tb-20261023.json), [screening note](soldcomps-ebay-uk-rtx4060-i5-12400f-16gb-1tb-20261023.md) |
| 3 | `gaming desktop Ryzen 5 5600X RTX 5050 16GB` | 4 | Zero RTX 5050 exact-title matches; returned RTX 5060 and 4060 Ti items. No export retained. This showed CPU-heavy terms were over-restrictive/noisy. | Query outcome retained here; one request used. |
| 4 | `gaming PC RTX 5050` | 65 | 32 titles contain RTX 5050; listings vary substantially by CPU, memory, storage, condition and bundle status. No exact Ryzen 5 5600X build established. | [JSON](soldcomps-ebay-uk-rtx5050-gaming-pc-20261023.json) |
| 5 | `gaming PC Radeon RX 9060 XT 16GB` | 11 | Seven titles name RX 9060 XT, mostly standalone graphics cards. The complete-PC titles have accepted-offer flags; one also says 8GB, conflicting with the candidate's 16GB card. | [JSON](soldcomps-ebay-uk-rx9060xt-gaming-pc-20261023.json) |
| 6 | `gaming PC Radeon RX 9070 16GB` | 4 | Includes an ambiguous `9070 XT/GRE` listing and separate 9070/9070 XT systems with different CPUs/specs. No exact match for the draft Ryzen 5 9600X or Ryzen 9 9900X builds. | [JSON](soldcomps-ebay-uk-rx9070-series-gaming-pc-20261023.json) |
| 7 | `gaming PC RTX 5060 Ti 16GB` | 172 | High-yield: 105 titles name 5060 Ti, 102 read as complete PCs, 15 flag accepted offers. One recent brand-new non-offer row names Ryzen 5 9600X, 32GB DDR5, 2TB and RTX 5060 Ti 16GB: item 396841543022, £1,229, free postage shown. This is a single title-level lead shared by three draft cells, not a pricing sample. | [JSON](soldcomps-ebay-uk-rtx5060ti16-gaming-pc-20261023.json) |
| 8 | `gaming PC RTX 5070 Ti 16GB` | 65 | 37 title-level GPU matches; several full PC sales, but the draft Ryzen 9 9900X combination is not verified in the returned rows. Similar-spec rows are contextual only. | [JSON](soldcomps-ebay-uk-rtx5070ti16-creator-pc-20261023.json) |

## Use and next query rule

The query phrase `gaming PC` plus a GPU family produced better discovery than adding the CPU to the search text; exact CPU/RAM/storage should be screened on the returned titles and, for any proposed comparable, verified on the item details. Do not repeat any of these terms. The current draft configurations and source grants are still unresolved, so additional SoldComps requests should wait until a specific retained cell has a sourceable, compatibility-reviewed BOM and the source permission gate is cleared. This preserves 92 requests for evidence that can change an actual Playbook decision.

All exports are local research only. No SoldComps/eBay rows were imported into the demand store or used to publish a price. Accepted-offer rows remain unknown-price data; component-only listings are not complete-PC sales. The results do not establish source rights for automated collection, commercial reuse or publication.
