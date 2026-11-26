# FlipFlop Automated Growth Engine PRD

**Version:** 1.0 | **Date:** 25 November 2026 | **Status:** Proposed consolidated specification for implementation

**Supersedes:** `docs/prd/marketing-engine-prd.md` v0.1 and `docs/prd/marketing-engine-codex-implementation-prompt.md`. This document defines the target product and phased delivery contract. It does not assert that integrations are already implemented.

## 1. Vision and outcomes

Create an AI-assisted marketing department inside FlipFlop Admin, turning builds, products, expertise, promotions and editorial ideas into useful content and measurable, profitable growth. Automate discovery, planning, creation, validation, scheduling, approved distribution, measurement and recommendations. The operator retains control of brand, public claims, channels, expenditure and availability. Use UK English and GBP. Communicate FlipFlop's Playbook, Pace and 3D personalisation proposition; use the current approved brand profile rather than hard-coded marketing claims.

The primary user is the solo FlipFlop operator. The default experience prioritises decisions needing attention, not dashboard noise. Success measures: time from eligible event to review-ready campaign, operator time per campaign, approval rate, publication success, attributable qualified traffic, enquiries, purchases, CPA, ROAS and contribution profit where reliable. Establish baselines before setting numeric commercial targets; missing data is not zero.

## 2. Release boundaries

| Release | Scope and gate |
|---|---|
| 1 Foundation | Existing Social Media + GA4 MVP; event intake, new-build and public-promotion drafts, curated rotation, basic unified calendar, approval and publishing; Facebook Pages and Instagram Business first. Pass eligibility, deduplication, approval, scheduling, retry and tracking tests. |
| 2 Creative Studio | Complete 3D assembly, AI-directed video templates, render pipeline and channel variants. Pass geometry, claim accuracy, asset rights and rendering tests on representative builds. |
| 3 Editorial and distribution | Blog workflow, ongoing calendar intelligence, Search Console, additional social adapters; pass CMS and provider-specific tests. |
| 4 Paid acquisition | Google Ads and Merchant Center first, then other paid adapters; pass spend, conversion, reconciliation and pause gates. |
| 5 Owned audience and placements | Newsletter, lifecycle, website placements; pass consent, suppression, delivery and placement tests. |
| 6 Growth intelligence | Demand-informed campaigns, creator/referral/community programmes, experiments and controlled optimisation; pass evidence and policy gates. |

All releases are in target scope. No paid spend, newsletter sending, automated blog generation or automatic replies in release 1. Do not expose unimplemented functionality as operational. Use feature flags and explicit roadmap states. Release 1 may prepare image-based announcements while the video pipeline is unavailable, but the target new-build workflow requires video; fallback is disclosed and separately approved. No release permits unapproved public publishing.

## 3. Admin experience

Retain top-level Marketing navigation and existing `/marketing/social` and `/marketing/analytics` routes, adapted to repository conventions. Social Media remains the initial default tab, with a Growth Command Centre overview as the product expands. Add Approval Centre, Content Calendar, Creative Studio, Blog & Editorial, Newsletter, Advertising, Owned Placements, Growth Intelligence and Brand & Automation Settings as releases become available.

Social dashboard: connected profiles, connection/token status, enable/disable, active workflows, new-build and rotation summaries, upcoming queue, approval queue, recent successes and failures, attributed traffic/conversions and global pause/resume. Profile settings: allowed content types, posting windows, daily/weekly limits, hashtag rules, link settings, platform copy overrides and scheduling preference. Automatic mode means automatic execution of an approved revision only; remove any bypass.

Command Centre answers what is connected, active, scheduled, awaiting approval, failing, paused, and whether tracking works. Show actionable errors and missing prerequisites. Use existing components, tokens, authentication and Lucide/SVG icons, no emoji icons. Responsive, high contrast, keyboard accessible, visible focus, clear empty states; target WCAG 2.2 AA.

## 4. Event-driven orchestration

Subscribe to authoritative business events using existing lifecycle hooks or durable outbox integration. Event envelope: event ID, type, entity ID, revision, occurred-at, source channel, correlation ID and payload schema version. Suggested event names (map to actual repository conventions): `build.listing.published`, `promotion.public.created`, `promotion.updated`, `promotion.expired`, `blog.published`, `build.price.changed`, `build.availability.changed`, `build.sold`, `rotation.due`. Reconcile missed events; do not trigger from an unconfirmed listing attempt.

On a new pre-built listing on any supported sales channel, confirm build is complete, visible, available and has a canonical website URL. Group cross-listings by canonical build ID and launch revision, not marketplace listing ID. Create one campaign with per-channel drafts; subsequent cross-listings update destinations without duplicating the launch. On a public promotion being created, prepare campaign drafts with exact eligibility, terms, start/end and discount; private promotions never trigger public marketing. Future-dated offers may be prepared early but cannot be represented as live prematurely. On blog publication, create social draft tasks referencing confirmed canonical URL. Price/availability changes invalidate affected drafts; sold builds and expired promotions cancel pending executions and flag existing live content for corrective review. Never silently alter approved public copy.

Pipeline: event → eligibility → campaign upsert → source snapshot → creative brief → assets/copy → platform variants → validation → review → approved scheduling → execution → reconciliation → measurement. Store job attempts, reason codes, correlation IDs and idempotency keys. Durable queue with bounded retries, backoff and dead-letter handling. Reconcile unknown provider outcomes before retrying. Repeated events and worker restarts must not duplicate campaigns or publications.

### 4.1 Curated build rotation

Collections support selected builds, manual order, random, weighted random, newest first, least recently promoted, price/performance filters, cadence, active dates/time windows, minimum repeat interval, maximum promotion count, available-only filtering, template and enable/disable. Skip sold, hidden, incomplete or unavailable builds. Rotation creates drafts for approval; it does not bypass approval. Record selection reason and last promotion time. Respect global/channel frequency limits and avoid conflicts with launch campaigns.

## 5. Content and templates

Versioned templates contain name, content type, platform, body, supported variables, enabled state, approval policy, media rules, character limits, brand voice and CTA. Preview with sample and real build data. Variables include `{{build_name}}`, `{{price}}`, `{{short_description}}`, `{{key_specs}}`, `{{performance_summary}}`, `{{availability_status}}`, `{{product_url}}`, `{{interactive_3d_url}}`, `{{hero_image}}`, `{{brand_name}}`, plus audience, Playbook segment, Pace options, promotion terms, discount, benchmark source and expiry. Validate missing required variables; never invent replacements.

Content types: launch freeverts (organic unpaid advertisements), curated rotation, promotions, price/availability updates, educational posts, blog promotion, paid creatives, newsletters and owned placements. Produce platform-native copy, hashtags, aspect ratios, captions, thumbnails, accessibility text and tracked CTA. Maintain shared campaign identity with independent variants. AI outputs are editable and explainable; record model, prompt/template version, source snapshot, cost and validation results. Verify technical claims, current news and asset rights. Treat external text as untrusted data, not agent instructions.

## 6. Automated 3D Video Studio

### 6.1 Source of truth and assembly

Reuse existing case/component 3D fields, build BOM, photos and configurator assets. Resolve each actual SKU to its GLB or supported model; maintain asset version, units, scale, coordinate system, mounting anchors, transforms, materials, textures, emissive/RGB maps and licence. Assemble case, motherboard, CPU/cooler, GPU, RAM, storage, PSU, fans and other installed components according to real layout. Hidden components may be shown in labelled exploded/cutaway views only if accurate. Validate fit, orientation, missing assets, collisions, materials and texture availability; show a preview and manifest. Do not substitute visually similar components without explicit review and disclosure. Missing critical assets block full-build video; allow approved photo/still fallback.

### 6.2 AI creative direction and deterministic rendering

Use a configurable frontier ChatGPT/OpenAI model, where supported through an authorised API, to produce a structured creative brief, script, storyboard, shot list, camera spline/keyframes, lighting, overlay timings, narration and CTA. Validate output against a schema and actual scene bounds. A deterministic 3D renderer (select existing compatible stack after repository inspection; Blender/headless renderer is a candidate) renders the actual assembled model. AI video generation may enhance backgrounds or transitions only if it preserves product truth; do not rely on it to recreate hardware geometry or factual text. Model/provider availability and commercial-use rights must be verified; no assumed ChatGPT subscription API access. Store renderer version, scene manifest, camera plan, render logs and output hashes. Use asynchronous render jobs, cost/time limits, progress, cancel and retry; cache by scene/template revision.

### 6.3 Mandatory launch video template

| Scene | Required content |
|---|---|
| Reveal | FlipFlop brand, build name, hero shot, target audience and Playbook segment |
| Fly-through | Smooth camera movement through actual assembled build; component labels and key specifications |
| Performance | Verified benchmark results with test/game, resolution, settings, metric and source where applicable; distinguish measured from estimated |
| Value | Current build price, valid discounts and promotion terms; avoid misleading savings |
| Pace | Fast Track, Standard and Flexible where actually offered; each eligible price, price difference, delivery estimate and conditions from current commerce data |
| CTA | Product page, interactive 3D viewer/configurator and approved brand message |

Generate platform-specific vertical, square and landscape exports as supported, with safe text areas, readable overlays, captions, licensed audio/voice and optional silent version. Use template-controlled timing and brand tokens; proposed durations are configurable, not fixed by this PRD. Missing benchmark or Pace data must be surfaced for correction; never invent FPS, delivery promises or prices. Validate render integrity, correct SKU appearance, audio rights, legibility, claim provenance and links. Preview final exact files per channel; regeneration invalidates approval. Media fallback order: verified fly-through/turntable, branded render, hero photo, approved fallback. Interactive viewer is linked, not assumed embeddable in social posts.

## 7. Unified marketing calendar

Maintain a rolling calendar of organic posts, paid campaigns, blogs, newsletters, promotions, owned placements and launch events. Support day/week/month/list views, filters by campaign/channel/type/status, drag/reschedule, posting windows, timezone Europe/London with UTC storage, campaign start/end, dependencies and conflict warnings. Distinguish planned, draft, awaiting approval, approved, scheduled, live, failed, cancelled and expired. AI proposes cadence and fills meaningful gaps using content pillars, launches, offers, blogs, seasonal opportunities and verified demand evidence; no filler requirement. Replan after stock changes, expiry or failures. Respect per-channel limits, minimum repeat intervals and campaign priorities. A changed approved schedule outside its authorised window requires reapproval. Calendar edits never publish directly.

## 8. Approval and publishing

Mandatory approval of exact revision, assets, claims, destination channels/accounts, tracked URLs, scheduled time/window and, for paid campaigns, audience and spend envelope. Owner may approve individually or in bulk with explicit scope; deselect channels, edit, reject, request regeneration or cancel. Store approver, timestamp, revision hash, scope and expiry. Proposed expiry policy: configurable by content type, bounded by offer/availability validity; confirm before production. No implicit approval from a template or prior campaign. Material changes invalidate approval. Revalidate at execution against current price, stock, terms, account health, consent and pause state; block stale content. Automatic publication occurs only after approval and at approved time. Provide emergency global, per-channel and per-workflow pause; prevent new dispatch while paused and surface in-flight jobs. Paid emergency pause must reconcile provider confirmation.

Lifecycle: draft → validating → review → approved → scheduled → publishing → published; rejected, cancelled, validation_failed, failed, unknown, partially_published and reconciled as appropriate. Track each destination independently. Retry transient failures only within approved scope; unknown outcomes require reconciliation; permanent errors require operator action. Audit generated, edited, approved, queued, published, failed and revoked actions. Provider IDs and timestamps prove publication; do not mark success from local enqueue.

## 9. Channel adapters

Initial Facebook Pages and Instagram Business. Expand to YouTube, TikTok, Reddit, X, LinkedIn, Threads, Pinterest and other selected channels subject to verified permissions, account type, media and API capabilities. Generate drafts for enabled channels even where publishing requires manual export; label capability full API, assisted, export-only or unsupported. Never pretend all channels support identical features. Document exact API/version, OAuth scopes, account mapping, formats, rate limits, webhooks/polling, error mapping, metrics, sandbox/fixtures and revocation. Encrypt tokens using existing secret conventions; no plaintext tokens or fake credentials. Connection states: connected, disconnected, not configured, unsupported, failed. Safe dev adapters cannot publish externally and must be visibly labelled. Automatic replies, DMs and moderation actions remain out of scope unless separately specified and approved.

## 10. Blog, SEO and owned content

Editorial ideas from customer questions, verified market data, demand, analytics and available builds. Generate sourced briefs, drafts, SEO title/meta, canonical slug, internal links, related products, media/alt text and CTA. Validate facts, rights, accessibility, stale prices and links. CMS preview, approval, schedule, publish confirmation, update/rollback, slug collision checks and sitemap/RSS integration. Publication creates social drafts. Search Console insights when practical; not a release 1 blocker. Track homepage hero, featured builds, recommendations, blog modules, newsletter placements, welcome emails, post-purchase pages, announcement bars and configurator recommendations as owned promotion, not paid or direct traffic. Approval required for public placement changes.

## 11. Paid advertising management

Google Ads first: connect account/customer IDs, OAuth and developer-token configuration; verify API access and account permissions. Integrate Merchant Center product feed and diagnostics for Shopping/Performance Max where eligible; map canonical products/builds, price, availability, destination, imagery and identifiers; do not invent GTINs. Support Search, Shopping, Performance Max and other campaign types only where provider/account supports them. Expose campaign/ad group or asset group, creative, targeting, keywords/negative keywords where applicable, bidding, budget, schedule, geography, conversion goals and status. Distinguish provider recommendations from executed changes. Support Meta Ads, Reddit Ads, X Ads, TikTok Ads and eBay Promoted Listings as later gated adapters. OpenAI advertising only if an approved API/surface exists.

Workflow: choose objective and campaign/build/offer → recommend channel, creative, audience, budget and economics → validate availability, feed, policy, tracking and consent → preview exact settings → owner approval → idempotent launch → sync status/spend/results → recommend pause/continue/adjust. Promote high-performing organic posts as paid drafts, not automatic spend. Daily/monthly caps, max CPA, minimum contribution margin, combined discount/ad exposure and approval thresholds configurable; block launch until required limits are configured. No autonomous budget increases, targeting changes or new spend. Provider budgets are not guaranteed hard caps; monitor spend and disclose reporting lag/overspend risk. Emergency pause, reconciliation and audit mandatory. Sold/expired products block new campaigns and trigger urgent pause workflow; safety pause may be preauthorised by owner, never new spend.

Report impressions, clicks, CTR, CPC, spend, conversions, CPA, attributed revenue, ROAS and contribution profit where available, with provider, attribution window and freshness. ROAS = attributed revenue / spend; CPA = spend / attributed conversions; zero denominator is unavailable. Compare creatives and campaigns; distinguish organic and paid. Use actual order economics, VAT treatment, COGS, fulfilment, payment/marketplace fees, discounts, refunds and ad spend without double-counting. Do not call attributed profit incremental profit without controlled evidence. Confirm finance source and calculation contract before profit-based automation.

## 12. Newsletter, lifecycle and community roadmap

Subscriber management, weekly digest, launch/blog announcements, welcome sequence, back-in-stock campaigns, email attribution and customer lifecycle segmentation. Consent and suppression checked at send time; unsubscribe, bounce and complaint handling, sender authentication, frequency limits, exact audience preview, approval, idempotent sends and provider reconciliation. Skip empty editions. UK GDPR/PECR compliance review before launch. Creator/affiliate tracking, referral programme, personalised recommendations, user-generated content, community/reputation monitoring and marketing copilot remain target scope; define programme rules, rights, disclosure and consent before activation. No unapproved public replies or messages.

## 13. Analytics and tracking contract

GA4 connection/configuration state from release 1, including Measurement ID where appropriate; separate collection configuration from reporting API access. Date range and channel/content filters; traffic summary, social sessions, top referring channels/posts/templates, build views, 3D opens, configurator starts, enquiries, newsletter signups, cart, purchases, attributed revenue and recent trend comparison. Show only available metrics with source, freshness and empty/disconnected explanations. Search Console later. Reuse existing analytics infrastructure or create provider-neutral abstraction.

Required storefront event names: `page_view`, `build_view`, `viewer_3d_open`, `configurator_start`, `add_to_cart`, `checkout_start`, `purchase`, `newsletter_signup`, `contact_submit`, `blog_view`, `outbound_marketplace_click`. Define versioned payloads with event ID, timestamp, consent state, session/pseudonymous identifier where permitted, relevant build/product/article ID, campaign/content/variant IDs and destination. Purchase includes unique transaction ID, value, currency and items; deduplicate and reconcile refunds where available. Map custom events to GA4-supported ecommerce events where appropriate. Do not transmit PII to analytics. Validate payload and consent before emission.

Tracking builder preserves canonical URL and existing query/fragment, URL-encodes values and supports `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, build/article ID, template ID and creative variant ID. Use opaque IDs, no PII. Report organic social, paid, email, search, referral, owned, direct and unattributed separately. Never infer direct traffic is paid. Separate provider-reported attribution, observed site events and modelled estimates; disclose windows, cross-device gaps and missing marketplace conversions. Avoid summing overlapping provider conversion totals.

## 14. Growth intelligence

Use verified trends, component demand, website funnel, campaign results and customer questions to recommend content, target audience, channel, timing and budget. Evidence bundle: source, timestamp, sample size, freshness, confidence, assumptions and expected outcome. Rank actionable recommendations; allow no-action outcome. Test creative variants with explicit hypothesis, metric, exposure window and stopping rule; do not claim causality without appropriate control. Learn from approved actions and outcomes, not merely clicks. No public action or expenditure bypasses approval. Model cost budgets, tool allowlists, timeouts and prompt/version logs required.

## 15. Domain model and ownership

Reuse existing catalogue/build/listing, promotions, inventory, orders, media and authentication as authoritative sources. Marketing owns campaigns, content revisions, approval, scheduling and execution; analytics providers own raw reported metrics. Suggested entities (adapt to existing schema): `MarketingBrandProfile`, `SocialConnection`, `SocialChannel`, `ContentTemplate`, `ContentAsset`, `ContentItem`, `ContentRevision`, `AutomationWorkflow`, `PublicationJob`, `BuildCollection`, `TrackingLink`, `PerformanceMetric`, `Campaign`, `BlogArticle`, `NewsletterCampaign`, `AdAccount`, `OwnedPlacement`, `ApprovalRequest`, `MarketingEvent`, `RenderJob`, `SceneManifest`, `CalendarEntry`, `AdExecution`, `AuditEvent`. Campaign groups a business objective; content item is logical creative; revision immutable; publication job is one destination execution. Use foreign keys, unique event/execution keys, versioning and transactional state transitions. Do not duplicate build records. Define retention, access and deletion policies before production. Store secrets outside ordinary content records.

Provider contracts: `SocialPublisher`, `AnalyticsProvider`, `TrackingProvider`, plus proposed `CreativeModelProvider`, `SceneRenderer`, `EditorialPublisher`, `AdProvider`, `MerchantFeedProvider`, `EmailProvider`. Separate capabilities, validate, execute, status/reconcile, pause and metrics methods as applicable. Exact API routes and schemas follow repository conventions after inspection. Authorisation enforced server-side; owner approval/spend rights, editor draft rights, reviewer rights and read-only analytics roles; initial owner may self-approve. Record all external writes.

## 16. Operational and safety requirements

Global/channel/workflow pause, daily/weekly frequency limits, duplicate-content detection, link/media/availability/brand checks, full audit trail, failure logs and retry. Durable jobs survive restarts; use locking and idempotency; monitor queue age, error rate, token expiry, provider quotas, render costs and spend. Alert on actionable failures and stale metrics. Never leak secrets in logs or prompts. Use least privilege, encrypted credentials, retention policies, consent enforcement and provider terms. Configure measurable service targets and recovery objectives after repository inspection; no invented infrastructure guarantees. Provide safe development fixtures and dry runs; never publish or spend during automated tests.

## 17. Acceptance criteria and test matrix

| ID | Testable outcome |
|---|---|
| A01 | Marketing visible; Social Media default initially; profile connect/view/disable and clear disconnected states. |
| A02 | Eligible build event generates correct channel variants, copy, approved media and tracked website link; ineligible build blocked. |
| A03 | Cross-listing/replayed events generate one launch campaign; public promotion generates drafts; private offer does not. |
| A04 | Rotation supports configured cadence/selection, repeat prevention and skips unavailable builds. |
| A05 | Template variables render correctly; missing facts fail validation; links preserve existing parameters. |
| A06 | No external publish before exact revision/channel approval; edit invalidates approval; scheduled approved job publishes automatically. |
| A07 | Global/channel/workflow pause blocks dispatch; stale price, expired offer and sold build block execution. |
| A08 | Failed jobs show actionable errors; timeout reconciliation and retry prevent duplicates; partial channel success visible. |
| A09 | GA4 configuration and disconnected states visible; event naming/payload and consent tested; unavailable metrics not fabricated. |
| A10 | Actual full-build scene matches BOM, transforms and materials; missing asset blocks or explicitly falls back. |
| A11 | Video includes name, audience, specs, sourced benchmarks, price, valid discounts, eligible Pace prices/differences and CTA; channel exports preview correctly. |
| A12 | Calendar includes all active content types; conflicts, frequency and expiry enforced; reschedule respects approval scope. |
| A13 | Approved blog publishes with confirmed URL, rollback and social draft trigger. |
| A14 | Google Ads/Merchant Center capability and feed diagnostics visible; approved campaign launches once; unapproved spend blocked. |
| A15 | Spend limits, emergency pause, provider failure and reconciliation tested; organic/paid metrics separate. |
| A16 | Newsletter suppression and audience approval enforced; owned placements tracked separately. |
| A17 | Recommendations include evidence/confidence and no-action option; no autonomous public actions. |
| A18 | Keyboard access, focus, responsive UI, audit history and secret redaction verified. |

Run relevant type checks, lint, unit, integration and targeted end-to-end tests for each release. Include concurrency, replay, provider timeout, revoked token, partial success, stale data, approval race, timezone/DST, render failure, cost cap and consent fixtures. Live integrations require separately authorised smoke tests. Report unrelated pre-existing failures separately. Release acceptance requires evidence, not merely UI presence.

## 18. Codex implementation contract

Repository: `C:\Users\mclar\CODING\FlipFlop`. Inspect before editing: Next.js admin navigation, build APIs, manual/pre-built lifecycle, storefront URLs, image/photo handling, 3D model fields, scheduler conventions, backend framework, database models/migrations and API style. Identify existing marketing implementation and related PRDs; map requirements to existing code and report conflicts. Reuse UI, tokens, auth, API helpers, scheduling and existing infrastructure. Do not rewrite unrelated systems. Never add fake credentials or claim a provider is connected without verification.

Implement one release at a time in dependency order. First deliver release 1 vertical slice; document interfaces for later releases, but do not implement paid advertising, newsletters, automated blog generation or replies in that slice. Use migrations consistent with existing schema, feature flags, typed contracts, fixtures and safe disconnected states. Preserve existing routes or provide compatibility redirects. Before implementation, produce repository-specific file/module map, provider feasibility matrix and unresolved decisions; do not silently choose expensive services or enable external writes. After each release, summarise files changed, workflow, credentials/setup needed, tests and results, deferred work, known limitations and next release gate. Do not claim live social publishing, GA4, video generation or advertising unless actually configured and verified.

## 19. Consolidation decisions and traceability

| Original source | Consolidated location |
|---|---|
| Marketing PRD §§1–4 | §§1–3, 9 |
| Marketing PRD §§5–8 | §§4–6, 8 |
| Marketing PRD §§9–12 | §§8, 13, 16 |
| Marketing PRD §§13–14 | §§2, 7, 10–12, 14 |
| Marketing PRD §§15–17 | §§15–18 |
| Codex prompt: objective, method, navigation, social, templates, build and rotation | §§2–5, 18 |
| Codex prompt: tracking, analytics, events, providers | §§9, 13, 15 |
| Codex prompt: safety, UI, testing and delivery | §§3, 8, 16–18 |

Explicit supersession: optional unapproved automatic publishing is replaced with mandatory approval; automatic execution after approval is retained. New-build event scope expands from eligible build to confirmed listing on any supported sales channel; public promotions become first-class triggers. Basic media strategy expands to mandatory target-state 3D video. Calendar moves into foundation and expands later. Original MVP exclusions remain release boundaries, not permanent product exclusions. Existing roadmap features remain in scope.

Open decisions: exact connected social accounts and API permissions; current repository implementation status; frontier model and renderer choice, licences and costs; missing 3D assets and benchmark provenance; actual Pace data contract; posting cadence and approval expiry; advertising budgets and finance/attribution contract; consent and retention policies; operational SLAs. Proposed release sequencing and architecture are design recommendations, not confirmed existing infrastructure. No external provider capabilities or live repository implementation were verified during this document merge.
