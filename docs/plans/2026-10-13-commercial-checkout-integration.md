# Commercial delivery quotes through checkout

**Status:** Implemented and locally validated with disposable data; live enablement outstanding  
**Date:** 13 October 2026  
**Repositories:** FlipFlop API and sibling `C:\Users\mclar\CODING\FlipFlop.shop`

## Behaviour

The curated build detail and checkout now compare Fast Track, Standard and Flexible full payable prices, delivery estimates and differences against Standard. Flexible shows a saving only when the commercial engine establishes one for the same reviewed component/case selection. Loading, unavailable, retry and expiry states prevent stale selections from reaching payment. Changing components/case immediately hides the previous comparison. Checkout locks addresses, software and delivery selection while payment is being prepared.

Policies live on the existing parent Playbook under `pricing_model.commercial_cells[cell_id]`. They now additionally support:

```json
{
  "checkout_enabled": true,
  "checkout_slot_parts": {"11": [101, "exact-cpu-product-key"]},
  "checkout_case": [7, "exact-case-product-key"]
}
```

This fragment illustrates the mapping contract, not a complete or real policy. Supply all existing cost, tax, reserve, margin, market and delivery fields. Each selected slot maps its catalogue variant to an exact supplier product key. The case has its own mapping. Mappings must cover the entire reviewed BOM exactly once. Enabled checkout currently supports new-condition curated builds only. The existing catalogue pricing/eligibility validation still checks that the complete configuration is actually selectable; arbitrary upgrades or cases cannot reuse a core quote.

`POST /api/payments/delivery-quotes` accepts a `PlaybookBuildConfig` directly and returns `pricing_mode`, `quote_snapshot_id` and a customer-safe mode comparison. It does not expose supplier identifiers, cost breakdowns, margins or reserves. The server finds current workshop evidence; the customer cannot select capacity records or set prices. Public comparisons do not reserve workshop capacity or call Stripe.

An absent policy retains legacy checkout. A configured but disabled/invalid policy blocks checkout with a review requirement; it cannot silently revert to legacy prices. Missing current evidence disables the affected commercial offers. No live policies were created or enabled by this task.

## Acceptance and payment

For commercial builds, `POST /api/payments/intent` requires the source comparison's `commercial_quote_id`, exact build configuration, selected delivery mode and the authenticated owner matching `customer_id`. Legacy clients remain supported for builds without commercial policy. The storefront sends its existing Bearer token for commercial checkout.

The server locks the source quote and policy, checks expiry/configuration, recalculates current supplier and capacity evidence, and compares price, timing, policy hash and selected suppliers/capacity against what the customer reviewed. A change returns 409 for new consent. Acceptance saves a separate immutable contract and a short weekly capacity hold using the existing ledger; it does not assign a customer to a build slot. Retrying the same customer/quote/mode reuses the acceptance and hold. Accepted-checkout retries expire after 15 minutes.

The Stripe amount is the accepted full price, not catalogue total plus global surcharge. The intent metadata references the accepted contract and selected mode. A stable per-customer/source-quote/mode idempotency key prevents provider retries creating another intent within that checkout window.

Before contacting Stripe, the accepted contract and a provisional `OrderCheckoutSnapshot` are committed. The latter stores delivery/billing/software choices under a temporary `commercial:{accepted_id}` key, preserving the existing 30-day abandoned-checkout PII retention. After provider success it is rebound to the actual intent ID. Confirmation and webhook can also find the provisional record if the provider succeeded but the response/binding transaction failed. PII is not copied into the permanent commercial evidence record.

Both confirmation paths recover the accepted build, mode, total, cost references and estimate from the same saved contract. They verify the paid amount and customer. Later pricing changes never reprice the paid order. The selected delivery estimate is calculated from acceptance time; a client-supplied legacy `chosen_week` does not override it. Commercial webhook reconciliation failures return an error for provider retry rather than silently acknowledging an uncreated order.

## Verification evidence

- **25 pure/mocked API regressions:** existing new quote calculation and policy adapter suites pass.
- **12 real PostgreSQL integration checks:** policy persistence/version conflicts, customer-safe responses, same-spec acceptance, retry/hold reuse, changed component/case rejection, stale/out-of-stock rejection, expiry, disabled-policy rejection, wrong-owner/amount recovery rejection, actual payment-route amount and metadata, confirmation, webhook and provisional-address recovery pass. External payment/email/job adapters are mocked.
- **14 existing API regressions:** payment build-config contracts, commerce arithmetic and admin assessment checks pass.
- **Storefront:** new delivery component/hook checks and existing curated decision checks pass; TypeScript and production build pass. The expiry test additionally rejects an already-expired response without creating an automatic request loop.
- **Browser:** actual `/order/payment` served by the existing local storefront process on port 4313 was checked at desktop and 390px mobile widths with all API calls intercepted. The comparison displayed £1,200 Fast Track, £1,100 Standard and £950 Flexible/£150 saving as explicit fixture prices. Selecting Flexible sent quote ID 9001, `delivery_option=flexible`, the expected case and an Authorization header. The intent endpoint was deliberately intercepted with 409; no payment/provider call occurred. Retry rendering was also exercised. These fixture prices are not published offers.
- **Schema:** existing ORM tables initialized in a dedicated temporary PostgreSQL 18 instance at `127.0.0.1:55439`, database `flipflop_commercial_test`. No development/production database was modified. No schema changes were introduced; historical migration replay was not tested.

The temporary PostgreSQL instance was stopped after validation; its test data remains under `%TEMP%\flipflop-commercial-pg-20261013`. The user's existing PostgreSQL and storefront processes were left running.

Repeat backend validation with `DATABASE_URL`, `SYNC_DATABASE_URL` and `TEST_DATABASE_URL` explicitly targeting a disposable PostgreSQL database ending `_test`. The PostgreSQL unittest suite skips unless its effective database name satisfies that boundary. Do not substitute the default developer database.

The previously failing browse test was fixed on 13 October: each flip card has a front and an aria-hidden back, both containing its name. The test now queries accessible headings, opens the cards before inspecting specifications/prices, follows the current Explore & personalise action, and verifies return navigation. Local matchMedia, ResizeObserver and canvas test stubs support the actual card component without changing production UI. All 17 tests across curated journey, curated decision and commercial delivery now pass, and TypeScript passes. The earlier diagnosis of duplicate desktop/mobile cards was incorrect. Existing background/face-api dev warnings and TestClient/Pydantic/datetime deprecations remain separate.

The storefront's existing autosync committed source changes during implementation. Only browser snapshots generated by this task were removed from current tracking; `.playwright-cli` is now ignored for future runs. No history rewrite, explicit push or production deployment was performed.

## Remaining release gates

Review and populate real per-cell policies/mappings and current supplier/workshop evidence, then validate the intended development/staging offers. This task did not invent margin floors, tax treatment or supplier costs to activate live purchases. Live Stripe sandbox/provider checks and deployment remain separate gates.

The [population runbook](./commercial-policy-population-runbook.md) defines the required inputs, current API workflow, pilot enablement and missing automation adapters.

This slice covers explicitly reviewed core configurations. General upgrade/custom selection economics, segment promotions, autonomous evidence ingestion/withdrawal, demand-driven proposals and measured learning remain the subsequent commercial-engine work. Accepted quotes are not supplier stock reservations; delayed payment beyond a short workshop hold or changed procurement evidence requires the existing sourcing/operational reconciliation path. Full legacy admin profitability reporting still needs reconciliation against the authoritative accepted cost stack.
