# FlipFlop Growth Engine — Marketing MVP PRD

**Parent specification:** `flipflop-growth-engine-mega-prd.md` v1.1  
**Release:** Marketing MVP  
**Status:** Implementation-ready  
**Primary outcome:** Reliable social publishing plus website analytics

## 1. Purpose

Deliver the narrowest useful release of the Growth Engine: one admin entry point for creating, reviewing, scheduling and publishing social content, with website analytics and tracked-link visibility.

This release establishes the shared foundations required by later PRDs without implementing paid advertising, newsletters, blog publication, offers, loyalty, replies or autonomous optimisation.

## 2. Scope

### Included

- `Advertising & Growth` admin navigation entry.
- Command Centre showing MVP-only cards.
- Social account connection for the providers defined in the implementation configuration.
- Content calendar.
- Post drafts and platform-specific variants.
- Selection of approved FlipFlop media.
- Manual approval before every external publication.
- Scheduling, publishing, retry and reconciliation.
- Website analytics ingestion.
- UTM/tracked links where supported.
- Basic reach, impressions, engagement, clicks and website-session reporting.
- Audit history, connection health and failure alerts.

### Explicitly excluded

- Paid advertising creation, spend or budget changes.
- Automated blog publishing.
- Newsletter creation or sending.
- Automated replies, deletion, hiding or moderation.
- Vouchers, abandoned-cart offers or loyalty redemption.
- Automated custom audiences.
- Revenue, profit or incrementality claims.
- Automatic publication without approval.

Disabled features must appear as Roadmap, not as misleading active controls.

## 3. Users and permissions

Initial single-user mode uses Michael as Owner. The permission model must nevertheless support Owner, Growth Editor, Content Reviewer and Read-only Analyst.

- Owner: connect accounts, approve, publish, schedule, view analytics and change settings.
- Growth Editor: create and edit drafts.
- Content Reviewer: approve or reject posts.
- Analyst: view content and analytics only.

The author may not approve their own post when separation-of-duties is enabled.

## 4. Core workflow

1. Create a post manually or from an approved source asset.
2. Select destination platform(s).
3. Generate or write a platform-specific draft.
4. Attach only approved media and verified claims.
5. Run validation for required fields, character limits, links, accessibility and provenance.
6. Submit for approval.
7. Approver sees exact copy, media, platform, schedule and link.
8. Schedule or publish.
9. Record provider confirmation or failure.
10. Synchronise performance metrics and website analytics.

## 5. State model

`draft → validation_failed/review → approved → scheduled → publishing → published`.

Failure states: `rejected`, `cancelled`, `timed_out`, `needs_attention`, `reconciled`.

Editing an approved post creates a new revision and invalidates the prior approval. Provider timeouts must be reconciled before retrying.

## 6. Data model

- `social_account`
- `social_post`
- `social_post_revision`
- `social_publication`
- `content_asset`
- `tracking_link`
- `analytics_event`
- `performance_snapshot`
- `approval_request`
- `connector_execution`
- `audit_event`

Every external action uses an idempotency key. Every metric stores provider, retrieval time, freshness and source record.

## 7. Connector requirements

Before each provider is enabled, document its exact API, OAuth scopes, supported media, rate limits, publish capability, metric gaps, webhook/polling model, sandbox/fixture strategy and revocation behaviour.

The UI must identify whether a connector supports full API publication, assisted publication or analytics-only access.

## 8. Analytics

Show organic metrics only:

- Reach
- Impressions
- Likes/reactions
- Comments as observed data only
- Shares
- Saves
- Video views where available
- Link clicks
- Website sessions and UTM visits

Do not show attributed profit or claim that a post caused a sale in this release.

## 9. Acceptance criteria

- A user can connect an approved social account and see connection health.
- A user can create, revise, approve, schedule and publish a post.
- A failed or uncertain provider result is visible and recoverable.
- Duplicate publication is prevented in retry tests.
- Every external action has an audit event and approval record.
- Analytics show source and freshness.
- Website links contain campaign tracking where supported.
- No excluded feature can execute in MVP.

## 10. Launch gate

- ≥99% confirmed publication success excluding provider outages.
- Zero duplicate publications in acceptance tests.
- 100% external actions auditable.
- Analytics visible within the configured freshness SLA.
- WCAG 2.2 AA checks pass for admin MVP screens.

