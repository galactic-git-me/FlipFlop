# FlipFlop Growth Engine — Paid Acquisition PRD

**Parent specification:** `flipflop-growth-engine-mega-prd.md` v1.2  
**Depends on:** MVP, Campaign Service, Product/Listing Service, Profitability Service, Consent Service, Tracking Service  
**Release:** Paid Acquisition  
**Primary outcome:** Launch and measure approved profitable paid campaigns

**Authority:** This phase governs paid-acquisition scope and acceptance. The Master Mega-PRD governs cross-cutting rules. Provider-specific implementation briefs govern concrete API versions, scopes and mappings.

## 1. Scope

The first paid release must enable only providers with an approved connector contract. The initial candidate set is eBay Promoted Listings, Google Shopping/Search and Meta/Instagram, but each is separately gated.

### Included

- Campaign and objective creation.
- Product/build/article destination selection.
- Creative and audience selection.
- Budget and duration.
- Spend/performance synchronisation.
- Tracked links and conversion events.
- Approval, pause, reconciliation and reporting.
- Organic-to-paid recommendation from high-performing social posts.

### Excluded

- Automatic budget increases.
- Unsupported provider surfaces.
- Unverified customer custom audiences.
- Claims of incremental profit without experiment evidence.

## 2. Connector contract

Each provider requires exact API/product, OAuth scopes, region, campaign-object mapping, supported objectives, media limits, rate limits, metrics, webhooks/polling, sandbox/fixtures, error mappings, reconciliation cadence, deletion behaviour and provider source-of-truth fields.

The UI displays capability status: full API, assisted, export-only or unavailable.

## 3. Campaign workflow

1. Select a product, build, article, offer or objective.
2. Create or attach a Growth Campaign.
3. Advertising Agent recommends provider, audience, creative, budget and destination.
4. Profitability Service calculates safe exposure.
5. Compliance, consent, brand and tracking checks run.
6. User reviews exact campaign, spend, audience, creative and predicted economics.
7. Approved connector creates the campaign with idempotency key.
8. Provider confirmation is stored.
9. Spend and performance sync runs.
10. Agent recommends pause, continuation or manual adjustment.

## 4. Financial reporting

Show gross revenue, net revenue, COGS, fulfilment, payment/marketplace fees, voucher cost, advertising spend, contribution profit, attribution model and data freshness. Advertising spend must never be treated as profit or revenue.

## 5. Guardrails

- Maximum daily and monthly spend.
- Maximum CPA.
- Minimum contribution profit and margin.
- Maximum combined discount and advertising exposure.
- Approval threshold by spend.
- Automatic pause recommendation, not automatic budget increase.

## 6. State model

`draft → validating → pending_approval → approved → queued → publishing → active → paused/completed → reconciled`.

Provider timeout becomes `unknown` until reconciliation. Partial batches report each execution independently.

## 7. Acceptance criteria

- No campaign launches without correct approval.
- Provider capabilities and unsupported fields are visible.
- Retry cannot create duplicate campaigns.
- Spend caps block unsafe changes.
- Performance data includes source and freshness.
- Organic and paid metrics remain distinct.
- Attribution is labelled estimated/modelled unless directly observed.
- Emergency pause works from the Command Centre.

## 8. Launch gate

One provider passes sandbox/fixture, spend-cap, timeout, partial-success, reconciliation and pause tests before the next provider is enabled.
