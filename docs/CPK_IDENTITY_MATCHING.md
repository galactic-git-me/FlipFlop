# Gem Radar CPK identity matching

Gem Radar treats identifiers as aliases attached to one canonical product. The
identifier used to create a CPK does not limit which later identifiers can
resolve to it.

## Evidence order

New CPK keys are seeded in this order: validated GTIN, manufacturer plus MPN,
brand-scoped model number, eBay ePID, Amazon ASIN, vendor product ID, then a
category-aware normalized title key. Every captured identifier is registered
as an alias when it can be safely attached to the selected CPK.

Vendor product IDs are namespaced by the product-page hostname. The extension
captures them from structured product data tied to the exact result card, or
from an explicit vendor product object. They remain separate from offer/listing
IDs, which can identify a single sale rather than a product.

Amazon ASINs establish an Amazon product CPK even when no current retailer
listing matches. That gives a later observation an exact alias to resolve.
An ASIN-backed CPK does not by itself prove that another vendor currently has
the item; cross-vendor coverage is counted only when another vendor listing
resolves to the same CPK.

## Conflict handling

If exact identifiers point to different CPKs, the listing remains unresolved
for review. If exact identifiers agree on one CPK but a weaker title alias
points elsewhere, the exact ID wins and the title alias is left unchanged.
Backfill never reassigns a listing CPK or merges existing CPK groups.

The title-key resolver is deliberately narrow. It supports exact CPU model
keys, variant-complete RAM and SSD keys, GPU keys with an exact board part code,
and configured case keys. Unsupported or ambiguous titles do
not create a title alias.

## Backfill and audit

`flipflop-api/scripts/backfill_cpk_identity_aliases.py` defaults to a read-only
report. `--apply` is restricted to the verified DEV database and inserts only
aliases that point to one existing CPK. Conflicting aliases are listed with
their CPKs and sample listing IDs for review. It also assigns ASIN-resolved
CPKs to previously unmatched Amazon bestseller observations without changing
marketplace listing assignments.
