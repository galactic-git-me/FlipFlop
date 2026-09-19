# FlipFlop Growth Engine — Offers and Loyalty PRD

**Depends on:** Customer/Account Service, Checkout, Order Service, Profitability Service, Loyalty Service  
**Release:** Offers and Loyalty  
**Primary outcome:** Issue and redeem safe, auditable discounts without AI controlling eligibility or balances

## 1. Scope

### Included

- Site-wide offers.
- Individual account-linked vouchers.
- Abandoned-cart vouchers requiring login.
- Loyalty-tier discounts.
- Points exchanged for fixed-value discounts.
- Eligibility, stacking, minimum order, product, currency and expiry rules.
- Exposure and profit guardrails.
- Approval, pause, expiry, revocation and redemption audit.

### Excluded

- AI directly changing loyalty balances.
- Unrestricted automatic discounts.
- Anonymous personal vouchers.
- Voucher eligibility calculated in prompts or frontend code.

## 2. Canonical model

- `offer`: customer benefit and eligibility rules.
- `voucher_code`: redeemable code or secure token, optional for automatic offers.
- `voucher_assignment`: links a personal voucher to a customer/cart.
- `voucher_redemption`: immutable successful or rejected redemption event.
- `loyalty_ledger_entry`: points award, deduction, reversal or expiry.
- `offer_exposure`: issued, displayed, emailed or advertised exposure.

A loyalty discount may therefore involve an offer, a customer entitlement and a loyalty ledger transaction, but these remain separate records.

## 3. Offer types

### Site-wide

Multi-use or capped, time-bound, optionally new-customer-only, with minimum spend and stacking rules.

### Individualised

Account-linked, one-time or limited-use, expiring and optionally product-restricted.

### Abandoned-cart

Triggered only by a qualifying event, linked to the customer/cart, one-time, short-lived, login-required and frequency-capped.

### Loyalty

Tier or points funded. Points deduct transactionally and reverse according to refund policy.

## 4. Deterministic checkout validation

The Offer Service validates identity, login, customer status, voucher state, expiry, cart linkage, product eligibility, minimum order, usage, loyalty tier/balance, stacking, currency, market and contribution-profit floor.

AI can recommend an offer but never authoritatively approve or redeem it.

## 5. Financial guardrails

Use configured policy fields:

- `maximum_offer_exposure_gbp`
- `maximum_discount_percent`
- `minimum_contribution_profit_gbp`
- `minimum_contribution_margin_percent`
- `maximum_customer_redemptions`
- `maximum_campaign_discount_exposure_gbp`

Crossing a threshold requires explicit approval. Offer funding responsibility—FlipFlop, supplier, loyalty budget or campaign budget—must be recorded.

## 6. State and concurrency

`draft → pending_approval → approved → scheduled → active → paused/exhausted/expired → archived`.

Checkout redemption uses a transaction and idempotency key. Failed payment must not permanently consume a one-time voucher or loyalty points unless policy explicitly says so.

## 7. Acceptance criteria

- All four offer types work with deterministic tests.
- Personal vouchers cannot be transferred or reused.
- Abandoned-cart vouchers require login and correct cart/customer linkage.
- Stacking and expiry are enforced at checkout.
- Loyalty redemption updates the ledger transactionally.
- Refunds and cancellations reconcile discounts and points.
- Unsafe exposure or margin is blocked.
- Issuance, display, redemption and reversal are auditable.

## 8. Launch gate

Pass concurrency, expiry, refund, duplicate redemption, account isolation and margin-protection tests with a sandbox checkout.

