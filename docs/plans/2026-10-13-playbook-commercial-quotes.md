# Playbook commercial quotes: first implementation slice

**Status:** Implemented for admin assessment; unit and mocked adapter verification only  
**Date:** 13 October 2026

**Follow-on:** [Commercial checkout integration](./2026-10-13-commercial-checkout-integration.md) now connects enabled, reviewed core policies to customer comparisons, payment and order recovery, with real disposable PostgreSQL validation. The assessment-only boundaries below describe the initial slice; the follow-on document defines the current customer path and remaining release gates.

## Existing flow and ownership

`app/routes/payments.py` calls `price_playbook_build`, validates the selected catalogue configuration, calls `delivery_choice`/`apply_component_delivery_estimate`, then adds the separate delivery fee to the build total. `app/routes/webhooks.py` recovers the Playbook/cell and order details from saved payment metadata. This slice does not change either payment path.

The parent `Playbook` already owns `pricing_model`; the canonical curated definition identifies the cell by `id` and maps it to the parent by `segment == Playbook.name`, matching public curated catalogue behaviour. Store each cell's reviewed commercial policy at `pricing_model.commercial_cells[cell_id]`. No new table, cell identifier or migration is introduced. The existing `CuratedBuildSegment.selling_price` remains legacy pricing data; it does not override these assessments or become a second commercial policy.

## Admin API

All paths below are under `/api/commerce-intelligence`, with the existing admin authentication dependency.

1. `GET /playbooks/{playbook_id}/cells/{cell_id}/commercial-policy` returns the canonical definition, its SHA-256 and any current policy. No default profit, cost or tax values are invented.
2. `PUT /playbooks/{playbook_id}/cells/{cell_id}/commercial-policy` accepts `CellCommercialPolicy` from `app/schemas/commercial_quote.py`. Supply the current definition hash, exact source `part_key` values for the reviewed complete BOM, condition, sold-market evidence, tax/fee/reserve rates, and explicit costs, profit floors and timings for all three modes. Start at version 1; subsequent saves must increment by exactly one. The locked update preserves unrelated pricing fields and records the old/new policy, definition and operator in an append-only `PriceQuoteSnapshot` with status `policy_review`.
3. `POST /playbook-quotes` accepts only identity, capacity references and condition consent:

```json
{
  "playbook_id": 1,
  "curated_build_id": "FF-GVG-01",
  "capacity_evidence_ids": {
    "fast_track": 10,
    "standard": 10,
    "flexible": 11
  },
  "nonnew_consent": false
}
```

IDs above illustrate the contract; they are not known live records. Capture supplier and workshop evidence using the existing authenticated evidence endpoints. Exact source part keys must be reviewed against every core component, case and separately procured licence before policy authoring. No arbitrary SKU substitution or customer-priced request is accepted.

The server loads current listing observations, discarding older stock observations for the same part/supplier/channel/listing reference. `evidence_ref` must consistently identify the source listing. It independently resolves current, unsuperseded workshop evidence and active holds for each mode. Missing capacity disables that mode. A future workshop week contributes waiting time. Supplier arrival, reviewed workshop queue/build/QA/packing time and courier time must fit the mode target.

Results contain server-computed totals, contribution, margin, cost breakdowns, supplier/capacity IDs, policy/definition hashes, estimated working days, expiry and comparison against Standard. The snapshot retains complete reviewed policy, canonical definition and input evidence. Flexible requires a valid Standard comparison and a strictly lower price; Fast Track must be faster and more expensive when Standard is available. Missing/stale evidence or failed commercial checks disables the affected mode.

## Money and tax semantics

All arithmetic uses Decimal. Operating costs are explicitly authored net of any recoverable VAT. Supplier landed costs plus risk are conservatively included at their observed amounts; the service does not infer or deduct input VAT from vendor prices. An operator must not assume the scraper established VAT recoverability. `vat_rate` is the reviewed output VAT rate (explicit zero for no output VAT), not a deduction from supplier costs. Sold-market comparison uses the same gross customer-price basis.

Net revenue is gross price less output VAT. Payment percentage, warranty reserve (minimum 5%) and returns reserve are each computed from the final gross selling price and rounded up individually. Fixed payment charges belong in the mode's explicit operating costs. The solver rounds the selling-price floor up and checks actual rounded contribution and margin before adding the mode premium. The quote never relies on an old global £49 surcharge to establish profitability.

## Boundaries and remaining work

These are review assessments with `purchasable: false` and snapshot status `assessment_only`; existing capacity reservation routes cannot treat them as offerable payment quotes. They neither reserve capacity nor promise stock retention. Quote expiry is capped at 15 minutes and the earliest supplier/capacity/market evidence expiry. Changed observations can invalidate an assessment sooner; customer acceptance must revalidate them in the next slice.

No policy was populated in a live database. No customer payment, provider call or production deployment was performed. The admin editor, selectable upgrades, promotions, custom configurations, automatic supplier ingestion into this contract, immutable accepted checkout quotes and payment/order integration remain subsequent work. Authored workshop/courier timings produce estimates, not live carrier guarantees. Compatibility is inherited from the reviewed core definition; this endpoint is not a substitute for checkout's configuration validation.

## Verification

Run from `flipflop-api` with `PYTHONPATH` set to that directory:

```powershell
.venv\Scripts\python.exe tests/test_playbook_commercial_quote.py
$env:DATABASE_URL = 'postgresql+asyncpg://unused:unused@127.0.0.1:1/commercial_unit_test'
.venv\Scripts\python.exe tests/test_playbook_commercial_quote_adapter.py
```

The first suite imports only pure pricing/schema modules. The second uses mocked sessions and a minimal in-memory FastAPI app, never application startup or database connections. The unreachable `_test` URL guards against accidentally using the developer database during imports. The repository-wide pytest fixtures are not loaded.

Results: 15 pure regressions and 10 adapter regressions passed. Adapter coverage includes successful stored-evidence quotes, policy version conflicts/audit snapshots, changed definition, missing policy, wrong parent, newer out-of-stock evidence and unauthenticated HTTP rejection. PostgreSQL persistence, full API startup and browser/payment integration remain unverified.

The existing FastAPI/Starlette TestClient emitted a deprecation warning about its installed HTTP client. It did not fail these checks; dependency changes are outside this slice.
