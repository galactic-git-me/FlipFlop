# Existing listing backfill: DEV verified

Examined all 55,285 distinct saved listings using the latest observation per listing, across 571,903 observations. No provider calls, new scrapes or product detail requests. Historical sold observations and capture timestamps were not rewritten.

Applied 443 additional per-listing identity changes, verified every saved key, and recalculated 386 current-price aggregates. Zero concurrent skips; original mappings and aggregates backed up.

| Measure | Before | Verified after |
|---|---:|---:|
| Products linked across sources | 183 | 196 |
| Products linked across direct retailers | 58 | 67 |
| Amazon products linked another source | 68 | 74 |
| Amazon products linked another direct retailer | 35 | 42 |

Metrics count the manufacturer-plus-MPN identifiable cohort; they do not measure all title-only links or establish manual matching precision. Direct retailers exclude eBay and Google Shopping. Ambiguous or conflicting evidence remains unmatched. Older matched listings are not thereby made active or fresh. Production was not modified.

Backup: `search-matching-all-history-backup-235209.json`
