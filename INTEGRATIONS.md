# Integrations router

- `flipflop-api/app/services/` and `flipflop-api/app/routes/` — external-service adapters and API entry points.
- `EBAY_LISTING_IMPROVEMENTS.md`, `OAUTH_SETUP.md`, and `CROSS_LISTING_IMPLEMENTATION_PROMPT.md` — marketplace and listing workflows.
- `APIFY_TEMU_SETUP.md` and `CASES_3D_SOURCING_GUIDE.md` — sourcing and scraper integrations.
- `RESELLING_CENTER_WORKFLOW.md` and `LISTING_TEMPLATE_GUIDE.md` — selling and listing operations.
- `deploy/` and `docker-compose*.yml` — integration-specific runtime wiring and environment boundaries.

## Google Merchant Center / Shopping

The Cross-listing page submits only a live FlipFlop.shop build with its saved
asking price, listing text, and public HTTPS photos. Product inputs use the
stable `FF-BUILD-{build_id}` offer ID; repeated submissions replace the same
input. Google review is asynchronous, so an API-accepted item is not necessarily
approved or visible yet. The API worker reconciles price, content, images, and
reservation stock every two minutes, and deletes the input after a confirmed
sale or withdrawal. Failed withdrawals remain queued for retry.

Before enabling writes, verify the shop domain and account policies, enable
Merchant API in the dedicated Google Cloud project, create a service account,
and add that identity to the Merchant Center account. The one-time
`POST /cross-listing/google/register-project` operator endpoint links the
authenticating GCP project to the production Merchant Center account; Google
requires the service account to have Merchant Center Admin access for this
call. Then assign that service account the API Developer access right and
reduce its account access type to Standard if available. The endpoint does not
accept a developer email, avoiding an implicit contact change. Store the
account ID, data source ID, and service-account key in
the API runtime secret environment (`GOOGLE_MERCHANT_ACCOUNT_ID`,
`GOOGLE_MERCHANT_DATA_SOURCE_ID`, and either
`GOOGLE_MERCHANT_SERVICE_ACCOUNT_JSON` or
`GOOGLE_MERCHANT_SERVICE_ACCOUNT_FILE`). Then set
`GOOGLE_MERCHANT_WRITES_ENABLED=true` only in the live API environment. Do not
commit service-account keys. The first API primary product data source can be
created with the operator-only `/cross-listing/google/data-source` endpoint;
save its returned ID in the live API environment before enabling product
writes. `GOOGLE_MERCHANT_FEED_LABEL=GB` and
`GOOGLE_MERCHANT_CONTENT_LANGUAGE=en` match the UK product inputs.
