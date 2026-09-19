# FlipFlop Growth Engine
## Mega Product Requirements Document

**Status:** Draft for implementation
**Product:** FlipFlop Admin / theflipflop.shop
**Primary navigation:** One `Advertising & Growth` link in the admin application
**Version:** 1.0
**Date:** 19 September 2026

---

## 1. Executive summary

FlipFlop requires a single AI-driven Growth Engine that turns market intelligence, products, builds, customer behaviour and published content into profitable attention and sales.

The Growth Engine combines:

- AI-driven social-media management
- Automated blog-topic discovery and article production
- Automated visual/media creation for articles and campaigns
- Customer-storefront blog publishing
- Social distribution and engagement monitoring
- Weekly newsletter generation and delivery
- Paid advertising across eBay, Google, Meta and future channels
- Campaign planning, budgeting, attribution and profit protection
- Discount vouchers and promotional offers
- Loyalty-based discounts and points redemption
- Abandoned-cart and lifecycle campaigns
- Cross-channel analytics and a long-term learning system

Every capability is accessible from one admin link: `Advertising & Growth`.

The system is not merely a content scheduler or advert manager. It is an AI-assisted growth operating system that continuously answers:

1. What should FlipFlop publish next?
2. Which audience should receive it?
3. Which product, build, offer or article should it support?
4. On which channel should it appear?
5. Should it be organic, paid, emailed or all three?
6. What discount, if any, is commercially justified?
7. Did it create profitable customer action?
8. What did the result teach FlipFlop for future campaigns?

AI agents may research, suggest, draft, adapt, schedule and optimise within configured guardrails. Human approval is required for consequential activity such as spending money, publishing sensitive claims, issuing high-value discounts or materially changing campaign budgets.

---

## 2. Product vision

FlipFlop should be able to discover a relevant subject such as rising RAM prices, explain it beautifully, publish the article to the storefront, create engaging supporting imagery, distribute it through social media, include it in the weekly newsletter, promote it with paid advertising when justified, attach a measurable offer and learn from the resulting engagement and sales.

Example:

> RAM prices rise sharply. The system detects the trend from FlipFlop market data, proposes “Why RAM Is So Expensive in 2026 — and What Buyers Should Do”, researches and drafts the article, creates a chart and hero image, publishes it to the blog, creates social posts and a newsletter section, identifies relevant PC builds, generates a tracked “memory upgrade” offer, and measures whether readers later buy, configure or enquire.

---

## 3. Goals and non-goals

### 3.1 Goals

- Increase relevant organic reach and audience engagement.
- Convert attention into visits, enquiries, configurator starts, sales and repeat purchases.
- Reduce the time required to produce high-quality content and campaigns.
- Make every article, post, advert, email and voucher measurable.
- Use first-party customer and campaign data to improve future decisions.
- Protect profit by applying deterministic discount, spend and margin guardrails.
- Give Michael one coherent workflow instead of separate disconnected tools.
- Support Hermes agents, local agents and future AI providers through a provider abstraction.
- Preserve approval and audit control over publishing, spend and customer incentives.

### 3.2 Non-goals for the initial release

- Becoming a general-purpose advertising agency platform.
- Automatically spending unlimited money without approval.
- Publishing unverified technical, pricing, legal or market claims.
- Replacing the existing commerce, inventory, listing, customer or loyalty systems.
- Allowing AI to invent specifications, prices, discounts, stock levels or performance results.

---

## 4. Product principles

1. **One growth system, many channels.** Blog, social, email and paid advertising share campaigns, audiences, assets, links and outcomes.
2. **Profit before vanity metrics.** Reach and engagement matter, but the system must distinguish attention from profitable commercial impact.
3. **Organic before paid where appropriate.** Strong organic content may become paid creative; paid promotion is not the only measure of success.
4. **AI proposes; deterministic services decide.** AI may draft and recommend, but calculations, eligibility, margin checks, voucher redemption and spend limits are controlled by application services.
5. **Approval for consequential actions.** The system may prepare work automatically, but money, public publishing and high-value customer incentives require configurable approval.
6. **Every claim has provenance.** Facts, prices, specifications, statistics and source material must be traceable.
7. **Learn from outcomes.** Campaign, content, audience, offer and customer results must improve future recommendations.
8. **Brand consistency is mandatory.** All generated output follows FlipFlop’s design bible, tone, visual identity and claims policy.

---

## 5. Unified information architecture

The admin application exposes one primary navigation item:

```text
Advertising & Growth
├── Command Centre
├── Strategy & Opportunities
├── Campaigns
├── Blog & Editorial
├── Social Media
├── Newsletter & CRM
├── Paid Advertising
├── Offers & Vouchers
├── Loyalty
├── Creative Studio
├── Audiences
├── Tracking & Attribution
├── Analytics & Learning
├── Approvals & Agent Activity
└── Settings
```

These are tabs or sub-routes within one module. They are not separate products.

### 5.1 Shared top-level entities

- **Growth campaign:** The commercial or editorial initiative connecting content, channels, offers, audiences and outcomes.
- **Content idea:** A suggested subject, angle, audience, urgency, source evidence and recommended channels.
- **Content asset:** Article, social post, image, video, chart, email section, advert or landing-page copy.
- **Channel execution:** A specific published or scheduled version of an asset on one channel.
- **Audience:** A reusable group defined by characteristics, behaviour, lifecycle state or campaign intent.
- **Offer:** A discount, voucher, bundle, free delivery incentive, loyalty reward or other customer benefit.
- **Conversion:** A measurable action such as article view, email click, configurator start, enquiry, checkout or sale.
- **Learning observation:** A structured outcome used to improve future recommendations.

---

## 6. Command Centre

The Command Centre is the default landing page for Advertising & Growth.

### 6.1 Dashboard cards

- Campaigns needing approval
- Articles awaiting review
- Social posts scheduled today
- Newsletter status
- Advertising spend today and this month
- Revenue attributed to growth activity
- Profit after advertising and discounts
- Active offers and expiry warnings
- Abandoned carts eligible for recovery
- Best-performing content
- Underperforming campaigns
- AI recommendations awaiting decision

### 6.2 Command Centre recommendations

The AI should surface actionable recommendations such as:

- “RAM-related search interest has increased 34%; create an article this week.”
- “This Instagram reel is performing in the top 10% of recent content; consider paid amplification.”
- “The current promoted-listing rate makes this build fall below the minimum profit threshold.”
- “Three customers are eligible for a loyalty reward before their points expire.”
- “The newsletter has no content planned for Sunday; approve the proposed edition.”

Every recommendation must show:

- Reason
- Supporting data
- Confidence
- Expected impact
- Proposed action
- Estimated cost or discount exposure
- Approval requirement

---

## 7. Strategy and opportunity discovery

The system should continuously generate content, campaign and offer opportunities from:

- Component price changes
- Market-price anomalies
- GPU, CPU, RAM and storage trends
- Search demand and website queries
- eBay listing performance
- Customer questions and enquiries
- Reviews and support conversations
- Social comments and recurring questions
- Configurator abandonment
- Inventory requiring movement
- Builds newly completed or newly discounted
- Seasonal events and relevant technology launches
- Existing blog and social performance
- Competitor and category observations where legally and technically permitted

### 7.1 Opportunity types

- Educational article
- News or market explanation
- Product comparison
- Buying guide
- Build showcase
- Customer story
- Troubleshooting guide
- Upgrade guide
- Myth-busting article
- Social discussion prompt
- Product launch campaign
- Inventory clearance campaign
- Loyalty campaign
- Abandoned-cart campaign
- Newsletter feature

### 7.2 Opportunity scoring

Each idea receives a deterministic and explainable score based on:

- Relevance to target audience
- Evidence strength
- Search or demand signal
- Commercial relevance
- Product availability
- Profit opportunity
- Timeliness
- Brand fit
- Novelty versus recent content
- Expected production effort
- Legal or reputational risk

The AI may explain and rank ideas, but the score must be backed by stored inputs.

---

## 8. AI agent architecture

The Growth Engine uses specialist agents coordinated by an orchestrator. The orchestrator may run Hermes agents, local models through Ollama, hosted models or future providers through a common interface.

### 8.1 Agent roles

#### Growth Strategist Agent

- Reviews performance, market trends, inventory and business priorities.
- Proposes campaigns, content themes, audiences and offers.
- Produces a reasoned brief rather than directly publishing.

#### Trend and Research Agent

- Detects relevant market and customer topics.
- Collects approved sources and evidence.
- Flags uncertainty, conflicting information and stale data.

#### Editorial Agent

- Creates article outlines, drafts and revisions.
- Maintains FlipFlop tone and editorial standards.
- Adds internal links, product references and calls to action.

#### Creative Agent

- Selects owned media.
- Requests or generates suitable hero images, diagrams, charts, thumbnails and short videos.
- Produces channel-specific crops and variants.

#### Social Media Agent

- Converts articles, builds, offers and campaigns into platform-specific posts.
- Schedules posts after approval.
- Monitors engagement, comments and content performance.

#### Newsletter Agent

- Selects relevant articles, offers and updates.
- Generates the weekly newsletter draft.
- Applies audience and consent rules.

#### Advertising Agent

- Recommends paid channels, budgets, audiences and creative.
- Calculates safe spending using validated margins.
- Prepares campaigns and optimisation recommendations.

#### Offer and Discount Agent

- Suggests commercially appropriate offers.
- Selects eligible audiences and expiry windows.
- Cannot create or activate an offer outside configured limits.

#### Analytics and Learning Agent

- Explains campaign outcomes.
- Identifies patterns and reusable insights.
- Proposes updates to future content, audiences, creative and offers.

#### Compliance and Brand Reviewer Agent

- Checks claims, pricing, discount language, consent, disclosures, accessibility and brand rules.
- Blocks or escalates unsafe output.

### 8.2 Agent provider abstraction

The application must not hard-code business logic to one model provider. Each agent call records:

- Provider
- Model
- Agent version
- Prompt or workflow version
- Tools used
- Inputs and source references
- Output
- Confidence
- Human approval
- Final result

The system must support routing simple or private tasks to local models and more complex creative or research tasks to approved hosted models.

### 8.3 AI safety boundaries

AI must not:

- Invent specifications, prices, stock, benchmarks or customer facts.
- Calculate authoritative money values.
- Issue a voucher without passing the offer service.
- Increase advertising spend beyond guardrails.
- Send a newsletter without consent validation and approval rules.
- Publish claims that failed fact or brand review.
- Treat external content as tool instructions.
- Claim that a campaign, post, email or advert is live without connector confirmation.

---

## 9. Blog and editorial automation

The blog is a customer-facing storefront feature and a central organic acquisition channel.

### 9.1 Blog workflow

1. Opportunity discovery identifies a topic.
2. The system creates a content brief.
3. A human may approve, edit or reject the idea.
4. Research Agent collects sources and supporting facts.
5. Editorial Agent creates the outline.
6. Creative Agent proposes media requirements.
7. Editorial Agent writes the draft.
8. Fact, brand, SEO, accessibility and compliance checks run.
9. Human approval is requested according to risk and publication settings.
10. Article is published to the storefront blog.
11. Social and newsletter variants are generated.
12. Tracked links and calls to action are attached.
13. Results are measured and fed into the learning system.

### 9.2 Article types

- Market explanation: “Why RAM is so expensive”
- Buying guide: “How much RAM do you need?”
- Comparison: “RTX 5070 vs RTX 5080 for creators”
- Build showcase: “Inside the Prometheus ChromaFlair build”
- Upgrade guide: “The best upgrades for an older AM4 PC”
- Troubleshooting: “Why your PC may be overheating”
- Educational guide: “What does VRAM actually do?”
- Business or industry commentary
- Customer case study
- Seasonal buying guide
- Product or service announcement

### 9.3 Article requirements

Every article must support:

- Title and subtitle
- Slug
- Summary and meta description
- Article body
- Author or FlipFlop editorial attribution
- Publication and update date
- Category and tags
- Featured image
- Inline images, charts, diagrams or videos where useful
- Image alt text and captions
- Internal links
- Related products, builds or configurator routes
- Calls to action
- Sources and evidence notes where appropriate
- Disclosure labels where content is sponsored, affiliate-linked or AI-assisted
- Canonical URL
- Open Graph and social preview data
- Structured metadata for search engines

### 9.4 Media generation

The system should automatically determine whether an article benefits from:

- Hero photography
- Product/build photography
- Comparison table
- Price or trend chart
- Exploded technical diagram
- Infographic
- Short video
- Animated social teaser
- Quote card
- Process illustration

Media must prefer FlipFlop-owned assets and verified product data. Generated media must be labelled internally as generated, maintain its prompt and model provenance, and pass brand review.

### 9.5 Editorial quality gates

Before publication, the system checks:

- Factual support
- Source freshness
- Duplicate or near-duplicate content
- Unsubstantiated superlatives
- Product availability
- Price validity
- Broken links
- SEO completeness
- Accessibility
- UK English spelling and tone
- Disclosure requirements
- Brand colour and visual consistency
- Required approval level

### 9.6 Blog publishing states

`idea`, `briefed`, `researching`, `drafting`, `review`, `approved`, `scheduled`, `published`, `updated`, `archived`, `blocked`.

---

## 10. Social media management

The existing AI-driven social-media functionality becomes a specialist channel within the Growth Engine.

### 10.1 Social responsibilities

- Platform account connections
- Content calendar
- Post generation
- Platform adaptation
- Media selection and resizing
- Scheduling
- Publishing
- Comment and engagement monitoring
- Content approval
- Organic performance analysis
- Social listening and topic discovery
- Creator or customer-content tracking where applicable

### 10.2 Supported content sources

Social posts may be generated from:

- Blog articles
- New builds
- Product listings
- Customer reviews
- Build diaries
- Benchmarks
- Offers
- Frequently asked questions
- Market trends
- Behind-the-scenes content
- Newsletter content
- Campaign briefs

### 10.3 Social-to-paid bridge

Every eligible social post may expose:

- Promote this post
- Create paid campaign
- Add to campaign
- Generate alternative creative
- Create retargeting version
- Create follow-up article

The system should identify high-performing organic posts and recommend paid amplification, while preserving organic and paid metrics separately.

### 10.4 Social content states

`idea`, `draft`, `needs_review`, `approved`, `scheduled`, `published`, `partially_published`, `failed`, `paused`, `archived`.

### 10.5 Engagement data

Capture, where supported:

- Reach
- Impressions
- Engagements
- Likes
- Comments
- Shares
- Saves
- Video views
- Watch time
- Profile visits
- Link clicks
- Follower changes
- Sentiment and recurring questions

---

## 11. Weekly newsletter automation

The newsletter is an owned-audience channel connecting editorial content, social activity, products, offers and customer lifecycle information.

### 11.1 Weekly newsletter workflow

1. Newsletter Agent reviews the editorial calendar, recent articles, product availability, offers and campaign priorities.
2. It proposes a content mix.
3. It selects audience segments according to consent and eligibility.
4. It creates a draft subject, preview text and body.
5. It adds relevant images, articles, products and calls to action.
6. It runs link, tracking, compliance, accessibility and rendering checks.
7. It presents a preview and predicted outcomes.
8. Michael approves, edits or rejects the draft.
9. The system sends or schedules it through the connected email provider.
10. Opens, clicks, unsubscribes, conversions and revenue are recorded.

### 11.2 Newsletter sections

- Opening editorial note
- Main blog article
- Market or technology insight
- Featured build
- Product or configurator recommendation
- Customer story or review
- Limited-time offer
- Upgrade or trade-in recommendation
- Upcoming content or event
- Community question or poll

### 11.3 Newsletter rules

- Only send to customers or subscribers with valid consent.
- Respect unsubscribe, suppression and frequency rules.
- Do not expose one customer’s personalised offer to another customer.
- Include required sender and unsubscribe information.
- Do not make scarcity or urgency claims unless validated.
- Do not send high-value discount offers without configured approval.

### 11.4 Newsletter learning

Measure:

- Delivery rate
- Open rate where available
- Click-through rate
- Article views
- Product views
- Configurator starts
- Checkout starts
- Voucher redemptions
- Sales and profit
- Unsubscribes
- Complaints

---

## 12. Paid advertising

Paid advertising is a channel execution within a growth campaign, not a separate disconnected system.

### 12.1 Initial paid channels

- eBay Promoted Listings
- Google Shopping
- Google Search where appropriate
- Meta Ads
- Instagram paid promotion
- Facebook paid promotion
- Retargeting
- Future channels through adapters

### 12.2 Paid campaign workflow

1. Select a product, build, article, offer or objective.
2. Create or attach a Growth Campaign.
3. Advertising Agent recommends channels, audiences, creative, budget and duration.
4. Profitability service calculates safe spending limits.
5. Creative variants are generated from approved assets.
6. Compliance and brand review runs.
7. A campaign preview displays all spend, audience, creative and destination details.
8. Human approval is required according to budget and risk settings.
9. Connector publishes the campaign and confirms its status.
10. Performance is synchronised.
11. Agent recommends continuation, adjustment or pause.

### 12.3 Advertising channel capability model

Each channel declares whether it supports:

- Account connection
- Read performance
- Create campaign
- Update budget
- Update creative
- Pause campaign
- Create audience
- Read conversions
- Export-only or assisted workflows

The interface must never imply that an export or browser-assisted workflow is a full API integration.

### 12.4 Profitability rules

The system calculates:

```text
Net profit after growth activity =
selling revenue
- product/component cost
- marketplace and payment fees
- delivery and packaging
- refunds/returns allowance
- voucher discount
- advertising spend
- attributable fulfilment cost
```

Advertising recommendations must display every input. The AI may recommend a rate or budget, but the Profitability Service is authoritative.

### 12.5 Guardrails

- Maximum daily spend
- Maximum monthly spend
- Maximum cost per acquisition
- Minimum absolute profit
- Minimum profit margin
- Maximum discount exposure
- Maximum combined advertising and discount cost
- Approval threshold by spend
- Automatic pause threshold
- Frequency and audience caps

---

## 13. Offers, vouchers and discounts

The Offer Service supports reusable, personalised, advertising-led and loyalty-funded discounts.

### 13.1 Offer types

#### A. Site-wide offers

Examples:

- New-customer £50 off
- 10% off selected products
- Free delivery above a threshold
- Seasonal site-wide campaign

Rules:

- Multi-use or customer-limited according to configuration.
- Start and expiry date.
- Optional minimum order value.
- Optional product, category or channel restrictions.
- Optional new-customer condition.
- Configurable stacking rules.
- Maximum total redemptions and financial exposure.

#### B. Individualised offers

Examples:

- £50 off a customer’s next order
- Birthday or anniversary offer
- Service recovery voucher
- Post-purchase upgrade incentive

Rules:

- Linked to one customer account.
- One-time or limited-use redemption.
- Expiry date.
- Optional product and order restrictions.
- Optional minimum spend.
- Never transferable unless explicitly configured.

#### C. Abandoned-cart offers

Examples:

- Short-lived £50 voucher after an abandoned checkout.
- Logged-in customer receives a one-time recovery code.

Rules:

- Requires a qualifying abandoned cart event.
- Linked to the customer account and cart or checkout context.
- Customer must be logged in to redeem.
- Short expiry window.
- One-time use.
- No generation if the cart contains excluded items.
- No repeated issuance beyond a configurable frequency cap.
- Must not reveal that customer behaviour is being aggressively monitored.

#### D. Loyalty-based discounts

Examples:

- Silver: 5% off
- Gold: 10% off
- Points exchanged for £25 off
- Trade-in or referral reward

Rules:

- Loyalty Service calculates tier and point balance.
- Redemption deducts points transactionally.
- Failed checkout must not permanently deduct points.
- Refunds must reverse or reconcile the reward according to policy.
- Loyalty discounts must comply with stacking and margin rules.

### 13.2 Voucher state model

`draft`, `pending_approval`, `approved`, `scheduled`, `active`, `partially_redeemed`, `exhausted`, `expired`, `paused`, `cancelled`, `revoked`.

### 13.3 Voucher code model

Support:

- Human-readable codes
- Unique personal codes
- Non-guessable secure tokens
- Account-linked redemption tokens
- QR or deep-link redemption
- Automatic application for eligible logged-in customers

Codes must be stored securely and never expose unnecessary customer information.

### 13.4 Deterministic eligibility checks

At checkout, the Offer Service validates:

- Customer identity
- Login state
- New-customer status
- Voucher status and expiry
- Product or category eligibility
- Minimum order value
- Usage count
- Customer usage count
- Cart linkage
- Loyalty tier or point balance
- Stacking rules
- Currency and market
- Margin guardrail

AI must not perform these checks itself.

### 13.5 Approval guardrails

Approval may be required for:

- Any offer above £X total exposure
- Any discount above Y%
- Any discount reducing expected profit below the configured floor
- Site-wide offers
- Offers sent to more than a configured audience size
- Combining advertising spend and discount exposure above a campaign limit
- Automated changes to an active promotion

### 13.6 Offer advertising

Every offer can be associated with:

- Blog article
- Social post
- Newsletter
- Paid advert
- Landing page
- Customer segment
- Campaign

The system must show whether the discount generated incremental profit or merely reduced the price of a sale that would likely have happened anyway.

---

## 14. Loyalty integration

The Growth Engine integrates with the existing or future Loyalty Service.

### 14.1 Loyalty inputs

- Completed purchases
- Review participation without requiring positive sentiment
- Referrals
- Trade-ins
- Content engagement where explicitly permitted
- Newsletter membership where appropriate
- Customer milestones

### 14.2 Loyalty outputs

- Tier status
- Available points
- Points expiring soon
- Redeemable discount value
- Recommended loyalty campaign
- Customer eligibility for upgrade or referral offers

### 14.3 Loyalty safety

- Points ledger is append-only and auditable.
- Redemptions are transactional.
- Refund and cancellation behaviour is explicitly defined.
- AI cannot alter balances directly.
- Customers can see why points were awarded or deducted.

---

## 15. Campaigns and cross-channel orchestration

### 15.1 Campaign objectives

- Brand awareness
- Audience growth
- Blog traffic
- Product discovery
- Configurator starts
- Lead generation
- Direct sale
- Inventory movement
- Abandoned-cart recovery
- Customer retention
- Upgrade sale
- Trade-in
- Loyalty engagement

### 15.2 Campaign composition

A campaign may contain:

- One or more products or builds
- One or more blog articles
- Organic social posts
- Paid advertisements
- Newsletter placements
- Landing pages
- Vouchers
- Loyalty rewards
- Audience definitions
- Budget and profit constraints
- Experiment variants

### 15.3 Example campaign

```text
Campaign: 2026 Memory Upgrade Week

Trigger: RAM market price increase plus customer search demand
Audience: Existing customers, developers, creators and high-RAM configurator users
Blog: Why RAM is expensive and how much you really need
Social: 6 posts, 2 reels, 1 poll and 1 build comparison
Newsletter: Main article plus upgrade offer
Paid: Google Shopping and Meta retargeting
Offer: £50 off eligible memory upgrades, one use per customer
Budget: £150
Minimum campaign profit: £500
Status: Awaiting approval
```

### 15.4 Cross-channel sequencing

Campaigns must support schedules such as:

- Article first, social announcement immediately after publication.
- Newsletter after the article has collected initial engagement data.
- Paid promotion after organic performance passes a threshold.
- Abandoned-cart offer after a configured delay.
- Loyalty offer after a completed purchase.

The workflow must show dependencies and what happens if an earlier step fails.

---

## 16. Creative Studio

Creative Studio is the shared asset and variant workspace for blog, social, newsletters and advertising.

### 16.1 Asset types

- PC/build photography
- Component photography
- Product renders
- 3D models and renders
- Brand graphics
- Charts
- Infographics
- Video clips
- Reels and short-form video
- Social thumbnails
- Email headers
- Advert images
- Quote cards
- Customer reviews

### 16.2 Asset provenance

Every asset records:

- Source
- Licence status
- Owner
- Creation method
- AI model and prompt if generated
- Related product/build
- Brand review status
- Approved channels
- Accessibility metadata

### 16.3 Variant generation

From one approved master asset, generate channel-specific versions while preserving the master:

- Blog hero
- Instagram post
- Instagram story
- Facebook image
- TikTok cover
- Newsletter image
- Google advert image
- eBay promotional creative

---

## 17. Audiences and customer lifecycle

### 17.1 Audience sources

- Customer records
- Purchase history
- Build ownership
- Product views
- Article views
- Social engagement
- Newsletter engagement
- Configurator activity
- Cart events
- Loyalty tier
- Geographic or language preference
- Stated interests
- Consent and suppression status

### 17.2 Standard audiences

- New prospects
- Blog readers
- Engaged social followers
- Newsletter subscribers
- First-time customers
- Repeat customers
- Silver customers
- Gold customers
- Abandoned carts
- Previous GPU buyers
- Customers approaching an upgrade window
- Customers with expiring warranty
- Customers who have not engaged recently

### 17.3 Privacy and consent

Audience activation must enforce:

- Consent purpose
- Channel permission
- Opt-out and suppression
- Data minimisation
- Retention rules
- Account access controls
- UK GDPR and PECR-aware workflows
- No sensitive inference without explicit lawful basis

The system must retain the reason a customer entered an audience and the rule version used.

---

## 18. Tracking and attribution

### 18.1 Tracking links

The system generates and manages:

- UTM parameters
- Campaign IDs
- Content IDs
- Channel IDs
- Offer IDs
- Creative variant IDs
- Audience IDs

### 18.2 Conversion events

- Article view
- Social link click
- Newsletter click
- Product view
- Configurator start
- Configurator completion
- Enquiry
- Add to cart
- Checkout start
- Voucher application
- Purchase
- Refund
- Repeat purchase
- Trade-in request
- Review or referral

### 18.3 Attribution models

Support, at minimum:

- First touch
- Last non-direct touch
- Campaign touch
- Time decay
- Assisted conversion
- Organic versus paid comparison

Attribution is an estimate, not an absolute truth. Reports must show the model used and avoid double-counting revenue.

### 18.4 Revenue and profit attribution

Reports must separate:

- Gross revenue
- Net revenue
- Advertising cost
- Voucher value
- Marketplace fees
- Product cost
- Fulfilment cost
- Estimated contribution profit

---

## 19. Analytics and learning system

The Growth Engine must retain outcome data so future recommendations improve over time.

### 19.1 Learning observations

Record relationships between:

- Topic and engagement
- Article angle and conversion
- Headline and click-through rate
- Image style and performance
- Video length and completion
- Audience and conversion
- Channel and profit
- Offer value and incremental conversion
- Discount depth and margin
- Newsletter section and clicks
- Social format and assisted revenue
- Timing and performance
- Product type and campaign response

### 19.2 Insight examples

- “Build photography with visible RGB produces more saves than isolated component images.”
- “RAM articles attract developers but convert better when paired with upgrade consultations.”
- “Newsletter readers who click troubleshooting articles have a higher later conversion rate for support plans.”
- “£50 abandoned-cart vouchers recover sales but are unprofitable on low-margin builds.”
- “Instagram is strong for discovery; Google Shopping produces higher purchase intent.”

### 19.3 Learning controls

- Insights require evidence thresholds.
- Small samples are labelled low confidence.
- The system must distinguish correlation from proven causation.
- Recommendations must retain the underlying observations.
- Human feedback can accept, reject or correct an insight.
- Rejected insights must not silently reappear as facts.

### 19.4 Feedback loop

```text
Market/customer signal
→ opportunity
→ content/campaign/offer
→ channel execution
→ engagement and conversion
→ profit outcome
→ learning observation
→ improved future recommendation
```

---

## 20. Approvals and guardrails

### 20.1 Approval categories

- Content publication
- Social publication
- Newsletter send
- Paid campaign launch
- Paid budget increase
- Site-wide offer activation
- High-value individual offer
- Large audience activation
- Use of generated or licensed media
- Material price or claim change

### 20.2 Approval levels

#### Automatic

Allowed for low-risk actions within pre-approved rules, such as:

- Drafting content
- Creating internal suggestions
- Resizing approved assets
- Generating tracked links
- Preparing a newsletter draft
- Creating a social draft

#### User review

Required for:

- Publishing public articles
- Scheduling public social posts
- Sending newsletters
- Activating adverts
- Issuing customer discounts

#### Explicit high-risk approval

Required for:

- Spend above threshold
- Discount exposure above threshold
- Site-wide promotions
- Campaigns using sensitive or restricted audiences
- Claims with legal or reputational implications

### 20.3 Approval screen

Every approval must show:

- Exact action
- Target channel
- Audience
- Creative and copy
- Product and destination
- Dates and timing
- Spend
- Discount exposure
- Expected revenue and profit
- Evidence and AI reasoning
- Warnings
- Rollback or pause capability

---

## 21. Data model

The implementation must reconcile with existing FlipFlop entities. Suggested entities include:

### Core

- `growth_campaign`
- `growth_campaign_objective`
- `growth_campaign_product`
- `growth_campaign_channel`
- `growth_campaign_event`
- `content_idea`
- `content_brief`
- `content_asset`
- `content_variant`
- `content_publication`
- `audience`
- `audience_rule`
- `audience_membership`

### Editorial and social

- `blog_article`
- `blog_article_revision`
- `blog_source`
- `social_account`
- `social_post`
- `social_post_variant`
- `social_publication`
- `social_engagement_snapshot`
- `newsletter_edition`
- `newsletter_section`
- `newsletter_delivery`

### Advertising

- `ad_account`
- `ad_campaign`
- `ad_group`
- `ad_creative`
- `ad_audience`
- `ad_spend_snapshot`
- `ad_conversion_snapshot`
- `channel_capability`

### Offers and loyalty

- `offer`
- `offer_rule`
- `voucher_code`
- `voucher_assignment`
- `voucher_redemption`
- `offer_exposure`
- `loyalty_account`
- `loyalty_ledger_entry`
- `loyalty_redemption`

### Analytics and governance

- `tracking_link`
- `conversion_event`
- `attribution_touch`
- `revenue_attribution`
- `profitability_snapshot`
- `experiment`
- `experiment_variant`
- `learning_observation`
- `agent_run`
- `agent_recommendation`
- `approval_request`
- `audit_event`

### Data rules

- Store money in minor units plus currency.
- Store timestamps in UTC and display in UK local time.
- Use idempotency keys for external actions.
- Use immutable or append-only ledgers for spend, redemption and loyalty balances.
- Preserve revisions rather than overwriting published content.
- Use soft lifecycle states rather than destructive deletion.
- Maintain field-level provenance where content is generated or transformed.

---

## 22. Service boundaries

- **Market Intelligence Service:** trends, prices, demand and source evidence.
- **Content Intelligence Service:** topics, briefs, editorial drafts and source tracking.
- **Media Service:** assets, transformations, generation and provenance.
- **Social Channel Service:** accounts, posts, scheduling, publishing and engagement.
- **Newsletter Service:** editions, consent, delivery and email analytics.
- **Campaign Orchestration Service:** campaign state, dependencies and channel coordination.
- **Advertising Adapter Service:** eBay, Google, Meta and future paid channels.
- **Audience Service:** segmentation, membership and suppression.
- **Offer Service:** eligibility, voucher lifecycle, redemption and stacking.
- **Loyalty Service:** points, tiers and ledger operations.
- **Tracking Service:** links, events and conversion capture.
- **Attribution Service:** touchpoints, revenue and profit allocation.
- **Profitability Service:** authoritative cost, fee, margin and guardrail calculations.
- **AI Agent Runtime:** provider abstraction, tools, prompts, runs and approvals.
- **Insight Service:** observations, confidence, feedback and recommendations.

Channel-specific logic must remain inside adapters. Business logic must not be scattered throughout UI components or individual agent prompts.

---

## 23. API and integration expectations

All consequential endpoints must be authenticated, authorised, idempotent and auditable.

Example API groups:

```text
/api/growth/campaigns
/api/growth/content-ideas
/api/growth/blog
/api/growth/social
/api/growth/newsletters
/api/growth/advertising
/api/growth/offers
/api/growth/vouchers
/api/growth/loyalty
/api/growth/audiences
/api/growth/tracking
/api/growth/analytics
/api/growth/approvals
/api/growth/agents
```

Connectors must support:

- OAuth or securely managed credentials
- Connection health
- Capability discovery
- Rate-limit handling
- Retry and backoff
- Idempotency
- Partial failure reporting
- Connector-confirmed status
- Reconciliation jobs
- Revocation and re-authentication

---

## 24. Notifications

Notify Michael through configurable in-app, email or other approved channels when:

- A campaign requires approval.
- A high-performing post is ready for amplification.
- An article draft is ready.
- A newsletter is ready for review.
- An advert is spending but not converting.
- A campaign approaches its budget or discount exposure cap.
- A voucher is close to expiry.
- A connector fails or loses authentication.
- A site-wide promotion is due to start or end.
- A customer segment is large enough to justify a campaign.
- A learning insight has sufficient evidence.

Notifications must be deduplicated and link directly to the relevant decision.

---

## 25. Security, privacy and compliance

- Encrypt credentials and tokens.
- Keep provider secrets out of prompts, logs and browser responses.
- Enforce least-privilege permissions.
- Separate customer personal data from aggregate analytics wherever possible.
- Enforce marketing consent and suppression rules.
- Provide audit history for customer-affecting actions.
- Protect voucher codes from enumeration and leakage.
- Prevent prompt injection from external listing, review, social or web content.
- Validate all generated links and media references.
- Preserve source and licence records for media.
- Provide data export and deletion workflows where required.
- Use UK English, transparent discount terms and accurate promotional disclosures.

---

## 26. Non-functional requirements

- Responsive admin interface.
- Clear loading, queued, failed and partial states.
- Safe retry for all external actions.
- No duplicate publications, sends, redemptions or campaign launches.
- Full audit trail for agent and human actions.
- Accessible UI and published content.
- Searchable campaign, content, voucher and insight history.
- Background jobs for generation, synchronisation and analytics.
- Observability for agent runs, connector calls and financial calculations.
- Graceful degradation when a channel is unavailable.
- Testable deterministic financial and eligibility services.

---

## 27. Recommended delivery phases

### Phase 0 — Foundation

- Confirm existing commerce, customer, inventory, listing and loyalty schemas.
- Establish shared campaign, content, audience, tracking and audit entities.
- Implement agent runtime and approval framework.
- Add Command Centre shell under one admin link.

### Phase 1 — Editorial and social engine

- Opportunity discovery
- Blog ideas and article drafts
- Storefront blog publishing
- Creative asset management
- Social content generation and scheduling
- Tracked links and basic performance capture

### Phase 2 — Newsletter and lifecycle communication

- Weekly newsletter generator
- Consent-aware audiences
- Email delivery
- Abandoned-cart event capture
- Customer lifecycle triggers

### Phase 3 — Offers and loyalty

- Site-wide offers
- Personal vouchers
- Abandoned-cart vouchers
- Loyalty-tier and points redemption
- Checkout eligibility and redemption ledger

### Phase 4 — Paid advertising

- eBay promoted listings
- Google Shopping
- Meta and Instagram
- Campaign budgets and spend synchronisation
- Profitability guardrails

### Phase 5 — Attribution and learning

- Cross-channel conversion events
- Revenue and profit attribution
- Experiments
- Learning observations
- AI recommendations based on historical outcomes

### Phase 6 — Controlled optimisation

- Automated budget recommendations
- Organic-to-paid amplification
- Automated campaign sequencing
- Predictive offer selection
- Limited automatic actions within explicit guardrails

---

## 28. Acceptance criteria

### Unified module

- The admin has one `Advertising & Growth` link.
- All tabs use shared campaign, asset, audience, tracking and approval concepts.
- Users can move from an article to its social posts, newsletter placement, advert and attributed results.

### Blog

- The system proposes content ideas from market, customer and performance data.
- A user can approve an idea and generate a researched draft.
- The article can include relevant approved media, internal links and calls to action.
- The article can be reviewed and published to the storefront.
- Publication creates trackable social and newsletter tasks.

### Social

- The system can turn an article, build or offer into platform-specific social drafts.
- Approved content can be scheduled and published through available connectors.
- High-performing organic posts can be recommended for paid promotion.
- Organic and paid performance remain separately visible.

### Newsletter

- The system proposes and drafts a weekly newsletter.
- It respects consent and suppression rules.
- A user can preview, approve, schedule and measure the edition.
- Newsletter clicks and sales are attributed using tracked links.

### Advertising

- A campaign can contain multiple paid and organic channel executions.
- Spend and performance are synchronised where supported.
- The user sees profit after advertising and discounts.
- Budgets and campaign changes are approval-controlled.
- Connector failures are visible and recoverable.

### Discounts

- The system supports site-wide, individual, abandoned-cart and loyalty discounts.
- Voucher eligibility is deterministic and enforced at checkout.
- Personal vouchers are linked to the correct customer account.
- Abandoned-cart vouchers require login and expire correctly.
- Loyalty redemptions update the points ledger transactionally.
- Stacking, minimum spend, expiry and margin rules are enforced.
- All offer issuance and redemption is auditable.

### Learning

- Article, social, newsletter, advert and offer outcomes are stored.
- The system can explain which content, audience, offer or channel contributed to an outcome.
- Recommendations show evidence and confidence.
- Low-confidence or small-sample observations are labelled appropriately.

---

## 29. Testing strategy

### Unit tests

- Voucher eligibility
- Expiry and usage limits
- Discount stacking
- Loyalty ledger operations
- Profitability calculations
- Budget guardrails
- Audience rules
- Attribution calculations
- Campaign state transitions
- Idempotency

### Integration tests

- Blog publishing
- Social connectors
- Newsletter delivery
- Advertising connectors
- Checkout voucher application
- Customer account linking
- Loyalty redemption
- Tracking and conversion capture

### AI evaluation

- Factual accuracy
- Source citation
- No fabricated specifications
- Brand voice
- UK English
- Correct audience and channel adaptation
- Safe offer recommendations
- Prompt-injection resistance
- Correct escalation of uncertainty

### End-to-end tests

1. Detect RAM trend.
2. Generate article idea.
3. Approve and draft article.
4. Generate media.
5. Publish article.
6. Generate and approve social posts.
7. Add article to newsletter.
8. Create tracked campaign.
9. Generate offer within margin rules.
10. Launch approved paid campaign.
11. Simulate traffic, voucher use and sale.
12. Attribute revenue and profit.
13. Generate learning insight.

### Security tests

- IDOR and customer-account isolation
- Voucher enumeration
- Token leakage
- Prompt injection
- Unauthorised campaign publishing
- Spend escalation
- Consent bypass
- Duplicate redemption
- Duplicate email or social publication

---

## 30. Product decisions

| Decision | Recommended default |
|---|---|
| Primary navigation | One `Advertising & Growth` admin link |
| Campaign model | Shared parent object containing organic, owned and paid executions |
| Blog publishing | Automated drafting, approval-controlled publication |
| Newsletter | Weekly AI draft, approval-controlled send |
| Social | Existing social PRD remains the channel specialist; Growth Engine orchestrates it |
| Paid ads | Recommendation-first, manual approval before spend |
| Discounts | Deterministic Offer Service with configurable AI recommendations |
| Abandoned-cart offers | Logged-in, one-time, short-lived and account-linked |
| Loyalty | Append-only ledger and transactional redemption |
| AI runtime | Provider abstraction supporting Hermes, local and hosted models |
| Financial truth | Deterministic Profitability Service |
| Learning | Evidence-backed observations with confidence and human feedback |
| Default publishing | Draft and approval unless explicitly authorised by policy |

---

## 31. Final product definition

The completed module should feel like one intelligent growth command centre:

> FlipFlop notices what matters, explains it, makes it beautiful, publishes it, distributes it, promotes it when justified, rewards the right customers, protects profit and learns from what happened.

The blog is the long-form knowledge engine.

Social media is the reach and conversation engine.

The newsletter is the owned-audience relationship engine.

Paid advertising is the scalable acquisition engine.

Offers and loyalty are the conversion and retention engine.

Analytics and learning are the improvement engine.

AI agents coordinate all of them, while deterministic services and approval guardrails keep the system commercially safe.

