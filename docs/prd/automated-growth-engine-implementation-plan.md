# Automated Growth Engine implementation plan

**Status:** Owner approved on 2026-11-26; Release 1 implementation in progress.
**Basis:** [implementation audit](./automated-growth-engine-implementation-audit.md) and [progress tracker](./automated-growth-engine-progress-tracker.md).

## Goal and boundaries

Finish the quickest useful Release 1 vertical slice using the existing Growth Engine foundation: authoritative eligible-build event → idempotent campaign/draft upsert → approved media/copy/tracked URL → validation → exact-revision/channel approval → approved scheduling → provider execution/reconciliation → clearly sourced measurement.

Do not implement paid spend, newsletter sends, automated blog generation, replies, or later-release experiences in Release 1. Do not enable a live publisher until account, credentials, API permissions, provider review, and safe retry/reconciliation are verified. No publishing or provider calls in automated tests.

## Progress (2026-11-26)

Implemented in the first approved slice:

- Growth administration/read/write routes now require admin authentication; public storefront event ingestion and tracked redirects remain public.
- A global dispatch pause record and authenticated control were added. The migration seeds it paused, and the due-post worker checks it.
- Fixture outcomes are reported as simulations, not publications. Synthetic engagement snapshots were removed from dispatch.
- Successful Ready-to-Ship storefront listing creates one factual, UTM-tracked Facebook and Instagram draft per canonical build/product launch in the listing transaction. Replays deduplicate by source reference and lock the product row.
- Reused hero imagery starts unapproved for social use; the admin can approve the asset before submitting the draft for review.
- The admin shows fixture/not-configured accounts, pause state, and an explicit GA4-not-configured message. Dispatch cannot resume from the UI without a verified adapter.

Validation passed: Python syntax compilation, focused admin ESLint, admin TypeScript check, Alembic head discovery, and targeted PostgreSQL SQL generation for the dispatch migration. API tests were not run because the isolated runner requires `FLIPFLOP_TEST_ADMIN_DATABASE_URL`, which is unset. No live provider, database migration, or production action was performed.

## Critical path

1. **Owner approval received.** The audit/plan approval gate is complete. Before live-provider or scheduling work, resolve the route, Meta accounts, GA4 access, posting windows/limits and approval-expiry decisions documented in the audit. Per-draft approval of reused image fallback is now enforced.
2. **Repository trace and contracts.** Successful Ready-to-Ship storefront listing now creates locked, idempotent drafts from canonical product/build identity and a listing revision. Remaining: trace availability/sale/withdrawal, public-promotion visibility/terms, marketplace-wide lifecycle hooks, and durable replay/reconciliation. Do not trigger from an attempted/failed listing.
3. **Governance gates.** A global default-paused control is implemented, audited, and checked by the due-post worker; post claiming and product locking reduce duplicate work. Remaining: per-channel/workflow pause, frequency constraints, and price/stock/terms revalidation immediately before dispatch. Make stop/pause auditable and verify worker concurrency.
4. **Eligibility and event intake.** Listing-triggered drafts are keyed on canonical build, product and update revision and deduplicated on replay. Remaining: versioned outbox/event envelope and restart reconciliation, public-promotion drafts only after terms/eligibility are verified, and sold/hidden/incomplete/unavailable/expired corrective lifecycle handling; never rewrite approved copy.
5. **Campaign content foundation.** Reuse `SocialPost`, immutable revision, `ContentAsset`, `TrackingLink`, approval and audit entities where they fit. Add versioned template storage/validation only after confirming no existing generic template store should own it. Render variables deterministically from a source snapshot; missing facts block instead of inventing. Preserve URL query/fragment and use opaque build/template/variant IDs. Image fallback must be explicit and disclosed in the draft.
6. **Admin Release 1 workflow.** Preserve `/advertising-growth` as a compatibility route unless route approval chooses otherwise. Separate Social Media from Analytics, then add queue/approval state, connected vs fixture account capability, workflow health and global/channel pause. All controls remain disabled and clear when no real connector exists. Add accessible empty/loading/error states.
7. **Provider adapters.** First inspect official current Meta documentation and actual target account permissions. Implement Facebook Pages and Instagram Business only for approved content/media forms. Store credentials using established secret handling, never plaintext DB fields/logs. Model disconnected, not configured, expired, revoked, failed and connected accurately. Every request uses bounded retries and provider idempotency where available; unknown outcomes reconcile before retry. Keep fixture adapters isolated to tests/development and prevent them from being represented as live evidence.
8. **Calendar and analytics.** Evolve post list into a truthful social calendar with Europe/London display and UTC storage only where supported; Release 1 needs basic social scheduling, conflict/frequency checks and approved-time enforcement. Define first-party event allow-list, consent boundary and retention. Decide GA4 reporting credentials separately from Measurement ID/collection config, then implement source/freshness-labelled metrics; show disconnected/unavailable instead of zero. Do not infer revenue or conversions from fixtures.
9. **Acceptance verification.** Add focused tests for eligibility, canonical dedupe/replay, template missing data, tracked URL preservation, approval invalidation, schedule timezone/DST, pause races, stale stock/price, retry/unknown provider result, partial channel success, consent, metric missingness and UI access. Run approved static checks/unit/integration tests; only use a separately authorized provider smoke test after credential/account and publication approvals.
10. **Release review.** Update every tracker row with evidence and verification date, report provider setup/costs/limitations, and obtain acceptance before activating live publishing.

## Reuse and migration approach

- Reuse Growth Engine API under `/api/growth`, existing ORM models in `app.models.growth`, migration lineage, `growth_release_configuration`, the scheduler, admin API helper and existing approval/audit flow.
- Reuse canonical commerce/product/build records. Do not copy build inventory into marketing tables; store source revision/snapshot and stable canonical IDs.
- Prefer an additive, reversible Alembic migration for outbox/rotation/template/provider state only after exact gaps are confirmed. Include indexes/unique idempotency keys and a safe downgrade. Never run it against production during implementation or tests.
- Reuse the established credentials/OAuth pattern after tracing it; do not store provider secrets in plaintext or add credentials to fixtures.
- Keep `SocialPublication` attempt records and provider result reconciliation, but audit race safety before relying on the current uniqueness constraint alone.

## Provider feasibility matrix (to complete before adapter implementation)

| Provider/capability | Current evidence | Required feasibility check | Gate |
|---|---|---|---|
| Facebook Pages organic publishing | Fixture connector only; no verified account | Official Graph API endpoint/media support, scopes, app mode/review, Page roles, token lifetime, rate limits, current account eligibility and cost | No live publishing until all verified |
| Instagram Business organic publishing | Fixture connector only; no verified account | Professional account linkage, supported media/container formats, scopes, app review, publishing limits, token lifecycle and account eligibility | No live publishing until all verified |
| GA4 collection/config | Internal event intake exists; no GA4 connection verified | Property/Measurement ID ownership, event mapping, consent, deduplication, retention and whether Measurement Protocol is required | Do not label connected absent runtime confirmation |
| GA4 reporting | No reporting API implementation verified | Data API access method/scopes, service account or OAuth ownership, quota, latency, metric definitions and missingness | Report only source-confirmed metrics |
| OpenAI content generation | SDK dependency is present but credentials/model policy are not verified | Authorized API key, model availability, data handling, cost ceilings, structured output and prompt-injection controls | Approval gate; deterministic templates can launch without LLM |
| 3D/video rendering | Existing 3D fields/assets exist elsewhere; growth renderer not verified | Exact SKU asset coverage, renderer, geometry/fit validation, licences, host resources, queue/cost/time limits | Release 2; image fallback stays explicit |
| Paid, email, CMS, community | Roadmap only | Provider and legal/finance/consent gates from PRD | Explicitly out of Release 1 |

Use current official provider docs at implementation time; this audit does not freeze API claims or pricing. No live credentials were inspected.

## Release 1 acceptance checkpoints

1. A complete, visible, available pre-built with canonical URL and approved media yields one reviewable, tracked draft per configured channel; ineligible/replayed/cross-listed events do not duplicate campaigns.
2. A public promotion with verified terms creates a truthful draft; private, future-not-yet-live, expired or changed offers cannot be misrepresented.
3. Build sale/withdrawal or material price/availability changes invalidate/cancel pending work and require corrective review for published copy.
4. Approval binds exact revision, asset, channel/account, URL and schedule. Any material edit resets approval. No unapproved public write is possible.
5. Global/channel/workflow pause is enforced by worker at dispatch and under concurrent workers; queue remains inspectable and restart-safe.
6. Provider error/timeout/partial channel success remains visible; unknown result is reconciled before retry; retries do not duplicate publication.
7. GA4/internal analytics pages identify source/freshness and disconnected/missing data. No synthetic metrics or ungrounded attributed revenue appear.
8. Keyboard, focus, responsive and empty/error states meet project standards; high-risk paths have regression coverage.

## Decision log

- Approval remains mandatory; there is no automatic mode that bypasses approval.
- Fixture publication is not a production connector and its generated metrics are not customer/business evidence.
- Preserve the existing admin URL while adding compatibility only if requested by route decision.
- Image-based new-build draft is a disclosed fallback that needs separate approval; it does not satisfy the target video acceptance criterion.
- No paid spend, newsletter sends, automated blog generation or automatic replies in Release 1.

