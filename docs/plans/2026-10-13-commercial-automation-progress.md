# Approved commercial pilot: implementation and evidence

## Implemented in source

- Approval recorded for the decision pack's development/staging operating model; production publication remains separate.
- New draft policies receive approved tier contribution floors, 5% warranty reserve, 2% provisional returns reserve and 7/14/28-working-day ceilings. Canonical `High-end` maps to the pack's premium tier. Missing actual costs, VAT/payment terms and workshop timings remain unknown. Fast Track's premium remains unset until a Standard total can support its approved calculation.
- Optional collector stock state/evidence is captured with original price, postage, URL and capture time in an additive nullable JSON column. Lightweight sighting updates cannot renew this commercial capture. Known commercial captures get new observations on a re-scan, even at an unchanged price.
- Overclockers extension extraction passes explicit availability-element evidence; unknown/backorder text is not positive stock. Existing filtering behaviour remains in place, so this does not guarantee every out-of-stock card reaches the API. Other vendors still need their individual source-backed adapters.
- Previously reviewed exact catalogue links can be reconciled without changing business rules or enabling checkout. New unknown/negative availability cannot inherit an old positive stock review. Unchanged retries reuse evidence; original timestamps remain unchanged. Ambiguous links and unverifiable original captures are reported for review.
- Hourly scheduler and completed-scan hooks are wired behind `COMMERCIAL_RECONCILIATION_ENABLED`, default false. Runs use a database advisory lock, a 120-second limit, durable success/failure records and the existing scheduler history. The admin readiness page shows run health and provides a manual refresh action. Additional retry/alert policy and source coverage remain follow-up work.

## Verified

59 focused backend tests passed against the explicit disposable PostgreSQL `flipflop_automation_test`, including migration round trip, evidence refresh/retry, negative stock and failure auditing; four admin rendered tests passed. Admin TypeScript/focused lint and production build passed. Extension TypeScript, nine focused stock/schema tests and DEV build passed. No production migration, service restart, installed extension reload or live payment was performed.

## Read-only development inventory

The local `pcflipper` database has 11 Playbooks, 22,342 catalogue variants and 713 cases, but zero supplier-offer evidence, workshop-capacity evidence and commercial snapshots. Its recorded migration revision is `20261012_0002`, and the new commercial provenance column is absent. No developer data was changed by this inventory. The serving API on port 4311 is not running with reload.

Do not enable or restart into the new observation model until the development schema has been reconciled with its pending migration branches and upgraded deliberately. Do not stamp past missing migrations. The new column was tested only in the disposable database. Scheduling remains disabled.

## Outstanding pilot inputs and subsequent work

Actual VAT/payment terms, labour/material/shipping/insurance costs, comparable sold-PC evidence and workshop capacity are still required for a real pilot. See [the input guide](commercial-inputs-explained.md). Approval of the policy model does not establish these facts.

Next: safely prepare the development migration path and populate one reviewed cell; then complete source coverage/withdrawal and run alerts, full configuration/service upsells, promotion enforcement, normalised demand/sold adapters and outcome calibration. Bounded repricing remains recommendation-only until the approved pilot conditions are met. The full commercial engine is not complete.

## 14 October input update

The owner confirmed nonregistered VAT status, zero owner-labour allowance for now, configurable £10 packaging and £15 separate insurance, and configurable capacity. These now populate new draft defaults alongside a researched, editable Stripe card-fee allowance. A real Parcel2Go quote comparison was performed. See [confirmed costs and courier evidence](2026-10-14-pilot-costs-and-courier-quotes.md); signature remains unconfirmed and no courier offer has been approved for checkout.
