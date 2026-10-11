# FlipFlop platform test strategy

**Status:** Approved for local deterministic validation; provider sandboxes and live canaries remain separately gated  
**Version:** 4.29
**Prepared:** 30 September 2026
**Approved:** 9 October 2026
**Applies to:** FlipFlop API and admin, FlipFlop.shop, FlipFlopXtension, background workers, and approved external integrations

## 1. Objective

Create a reliable, maintainable suite that proves both views of the business:

1. a customer can complete each supported purchase and aftercare journey; and
2. a physical build and its data can move safely from sourced components through sale, fulfilment, delivery, warranty, return, repair, reserve release, or closure.

The suite must detect broken contracts between the three repositories, prevent duplicate financial or marketplace actions, and make clear when an external provider was simulated, exercised in a sandbox, or verified live.

## 2. Approval boundary

This document was approved on 9 October 2026 for local deterministic validation. The following boundaries remain in force:

- do not run the existing test suites;
- do not start browsers, containers, migrations, workers, or local services for testing;
- do not call live marketplace, courier, insurer, email, social, analytics, payment, LLM, or scraping providers;
- do not create listings, orders, charges, bookings, policies, posts, messages, or customer records.

Live provider actions and production data changes require their separate documented gates and approvals.

## 3. Source-of-truth hierarchy

Tests will derive expected behavior from, in order:

1. applicable law and published customer policies;
2. `docs/product/customer-policies.md`;
3. product strategy, catalogue/Playbook rules, and lifecycle documentation;
4. the applicable current sub-PRD;
5. explicit API and event contracts;
6. current implementation status.

Planned or gated requirements become skipped executable specifications carrying a reason and capability identifier. They must not be written as passing tests against placeholder behavior.

## 4. Test architecture

### 4.1 Layers

| Layer | Purpose | Technology | External systems |
|---|---|---|---|
| Static contract | Schemas, state transitions, tag vocabulary, generated clients, environment checks | Python/TypeScript checks | None |
| Unit | Deterministic business rules and failure behavior | Pytest, Vitest | Fakes only |
| Component | Storefront/admin components, validation and accessible interaction | Testing Library + Vitest | Mock Service Worker or route fakes |
| Service integration | API + real test database + workers/outbox/object storage substitute | Pytest, PostgreSQL test database | Provider adapters stubbed at HTTP boundary |
| Repository contract | Prove extension/storefront/admin payloads match the API | OpenAPI/schema fixtures and consumer contract tests | None |
| Browser journey | Customer and operator journeys across rendered applications | Playwright | Local API and deterministic provider simulators |
| Provider sandbox | Authentication, request mapping and webhook handling | Focused opt-in suites | Official test/sandbox accounts only |
| Live canary | Read-only or explicitly approved minimal production checks | Separate manual workflow | Never part of normal CI |

### 4.2 Test profiles

- **PR fast:** static contracts, changed unit/component tests, migration lint and focused integration tests; target under 10 minutes.
- **Main branch:** all unit/component tests, PostgreSQL integration, contract tests and critical browser journeys.
- **Nightly:** full browser matrix, workers/schedulers, time travel, scraper fixture replay, accessibility, visual snapshots, retry/idempotency and failure injection.
- **Provider sandbox:** scheduled or manual, credential-gated, rate-limited and tagged by provider.
- **Release:** main + nightly evidence, production configuration validation and explicitly approved live canaries.

Every report records repository commits, schema revision, Playbook version, browser, test-data seed and whether each provider was fake, sandbox or live.

## 5. Harness and test data

### 5.1 Environment

- Use an isolated PostgreSQL database created from the full migration chain. Do not treat SQLite as migration evidence.
- Use isolated object/file storage, queue/outbox, email sink and fake clock.
- Assign each run a unique namespace for users, builds, listings, orders and provider idempotency keys.
- Deny outbound network traffic by default in unit, integration and browser profiles. Allow only named sandbox hosts in provider jobs.
- Fail startup if production credentials, production base URLs or live-purchase flags are present in a test profile.

### 5.2 Canonical fixture factory

Build a shared scenario factory rather than maintaining unrelated JSON blobs. It will generate:

- one Playbook cell for each customer/use-case and budget combination under test;
- benchmark tiers with below, equal and better CPU/GPU candidates;
- component observations from Amazon Prime/non-Prime, ordinary vendors, eBay Buy It Now, eBay auctions and Vinted;
- delivery evidence for listing ETA, vendor fallback, 1/3/7-day bands and unknown ETA;
- new, used, refurbished, flip-derived and incompatible components;
- Ready-to-Ship, Curated-for-you and Made-by-you builds;
- direct account, guest checkout and indirect-channel customers;
- software selections, paid AI option, licences and no-licence variants;
- dispatched, delivered, cancelled, returned, damaged-in-transit, warranty-repair and expired-warranty cases.

Fixture values must be visibly synthetic. No production customer data, tokens, licence keys or downloaded marketplace session state may enter the suite.

### 5.3 Provider simulators

Create stateful fakes for Stripe, eBay, Amazon/listing pages, Vinted, Parcel2Go, Figural/Secursus, email, social networks, analytics and the configured LLM. Fakes must support success, timeout, malformed response, rate limit, duplicate webhook, stale quote and partial failure. Requests are captured for assertions with secrets redacted.

## 6. Traceability model

Every important scenario receives an ID and maps to requirements, code owners and evidence:

- `CJ-*`: customer journeys;
- `BL-*`: build lifecycle;
- `SRC-*`: sourcing and catalogue;
- `MKT-*`: listings, marketing and content;
- `GR-*`: Getting Ready and dispatch;
- `PS-*`: portal and support;
- `NF-*`: security, privacy, accessibility, resilience and performance.

The test report must show pass, fail, skipped-planned, skipped-gated or blocked-external. A skipped test cannot satisfy a release gate.

## 7. Customer journey suites

### 7.1 Identity and portal foundation

| ID | Journey and assertions |
|---|---|
| CJ-001 | Registration creates one empty customer portal with no build portals or orders and lands on a useful private empty state that explains what will appear after purchase and links to starting a build. Login, logout, verification, password reset and session expiry behave correctly. |
| CJ-002 | A returning customer can own multiple independent orders/build portals; access control prevents cross-customer access. |
| CJ-003 | Guest checkout creates an order/build portal without silently creating an account. A high-entropy single-use claim opens that one build in scoped guest mode, cannot be replayed, and does not create or attach an account; authenticated account ownership is used only when the buyer checked out while signed in. |
| CJ-004 | An indirect-channel buyer receives a one-build claim route through the permitted method for that channel; eBay/Vinted default to the printed QR leaflet, while guessable surname/order-number-only authentication is rejected. |
| CJ-005 | Billing and delivery addresses are snapshotted on the order and do not change when the customer later edits their profile. |
| CJ-006 | Portal-claim behavior is channel-specific: dispatch automatically sends a direct guest the one-time claim link and tracking details only at the exact verified order email, with a printable-leaflet fallback if email fails; eBay/Vinted and other marketplace/printed-insert buyers never receive off-platform links and use the printed QR leaflet. |

### 7.2 Ready-to-Ship

| ID | Journey and assertions |
|---|---|
| CJ-RTS-001 | Browse/filter a listed build, read its Playbook explanation, benchmarks, condition, delivery promise, warranty and total price. |
| CJ-RTS-002 | Add to cart, apply valid/invalid/expired discount, choose the Playbook's recommended software or edit/remove apps before payment, verify each selection updates the same reservation/payment intent and total, choose delivery, accept policies and place a Stripe test-mode payment. |
| CJ-RTS-003 | Concurrent customers cannot both buy the same build; reservation expiry restores availability; successful payment marks it sold and withdraws all channel listings exactly once. |
| CJ-RTS-004 | A Ready-to-Ship build is assigned one customer-type × budget cell at creation; the assignment and software rationale survive Built, listing, storefront/marketplace sale and portal linking. Checkout app choices survive primary confirmation and webhook recovery into the order and Getting Ready job. Legacy unassigned builds require an explicit cell selection before package generation. |
| CJ-RTS-005 | Cancel/refund before the applicable gate, dispatch, tracking, delivery, warranty start, claim, repair/replace/refund outcome and reserve handling complete end to end. |

### 7.3 Curated-for-you

| ID | Journey and assertions |
|---|---|
| CJ-CUR-001 | Questionnaire selects the correct Playbook cell and recommends equal-or-better benchmark-tier parts within budget, catalogue tags, compatibility and delivery constraints. |
| CJ-CUR-002 | Explanation states why the build suits the customer; the admin suggestion considers only exact-model approved bestseller evidence and active curated targets, weights popularity and incremental catalogue price equally, chooses distinct categories, and never saves/publishes without human review. Exactly two saved cell upsells appear and are selectable; each is bound to a source candidate and rank/price evidence. CPU/GPU choices require benchmark evidence at least equal to the cell's `from_sku` under its customer-type metric; missing or worse scores block approval. Changed/revoked evidence invalidates the pair; server-side checkout reprices the selected options and rejects unsupported or worse substitutions. |
| CJ-CUR-003 | Before payment, customer sees the selected cell's software rationale and defaults, can add/remove any allow-listed app (including selecting none), and the stable string cell ID plus exact configuration are bound to the paid intent; the server rejects component IDs outside that cell and order/job/portal retain the cell profile and selection through webhook recovery. |
| CJ-CUR-004 | Pre-Components Ordered change request pauses procurement and reprices with approval; cancellation refunds fully. Self-service closes at Components Ordered. |
| CJ-CUR-005 | Components received, build, QA, benchmarks, Getting Ready, dispatch, delivery and warranty claim populate the same portal and audit trail. |
| CJ-CUR-006 | Checkout requires complete UK delivery and billing addresses, defaults billing to delivery, snapshots both privately outside Stripe metadata, and copies them into the order through either browser confirmation or webhook recovery. Courier handoff maps the normalized street/postcode/contact/country fields correctly. A repeated confirmation returns the existing order even after the snapshot was consumed. |
| CJ-CUR-007 | Payment intent creation rejects a paid build without an exact active case/chassis selection; incomplete orders from older records cannot pass the dispatch readiness gate. |
| CJ-AFTER-001 | An authenticated customer submits a support or warranty case from the correct order portal; it is durably linked to that order, a warranty case attaches to its reserve, and the admin alert commits atomically with the case. |
| CJ-AFTER-002 | A verified guest claim token can submit and view support cases only for its single order/build; warranty cases attach to the matching reserve. Tokens without the capability, expired/revoked grants, mismatched contact details, other portal IDs, and requests above the per-grant limit are rejected. |
| CJ-AFTER-003 | A warranty case submitted before delivery is recorded remains linked to its sale, attaches when delivery creates the reserve, and blocks release if still open; if support resolves it before delivery, reserve reconciliation preserves the resolved status. |
| CJ-AFTER-004 | Admin claim milestones (approval, customer return, inspection, repair, parts, replacement, rejection/resolution) synchronize to the customer portal and reserve hold; terminal claims no longer block expiry eligibility, while every active stage does. |
| CJ-AFTER-005 | The customer sees plain-language case status labels; repair shipment events are not implied unless verified courier tracking exists. |
| CJ-AFTER-006 | A changed warranty-case stage for a direct storefront order queues one sandboxed status email containing the case reference and private portal link; an unchanged status sends none, and marketplace/manual-build cases do not receive an off-platform email. |
| CJ-AFTER-007 | An account or scoped guest portal can attach up to twelve size-limited, signature-checked JPEG/PNG/WebP/PDF files to only its own case; an administrator can retrieve them, while another order, expired/revoked grant, malformed file, excess count, or public static path cannot access them. |
| CJ-AFTER-008 | Warranty expiry eligibility and its one-time admin alert commit in the same transaction; a failed transaction retries without losing the alert, while active claims continue to block eligibility. |
| CJ-AFTER-009 | Admin repair tracking accepts only warranty/repair cases at `return_in_transit` or `replacement_dispatched`, requires a carrier, tracking ID, credential-free HTTPS URL and audit note, and appears in the matching signed-in order portal and scoped guest portal using an explicit customer-safe field allow-list. Extra stored fields and the admin audit are never exposed; cross-order and cross-grant access fail. Invalid stage/category/URL data is rejected; changed tracking queues a direct-order case email containing escaped carrier/tracking details and link, unsafe/credentialed links are omitted, and indirect cases do not send off-platform email. |
| CJ-READY-DEPLOY-001 | The server blocks courier booking and dispatch until Windows 11 Pro en-GB deployment is explicitly recorded complete with an operator verification note; attempts to mark it not required or without a meaningful note are rejected. |

### 7.4 Made-by-you

| ID | Journey and assertions |
|---|---|
| CJ-MBY-001 | Questionnaire establishes the Playbook cell; configurator enforces compatibility while allowing deliberate customer choice. Payment pricing accepts only component IDs published by the Custom catalogue for the selected Playbook. |
| CJ-MBY-002 | Recommendation assistant warns when spend conflicts with the stated use case, proposes a better allocation, explains impact and never silently changes the basket. |
| CJ-MBY-003 | Equal-or-better Playbook compliance, permitted catalogue tags, Flex-only flip components and delivery/vendor eligibility are enforced. |
| CJ-MBY-004 | Component-help links/modal fallbacks work even while video assets remain unavailable; missing planned content is clearly labelled rather than fabricated. |
| CJ-MBY-005 | Payment through post-sale uses the Curated sequence, retaining the exact approved custom specification and every accepted/rejected recommendation. |
| CJ-MBY-006 | The customer portal receives its per-order Build shell at sale; known structured billing, delivery, nested address, contact, email, and phone fields are scrubbed recursively from order specs, while technical component fields remain. It is enriched with exact physical components and measured evidence at Ready to Ship. Missing benchmarks, components, case or destination block dispatch preparation with an actionable reason. |
| CJ-MBY-007 | Made-by-you requires a customer-declared Budget, Mid-range or High-end Playbook tier before checkout; the storefront `studio` flow marker maps to custom-catalogue pricing, while the server rejects any non-curated checkout without a declared tier regardless of the client marker. The tier survives shared build links, cart, payment-intent metadata, confirm/webhook recovery and order snapshot. The software-options endpoint returns the exact reviewed customer-type × tier profile, or the reviewed use-case default when no cell override exists. Client edits cannot mismatch a paid tier, and final component spend never silently changes it. |

### 7.5 Cross-product and negative journeys

- Declined, abandoned, duplicate and webhook-delayed payment.
- Price or stock changes between selection and payment.
- Partial Made-by-you drafts remain saveable/repriceable while payment requires every published Custom slot and rejects components outside that catalogue.
- Component becomes unavailable and substitution needs approval.
- Account, guest and indirect customer communication rules.
- Cancellation before and after Components Ordered.
- A successful, pending, failed and retried pre-components-order refund keeps the Build shell and Getting Ready job aligned with order state; software edits are unavailable while refund reconciliation is pending and after cancellation.
- Fault reported inside 30 days, later statutory repair/replacement, commercial warranty claim, out-of-warranty support and abusive/duplicate claim.
- Return in transit, inspection, diminished-value evidence, refund timing and failed refund recovery.
- Courier loss/damage, evidence pack, insurance claim and customer resolution independent of insurer reimbursement.
- Concurrent and repeated Parcel2Go booking requests; timeout after order creation and after payment; saved-booking replay; admin reconciliation attaches an already-paid booking or permits retry only after recording that no active booking exists.

## 8. Build lifecycle suites

### 8.1 Sourcing to catalogue

| ID | Coverage |
|---|---|
| SRC-001 | Manual and scheduled extension scans carry workspace/catalogue markers, source, search definition, run ID and tags through ingestion. |
| SRC-002 | Dedup preserves additive catalogue tags; repeated observations update price/availability without erasing provenance. |
| SRC-003 | Curated/custom tags populate their catalogues; Ready-to-Ship remains on the prebuild workflow. |
| SRC-004 | Amazon Prime is detected when supported and receives its configured fallback; explicit listing ETA overrides vendor fallback. Other vendors default to 3 days; Vinted/eBay/eBay auctions default to 7 days and Flex-only eligibility. |
| SRC-005 | Auctions ending within 24 hours can enter Ready-to-Ship candidate generation but cannot create an unapproved purchase. |
| SRC-006 | Equal-or-better benchmark tiers accept equivalent/better parts and reject worse, missing-evidence or incompatible parts. |
| SRC-007 | A potential flip may supply components only when the Playbook cell allows it and fulfilment is Flex or Ready-to-Ship. Allocation remains exclusive and auditable. |

### 8.2 Build state machine

Exercise every permitted transition and reject every illegal transition for each build type. Assert actor, timestamp, reason, evidence, emitted event, portal projection, email/outbox item and financial side effect.

- Ready-to-Ship: planned → stock secured → built → QA → listed → sold → Getting Ready → delivery booked → dispatched → delivered → aftercare.
- Curated/Made-by-you: recommended/configured → approved → paid/sold → components ordered → received → built → QA → Getting Ready → delivery → dispatched → delivered → aftercare.
- Exception branches: cancel, change request, substitution, sourcing failure, QA failure/rework, return, transit claim, warranty repair, replace, refund and closure.

### 8.3 Financial invariants

- Money uses minor units/decimal rules without float drift.
- Totals equal line items, software/AI services, delivery and discounts.
- Payment, refund, marketplace fee, courier booking and insurance purchase are idempotent.
- Warranty reserve is created once from the configured eligible basis, remains held through an open claim, and releases only after delivered date + 12 months and accounting checks.
- Cancellation or refund reverses/reconciles reserve and profit reporting correctly.

## 9. Listings and third-party channels

| ID | Scenario |
|---|---|
| GR-001 | Exactly one durable job is created at Built for Ready-to-Ship and at paid/sold for Curated and Made-by-you. Retry cannot duplicate it. |
| GR-002 | Customer software defaults come from the selected Playbook cell snapshot; stable string cell IDs survive payment-intent creation, confirmation and webhook recovery; checkout choices survive normal confirmation and webhook recovery, edits remain possible until Components Ordered, and only allow-listed WinGet IDs enter the manifest. |
| GR-003 | AI setup offers default disabled and unpriced; admin cannot enable an unpriced option and must attest that scope/licensing, data/account needs, ongoing costs, support and cancellation/refund terms were reviewed; customers see only reviewed configured offers and all one-off prices come from server settings. Local model setup is purchasable only with at least 12 GB sourced benchmark VRAM evidence; missing/low VRAM and client-supplied prices are rejected. |
| GR-004 | The configured LLM receives redacted structured inputs and returns schema-valid draft content. Deterministic code owns scripts, files, checksums and state. |
| GR-005 | Missing benchmark, guide, licence entitlement, manual, driver evidence or review status blocks only the dependent action and gives an actionable error. |
| GR-006 | Regeneration creates a new version; approved/shipped packages remain immutable. Portal exposes only approved artifacts for its build. |
| GR-007 | The answer file selects en-GB and Audit Mode but contains no disk configuration, product key or account. A separate WinPE installer requires a prior Dispatch Centre model/serial, shows all disks, rejects boot/system/removable or ambiguous targets, checks image metadata for exact Windows 11 Pro and en-GB, and requires serial re-entry plus two distinct typed approvals before clearing only the matched disk. It creates UEFI/GPT partitions, applies the Pro image, sets up boot and Audit Mode, and writes a build-bound installation record. Missing WinPE PowerShell/StorageWMI, tools, media, model/serial match, UEFI, or free space fails before erase. The final OOBE script requires built-in Audit Mode Administrator, Windows 11 Pro/en-GB, a completed setup report, and separate typed approval before invoking Sysprep. The master script refuses unsupported Windows editions/locales, requires elevation and typed approval, runs only reviewed WinGet packages, installs Rainmeter machine-wide, and fails when an installer fails. Script guard tests run in CI; the physical erase/install remains a separately supervised hardware acceptance check. |
| GR-008 | Evidence requires working-build photo or video plus contents-before-packing and sealed-parcel stills with authenticated admin actor ID/name, upload time, size and SHA-256. Upload sets `needs_review`; only an admin approval with an audit note and matching stored checksum marks a valid build-bound artifact complete. Rejected, altered, wrong-category, missing, or wrong-build artifacts cannot satisfy insurance or dispatch gates. |
| GR-009 | Courier booking can follow non-photo Getting Ready completion and remains an explicit idempotent purchase. Admin must affirm signed-for suitability, then separately confirm the exact selected courier/service and price immediately before Parcel2Go booking; changing service clears the suitability affirmation. The server re-fetches the selected service and price, rejects stale or mismatched quotes, and records the exact fresh quote in the booking confirmation before calling Parcel2Go. Only then can insurance be purchased, and only after contents-before-packing and sealed-parcel still photos have been admin-approved against their stored checksums and revalidated against the build-scoped file, size and checksum immediately before the purchase. The operator attests to all current insurer conditions: new resistant double packaging, rigid outer box, non-deducible contents, discreet packaging, adult/direct signature, and official carrier collection/depot handover rather than parcel shop/locker absent written approval. Confirmations are recorded against the build. Dispatch again revalidates the checksums and requires the registered policy, all three admin-approved evidence items, the full dispatch checklist and explicit physical handover. Missing, changed, mis-scoped files, approvals or confirmations block insurance and dispatch, not the earlier courier booking. |
| GR-010 | Dispatch publishes courier/tracking and updates the portal. Direct account customers receive the shipment email; a direct guest's pre-issued claim is preserved and dispatch sends a tracking update without rotating that claim. Marketplace/manual-build sales do not receive off-platform email and continue through channel-compliant updates and the printed portal leaflet. Later courier events are consumed in order; repeated provider/event pairs are idempotent, the same event ID from different providers remains distinct, and out-of-order events are safe. Order tracking and live-map buttons appear only for credential-free HTTPS URLs; unsafe, non-HTTPS or credentialed values are omitted. |
| GR-011 | Saving a portal selection after manifest generation invalidates the draft; direct-order package approval is rejected until customer choices are submitted, then uses exactly that saved list. Indirect builds without a linked order require a separate explicit operator confirmation before the Playbook defaults are locked, and record the actor and decision in the job audit checklist. |
| GR-012 | Curated and Custom 3D asset queues show every selected active catalogue variant, including missing assets. Shared variants appear in both queues but resolve to one asset identity. Upload creates a new non-active version; wrong file type, invalid GLB, oversize upload, and failed media sync do not publish a usable asset. |
| GR-013 | A paid Curated/Made-by-you order bridges idempotently to the ManualBuild dispatch workflow only after QA and explicitly admin-confirmed measured results, complete component/case specification, and delivery destination. Missing or unconfirmed evidence and illegal status transitions are rejected. Whether the order-linked job already exists or must be created at the bridge, exactly one job is linked to the order/build/customer, carries the submitted software selection, and has status `awaiting_admin_review`. Account and claimed-guest portals render the same customer-safe preparation milestone and last-updated time using plain language that does not imply production started while the order is still sourcing. Only explicitly allow-listed progress flags may enter the customer API; the full operator checklist, private notes, actor identifiers, drive serials and evidence stay private. Confirmed evidence and exact order components appear in dispatch; courier/evidence/handover updates the original order and portal. Ready-to-Ship keeps its existing pre-sale workshop path and is linked at sale. |
| GR-014 | Account owners and one-build guest-token holders see only the reviewed customer package and individually allow-listed customer documents for their order/build; unlisted paths, traversal names and internal scripts are denied by individual-download routes. Customer ZIPs contain only allow-listed documents and checksums; workshop USB archives (scripts, answer files and deployment materials) are available only to authenticated admins from Dispatch Centre. Legacy mixed archives are filtered before customer delivery. The operator dispatch checklist is absent from customer downloads and available only through the admin-authenticated Dispatch Centre endpoint, including before ZIP approval for sold builds. Replacing a package updates the portal index without exposing files from another build. |
| GR-015 | Welcome Guide generation/status/download require the owning customer JWT or a guest token scoped to that exact order; guessed order IDs, cross-account JWTs, revoked/expired guest grants and mismatched guest order IDs are denied. Guest tokens cannot generate or regenerate a guide. |
| GR-016 | New Windows Welcome Guides never contain the assigned key. A legacy guide is regenerated before it can be downloaded, and its response is private/no-store. The separate admin activation helper remains excluded from customer documents and ZIPs. |
| GR-017 | A Ready-to-Ship unit with a Getting Ready job appears in the pre-sale Getting Ready queue at Built and remains visible while Listed; `mark-built` may transition only an in-progress or already-built build and cannot rewind Listed/Sold. Its build-row lock prevents duplicate job creation on concurrent calls. It is absent from courier, insurance and dispatch-evidence queues until Sold. API calls to book courier, upload/review shipment evidence, purchase insurance, or dispatch must reject a pre-sale build even when stale booking, policy, tracking or dispatch fields are present. Customer ZIP and setup-script download remain unavailable pre-sale. At Sold, the same single job and existing pre-sale orchestration Build row attach to the buyer and order while preserving physical component specifications, benchmark artifacts, checklist and audit notes; no duplicate Build row is created. Concurrent order/webhook recovery cannot create duplicates, order/build/customer mismatches and cross-order relinking fail closed, and conflicting pre-existing job/build rows require reconciliation. |
| GR-018 | Admin package approval assembles the checklist from the current persisted job state, marks only package-review actions complete, preserves prior audit/evidence entries, and records the indirect-channel Playbook-default decision when no linked order exists. |
| GR-019 | AI setup checkout is customer-owned and order-scoped; an unowned order, disabled/unknown offer, cancelled order, pre-components-order made-to-order build, locked preparation job, or ineligible GPU cannot create a PaymentIntent. Stripe amount is the configured server price and metadata cannot change the amount or order. |
| GR-020 | Repeated AI payment-intent requests reuse one persisted intent per order/offer; succeeded, processing and failed-card retries do not create duplicate charges. The webhook validates persisted purchase, customer, order, offer and amount, attaches the service once only after success, never creates a PC order, and safely retries duplicate or early webhook delivery. |
| GR-021 | A pending AI payment blocks final package approval; successful payment invalidates any draft manifest/package state, attaches a price/scope snapshot to the job, and makes AI setup blocking until operator completion. `not_required` is rejected for a paid service; dispatch remains blocked until completion. |
| GR-022 | Customer portal shows configured prices and eligibility, uses Stripe Payment Element, shows paid setup only after webhook confirmation, and preserves local AI model gating when benchmark evidence is absent or below 12 GB VRAM. Guest/preview portals cannot purchase. |
| GR-023 | Customer cancellation of an unpaid AI setup PaymentIntent is confirmed by Stripe before the purchase is marked cancelled; succeeded/processing payments cannot be cancelled. A cancelled offer can be retried with a new intent, while package approval is blocked only by genuinely pending payments and duplicate/late webhooks remain safe. |
| GR-024 | Dispatch Centre can preserve and submit an administrator-reviewed research bundle. Entries require an exact component present in that build, supported research topic, HTTPS URL, publisher, title, valid access date, bounded claim and explicit operator attestation; malformed, mismatched, unapproved, oversized or extra-field input is rejected. Accepted entries are snapshotted with the manifest inputs and reviewer identity/time, then supplied to the LLM as evidence, without source fetching, downloading, installation or checklist completion. |
| GR-025 | Manifest generation accepts only the active Getting Ready prompt-template version and exact source build name; instruction-like text embedded in supplied research/component/selection/policy data cannot override the system rules or output contract. The uploaded generic guide is excluded from model input. Invalid JSON, extra fields, wrong build identity and stale template version fail closed. |
| GR-026 | Parcel2Go booking persists the `OrderLineId` mapped from the submitted item ID separately from parent `OrderId`; if it is missing, payment is not attempted and the unpaid order enters reconciliation. Existing paid bookings without a saved line ID can attach a verified reference only when parent order ID and tracking number match, with no second charge. Callback verifies the documented HMAC-SHA256 hex signature before accepting a payload; absent secret, bad signature, stale new event and oversized/malformed bodies fail closed. A valid signed duplicate ID is acknowledged even after the freshness window so a saved event's failed direct-order email can be retried. Tracking stages attach by shipment line to the matching build/order and appear in the portal. Direct orders send one customer update per distinct event; retry never duplicates the timeline entry. Indirect/manual-build shipments do not receive off-platform status emails. Delivered uses the earliest verified delivery timestamp and backdates an unreleased reserve if an earlier event arrives later; repeat/out-of-order events cannot restart or extend the warranty clock. Unknown shipment references remain retryable, unsupported event types are acknowledged without mutation, and duplicate/out-of-order events never duplicate reserves or regress delivery state. |
| GR-027 | After successful manifest generation, the saved checklist persists `source_data_complete` as complete only when both specification and benchmark evidence exist, otherwise needs review; `content_manifest` is needs review until package approval. Regeneration preserves unrelated checklist state, and package approval advances only its own system-managed actions. |
| GR-028 | Operator-completed and `not_required` checklist actions require a meaningful 12-character audit note; Windows deployment still requires a current build-bound evidence report and pre-install target confirmation. API callers cannot bypass the note rule, and a supported paid AI service cannot be marked not required. RGB may be marked not required only with a recorded explanation when no applicable reviewed profile exists. |
| GR-029 | LLM driver/manual references must resolve by exact normalized component-model name to one component in the persisted build specification; partial-name matches fail closed even when only one candidate exists. Returned URLs, titles and access dates are bound to exact administrator-approved source records; an unapproved URL, wrong component association, invented source metadata, invalid HTTPS URL or model attempt to waive administrator approval fails closed. The versioned template and runtime contract advance together. |
| GR-030 | Dispatch evidence and the operator-only dispatch-checklist downloads require admin authentication. Evidence resolves only artifact-index entries contained beneath private storage and returns `private, no-store`, `no-cache`, and `nosniff` headers. Missing IDs, path escapes, and unauthenticated requests are denied. |
| GR-031 | Sold-state builds only: new shipment evidence remains `needs_review` after upload. An admin must inspect and approve or reject it with a meaningful note; checksum mismatch, missing file, video in still-image categories, pre-sale upload/review and review after dispatch are rejected. Approval records reviewer identity/time/note, updates the checklist, and only approved eligible media clears the insurer and handover gates. Insurance purchase and dispatch recheck the build-scoped path, file size and SHA-256; post-review tampering or cross-build references block both actions. |
| GR-032 | The standalone dispatch checklist follows the enforced order after Sold: verify parcel data, explicitly book the signed-for courier and obtain tracking, capture and review shipment evidence, create insurance only behind its production gate, then separately confirm physical handover. Pre-sale API attempts to book courier, insure or dispatch are rejected, including retries with stale fields. The handover record snapshots the authenticated admin ID/name, time, tracking number and provider order reference; repeated dispatch is idempotent and checklist/evidence changes are locked after handover. Working-build video is allowed; insurer contents/sealed-package photos remain still images. |
| GR-033 | Every canonical use-case Playbook resolves its reviewed software recommendations rather than the generic fallback; Curated and Made-by-you cell profiles resolve the exact customer-type × tier override when present. Recommendations contain only allow-listed WinGet IDs, and saved-time estimates sum only the apps the customer selected. Unknown package IDs and invalid Made-by-you tiers are rejected before script generation or paid checkout. |
| GR-034 | An admin-issued `direct_guest` claim grant must be bound to a non-cancelled order and the exact customer email on that order; its one-time claim URL is mailed only to that address. The email escapes customer/build text, links the opaque single-use token, and communicates expiry. SMTP unavailable/failure is reported to the admin with a printed-leaflet fallback. Marketplace and printed-insert grants never send a FlipFlop claim link by email. |
| GR-035 | Customer and guest build portals render warranty-case return/replacement carrier, tracking number and a usable link only when the API returns a credential-free HTTPS URL. Each case shows its current repair milestone; missing, malformed, credential-bearing or non-HTTPS tracking URLs never become clickable links. |
| GR-036 | A guest portal token without the optional `support:create` capability can still read its own existing support/warranty case statuses and safe repair tracking, but cannot see or submit the case form or access case evidence. A token with the capability can use the scoped support and evidence flows. |
| GR-037 | Package assembly emits a paid-AI operator runbook only from supported, webhook-confirmed paid offer snapshots. Unknown, duplicate, renamed or pending purchases fail closed; local-model instructions require an exact customer-approved model and recorded VRAM of at least 12 GB; assistant, second-brain, account and data boundaries require explicit customer/admin decisions. No script, secret or automatic install is generated by this runbook. |
| GR-038 | Completing the Paid AI services checklist for a build with paid AI selections requires an explicit operator confirmation that the customer approved the exact assistant/model and account/data permissions, followed by the existing required audit note. The API rejects completion without the confirmation flag and records it in the audit entry. No confirmation is required when the build has no paid AI selections. |
| GR-039 | Shared catalogue GLB upload accepts only binary glTF version 2 with a declared container size equal to the uploaded bytes; malformed headers fail with a client error before any public media file or database asset row is created. |
| GR-040 | Curated CPU/GPU upgrade approval compares the candidate with the saved Playbook `from_sku` baseline using gaming, workstation, or overall score for the relevant customer type. Equal/better scores are accepted and persisted with model, score, metric, and source; lower or missing benchmark evidence blocks approval. |
| GR-041 | Customer warranty summary reports `not_started` when there is no delivery reserve or the recorded warranty start is in the future, `active` from the delivery instant until the expiry boundary, and `expired` only after that boundary. Expired commercial cover still states that statutory rights are unaffected. |
| GR-043 | A warranty/technical-fault case opened before delivery is linked once when the order reserve is created, keeps the reserve in `claim_open`, and prevents release eligibility. Delivery-only support cases do not create warranty claims or hold the reserve. |
| GR-044 | Concurrent first-delivery events and warranty-case submissions for one sale serialize on the owning order/build before checking for a reserve. New warranty cases acquire the owner lock before insertion; explicit reserve release acquires the same owner lock before locking the reserve. Existing warranty-claim mutation paths—including the customer-problem admin endpoint, the dedicated claim endpoint and a delivered customer-return webhook—use the shared reserve-first claim-lock helper, then lock any case/shipment rows they change in that order before recalculating reserve state. Unit cases verify reserve-before-claim and owner-before-reserve query order. PostgreSQL integration cases verify reserve contention, latest-status reserve attachment, and that release waits while a new claim is flushed but not yet attached; after the case commits, release must reject and the reserve must remain claim_open. Exactly one reserve and one claim per case remain; retries return existing ledger state. Run race coverage on PostgreSQL because SQLite ignores row-level `FOR UPDATE`. |
| GR-045 | Getting Ready cannot mark Windows deployment complete without a previously recorded, current intended drive. The post-install build-bound report must match its model and serial, and its verification timestamp must be after target inspection; changing the target clears completion. The answer file has no disk selection/wipe, key or account. The generated WinPE installer binds erasure to the pre-recorded target and two typed confirmations, then applies only Windows 11 Pro in UEFI mode. The customer OOBE handoff script requires the elevated built-in Audit Mode Administrator, Windows 11 Pro/en-GB, the completed workshop report and a second typed confirmation before Sysprep. Rainmeter setup is machine-scoped and its shared Startup activation and skin are available to the customer profile. Windows SIM and physical hardware acceptance are separate supervised checks. |
| GR-046 | The generated workshop USB README directs the technician to run the master setup script from the elevated built-in Audit Mode Administrator on the new Windows 11 Pro installation, requires the typed `RUN` confirmation, and makes clear that customer first-run setup happens only after the separately confirmed Sysprep handoff. It must not tell the technician to use or create a customer Windows session. |
| GR-047 | Software installs requested in Audit Mode use explicit machine scope so WinGet cannot silently choose the workshop Administrator's user scope. A user-scoped app such as Discord is excluded from the Audit Mode install script, packaged as a customer-profile installer, copied to ProgramData, and scheduled from Common Startup. The script runs visibly as the signing-in customer; it does not pass source/package agreement-acceptance flags or `--disable-interactivity`, so required agreements remain for the customer to review and accept personally. It reports success in that profile, retries after failure, and the Getting Started guide explains the prompt and that declining a required agreement prevents that app from installing. The manifest's machine/user install plan is overwritten from the saved selection and allow-list, regardless of LLM output. |
| GR-048 | A warranty shipment with a Parcel2Go reference accepts only authenticated signed events for that exact shipment leg. Duplicate provider/event IDs persist once; unmapped and ambiguous references fail closed. Events appear in account and claimed-guest portals without exposing provider references or audit fields. A delivered customer return advances to `received_for_inspection` and updates the linked claim without changing the original build-delivery date or reserve; a delivered outbound repair parcel does not resolve the claim. Direct-storefront email retries are safe for return receipt and outbound delivery; marketplace/manual-build cases receive no off-platform email. Other carriers remain link-only. |
| GR-049 | A claim that has both a customer-return parcel and a later repaired/replacement parcel retains two distinct shipment records and timelines. Events from the inbound parcel remain attached only to that parcel after the outbound parcel is booked; provider references cannot be reassigned across shipment legs. The admin history remains visible through inspection/repair stages, and admins can edit the matching leg only before courier events exist. |
| GR-050 | The repair shipment migration carries the existing case tracking fields and case-attached events into one shipment leg without losing event time, tracking URL, provider reference or case ownership, and safely normalizes malformed legacy JSON values/purposes. Downgrade restores inbound-only events/fields and refuses once outbound repair shipment data would be lost. |
| GR-051 | The generated WinPE Windows installer is bound to the build ID/name and requires the exact target model/serial recorded in Dispatch Centre. It lists all disks, refuses missing/duplicate identities, boot/system/removable targets, non-UEFI mode, missing tools, missing media, or an image that does not report exact Windows 11 Pro and en-GB. It requires two distinct typed approvals before any `Clear-Disk`. No other disk is modified. It logs the selected target, image and result; the post-install evidence collector must still independently match the actual system drive before Dispatch Centre records completion. |
| GR-052 | The generated installer checks that its package-local answer file exists and that the selected image reports en-GB before showing the destructive approval prompts. A missing answer file or unsupported image language stops before any disk-modification command. |
| GR-053 | Build names are embedded in generated PowerShell only as encoded data, never interpolated as executable source. Names containing quotes, CR/LF or PowerShell syntax must remain inert while the generated script remains bound to the correct build. |
| GR-054 | The checklist API, courier-booking gate and physical-dispatch gate reject `not_required` for required preparation, verification, evidence, portal and handover actions, even when invoked directly or when an invalid waiver was already persisted. The Dispatch button remains disabled for those invalid waivers. All readiness gates use the same waiver policy. Only explicitly optional paid-AI setup when no purchase exists, and RGB personalization, can be waived; paid-AI purchases have the separate consent/completion rule. |
| GR-055 | Uncertain insurance creation cannot be retried without admin reconciliation. Reconciliation is limited to a sold build with a confirmed courier booking. The admin must confirm a provider-account check and either attach an existing policy whose parcel tracking number and insured value match this build or confirm no policy exists before retry. A `creating` request cannot be reconciled until its two-minute in-flight window has elapsed. Reconciliation is audited and idempotent; insurance purchase remains feature-gated and explicitly confirmed. |
| GR-056 | Customer, guest and admin case-evidence downloads verify the stored SHA-256 before returning the exact verified bytes. Missing or mismatched integrity metadata returns an error without serving the file. Responses are private, non-cacheable and use `nosniff`. |
| GR-057 | Package approval creates distinct customer-documents and workshop USB ZIPs with separate filenames, sizes and SHA-256 values. The customer archive contains only allow-listed customer documents and checksums; the admin download route serves the workshop archive and requires admin authentication. Customer portal downloads of pre-upgrade mixed archives reconstruct an allow-listed archive and never return workshop scripts. |
| GR-058 | Cached component manuals match only when the administrator-entered normalized key equals a normalized identity field on one build component. A shorter family name, substring found only in description/slot metadata, or inactive manual must never match. Exact punctuation/case normalization is allowed; package approval must revalidate the same component and checksum before including the cached PDF. |
| GR-059 | Before returning a customer ZIP or individual document, the API verifies the source archive against the SHA-256 captured at approval. Missing/invalid digest metadata or changed archive bytes fail closed for authenticated and claimed-guest downloads; legacy archive sanitization runs only after this integrity check. |
| GR-060 | Customer archive allow-list accepts cached manual PDFs only as a single safe filename directly beneath `07-component-manuals/`. Absolute paths, backslashes, dot segments, nested paths and unsupported document names are omitted from ZIP responses and individual-download indexes. |
| GR-061 | A new Parcel2Go charge is rejected unless the authenticated admin request carries explicit live-purchase confirmation and signed-for confirmation. The API re-fetches the selected service and requires the fresh GBP amount to match the confirmed amount to the penny before charging; even a £0.01 change requires reconfirmation. It persists service, confirmed amount, admin identity and time before the provider call. A previously booked shipment remains idempotently readable without a second purchase confirmation; uncertain in-flight outcomes still block retries pending reconciliation. |
| GR-062 | A verified direct guest claim is issued before courier booking, stores only its token digest, creates a private QR leaflet linked to the order and Getting Started job, and sends the claim email only to the exact verified order email. Physical dispatch reuses this grant, does not revoke it or rotate the QR, and sends the tracking update separately. Legacy sold builds without a pre-issued claim may recover by issuing one at dispatch and emailing the new claim with tracking. The API never returns the raw claim URL except in the authenticated issuance response; email status (`pending`, `sent`, `failed`) is persisted. eBay/Vinted/indirect orders never receive an off-platform claim URL. |
| GR-063 | Dispatch Centre reads the latest grant and persisted email status after reload and offers its private leaflet. Direct guest reissue is permitted only for a linked direct order and sends only to that order's verified email. Any reissue revokes older unclaimed grants; the returned leaflet must replace the prior one. Indirect-channel claims remain printed-QR only, and reissuing an existing indirect grant after courier booking or dispatch is rejected so the parcel's printed QR remains valid. |
| GR-064 | Figural policy creation is rejected while production eligibility is disabled, and requires each explicit operator attestation. Once enabled in an isolated test fixture, it fetches a fresh premium and compares the two-decimal GBP amount to the amount reviewed; a one-penny change, invalid amount or missing confirmation must reject before the insurer create call. Before an accepted provider call, the durable attempt records the exact confirmed premium, insured value, currency, admin ID and time. Uncertain outcomes retain the existing reconciliation gates. Reconciliation rejects a one-penny premium or insured-value mismatch both when attaching an uncertain policy and when confirming an already-linked policy idempotently. |
| GR-065 | The rendered Dispatch Centre checklist identifies every `DISPATCH_BLOCKING_ACTIONS` gate in plain operator language, including source-data review, manifest creation/review, customer and workshop artifact generation/review, customer package approval, software and USB setup, Windows and activation checks, driver/AI/RGB work, QA, portal/leaflet publication and all three evidence photos. The private Windows activation helper appears once, after USB checksum verification and before master setup; it requires the separate typed confirmation, is excluded from both ZIPs, and is removed after success. The rendered checklist remains an aid only: checking a paper item never changes the persisted checklist, evidence review, booking, insurance or handover state. |
| GR-066 | The paid `book-shipment` path refuses to request a fresh quote or call create/pay providers for direct guest, marketplace or manual-build sales until a current, unclaimed, non-revoked portal grant with a private leaflet exists. Signed-in direct account customers do not need a guest grant. Completing `leaflet_printed` records the exact current grant ID; if a new claim is issued later, booking rejects until the replacement leaflet is printed, scan-tested and recorded. Existing manual/marketplace claims cannot be reissued after booking; direct guest claims cannot be rotated between booking and handover. At dispatch, a pre-issued direct guest grant is reused and is not revoked; a missing/revoked/expired claim on a legacy booked build is recovered with a new emailed claim. |
| GR-067 | Redeeming a one-time guest claim issues a portal token whose expiry is 400 days after issuance, scoped to only its grant/order/build. Expired or revoked grants and mismatched grant ownership invalidate access immediately, including before token expiry; the grant remains single-use. |
| GR-068 | Concurrent redemption requests for the same unclaimed guest grant are serialized by the database so at most one request can consume the grant and receive a portal token. Verify against PostgreSQL; SQLite's lack of row-level `FOR UPDATE` behavior is not sufficient evidence. |
| GR-069 | Newly issued buyer claim URLs carry the one-time secret in the URL fragment, so it is absent from the initial HTTP request and normal referrer headers. The claim page accepts legacy query links during migration and removes the secret from browser history before any redemption request. |
| GR-070 | Opening a claim URL does not consume the one-time grant. Only an explicit buyer button action sends the redemption request, preventing ordinary email scanners and previewers from consuming access; both claim emails explain the extra action; one click submits at most one request, including under React Strict Mode. |
| GR-071 | Admin-triggered component-source discovery accepts only an exact identity already recorded on the build and a supported research topic. It returns at most eight external HTTPS title/URL/host suggestions, saves nothing, fetches no result pages/files, and never sets an access date, operator approval or factual claim. Selecting a candidate creates an unapproved editable draft with its access date blank; only the existing explicit source review can send it to manifest generation. |
| GR-072 | For manual research, the admin source-suggestion request checks the active central manual library first using exact normalized component identity. An exact active match is shown without calling external search; inactive or substring-only matches do not short-circuit search, and the suggestion is still not itself approval or ZIP inclusion. Manifest generation and package approval revalidate exact identity, active status and checksum. With no exact cache match, external candidates follow GR-071. |
| GR-073 | Editing a research draft's exact component name or topic immediately clears displayed web suggestions and cached manual matches for that draft and invalidates any in-flight response for the old query. Removing a draft invalidates all indexed search results and requests for that build before remaining rows shift. Superseded requests cannot alter another row's results or loading state; an earlier result or error must never appear or be selectable as if it belonged to the current identity. |
| GR-074 | For Made-by-you, only an explicit Playbook `gpu_required: false` makes the GPU optional. The GPU starts unselected and may be omitted from checkout while every required slot remains mandatory; curated builds still require their full approved specification. Selecting an optional GPU restores reviewed GPU fit, connector and power checks and surfaces a non-mutating budget advice message tied to the Playbook. Missing or malformed requirement data stays conservative and requires a GPU. |
| GR-075 | First-line support answers use the approved customer-safe knowledge-base version and may explain GPU optionality only when the current Playbook explicitly says it is optional. Advice must state that customer selections are unchanged, must not promise performance/savings, and must preserve the complete Curated-for-you specification. |
| GR-076 | A fresh Made-by-you Studio evaluation with `OPTIONAL_GPU_SPEND_REVIEW` opens Hermes with the bounded recommendation once for that configuration; unrelated advice codes are ignored and rerenders do not repeatedly append the same recommendation. |
| GR-077 | If the build's identity/order/status, specification, benchmark/performance evidence, Playbook assignment, delivery date, or the linked Getting Ready job/software/paid-AI scope changes while the LLM drafts a manifest, the API must reject the stale result, including when a job was created during generation. It locks build then job, rechecks source state, and must not overwrite concurrent evidence. |
| GR-078 | For a Ready-to-Ship package using a database-authored Curated cell, an admin profile edit to the cell or its parent Playbook while content is being drafted causes the API to reject the draft. Profile editing and manifest persistence serialize on the parent Playbook row; persistence reloads/locks the Playbook and Curated segment and compares the resolved profile to the one supplied to the model. |
| GR-079 | An eBay/Vinted/marketplace manual-build claim may be issued without a stored buyer email, remains bound to that build, is never emailed, and returns no raw bearer URL to Dispatch Centre; the private printed leaflet contains the claim. Guest support access succeeds only for that grant/build association. A supplied mismatching email and an email-free direct guest order claim are rejected. |
| GR-080 | New direct and printed marketplace claim grants default to a maximum 400-day lifetime, covering the 12-month delivery warranty window when the buyer redeems late; explicit values outside 1–400 days are rejected. The exchanged guest session remains build-scoped and expires after 400 days. |
| GR-081 | An expired/redeemed claim error presents recovery guidance that works for the grant's channel: verified order email for a direct order, marketplace support for an indirect purchase, and no promise to email or send the marketplace buyer an external URL. |
| GR-082 | When a guest browser lacks its saved portal session or the scoped token expires/revokes, the portal gives direct buyers verified-order-email guidance and marketplace buyers channel-compliant support guidance. It does not imply a marketplace URL can be emailed or reissued after dispatch. |
| GR-083 | A guest support-case request denied for missing capability or a marketplace/build mismatch gives channel-safe recovery guidance: direct guest order email for direct orders and the originating marketplace for indirect grants. It does not tell marketplace buyers to request verified-email reissue. |
| GR-084 | Public Hermes free-text support uses only the approved customer-safe support guide and the labelled customer-safe Software Playbook section; it returns source name/version/review date, never receives live account data, refuses to invent order-specific facts, and enforces message/history size limits. Provider failure returns a safe contact/support fallback. When repository docs are absent in a container, the packaged reviewed copies must provide the same versions and safe sections as the canonical docs. |
| GR-085 | In an API-only image without repository-level `templates/` or `docs/`, the prompt/checklist/Rainmeter resolver and customer support loader select the packaged copies. Each packaged file is byte-identical to its canonical source, the sync script's `-Check` mode detects stale or missing copies, and repository-level templates remain authoritative when both are present. Existing manifest, checklist and installer generation cases must continue to exercise the resolved content. |
| GR-086 | A failed direct-storefront dispatch email remains durably pending and a scheduled worker retries it with bounded exponential backoff. Success records `customer_notified_at`; concurrent workers cannot claim the same attempt; eight failed attempts emit one admin alert. Marketplace/manual channel sales never receive off-platform retry email. |
| GR-087 | Direct storefront warranty/aftercare status and repair-tracking emails are recorded in a durable outbox before the admin update commits, sent promptly after commit, and retried by a scheduled worker with bounded exponential backoff. Each email uses the saved status/tracking snapshot; success is terminal, eight send failures create one actionable admin alert, and a missing order recipient creates a terminal admin alert rather than silently dropping the update. Marketplace/manual-build cases never receive off-platform email. |
| GR-088 | Parcel2Go order and repair-shipment event emails persist an attempt before delivery, are retried by a five-minute worker with bounded backoff even if Parcel2Go does not resend its webhook, and stop after eight failed attempts with one admin alert. Concurrent webhook/worker attempts do not send the same event concurrently. Marketplace/manual-build events never receive off-platform email, and non-customer-visible repair scans do not produce mail. |
| GR-089 | Ready-to-Ship and Made-by-you checkout distinguish an omitted software selection from an explicit empty selection: omission uses the Playbook recommendations on initial checkout, while `[]` is encoded as a non-empty PaymentIntent metadata sentinel and remains no optional apps through checkout-option edits, confirmation/webhook recovery and the Getting Ready job. Omitting the field on an existing Ready-to-Ship checkout-options update preserves the saved app IDs; invalid IDs are rejected. The customer portal shows the correct edit deadline: dispatch for Ready-to-Ship and Components Ordered for Made-by-you/Curated-for-you. |
| GR-090 | In Dispatch Centre, editing any reviewed manual-source field clears its approval, and a stale result cannot be approved for a different component/topic. Only an admin-confirmed, manually downloaded and inspected PDF from the confirmed official HTTPS source can be uploaded to the shared manual cache. The upload enforces the PDF header/size and exact model key; the build ZIP includes it only for an exact build identity match and rechecks its active status and checksum at package approval. No URL or search result triggers a server-side file fetch. |
| GR-091 | Every Getting Ready operation that locks or mutates both `ManualBuild` and `GettingStartedJob` acquires locks in build-then-job order through the shared fresh-row helper. Unit coverage verifies the helper locks both rows in that order; PostgreSQL coverage verifies a competing preparation writer waits on the build row before proceeding to the job. Concurrent manifest generation and package approval must serialize without deadlock or lost evidence. Checklist updates, evidence reviews, dispatch uploads and physical dispatch use the same helper. |
| GR-092 | Customer cancellation and admin component-order milestones serialize on the same Order row. If cancellation commits first, procurement status changes are rejected; if `Components Ordered` commits first, self-service cancellation is rejected. Refund-pending orders remain sourcing-locked. |
| GR-093 | A clean Alembic upgrade creates `getting_started_jobs` with its unique order/build links, required JSON state and customer index; upgrade against a database where the legacy startup path already created the table preserves existing jobs. Downgrade must not delete live preparation data. |
| GR-094 | Getting Ready LLM output is validated against strict nested schemas for plaque, customer copy, software plan, upgrade items and portal document names. Unknown nested keys, malformed value types, or unapproved portal artifact names fail before manifest persistence; deterministic software IDs/scopes and build identity remain authoritative. |
| GR-095 | Missing or out-of-order System prompt, User prompt and Output contract sections in the active Getting Ready template fail with a typed generation error before any LLM call. |
| GR-096 | Prompt rendering substitutes only placeholders present in the template in a single pass. Braces and placeholder-like text inside JSON-encoded customer/guide inputs remain data and are not substituted or rejected; unknown placeholders authored in the template fail with a typed generation error. |
| GR-097 | The prompt loader requires a declared template version matching the active manifest contract and rejects missing or stale versions before any model call. |
| GR-098 | `ModelSelectionService.complete(max_tokens=N)` sends the same requested output limit to local Ollama as `options.num_predict=N`; the limit is not silently ignored for the configured local model. |
| GR-099 | Getting Ready measures the combined UTF-8 byte size of system and rendered user prompts and rejects requests above 20,000 bytes before calling any provider; inputs are not silently truncated. |
| GR-100 | An oversized Getting Ready prompt returns HTTP 413 with actionable guidance and does not call an LLM provider; template, model and output-validation failures retain the generation-error response. |
| GR-101 | The administrator-uploaded generic Getting Started guide is excluded from the model prompt, so guides up to the configured 1 MB limit do not consume the LLM prompt budget; the approved guide is still included verbatim in the customer package and bound by its recorded SHA-256. The active template and service contract use version 1.7. |
| GR-102 | The active template must include placeholders for every required manifest input: build identity, Playbook cell, exact specification, benchmarks, customer app choices/scopes, paid AI scope, warranty date, support base URL, approved research/manual sources and upgrade policy. Missing any required input fails before the LLM call. |
| GR-103 | Even an archive marked `customer_safe` must contain exactly its allow-listed customer documents plus `CHECKSUMS.sha256`, with no duplicate member names; a metadata pointer/digest changed to a workshop ZIP or any unexpected/missing/duplicate archive member is rejected before streaming. |
| GR-104 | If dispatch-evidence storage succeeds but a database operation fails before COMMIT is attempted, the API rolls back and deletes the newly written private file. If COMMIT is attempted but its outcome is uncertain, the API retains the private file and logs the build/artifact identity so a possibly committed database reference cannot point at deleted bytes; reconciliation is required. A confirmed successful commit retains the file and its build-scoped metadata. |
| GR-105 | A legacy eBay Ready-to-Ship build that reaches Sold without a Getting Started job remains visible in Dispatch Centre; manifest generation creates exactly one build-scoped job, preserves the sale/build identity, and package approval still requires explicit confirmation to use the Playbook defaults for an indirect buyer. Before booking, the operator must issue and print the build-bound guest claim; portal access remains scoped to that build, and marketplace orders receive no off-platform claim email. Repeated recovery/generation does not duplicate the job or guest portal. |
| GR-106 | The standalone machine-scope software script is generated by an authenticated, private, no-store download endpoint from the same allow-listed app selection embedded in the workshop ZIP. It requires a sold build, submitted customer choices or explicitly accepted indirect defaults, and a reviewed package; it is never embedded in the Dispatch Centre queue response. The UI button remains available after page reload when those conditions hold. Customer and workshop ZIP separation remains intact. |
| GR-107 | Package approval writes customer and workshop ZIPs before persisting their artifact metadata. A flush failure rolls back and removes both new files. If COMMIT was attempted and its outcome is uncertain, both files are retained and their identifiers are logged for reconciliation; successful approval preserves both artifacts. |
| GR-108 | At checkout, the displayed time-saving estimate is calculated from the currently selected apps and the copy describes it as an estimate for that selection. Toggling an app updates the estimate; it must not claim that an edited selection still represents the original recommended list. |
| GR-109 | Warranty expiry processing follows the common sale-owner-then-reserve lock order used by warranty claims and reserve release. Concurrent worker runs skip already locked owners/reserves, recheck expiry/status after acquiring locks, and create at most one eligibility alert; the worker never releases funds. |
| GR-110 | A build-specific preview token containing both a physical build ID and its sold order ID resolves through the order portal path, including the order-owned warranty reserve and order-scoped tracking events. A build-only indirect preview falls back to its build-owned reserve. The portal must not claim the warranty has not started when the linked order reserve is active. |
| GR-111 | Ready-to-Ship software choices remain editable after a package is reviewed until physical dispatch. A changed selection retires the old customer/workshop archive from current access, clears its reviewed state and build evidence pointer, preserves the old version number for monotonic package versioning, and reopens admin review. Dispatch and delivered builds reject the change; Made-by-you/Curated-for-you remain locked at Components Ordered or reviewed package state. |
| GR-112 | Re-submitting the already-submitted software set, even in a different order, is idempotent: it preserves the reviewed package and status. First submission and any set change invalidate drafts/review as appropriate; invalid package IDs remain a 422. |
| GR-113 | Workshop package approval requires a current, timezone-aware pre-install target drive record. The generated WinPE script embeds that exact model/serial and inspection time, accepts only the official media root as runtime input, and refuses a missing or expired (over 30 days) target. Changing the recorded target after package review retires the old workshop/customer archives from active access and clears review/evidence pointers so the package must be regenerated. The operator still re-enters the serial and types both destructive-operation confirmations; wrong/ambiguous/system/removable targets fail before disk changes. |
| GR-114 | A delivery confirmation found by the email-monitor fallback for a directly linked Ready-to-Ship build updates the order and starts the order-scoped warranty reserve, attaching any pre-delivery order warranty case to that reserve. A marketplace build without a linked order remains build-scoped. Duplicate/earlier delivery times must not lengthen the warranty period or create a second reserve. If the physical build resolves to more than one distinct sale order, record the delivery event for operator review and create no order- or build-scoped reserve until ownership is reconciled. |
| GR-115 | The email-monitor delivery fallback uses an explicit past ISO-8601 timestamp only when it appears on a line describing delivery and includes a timezone; it normalizes to UTC before starting the warranty clock. Future or timezone-free timestamps are ignored, and the message-processing time remains the fallback. |
| GR-116 | A matched email-monitor delivery is persisted once in the correct order/build portal timeline. Repeated confirmations do not duplicate the event or customer email. Only a direct storefront order is marked for an off-platform delivery email; marketplace/build-only and ambiguous ownership events remain portal-visible without such email. The shared notifier and admin-authored shipment-event route check persisted build/product channel evidence and suppress order-linked eBay sales. Build-only admin events never trigger off-platform email. Admin-authored direct-order events receive a stable event ID, enqueue the durable notifier after commit, and are picked up by the bounded retry worker if the process stops before delivery. Dispatch-prefixed events remain owned by the dispatch retry worker and are not double-sent. |
| GR-117 | An eBay/Vinted/other marketplace sale detected from email remains build-scoped. The monitor may record the buyer email for claim matching, but it never creates a customer account, links an existing account by email alone, generates a password, or emails credentials/portal links. The dispatch claim is the existing private printed QR flow. |
| GR-118 | Every delivered build sale reserves at least 5% of its sale value. Missing, zero, or lower-than-5% legacy/configured rates resolve to 5%; higher finite rates remain supported up to 25%; non-finite rates are rejected. Data-backed pricing calibration uses historical warranty claim cost divided by historical sale value, and never recommends below 5%. |
| GR-119 | The admin price bridge calculates the displayed warranty reserve from expected sale price (not component cost), and the protected price floor accounts for marketplace fees plus the sale-based warranty percentage. Insurance requoting updates base costs and recomputes the same floor formula. |
| GR-120 | A Parcel2Go stage timestamp is normalized to UTC and used for the tracking event and warranty start only when valid and not in the future. Malformed or future stage timestamps fall back to webhook receipt time, so a delayed or bad carrier clock cannot postpone warranty activation. |
| GR-121 | A 12-month reserve expiry preserves the delivery time of day and handles a 29 February start by expiring on 28 February the following year, without date arithmetic failure. |
| GR-122 | The customer-safe software Playbook table's recommended app names and saved-time totals match the runtime use-case profiles and current per-app minute estimates, including the general-purpose fallback. |
| GR-123 | Manual-build warranty reserves use only a positive confirmed actual sale price, never a channel listing price. If the sale price is missing at delivery, the delivery timeline and warranty start still persist, reserve creation is deferred, and one actionable admin alert is recorded. Recording the actual price later through eBay order sync/reconciliation creates or updates the reserve to at least 5%; a mismatch discovered after release raises a critical reconciliation alert. Marketplace email parsing with a missing or invalid amount does not copy the listing price into the actual sale field. |
| GR-124 | Ready-to-Ship and Curated-for-you recommendation explanations reach the customer both inline and in Hermes. Ready-to-Ship copy identifies only a saved Playbook assignment and directs the customer to exact specifications/measured results; it must not claim a performance match without reviewed evidence. Curated advice reflects the selected workload, answers, budget, authored cell/use and price state, including honest above-budget or lower-tier caveats. The Hermes event queue delivers advice even when the chat widget mounts later and suppresses duplicate keys. Made-by-you GPU-spend advice continues to work through the same event path. |
| GR-125 | The customer build portal warranty panel clearly distinguishes `not_started`, `active`, and `expired` commercial warranty states, shows recorded delivery/expiry dates when available, links to the warranty policy, and always preserves the statutory-rights clarification. Invalid or absent dates must not crash rendering or be presented as a valid coverage date. |
| GR-126 | If delivery and the warranty start are recorded for a marketplace/manual build while reserve creation is deferred because the confirmed sale price is missing, the customer portal still shows the warranty as active from delivery with the correct 12-month expiry. Reserve reconciliation later must not reset the customer-facing start date. |
| GR-127 | Marketplace email detection, eBay order reconciliation, and manual eBay order sync ensure a missing Getting Ready job exists for the sold physical build. Repeated or concurrent sale processing creates one job, keeps the job build-scoped with no account linked from marketplace data, preserves the Playbook software defaults, and uses the existing Ready-to-Ship status/checklist contract. |
| GR-128 | When a reviewed customer package is available, both authenticated account and one-build guest portals expose its ZIP and only allow-listed customer document links. Guest links use guest-scoped endpoints; account links remain order-scoped. Individual links resolve the expected filename/media type, exclude workshop scripts and internal checklists, and update to the latest reviewed package version. |
| GR-129 | Manifest validation emits one driver/firmware review row and one manufacturer-manual row for every distinct exact component model, even when the LLM omits rows. A missing manual uses `needs_research`; missing approved driver research is stated in its review reason. Existing exact, admin-reviewed sources are retained in deterministic fallback rows. Administrator approval stays required, duplicate identical parts share one model-level row, and exact source binding plus unsupported/partial-name rejection continue to apply. |
| GR-130 | Customer package approval is rejected until an administrator completes the component-manual review action with an audit note. The action cannot be waived as `not_required`, is reset when the manifest is regenerated, and blocks courier booking/dispatch readiness until recorded. The admin UI exposes the action and the standalone dispatch checklist calls it out. |
| GR-131 | Completing the manual-review action and approving a package both compare stored manifest coverage against the current build specification by exact component model and representative component ID. A stale/partial/mismatched manifest or a build with no recorded components cannot pass the manual gate; repeated identical models require only one review row. |
| GR-132 | The guest customer portal renders the reviewed build-pack download and the individually allow-listed plaque and Getting Started guide links supplied by its scoped portal response, alongside warranty status. |
| GR-133 | Completing driver/firmware review is rejected when the current manifest omits any distinct exact component model or uses a non-representative component ID. Driver/update installation cannot be marked complete until that review gate is complete. Regenerating a manifest resets both driver gates and retires any previously reviewed customer/workshop package from active download routes. Repeated identical models require one review row; the action cannot be waived. |
| GR-134 | Driver/firmware review completion requires one structured operator outcome per distinct exact model. An installed update must cite an exact administrator-approved source for that model; a no-update outcome requires an explanatory note. Persisted outcomes include reviewer and time, appear in the admin review UI, and are revalidated before driver installation completion. Missing, duplicate, stale, mismatched, unsupported-source or unapproved-source outcomes are rejected. |
| GR-135 | Authenticated and guest customer portal responses expose only the allow-listed Getting Ready status, confirmed customer-facing AI purchase summaries, approved customer-document index and reviewed package details. They never include the raw internal manifest, driver/manual review items, approved research records, operator outcomes, drive serials, audit metadata, pending AI purchases, Stripe PaymentIntent IDs or client secrets. |
| GR-136 | The authenticated admin shipment-evidence download resolves only within the requested build's private directory, opens the file once, verifies its recorded byte count and SHA-256 on that handle, and streams from the same handle. Cross-build storage keys and path replacement are rejected/cannot swap the response. Missing files return not found; malformed metadata or changed files are rejected without streaming bytes. Tampered evidence must be re-uploaded and reviewed. |
| GR-137 | The generic admin order-status endpoint rejects `completed` when no confirmed `delivered_at` exists; it does not set a delivery timestamp, create a warranty reserve, or change the order status. Authenticated carrier/operator delivery events retain their supplied valid occurrence time and remain the delivery transition that starts the warranty clock. |
| GR-138 | A build-scoped shipment event is rejected if an orchestration Build or sold Product links that physical build to an Order. The conflict response identifies the order to use; no event or second build-owned reserve is created. Conflicting order links are rejected for manual reconciliation. Marketplace/manual sales without an order continue to use the build-owned timeline and reserve. |
| GR-139 | The authenticated operator shipment-event action rejects a delivered/delivery-confirmed/proof-of-delivery event whose normalized UTC occurrence time is in the future. No tracking event, completed order state, delivery timestamp, warranty reserve or customer notification is created. Parcel2Go's provider adapter separately retains the documented receipt-time fallback before normalizing its events. |
| GR-140 | After an insurer returns a created-policy response, the API links it as dispatch-valid only when a usable policy ID exists, provider mode is `production`, currency is GBP, and insured value and premium match the confirmed sale and fresh quote to the penny. A mismatch remains dispatch-blocking and stores only a redacted provider-response summary for reconciliation. Reconciliation must match the originally returned policy ID, production mode and recorded values; when the original response omits or has an unusable policy ID, an operator-entered ID cannot be attached as a substitute. It cannot attach another policy or accept a non-GBP/mismatched insured amount. Insurer raw error payloads and customer fields never appear in application logs. |
| GR-141 | After a provider-created policy mismatch, the authenticated Dispatch Centre queue exposes only an allow-listed reconciliation summary (policy/invoice references, insured value, premium, currency, mode, receipt time and mismatch reasons). The admin UI shows it after reload and pre-fills reconciliation suggestions while still requiring the operator to check the provider account and confirm all values. Raw provider responses, credentials and unrelated buyer fields are not included in this summary. |
| GR-142 | When normalized delivered events are recorded against an order linked to a physical ManualBuild, concurrent/out-of-order events preserve the same earliest confirmed delivery time on the order and linked build, the build dispatch state becomes `delivered`, and the single order-owned warranty reserve uses that time. Admin completion of an order with an existing delivery timestamp also reconciles the linked build. No duplicate build-owned reserve is created. Existing marketplace/manual deliveries without an Order remain build-owned. |
| GR-143 | Account and claimed-guest portal Getting Ready summaries show only submitted allow-listed software choices as names/categories, with the indicative saved-time estimate and basis. Unsubmitted selections are clearly pending; no internal manifest, install script, research record or operator note is exposed, and guest write permissions remain unchanged. |
| GR-144 | Physical handover is terminal for build name/component edits and archiving/inventory release, collection scheduling, Getting Ready manifest/package generation, Windows licence/software script release, evidence/checklist mutation, new paid courier booking, shipment-booking reconciliation, and insurance-policy reconciliation. The API exposes only a safe handover boolean to Dispatch Centre, which disables preparation, upload, review, purchase and repeat-dispatch controls while retaining evidence downloads and allowed portal access. The guard recognizes both `dispatched` and `delivered`, a recorded delivery time, or confirmed handover evidence, so a stale/reset dispatch status cannot reopen the workflow. Existing saved courier bookings return without writes or new provider calls; delivery state and warranty timestamps are preserved; repeat dispatch does not create another tracking event or customer notification. |
| GR-145 | A direct generic component edit to a sold build is rejected before persistence, even before physical handover; the saved component snapshot remains unchanged. Draft/in-progress build editing retains its existing behavior. |
| GR-146 | An authenticated order owner can create one pre-components-order change request for a made-to-order build. It is persisted and pauses both order-status sourcing transitions until the customer withdraws/declines or a reviewed change is fully settled and implemented. Ready-to-Ship orders and orders already at/after Components Ordered reject the request. Admin quotes must include revised specs, customer price and customer-facing explanation; internal notes are never returned in the owner portal. While settlement/application is unimplemented, quote acceptance is rejected by the API and never mutates the paid order or unpauses sourcing. |
| GR-147 | The account portal lets the owner submit/withdraw a pre-sourcing change request, shows the hold/status and proposed quote without leaking internal notes, and lets the customer decline a quote and retain the original build. It does not present an unimplemented repricing/payment path as complete. Admin order detail can review, quote or decline the request; quoting does not mutate the paid order. Verify validation errors, duplicate requests, cancellation overlap, Ready-to-Ship rejection and status-transition holds. |
| GR-148 | Parcel2Go quote parsing omits malformed rows, rows without a non-empty bounded service slug, and zero, negative, NaN, infinite or nonnumeric prices. Valid positive finite quotes remain price-sorted and selectable. Booking still obtains a fresh quote and requires the live-purchase confirmation before calling create/pay endpoints. |
| GR-149 | Courier quote requests ask for Parcel2Go's `Signature` extra and exclude any returned service quote that does not show it included; the shown total includes the extra. Order creation sends the same extra under `Upsells`. Before payment, the API requires the created unpaid order's finite positive GBP total to match the confirmed quote to the penny; missing/mismatched totals enter reconciliation and never call payment. Insurance and dispatch reject bookings without recorded signature-extra evidence. |
| GR-150 | The generated order-specific portal leaflet is a two-page A5 PDF. Page one contains the live guest-claim or account sign-in QR and the correct customer instruction; page two explains build documents, delivery tracking, getting-started materials and aftercare. Both pages use safe customer copy, and the ZIP includes the PDF only in the customer-document allow-list. The standalone checklist still requires printing and scan-checking the actual order leaflet. |
| GR-151 | Curated Playbook definitions contain exactly one cell for each of the eight canonical customer types at each of Budget, Mid-range and High-end (24 unique cells). No renamed, missing, duplicate or unexpected segment/tier pair is allowed. Authored software profiles resolve only for a matching segment/cell; cells without a reviewed cell override use the matching use-case default, not an unknown-segment fallback. |
| GR-152 | Parcel2Go authentication, quote, order-create and payment failures do not log or return raw provider response bodies. Errors retain safe status/reference details, while the booking route preserves its retryable versus reconciliation-required state behavior. A provider error body containing buyer name, address, email, client credentials or tracking data must not appear in logs or API errors. Successful booking logs contain only tracking/label presence flags, and the raw provider response is not retained after its required fields are parsed. |
| GR-153 | When an admin confirms physical handover after a Parcel2Go booking, the persisted dispatched event carries the provider's bounded credential-free HTTPS tracking URL into the customer portal timeline and direct-customer notification. Older events without a link fall back to the validated URL saved with the booking. HTTP, malformed, credential-bearing or overlong URLs are omitted. |
| GR-154 | Customer portal serialization revalidates stored tracking and live-map URLs, including legacy events, and emits only bounded credential-free HTTPS links. Unsafe values are returned as null and cannot become customer-clickable links. |
| GR-155 | Warranty repair portal summaries, return/replacement shipment details and their event timelines all enforce the same bounded, credential-free HTTPS URL rule, including legacy values. Unsafe values are suppressed without hiding safe status history. |
| GR-156 | The admin Getting Started guide endpoint accepts only non-empty UTF-8 `.md`/`.txt` files of at most 1 MB, atomically replaces the configured guide, strips a UTF-8 BOM, and returns metadata whose SHA-256 and byte count match the persisted normalized file. Invalid extension, encoding, empty content and oversize uploads fail without replacing a prior guide. |
| GR-157 | Configured, request-supplied and generated-intro Getting Started guides share one normalization rule and source priority; persisted source metadata hashes the exact normalized UTF-8 text copied into the package source snapshot. The generic guide remains excluded from the LLM prompt. Empty generated fallback fails before evidence persistence. |
| GR-158 | During package assembly, guide text with recorded provenance must have an allowed source and match the saved SHA-256 after the same UTF-8 newline normalization used for the archive; changed snapshots fail before ZIP creation. Legacy manifests without a guide hash remain packageable. |
| GR-159 | Checkout and webhook recovery preserve the selected curated cell ID with the server-resolved software profile. If a legacy order has no profile snapshot, Getting Started options reconstruct the authored Made-by-you customer-type × tier or Curated cell profile before falling back to the Playbook-level default. |

ZIP tests inspect entries, checksums, MIME types, path traversal protection, size limits and provenance. Manual/driver research uses approved fixture documents in CI; current manufacturer-source discovery belongs in an opt-in integration test and always requires human review.

## 12. Email, portal and support

### 12.1 Automated emails

- Verify recipient rules, trigger, subject, rendered text/HTML, policy links, portal link, unsubscribe where applicable and absence of secrets.
- Cover verification, claim invitation, payment, approval/substitution, component/order milestones, cancellation/refund, dispatch, delay, delivery, return, insurance claim, warranty case and resolution.
- Use an outbox/idempotency key so transaction retry or duplicate webhook sends once.
- Bounce, suppression, provider timeout and retry are visible to admin without rolling back the business transaction.
- Indirect-channel communications obey channel-specific restrictions.

### 12.2 Personalized build portal

- Timeline, specification, benchmarks, documents, tracking, warranty dates and cases derive from the correct build.
- Pre-sale Ready-to-Ship evidence survives ownership linking.
- Curated/Made-by-you sections appear only when their lifecycle data exists.
- Delivered starts warranty; expiry display uses the recorded date; an open claim is not hidden at expiry.
- Authorization tests enumerate object IDs, guessed URLs, expired claim links and account changes.

### 12.3 Support and chatbot

- Customer-safe knowledge base outranks PRDs and includes source/version in answers.
- Order-specific answers require authentication and current order data.
- The bot does not invent stock, prices, dates, warranty outcomes or legal conclusions.
- Escalation covers ambiguous policy, safety issue, payment dispute, vulnerability, complaint, insurance claim and vulnerable customer.
- Recommendation interventions use current Playbook evidence and preserve customer agency; validate the Made-by-you optional-GPU explanation against the approved knowledge-base version, ensure it never claims the build changed automatically, and keep curated specifications fixed.

## 13. Non-functional coverage

### Security and privacy

- Role/ownership authorization, CSRF where relevant, rate limits, upload validation, SSRF/path traversal, stored/reflected XSS and webhook signatures.
- Secret and personal-data scanning across logs, generated ZIPs, browser storage, analytics and failure artifacts.
- Account claim tokens are single-use, limited to at most 400 days, hashed at rest and invalidated after use.
- Retention/deletion handles portals, media evidence and legally retained transaction records correctly.

### Accessibility and responsive UI

- Automated axe checks on critical pages plus keyboard/focus/manual screen-reader checklist.
- Desktop and mobile Playwright coverage for the storefront journeys, customer portal and core admin operational pages.
- Loading, empty, error, retry, offline and expired-session states.

### Resilience and performance

- Timeouts, retries with backoff, circuit behavior, worker restart/resume and poison-message handling.
- Concurrent reservation/sale, duplicate webhook/event and scheduler overlap tests.
- Budgets for core catalogue/recommendation APIs and customer page performance using stable seeded data; regressions reported rather than hidden by retries.

### Migration and compatibility

- Upgrade a representative previous schema to head and verify important existing records.
- New code works during the intended rolling-deployment window where applicable.
- Extension DEV/LIVE builds carry exact source attribution and API schema compatibility.

## 14. Execution sequence

### Phase A — baseline and gap report

1. Record git commits/dirty state and environment without exposing secrets.
2. Inventory existing tests against the IDs above; identify duplicates, false positives and tests that hit the network.
3. Run existing suites unchanged in isolated environments to establish an honest baseline.
4. Publish failures as product defects, test defects, environment gaps or external blockers. Do not weaken assertions to turn the baseline green.

### Phase B — foundations

1. Add test markers/tags, shared factories, fake clock and network deny-by-default.
2. Add ephemeral PostgreSQL migration fixture, provider simulators, email sink and common evidence reporting.
3. Add OpenAPI/consumer contracts across all three repositories.
4. Make each repository expose stable `test:unit`, `test:integration`, `test:e2e` and report commands as appropriate.

### Phase C — critical commerce and lifecycle

Implement in this priority:

1. payments, inventory exclusivity and state-machine invariants;
2. Ready-to-Ship end to end;
3. Curated-for-you end to end;
4. Made-by-you end to end;
5. cancellation, return, courier claim and warranty repair;
6. portal ownership and email delivery.

### Phase D — sourcing, listings and operations

Implement extension-to-catalogue contracts, delivery/Prime rules, flip components, listing/cross-list/re-list, reconciliation, Getting Ready, dispatch and evidence gates.

### Phase E — growth and support systems

Implement marketing machine, advertising, blog, social factory, analytics and chatbot suites with publishing/spend disabled in normal CI.

### Phase F — sandbox and release evidence

Run approved sandbox suites provider by provider. Live read-only canaries require a separate checklist and explicit approval; any action capable of spending, publishing, messaging, booking, insuring or changing production data remains outside automated live canaries.

## 15. Quality gates

A capability is release-ready only when:

- its critical happy path and material failure paths pass at the appropriate layers;
- state, money, authorization, idempotency and audit assertions pass;
- no critical/high unresolved defect remains;
- no required scenario is satisfied by a skipped test;
- changed deterministic business logic has at least 85% branch coverage, while critical state/financial rules cover every defined branch;
- frontend critical routes have keyboard/accessibility and mobile/desktop evidence;
- provider claims state whether they were fake, sandbox or live;
- migrations pass from a representative prior schema;
- artifacts and reports identify exact commits and are retained outside source directories.

Repository-wide percentage alone is not a release gate because it can conceal untested critical workflows.

## 16. Deliverables

After implementation and execution:

1. requirement-to-test traceability matrix;
2. deterministic seed/factory and provider simulator package;
3. expanded Pytest/Vitest/component suites;
4. customer, admin and cross-application Playwright projects;
5. extension lifecycle/contract harness;
6. CI profiles and network/production safety guards;
7. baseline and final reports with defects, skipped/gated capabilities and provider evidence;
8. concise runbook for local, CI, sandbox and release testing.

## 17. Decisions embedded in this plan

- PostgreSQL is the integration truth; SQLite is not migration evidence.
- The primary end-to-end suite is local and deterministic. Third-party sandboxes validate adapters separately.
- No normal automated suite can publish, spend, charge, book, insure or message externally.
- LLM outputs are tested against schemas, grounding and safety properties; exact prose snapshots are avoided.
- Planned functionality is recorded as skipped specification rather than misrepresented as working.
- The physical Windows installation and firmware/BIOS actions require a separate supervised hardware acceptance checklist; CI tests generation and safeguards only.
