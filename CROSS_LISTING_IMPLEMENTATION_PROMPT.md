# Codex implementation prompt: Cross-listing admin tool

You are working in the FlipFlop repository (`C:\Users\mclar\CODING\FlipFlop`). Build a production-ready **Cross-listing** feature in the existing `flipflop-admin` Next.js 16 application.

## Objective

Add a new admin menu item called **Cross-listing**. It must retrieve the user’s current listings from:

- eBay UK
- FlipFlop.shop/direct website

The user must be able to select one or many source listings, choose one or many destination platforms, review and edit platform-specific listing data, then publish or prepare the listings for:

- eBay UK
- FlipFlop.shop
- OnBuy
- Amazon
- Facebook Marketplace
- Vinted

This is also a **sales-monitoring and inventory-synchronisation system**, not merely a listing copier. It must monitor sales across every connected selling channel and react quickly when a unique pre-built computer sells.

For a confirmed sale, it must also start the fulfilment workflow: import the buyer/order details, create or match the customer in the admin app, create the order, associate it with the build’s customer portal, book insured delivery and book a collection from the configured home/dispatch address for the next business day where the selected courier supports that service.

The feature must be honest about integration capability. Do not create fake “published” results, mock URLs, or pretend that a platform API exists. Before implementation, verify the current official seller/API capabilities and document any platform limitation. Where direct API publishing is unavailable or not permitted, provide a compliant manual-assist/export workflow with clear status such as `manual_action_required`.

## Repository context to preserve

- Frontend: `flipflop-admin`, Next.js App Router, React 19, TypeScript, Tailwind CSS v4, Radix UI, Lucide icons, TanStack Query, Vitest and Playwright.
- Existing navigation is in `flipflop-admin/components/sidebar.tsx`.
- Existing admin layout is in `flipflop-admin/app/layout.tsx`.
- Existing shared types are in `flipflop-admin/lib/types.ts`.
- Existing API client patterns are in `flipflop-admin/lib/api.ts` and `flipflop-admin/lib/admin-api.ts`.
- Existing build selling UI is `flipflop-admin/app/builds/[id]/sell/page.tsx`.
- Existing build publish route is `flipflop-admin/app/api/builds/[id]/publish/route.ts`; it currently has eBay/FlipFlop.shop handling and TODO/mock behaviour that must not be copied into the new production workflow.
- Existing build detail page contains eBay and storefront listing state, generated listing copy, pricing, photos, FAQs, specifications, and publish status.
- Existing backend/proxy patterns must be followed. Keep provider credentials server-side and reuse existing authentication/session protection.
- Read `flipflop-admin/AGENTS.md` and the relevant Next.js guidance in `flipflop-admin/node_modules/next/dist/docs/` before editing code.

## First task: inspect and report

Before coding:

1. Inspect the existing admin routes, sidebar, build/listing models, database/backend endpoints, eBay OAuth/publish code, storefront publish code, environment variables, and tests.
2. Identify the canonical source of truth for a product/build and the canonical source of truth for each live channel listing.
3. Check official current documentation for eBay, OnBuy, Amazon Selling Partner API, Meta/Facebook Commerce, and Vinted. Use only supported official APIs or explicitly compliant browser/manual workflows. Do not scrape authenticated sites, bypass anti-bot controls, or automate personal-account Facebook/Vinted actions in violation of platform rules.
4. Write a short implementation note describing what can be fully automated, what requires seller approval/OAuth, and what must be manual-assist/export only.
5. Then implement the feature; do not stop at a plan.

## Functional requirements

### Navigation and page

- Add a clearly active **Cross-listing** item to the existing sidebar.
- Add route `flipflop-admin/app/cross-listing/page.tsx` or the repository’s established equivalent.
- Match the existing FlipFlop visual language: dark admin UI, existing spacing, cards, badges, toast patterns, responsive layout, keyboard accessibility.
- Do not redesign unrelated pages.

### Source listing retrieval

- Load current listings from eBay UK and FlipFlop.shop/direct website through server-side API routes or existing backend APIs.
- Provide a `Refresh listings` action, loading state, empty state, partial-failure state, retry action, and last-refreshed time.
- Show source platform, external ID, title, image, price, stock/quantity, condition, live status, URL, last updated time, and associated FlipFlop build/product when available.
- Deduplicate listings by canonical product/build and channel listing identity. Never silently merge two different products.
- Support search, filters by source/status, sorting, pagination or virtualisation for large inventories, and select-all on the current filtered result set.
- Make clear whether a row is live, ended, sold, draft, unavailable, or failed to retrieve.

### Selection and destination workflow

- Allow selecting multiple source listings.
- Allow selecting multiple destination platforms independently for each source listing or for the whole batch.
- Prevent invalid combinations and explain why, for example a destination already has a live listing for the same product.
- Show a batch summary before proceeding: source count, destination count, total jobs, warnings, estimated fees if known, and manual actions required.
- Make the workflow resumable. A failed platform must not erase successful results on other platforms.
- Require explicit confirmation immediately before any external publish/update action.

### Listing normalisation and per-platform mapping

Create a canonical internal listing model that can represent:

- product/build ID and SKU
- title, subtitle, description, bullet points and FAQs
- price, currency, tax treatment, quantity and condition
- images, image order, alt text and image-hosting URLs
- category and platform category ID
- brand, manufacturer, model, MPN, GTIN/EAN/UPC where applicable
- CPU, GPU, RAM, storage, motherboard, PSU, case, OS and other PC specifications
- warranty, returns, dispatch time, shipping methods, collection availability and location
- platform-specific item specifics/attributes
- channel listing ID, URL, status, error, last sync time and last successful payload hash

Implement platform adapters/mappers rather than putting platform conditionals throughout React components. Each adapter should expose a consistent contract such as:

- `capabilities()`
- `validateListing()`
- `previewListing()`
- `publishListing()`
- `updateListing()`
- `endListing()` where supported
- `getListingStatus()`
- `mapError()`

The canonical model remains the source of truth for shared content, while platform overrides are stored separately and never overwrite the canonical data accidentally.

### Content copied to every channel

- When a listing is cross-listed, copy the source listing’s photos, photo order, title, description, bullet points, FAQs, specifications, warranty text, price, stock and shipping information into the destination payload wherever that platform supports the field.
- Preserve the original source content in the canonical product record. Platform-specific transformations may resize/reorder images, truncate titles, convert formatting or map fields, but must not destroy the original.
- Show exactly what was copied, transformed, omitted or requires manual editing for each destination.
- Keep content synchronised on update: when the canonical title, description, photos, price or stock changes, identify affected channel listings and offer/update them through the supported adapter. Record whether each channel was updated successfully.
- Do not copy an image by hotlinking a private/local URL. Use an approved public asset URL or a secure provider upload flow and verify that the resulting image is reachable.

### Review and edit UI

- Before publishing, show a per-platform preview/editor for every selected destination.
- Display required, recommended, invalid and platform-specific fields.
- Support editing one listing or applying a safe field change to the batch.
- Show character counts and platform limits where known.
- Validate prices, currency, quantity, image URLs, required attributes, condition, delivery, returns, warranty, legal text and category requirements.
- Show a diff between the source listing and the proposed destination payload.
- Allow saving a draft without publishing.
- Allow downloading/copying a manual listing pack for unsupported platforms, including title, description, images, specs, price, URL and step-by-step manual instructions.

### Publishing and synchronisation

- Use idempotency keys for every publish/update job.
- Persist job, item and destination statuses. Suggested statuses: `draft`, `queued`, `validating`, `ready`, `publishing`, `published`, `updated`, `manual_action_required`, `failed`, `cancelled`.
- Use a durable job pattern if the backend supports it; do not rely on a browser tab staying open for long batches.
- Show live or pollable progress with per-item/per-platform results.
- Retry only safe transient failures, with exponential backoff and a retry limit.
- Never automatically retry validation errors or duplicate-listing conflicts.
- Store provider request IDs and sanitised error details for diagnostics.
- On success, persist the external listing ID, canonical URL, status and timestamp.
- Provide `View live listing`, `Retry`, `Edit draft`, `Download manual pack`, and, only where supported, `Update`/`End listing` actions.
- Add a reconciliation/refresh action to compare local status with each platform.

### Sales monitoring across all channels

This is a critical requirement and must be implemented as a durable backend capability, not only as a browser-page feature.

- Monitor sales/orders across every connected channel: eBay UK, FlipFlop.shop, OnBuy, Amazon, Facebook/Meta commerce route and Vinted where an official supported integration exists.
- Prefer official order APIs and webhooks. Where a provider has no usable webhook, use its official order API on a scheduled polling interval with provider-specific rate limits and a stored cursor/last-seen timestamp.
- Also support a secure email-monitoring fallback for sales notifications sent to `mac@theflipflop.shop` when a channel does not offer a usable API. Do not scrape arbitrary inboxes or store the mailbox password in the frontend. Use an approved IMAP/OAuth/app-password mechanism, server-side secret storage, sender/message validation, idempotent message processing and a processed-message audit record.
- Parse email only from configured/verified sender addresses and known templates. Treat email content as untrusted input; never execute links or instructions from an email.
- Normalise every sale into one internal sale/order event with channel, external order ID, external listing ID, canonical product/build ID, sale price, quantity, timestamp, buyer/shipping details only where necessary, and evidence/source.
- Deduplicate events by channel + external order/event ID and by a deterministic fallback fingerprint for email events. Reprocessing the same webhook, poll result or email must be safe.
- Reconcile API, webhook and email evidence when more than one source reports the same sale. Do not create duplicate orders or send repeated notifications.

### Sale reaction for unique pre-built PCs

For a unique pre-built computer, once a sale is confirmed on any channel:

1. Mark the canonical build/product as sold and unavailable in the backend.
2. Mark the sale platform, sale/order reference, sale time and realised sale price.
3. Mark the complete computer and every installed component in the inventory system as allocated/sold, preserving serial numbers and the audit trail. Do not mark unrelated spare components as sold.
4. Locate all equivalent live/draft listings on the other connected platforms by canonical product/build identity, SKU, channel listing ID and safe matching rules.
5. End/deactivate/cancel those equivalent listings through official APIs where supported. If a channel is manual-only, create a high-priority manual delist task and include the direct listing link/instructions.
6. If a delist fails, retry safe transient failures and prominently show the remaining live listing so the user can act immediately.
7. Prevent a second sale race by using a backend transaction/lock or equivalent idempotent state transition before attempting downstream delists.
8. Record a complete audit event showing the triggering sale, inventory changes, delist attempts/results and any manual actions still required.

### Customer, order and build-portal fulfilment

After a sale is confirmed, import only the information needed to fulfil and support the order, including where supplied by the channel:

- buyer/customer ID and channel username
- full name
- email address and telephone number
- delivery address and billing address where required
- price paid, currency, tax/shipping amount and discount information
- channel order ID, transaction ID where necessary, listing ID and sale timestamp
- delivery/service selection and any buyer notes

Implement this as an idempotent workflow:

1. Match an existing admin customer using verified channel identity and/or email according to a safe matching policy. Never merge customers solely on an unverified name or address.
2. If no safe match exists, create a new customer in the admin app with the imported details and source-channel identity.
3. Create the customer order and associate it with the canonical FlipFlop build/product, sale event, inventory allocation and channel listing.
4. Prevent duplicate customers and duplicate orders when the same sale is received through a webhook, polling API and/or the `mac@theflipflop.shop` email monitor.
5. Trigger or create the associated user portal for the build. Associate the new/existing customer with that portal and make the portal personalised for the customer, including customer name, build name/specification, order status, relevant photos, warranty/returns information, delivery status and safe support/contact options.
6. Do not expose internal costs, seller notes, other customers’ data, private inventory metadata or provider credentials in the customer portal.
7. Record consent, source, imported fields, changes and audit history for customer/order data. Make personal-data access and deletion/export considerations explicit.

Use the existing order/customer/portal models and API conventions where they exist; inspect them before adding duplicate concepts. If a required backend model does not exist, add a migration and typed API rather than storing fulfilment state only in React/local storage.

### Delivery insurance, booking and collection

- Add a courier/shipping adapter layer with a consistent contract for rate/service lookup, insurance options, shipment/label creation, collection booking, cancellation, tracking lookup and delivery-event normalisation.
- Use the customer’s imported delivery address as the shipment destination and the configured FlipFlop home/dispatch address as the collection address. Never infer the collection address from the customer record.
- Book delivery with insurance appropriate to the confirmed sale value, show the insured amount and any excess/limitations, and require admin confirmation if the courier cannot insure the full value.
- Book collection for the next business day by default, using the courier’s real available service/date and the correct parcel dimensions, weight, declared value and packaging requirements. If next-business-day collection is unavailable, show the earliest available date and require explicit confirmation or create a manual-action task.
- Address the shipment to the newly created/matched customer and persist the recipient, service, collection date/window, insurance, tracking ID, courier, label URL and booking/reference ID.
- Update the admin order with delivery tracking ID, courier, delivery service, insured value, collection date/window, fulfilment status and all relevant timestamps.
- Notify the customer through the existing approved communication mechanism only after the booking is confirmed, and include tracking information appropriate for customer visibility.
- Support booking failure, cancellation, rescheduling, label generation failure, address validation failure, courier outage and partial success without losing the order or sale record.
- Never silently book a shipment, charge a delivery account or create an insurance commitment without an explicit user-approved fulfilment action unless the user has configured an account-level automation setting for that exact behaviour.
- Make the delivery workflow auditable and idempotent. A retry must not create a second shipment or collection; use provider idempotency keys and stored booking references.
- If no courier API/connector is available, create a manual fulfilment pack and a prominent admin task containing the exact customer address, parcel data, insured value, collection address, next-business-day target and order reference. Do not claim the delivery is booked.

Do not end listings merely because a sale email is ambiguous. Require a confidently matched canonical product/build and a confirmed sale event, otherwise flag it for admin review.

### Admin sale notifications and confetti

- Create a durable admin notification for every confirmed sale and important downstream result, including: platform sold on, product/build, sale price, inventory updated, listings ended, failures and manual actions required.
- Also notify the admin app as fulfilment progresses: customer created/matched, order created, portal associated/personalised, delivery insurance selected, shipment booked, collection booked, tracking received, and any manual action or failure.
- Notifications must survive page reloads and be stored server-side with `unread`, `read_at`, severity, type, related sale/job IDs and timestamps.
- Show an in-app notification/toast immediately when the app is open, with a notification centre/badge and a detail view.
- For a confirmed successful sale of a pre-built PC, trigger celebratory confetti across the admin screen. Confetti must continue or re-trigger at a controlled, accessible rate until the specific sale notification is marked as read, then stop immediately.
- Respect reduced-motion preferences: replace or minimise confetti for users who prefer reduced motion while still showing the persistent notification.
- Marking a notification read must be an explicit, authenticated server-side action and must be idempotent across multiple open tabs.
- Avoid duplicate confetti/notifications when the same sale event is received through both API and email.

### Inventory and overselling protection

- Treat quantity as shared inventory when the product/build is cross-listed.
- Define and implement a safe stock policy, preferably reserve/decrement/reconcile through the backend.
- Do not publish the same unique PC to several channels with quantity greater than one unless explicitly configured.
- Clearly warn before publishing a unique item to multiple destinations.
- Design webhook/order-event handling where provider APIs support it; otherwise provide scheduled reconciliation and document the limitation.
- Add automated tests for the sale-confirmation transaction, equivalent-listing delisting, component inventory updates, duplicate-event handling and notification read/confetti lifecycle.

### Credentials and settings

- Add or reuse a secure integrations/settings area for connecting eBay, OnBuy, Amazon, Meta, Vinted and any direct website integration.
- Use OAuth where required. Never expose client secrets or refresh tokens to the browser, logs, error messages or client bundles.
- Encrypt tokens at rest using the project’s existing secret-management approach.
- Include connection state, account/store identity, scopes, token expiry, reconnect, disconnect and test-connection actions.
- Make platform availability visible: `connected`, `not connected`, `requires approval`, `manual only`, or `temporarily unavailable`.
- Use environment variables only for server-side configuration and document every new variable without committing secrets.

## Platform-specific expectations

- **eBay UK:** Reuse the existing production OAuth/account configuration and established listing policies. Support create/update/status retrieval where the current eBay integration permits it. Do not create a second competing eBay credential flow.
- **FlipFlop.shop:** Use the direct website’s canonical product/build and publish/update mechanisms. Avoid creating duplicate storefront products; link the cross-listing record to the existing product.
- **OnBuy:** Investigate official seller API/feed requirements, category/product identifiers, stock, price, delivery and returns. If onboarding/API approval is needed, implement connection state and a manual/export fallback.
- **Amazon:** Investigate SP-API roles, marketplace IDs, listings requirements, product identifiers, condition, category approval, fulfilment and pricing. Do not assume a simple product-post endpoint. Surface approval and identifier requirements clearly.
- **Facebook Marketplace:** Verify whether the intended business/catalog route supports these products and listing creation. Do not automate personal Marketplace posting or use prohibited scraping. If only catalog/feed/manual workflows are supported, implement those or a manual listing pack and label it accurately.
- **Vinted:** Verify whether a supported business/pro seller API or approved integration exists for the intended region and product type. Do not automate consumer-account posting or scraping. If unsupported, provide a compliant manual-assist export only.

## Suggested data model

Adapt names to the existing backend/database conventions, but introduce equivalent durable records:

- `channel_connections`
- `canonical_products` or a link to the existing build/product table
- `channel_listings`
- `channel_listing_overrides`
- `cross_listing_batches`
- `cross_listing_jobs`
- `cross_listing_job_events`
- `customers` or the existing customer/user table
- `customer_channel_identities`
- `customer_orders` or the existing order table
- `build_portal_associations`
- `shipments`
- `delivery_bookings`
- `collection_bookings`
- `admin_notifications`

Important constraints:

- unique `(canonical_product_id, channel, account_id)` where appropriate
- unique provider listing IDs per channel/account
- immutable audit events for publish, update, end, retry and manual completion
- immutable audit events for customer import/match, order creation, portal personalisation, shipment/insurance booking and collection booking
- encrypted credentials and redacted payload/error logging
- encrypted or appropriately protected PII, least-privilege access, retention/deletion rules and no PII in ordinary logs
- timestamps in UTC
- optimistic locking or version checks to avoid stale overwrites

## API design expectations

Use the existing Next.js proxy/backend architecture and authentication. Add typed endpoints for at least:

- list source listings
- refresh/reconcile source listings
- list channel connections/capabilities
- get monitored sales/orders and reconciliation status
- receive/process provider webhooks where supported
- run/poll email sales monitoring securely where configured
- list unread notifications and mark a notification read
- trigger/reconcile the sold-product cross-channel delist workflow
- create/match a customer from a confirmed sale
- create and retrieve the associated customer order
- associate and personalise the build user portal
- validate delivery address and parcel data
- get delivery rates/insurance options
- confirm/cancel/reschedule shipment and collection bookings
- receive/poll courier delivery and collection events
- update order tracking and fulfilment status
- validate a cross-listing batch
- save a cross-listing draft
- preview destination payloads
- submit a publish batch
- get batch/job progress
- retry a safe failed job
- mark a manual action complete
- refresh one channel listing status

Use consistent JSON error envelopes, request validation, rate-limit awareness, CSRF/session protection as applicable, and structured server logs with secrets removed.

## Testing and verification

Add tests proportionate to the feature:

- canonical-to-platform mapping unit tests
- required-field and platform-limit validation tests
- deduplication and unique-inventory tests
- idempotency and retry tests
- provider error classification tests
- sale-event normalisation and API/email deduplication tests
- unique-PC sale transaction and component inventory tests
- equivalent-listing automatic delist/manual-task tests
- customer matching/creation and duplicate-order tests
- build-portal association and personalisation tests
- delivery insurance, tracking and courier/collection booking idempotency tests
- next-business-day fallback and manual-fulfilment-pack tests
- notification persistence, unread/read and reduced-motion confetti tests
- API route authentication/authorisation tests
- component tests for selection, filtering, validation, preview and batch progress
- Playwright coverage for the main happy path, partial failure, manual-only destination, refresh, retry and duplicate protection
- test doubles/fakes for providers; never call real marketplaces from automated tests

Run lint, typecheck/build, unit tests and relevant e2e tests. Fix regressions rather than weakening tests. Report any provider/API limitation that prevents a complete live integration.

## Delivery requirements

Deliver:

1. Working Cross-listing admin page and sidebar navigation.
2. Backend/API/data-model changes required for durable cross-listing.
3. Provider adapter layer with real eBay/FlipFlop.shop integration reuse and explicit capability handling for OnBuy, Amazon, Facebook Marketplace and Vinted.
4. Secure connection/settings handling.
5. Preview, validation, batch publishing/manual-assist workflow and status history.
6. Tests and documentation.
7. A concise final report listing files changed, migrations/configuration required, supported automation per platform, tests run, and any remaining external approval or manual steps.

Work incrementally, keep the working tree’s unrelated changes intact, and do not replace existing working eBay or storefront functionality without a backwards-compatible migration path.
