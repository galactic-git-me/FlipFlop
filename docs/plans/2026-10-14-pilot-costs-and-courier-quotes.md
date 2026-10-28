# Confirmed pilot settings and real Parcel2Go comparison

**Date:** 14 October 2026. Development defaults only; no checkout enablement, shipment booking, payment or production change.

## Owner-confirmed settings

- Business is not VAT registered. Draft output VAT is 0; this is not a claim that the goods are zero-rated. Supplier/courier costs retain VAT paid.
- Owner labour is deliberately excluded for now: £0 per build, editable for future costing.
- Packaging allowance: £10 per build, editable per cell/mode.
- Separate shipment insurance allowance: £15 per build, editable per cell/mode. This is an allowance, not a verified insurer premium or active cover.
- Home collection, tracking and signature are required for every mode. No extra Parcel2Go insurance is requested.
- Workshop capacity is operator-configurable by ISO week in the readiness screen; no capacity value is invented. Record available capacity after committed work, without subtracting live quote holds twice. Zero pauses new offers for that week. Current evidence expires after 24 hours.

These defaults populate newly generated drafts. Existing saved drafts or approved policies are not silently overwritten. Other unconfirmed costs remain blank.

## Payment fees checked

Stripe UK published card pricing checked on this date: standard UK cards 1.5% + £0.20; premium UK cards 2.8% + £0.20; EEA cards 2.5% + £0.20; international cards 3.15% + £0.20. Currency conversion can add 2%. Other payment methods and custom account terms differ. [Stripe UK pricing](https://stripe.com/gb/pricing).

New pilot drafts use a configurable **3.15% + £0.20 GBP card processing allowance** to avoid treating the lowest published UK-card rate as universal. This is researched public pricing, not verified merchant-specific account pricing, and it does not cover FX or every non-card method. Review those separately if enabled. Percentage charges apply to the final customer total, not component cost.

## Live quote evidence

Used the configured home collection postcode and the owner's supplied pilot destination postcode through the authenticated **production quote API only**. No booking/order/payment endpoint was called. Addresses and credentials are intentionally omitted here.

Parcel: **25 kg; 57 × 30 × 55 cm**, using PROMETHEUS/manual build #2's stored packed dimensions. Declared value £1,000 was a comparison assumption; separate insurance was not included in the quote request. Request included `Extras: Signature` and no `Cover` or `ExtendedBaseCover`. Provider returned HTTP 200 with twelve quote rows; collection-only candidates below exclude shop/drop-off services. `TotalPrice` includes VAT; `TotalPriceExVat` is not the cost used for this nonregistered business.

| Pilot mode candidate | Service | Courier gross cost | Packaging + separate insurance + courier |
|---|---|---:|---:|
| Fast Track | Parcelforce Worldwide Express AM | £15.73 | £40.73 |
| Standard | Parcelforce Worldwide Express 24 | £13.49 | £38.49 |
| Flexible | Parcelforce Worldwide Express 48 | £13.19 | £38.19 |

Provider collection estimate was 15 October; delivery estimates were 16 October for AM/24 and 19 October for 48. These estimates apply to that quote request, not future guaranteed dates. They exclude procurement, workshop queue, assembly, QA and packing. Flexible's transport saving alone is only £0.30 versus Standard: meaningful overall savings must come from genuine sourcing/economic differences, not artificial delay or a fabricated courier discount.

**Signature remains unconfirmed.** None of the returned rows contained a selected Signature extra, and none advertised Signature in AvailableExtras. The API documentation says selected extras appear in `Extras` and affect the total. Requesting Signature therefore did not establish that it was included. These are valid **base transport estimates for internal comparison**, not verified signature-compliant offers. They have not been inserted as approved courier costs, and checkout remains gated. [Parcel2Go extras contract](https://sandbox.parcel2go.com/api/docs/articles/extras.html).

Next provider step is to establish a bookable signature-required service and its complete price for this parcel, through Parcel2Go's account/service support or a demonstrably supported quote response. Do not remove the signature requirement or label an ordinary tracked service as signed. Requote using each actual customer's route, dispatch date and final package/value before fulfilment.

## Implementation and checks

- New draft costs/rates reflect the confirmed settings and the researched payment allowance; each remains editable through the policy editor.
- Courier helper accepts explicit origin/destination postcodes and a collection-only constraint while preserving old callers. Signature confirmation remains mandatory; an ignored request produces no eligible signed quote.
- Admin readiness includes a workshop-capacity form with explicit week, number of builds and review basis, including zero to pause offers.
- 46 focused backend tests and five admin rendered tests passed. Actual Parcel2Go quote request succeeded; no signature-compliant service was verified. TypeScript/focused lint results are recorded in the session. Development migrations/service adoption and production remain separate from these source changes.
