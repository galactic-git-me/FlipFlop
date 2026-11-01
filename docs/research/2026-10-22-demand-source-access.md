# Autonomous demand source access investigation

Checked: 22 October 2026 (Europe/London). Scope: first-party documentation and public source pages; no account created, paid plan purchased, permission request sent, or authenticated entitlement verified. The user reports no existing source permissions. Public readability, a working parser, OAuth credentials, and robots allowance do not establish commercial reuse or automated collection permission.

## Recommended acquisition order

1. Use existing authorised first-party flipflop sales as transaction evidence. Keep market asking prices separate from realised sales.
2. Use eBay Seller Hub Product Research only for seller-side research unless eBay confirms in writing that transfer into FlipFlop's separate commercial playbook is permitted. It is the strongest documented UI for actual accepted Best Offer prices, but official pages reviewed do not document an export/API for its research results or permission to republish them on another site. Do not automate its private endpoints merely because login succeeds.
3. Obtain a licensed PC Atlas feed or written permission covering automated commercial ingestion and downstream derived recommendations. Investigate its stated SoldComps upstream as a potential licensed supplier; its existence is not evidence of eBay authorisation.
4. Use Google Trends official CSV export immediately through a human import workflow; apply for the official API alpha for unattended operation.
5. Treat Steam survey as a secondary adoption signal. Public page parsing is technically feasible, but commercial automated reuse permission still needs checking. PCPartPicker remains blocked pending a commercial data agreement.

These are engineering recommendations based on the evidence below, not claims that access has already been granted.

## Source findings and precise gates

| Source | Verified route and meaning | Account/setup gate | Automation state now |
| --- | --- | --- | --- |
| eBay Product Research | Seller Hub research UI; official help says up to three years of sales data and calculated results, including actual accepted Best Offer prices, average postage and 90-day sell-through | Current UK help says Product Research is available to Seller Hub sellers; mobile help additionally states an active listing or sale in the prior 90 days for mobile access. Sourcing Insights has a separate Shop requirement. In the existing signed-in Seller Hub, Research → Product research redirected to Overview; access is not currently usable in this session. No public Product Research API or research-result export route was verified. | Seller-side human research only. No external Playbook import, unattended collection or private-endpoint automation until eBay confirms the rights and method in writing |
| Individual eBay sold listings | Recent completed/sold listing evidence; do not assume displayed original asking price equals accepted offer | Explicit eBay permission for automated access, or an approved API/data contract | Scraping blocked |
| eBay Marketplace Insights | Official limited-release `item_sales` sold-history API, up to 90 days, category whitelisting | Existing approved production application/scopes/category approval or direct eBay business agreement | No entitlement established; not a dependable self-service onboarding path |
| PC Atlas | Public UK component sold-price medians, not complete-PC transaction demand | Publisher agreement for feed/API/export, storage, commercial derived use and cadence | No permission established |
| PCPartPicker | Reference/new retail pricing and compatibility context; not realised used sales | Commercial data/API agreement with publisher | No permission established; robots blocks relevant AI agents and `/api/` |
| Google Trends | Official UI CSV export; official API alpha application | Google account/UI export where required; alpha approval and supplied credentials for API | Manual CSV supported; existing unofficial endpoints do not establish API entitlement |
| Steam Hardware Survey | Public monthly aggregate hardware adoption page | Confirm automated commercial reuse basis; no survey API entitlement established | Parser capability separate from permission |

### eBay: sales quality and access

eBay says Seller Hub sellers can use Product Research. It covers three years and includes the actual accepted Best Offer price; ordinary completed search covers recent sold listings over approximately 90 days. Keep query, marketplace, condition, date window, shipping treatment and sample size with every import. [eBay Product Research help](https://www.ebay.com/help/selling/selling-tools/terapeak?id=4853)

UK onboarding: sign into the intended seller account, opt into Seller Hub, open Research → Product Research and verify a UK query. The UK announcement says mobile access requires at least one active listing or a sale in the previous 90 days; desktop availability should be checked directly rather than inventing a qualifying sale. Product Research is free; Sourcing Insights has separate Store requirements. [UK Seller Centre](https://www.ebay.co.uk/sellercentre/news/2024-june/product-research)

The eBay UK agreement requires prior express permission for robots, scrapers and other automated access. Neither seller membership nor a third-party scraper subscription satisfies that permission requirement by itself. [eBay UK User Agreement](https://www.ebay.co.uk/help/policies/member-behaviour-policies/user-agreement?id=4259)

Marketplace Insights is limited release, with approved developers and whitelisted categories; use `EBAY_GB` only after actual approval. The official questionnaire expressly states Marketplace Insights access cannot be granted upon request. Therefore, submitting that form must not be represented as a guaranteed route to access. [API overview](https://www.edp.ebay.com/api-docs/buy/marketplace-insights/static/overview.html), [official developer questionnaire](https://ebaypartnernetwork.ebay.com/page/developer-questionnaire)

Concrete setup: inventory existing developer application; verify production keyset, allowed OAuth scopes and account-deletion notification compliance without exposing credentials; authenticate seller; verify research entitlement; document approved access method. A public Browse/OAuth success does not verify access to other sellers' sold history. For a data supplier, require evidence of rights to collect and sublicense this specific data, not merely a successful sample response.

### PC Atlas

PC Atlas says its target price is a 90-day median including postage, with model matching, faulty/bundle exclusion and outlier filtering. Its methodology identifies SoldComps as the weekly completed-listing supplier and excludes Best Offer guide prices. This supports component valuation context, but does not establish that every accepted-offer price is known or that PC Atlas data may be republished. [Methodology](https://pcatlas.co.uk/methodology)

The publisher provides `hello@pcatlas.co.uk`; no public API or commercial ingestion licence was found in the examined home, about, methodology and contact pages. The robots URL could not be retrieved using the research browser, so its rules remain unverified. Request a documented JSON/CSV feed before writing a broad scraper. Ask for commercial derived use, cache/retention, attribution, request cadence, coverage, sample counts, individual sale identifiers and accepted-offer handling. [Contact](https://pcatlas.co.uk/contact), [About](https://pcatlas.co.uk/about)

### PCPartPicker

The first-party robots file explicitly disallows ChatGPT-User and other AI agents; general directives disallow `/api/`, `/search/`, account and user paths, specify a 60-second crawl delay, and reserve AI-input/training use. Those directives do not grant commercial reuse rights. Terms pages returned inaccessible/403 responses during this investigation; no assertion about their precise current wording is made. No public commercial API entitlement was verified. Seek the publisher's approved commercial feed/API rather than using unofficial scraper libraries. [First-party robots](https://pcpartpicker.com/robots.txt), [terms URL attempted](https://pcpartpicker.com/tos/)

### Google Trends

Google documents CSV chart downloads and attribution. Preserve geography, period, query/topic, comparison group and exported normalisation; search interest is neither sales nor absolute demand. [Official export instructions](https://support.google.com/trends/answer/4365538?hl=en)

The official API remains described as an alpha accepting applications from a limited set of developers. It offers five years, regular aggregation, regional detail and consistently scaled data. Apply using the form embedded in the official page with the commercial UK hardware-demand use case, expected cadence and feedback commitment. Wait for approval and supplied access instructions; do not label an unofficial explore/widget endpoint an authorised API. [Official API alpha](https://developers.google.com/search/apis/trends)

### Steam

Valve publishes a monthly optional anonymous hardware survey; the page currently identifies September 2026. This describes installed hardware adoption, not UK purchase intent or confirmed sales. Store robots does not disallow `/hwsurvey/`, but this alone is not a commercial data licence. No hardware-survey endpoint was identified in the official Web API overview/reference examined. Creating a Steam API key is therefore not an established way to acquire survey data. [Survey](https://store.steampowered.com/hwsurvey/), [robots](https://store.steampowered.com/robots.txt), [official Web API overview](https://partner.steamgames.com/doc/webapi_overview)

## Connector acceptance record

For each source, persist access method, publisher/contract evidence URL or document reference, approving principal, checked date, scope (manual import versus automated collection), commercial derived-use scope, expiry/recheck date, retention and attribution requirements. Keep manual review available while unattended collection is blocked. Record accepted-offer status as unknown unless the acquired evidence supplies the actual transaction price. Do not double-count PC Atlas aggregates and their underlying eBay transactions as independent sales.

Account setup requiring account-holder identity, verification/MFA, a paid plan, contractual acceptance or provider approval remains an external gate. No account was configured by this research task, and no source should be marked authorised on the strength of this document alone.

## Official eBay UK access re-check, 23 October 2026

This section supersedes any broader reading above that ordinary Product Research access or manual copying is enough for FlipFlop's separate commercial playbook. The eBay UK User Agreement effective 10 August 2026 prohibits automated access without prior express permission and separately prohibits scraping or gathering information from eBay to use on another site and commercialising eBay information without prior express permission. Because FlipFlop's playbook and storefront are separate from eBay, a Seller Hub login or a human research session alone does not clear the downstream-use gate. Obtain written permission for the intended acquisition, storage, derived pricing and display before importing or using eBay evidence in FlipFlop. [eBay UK User Agreement](https://www.ebay.co.uk/help/policies/member-behaviour-policies/uROr-agreement?id=4259), [eBay UK Site Interference policy](https://www.ebay.co.uk/help/policies/member-behaviour-policies/site-interference-policy?id=4371)

### Marketplace Insights and Buy APIs

The official Buy API marketplace table lists Great Britain (`GB`) as supported for Marketplace Insights, but the same page explicitly says Marketplace Insights is restricted and not open to new users at this time. Marketplace support is not an entitlement or an application approval. The official Marketplace Insights overview and `item_sales` search documentation currently redirect to sign-in pages whose return paths are under `marketplace-insights-private`; this confirms the public documentation is gated, not a public self-service onboarding route. [Buy API marketplace support](https://developer.ebay.com/api-docs/buy/ref-marketplace-supported.html), [Marketplace Insights overview](https://developer.ebay.com/api-docs/buy/marketplace-insights/overview.html), [item_sales search](https://developer.ebay.com/api-docs/buy/marketplace-insights/resources/item_sales/methods/search)

The general Buy API production route is an eBay Partner Network (EPN) partner application, not merely creation of developer keys. eBay says Buy API production use is intended for partners, requires application and approval based on business model, and is not guaranteed. Its published process is: join EPN; submit the Buy API application; if accepted, open an eBay Developer Support ticket with the registered EPN eBay ID, sandbox test/access instructions and EPN approval; pass compliance review, make requested changes, sign eBay's contracts, then receive production enablement. None of those generic steps override Marketplace Insights' closed-to-new-users notice or establish access to the restricted Insights API. [Buy API requirements and production access process](https://developer.ebay.com/api-docs/buy/buy-requirements.html)

For an official inquiry, eBay says Developer Technical Support requires a registered developer account with support activated from Profile & Contacts; questions and tickets are initiated from its AI-Assisted Support tab. For the partner route, use the official EPN join/application path and request explicit confirmation that Marketplace Insights is available to this applicant and that the contemplated downstream use is licensed. No application or support ticket has been submitted. [Developer Technical Support access](https://developer.ebay.com/support/developer-technical-support), [EPN](https://partnernetwork.ebay.com/)

### Product Research, access and exports

UK Seller Centre describes Product Research as free for sellers and located in Seller Hub's Research tab. UK help says it provides up to three years of sales data, average prices, sold-price ranges and postage metrics; a separate FAQ states that Product Research includes actual sold prices including accepted Best Offers. The UK mobile-specific help states that mobile access requires an active listing or a listing sold in the previous 90 days; it does not state that requirement for desktop. Sourcing Insights is a separate feature for eBay Shop subscribers. [UK Seller Centre: Research Tool](https://www.ebay.co.uk/sellercentre/selling/how-to-sell/research), [Product Research help](https://www.ebay.co.uk/help/selling/selling-tools/product-research?id=4853)

The official Product Research help pages reviewed describe in-product search, filters and metrics, but do not document a CSV/API export of Product Research results. Seller Hub's separate Reports documentation refers to downloadable order and listing reports; that is not evidence of an export of third-party market sales from Product Research. This is a documentation finding, not proof that no export control exists in every account or UI version. Do not use private network endpoints or automate the Seller Hub UI. Even a manually produced result must not be carried into FlipFlop pending written confirmation of downstream commercial permission under the current User Agreement. [Product Research help](https://www.ebay.co.uk/help/selling/selling-tools/product-research?id=4853), [Seller Hub overview](https://www.ebay.co.uk/sellercentre/selling/how-to-sell/seller-hub), [Seller Hub Reports help](https://www.ebay.com/help/selling/selling-tools/file-exchange?id=4096), [eBay UK User Agreement](https://www.ebay.co.uk/help/policies/member-behaviour-policies/uROr-agreement?id=4259)

### Current FlipFlop gate

- eBay Marketplace Insights ingestion: **blocked**; no entitlement and the public marketplace table says it is closed to new users.
- Generic Buy API production access: **not applied for**; partner application approval/contracts are required and would not by themselves grant Marketplace Insights access.
- Product Research in Seller Hub: **session access remains unverified** (the prior signed-in session redirected Research to the Seller Hub overview); official documentation supports seller-side research, not this external Playbook transfer.
- Product Research export: **no official API/export route found in reviewed public help**; do not infer an undocumented UI function is permission for automated or external use.
- External commercial use in FlipFlop: **blocked pending explicit written eBay permission**. The prepared request remains unsent.
