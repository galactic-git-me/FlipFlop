# Cross-listing vendor API options

Research date: 30 October 2026  
Scope: OnBuy, Amazon UK, Facebook/Meta product catalog, Vinted, and Google Shopping via Merchant Center, as shown or proposed for FlipFlop Admin's Cross-listing screen.

## Summary

There is no free, universal library that makes a FlipFlop build publish to every marketplace. Each vendor has its own API, data model, authentication, listing eligibility, and approval process. Open-source or royalty-free SDKs can reduce API plumbing; they do not provide seller authorization, marketplace approval, product/category mapping, or permission to publish.

For this app, use one small backend adapter per vendor and the existing canonical listing data. Prefer the vendor's official API and existing Python HTTP client support over adding an aggregator dependency. Keep “Create new” distinct from “update/relist” per vendor identity and reconcile remote status before creating, following the existing eBay approach.

## Current screen behaviour

The screen's `capabilities()` currently hard-codes OnBuy and Facebook catalog as manual-only, and Vinted as manual-only. Amazon is publishable only when its seller API connection is configured; otherwise it requires approval. That is the app's integration/configuration state, not proof that all four vendors lack APIs. Facebook Catalog API manages products in a business catalog; it does not automate consumer Marketplace posts.

Source in repo: [`flipflop-admin/lib/cross-listing.ts`](../../flipflop-admin/lib/cross-listing.ts), `capabilities()`.

## Vendor findings

### OnBuy

- OnBuy publishes a REST API with product creation, listing management, and stock/price endpoints. Its seller documentation describes test and live keys from the Seller Control Panel and temporary access tokens. [OnBuy API documentation](https://docs.api.onbuy.com/)
- Live product creation must be enabled for the seller account. OnBuy's docs say sellers first create with live keys, then request product/account approval before publishing. [OnBuy API documentation: Going Live](https://docs.api.onbuy.com/)
- No official OnBuy SDK was identified in the official documentation. A client can be implemented with the repo's existing Python HTTP stack; OnBuy also provides a Postman collection. An SDK would not remove seller keys or account approval.

**Assessment:** Automatable once seller API credentials and live product-creation approval are available. This is a good first additional channel after eBay because the API explicitly supports listings and price/stock updates.

### Amazon UK

- The Selling Partner API (SP-API) supports listing creation and management. Amazon's Listings Items API and Product Type Definitions API are the relevant path; listing data must conform to product-type requirements. [Listings Items API](https://developer-docs.amazon.com/sp-api/reference/listings-items-v2021-08-01) · [Product Type Definitions API](https://developer-docs.amazon.com/sp-api/reference/product-type-definitions-v2020-09-01) · [developer onboarding](https://developer-docs.amazon.com/sp-api/docs/onboarding-overview)
- A single-organization private application can be self-authorized and does not need to be published in Amazon's Appstore. The developer must register and qualify for the required roles, such as Product Listing. [Amazon onboarding: application types, authorization, and roles](https://developer-docs.amazon.com/sp-api/docs/onboarding-overview)
- Amazon maintains an official multi-language SDK, including Python and JavaScript, under Apache-2.0. [Official Amazon SP-API SDK](https://github.com/amzn/selling-partner-api-sdk)

**Assessment:** Automatable once the seller's SP-API application, OAuth/self-authorization, roles, credentials, marketplace-specific product attributes, and any ASIN/GTIN eligibility requirements are handled. The official SDK is free software; it does not grant API access or remove Amazon listing rules.

### Facebook / Meta catalog

- Meta's Catalog API can create and update items in a business-owned product catalog. The catalog-management permission is subject to Meta app permissions/review; access is limited to catalogs the connected business user can manage. [Meta catalog getting started](https://developers.facebook.com/documentation/ads-commerce/commerce-platform/catalog/get-started/) · [Meta permissions reference](https://developers.facebook.com/docs/permissions/)
- Meta maintains a Node.js Business SDK with a royalty-free license for use with its services, subject to Meta Platform Policy. [Meta Business SDK](https://github.com/meta/facebook-nodejs-business-sdk) · [license](https://github.com/meta/facebook-nodejs-business-sdk/blob/main/LICENSE)
- A catalog item is feed/catalog data for commerce surfaces and ads. It is not the same workflow as creating an ordinary Facebook Marketplace listing; the current screen's statement that personal Marketplace automation is unsupported is appropriate.

**Assessment:** Catalog synchronization is automatable with a business-owned catalog and approved access. Treat it as “sync to Meta catalog,” not consumer Marketplace cross-listing. Since the app's backend is Python, a small Graph API adapter can use its existing HTTP client rather than adding the Node SDK.

### Vinted

- Vinted now documents an official Pro Integrations API. Its item API supports creating, updating, validating, and tracking items; the service also documents webhooks and a sandbox/dev environment. [Vinted Pro Integrations API](https://pro-docs.svc.vinted.com/)
- Access is restricted to a limited set of allowlisted Vinted Pro businesses. Pro membership alone does not guarantee allowlisting. API tokens come from the Pro Integrations Portal and requests are HMAC-signed. [Vinted access and authentication](https://pro-docs.svc.vinted.com/)
- Vinted publishes an OpenAPI definition and explicitly supports generating a client from it. A generated Python client is a free option; the OpenAPI Generator project is Apache-2.0. [Vinted OpenAPI download](https://pro-docs.svc.vinted.com/) · [OpenAPI Generator license](https://github.com/OpenAPITools/openapi-generator/blob/master/LICENSE)
- Unofficial libraries target Vinted's private web endpoints and account sessions. They are not substitutes for the allowlisted Pro API and should not be used for seller-account automation.

**Assessment:** Technically automatable through the official Pro API only if FlipFlop's seller account is approved and allowlisted. The UI's current “no approved seller integration” state is a real blocker until that approval exists.

### Google Shopping / Merchant Center

- As of 30 October 2026, use Google's **Merchant API**. The older Content API for Shopping reached sunset on 18 August 2026, so new work should not target it. The Products sub-API `v1` is listed as active. [Content API sunset](https://developers.google.com/shopping-content/guides/deprecation-and-sunset) · [Merchant API versioning](https://developers.google.com/merchant/api/guides/versioning)
- Merchant API supports product input create, update (`patch`), and delete, plus reading the processed product and its status. Writes require an API-type product data source; a file-based source cannot be written through these product methods. Inserts/updates may take several minutes to appear as processed, and a successful upload does not mean Google approved the item. The input needs policy-compliant product attributes, including title, description, landing-page link, image, availability and price; category/GTIN and other fields depend on the product. [Add and manage products](https://developers.google.com/merchant/api/guides/products/add-manage) · [Products REST reference](https://developers.google.com/merchant/api/reference/rest)
- Prerequisites include a production Merchant Center account, verified website, a Google Cloud project with Merchant API enabled and registered against the account, a configured product data source, and an authorized identity with suitable Merchant Center permissions. Authentication supports OAuth 2.0, service accounts or ADC; API keys are unsupported. A service account can be added for the merchant's own integration, while third-party access should use OAuth. [Developer registration](https://developers.google.com/merchant/api/guides/quickstart/registration) · [Authorization](https://developers.google.com/merchant/api/guides/authorization/access-your-account)
- Google provides official Merchant API client libraries for Python, Node.js, Java, PHP, .NET/C#, Go and Ruby. Google's client-library guide and language samples are free to use; the official general Google API Node client is Apache-2.0. Choose the Merchant API's generated product client for the selected runtime, and verify the specific package license/version when pinning it. [Official client libraries](https://developers.google.com/merchant/api/client-libraries) · [Google API Node client and license](https://github.com/googleapis/google-api-nodejs-client)
- Google free listings can surface eligible products on Google properties at no cost, but inclusion is not guaranteed and requires policy-compliant data, return policy information and UK delivery settings. This sync publishes product data to Google's catalog and destinations; it is not an independent checkout marketplace listing. [Free listings requirements](https://support.google.com/merchants/answer/13889434?hl=en-GB)

**Assessment:** Technically automatable if FlipFlop has a verified business website and production Merchant Center account, and the listing data can meet Google product requirements. Treat it as a distinct **Google Shopping / Merchant Center catalog sync** destination in Cross-listing, with product ID, processing/approval and destination status. Do not describe it as a marketplace listing or relist: availability/discovery is governed by Merchant Center processing, policies and Google destinations.

## Recommendation

1. Check which seller accounts/permissions already exist: OnBuy live API access; Amazon SP-API private-app authorization and roles; Meta Business catalog ownership plus catalog-management access; Vinted Pro Integrations allowlisting.
2. Build a channel adapter only when the corresponding official credentials and vendor approval are available. Keep credentials server-side.
3. Start with OnBuy if its live API is enabled, then Meta catalog sync if its catalog and permission are ready. Amazon's product-type/identifier requirements need a richer mapping step. Vinted depends first on allowlisting.
4. Keep one canonical build record, but persist each destination's vendor ID, status, last sync, and error separately. Before publish, check whether that vendor already has a live item; update/relist when its remote state is known and create a new item only when none exists.

5. Consider Google Merchant Center as a separate catalog-distribution channel if the business has a verified website and can provide policy-compliant, current product data. The integration must track Google's processed/approval status; API upload success alone is not publication.

No additional dependency is required for the first implementation: the work is mostly vendor authorization, per-channel field mapping, lifecycle state, and error/retry handling.
