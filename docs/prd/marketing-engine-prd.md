# FlipFlop Marketing Engine PRD

**Status:** Draft for implementation planning  
**Version:** 0.1  
**Scope:** Initial Social Media + Website Analytics MVP, with an extensible roadmap for content, newsletters, advertising and growth intelligence.

## 1. Product vision

Create a Marketing Engine inside the FlipFlop admin tool that turns builds, products, expertise and editorial ideas into useful content and measurable growth.

The system should eventually support:

- Organic social publishing
- Website traffic and conversion analytics
- Blog and editorial content
- Newsletter campaigns
- Paid advertising
- Website-owned promotional placements
- Customer lifecycle marketing
- Creator, referral and community programmes

The first release must focus on reliable social publishing and website measurement.

## 2. Initial MVP

### 2.1 Admin information architecture

Add a new top-level admin section:

```text
Marketing
├── Social Media
└── Analytics
```

Social Media is the first/default tab.

The later information architecture may expand to:

```text
Marketing
├── Social Media
├── Analytics
├── Content Calendar
├── Blog & Editorial
├── Newsletter
├── Advertising
├── Owned Placements
└── Brand & Automation Settings
```

### 2.2 MVP social channels

Implement the architecture for multiple channel adapters, but begin with:

1. Facebook Pages
2. Instagram Business

YouTube, TikTok, Reddit, X and LinkedIn can be added later subject to provider API permissions and media requirements.

### 2.3 MVP website analytics

Include Google Analytics 4 from the initial release. Add Google Search Console when practical, but do not block the first release on it.

Every generated link must support UTM parameters and preserve the originating content, campaign, build and creative variant.

## 3. Target users

The primary user is the FlipFlop operator managing builds, listings, content and sales without a dedicated marketing team.

The product must minimise repetitive work while keeping control over brand voice, budgets, availability, quality and publishing safety.

## 4. Core user outcomes

- Configure connected social profiles once.
- Automatically promote a newly available pre-built.
- Automatically rotate selected curated builds.
- Use build images, renders or videos appropriate to each platform.
- Link every post back to the correct website page.
- Understand whether social content creates traffic, engagement, enquiries and purchases.
- Pause all automation quickly when needed.
- Add advertising, newsletters and editorial content later without rebuilding the core.

## 5. MVP workflows

### 5.1 New pre-built promotion

When a build becomes eligible for promotion:

1. Detect the build event.
2. Confirm the build is complete, available and has a valid website URL.
3. Select an approved media asset.
4. Generate post copy from the relevant template.
5. Adapt the copy and media dimensions to each enabled channel.
6. Add a tracked link.
7. Publish immediately, schedule it or queue it for approval.
8. Record the publication result.
9. Attribute subsequent website activity to the post.

Eligibility must exclude sold, hidden, incomplete or unavailable builds.

### 5.2 Curated build rotation

The operator can create a collection of builds and configure:

- Manual order
- Random selection
- Weighted random selection
- Newest first
- Least recently promoted
- Price or performance filters
- Minimum repeat interval
- Maximum promotion count
- Publishing cadence
- Active date range
- Availability rules

The system must automatically skip sold or unavailable builds.

## 6. Social Media dashboard

The Social Media page should show:

- Connected profiles
- Connection and token status
- Enabled publishing workflows
- Upcoming posts
- Posts awaiting approval
- Recently published posts
- Failed posts
- Basic attributed traffic and conversion metrics
- Global pause/resume control

Each profile should support:

- Enable/disable publishing
- Content types allowed
- Posting windows
- Maximum posts per day/week
- Hashtag rules
- Link settings
- Automatic or approval-based publishing
- Platform-specific copy overrides

## 7. Content templates

Templates must support structured variables including:

```text
{{build_name}}
{{price}}
{{short_description}}
{{key_specs}}
{{performance_summary}}
{{availability_status}}
{{product_url}}
{{interactive_3d_url}}
{{hero_image}}
{{brand_name}}
```

Templates should support platform-specific variants, character limits and media requirements.

## 8. Media strategy

Social platforms generally cannot embed FlipFlop's interactive 3D viewer directly. The MVP should therefore:

1. Use the interactive 3D viewer URL on the website.
2. Use an available rendered image or hero photograph in the post.
3. Support future turntable/video rendering.
4. Link the post to the product page or interactive viewer.

Preferred asset order:

1. Rendered turntable video
2. Branded rendered still
3. Hero product photograph
4. Approved fallback asset

## 9. Website analytics

The website should record at least:

- Landing page view
- Build/product page view
- 3D viewer opened
- Configurator started
- Add to cart
- Checkout started
- Purchase completed
- Newsletter signup
- Contact/enquiry submitted
- Blog article view
- Outbound marketplace click

The implementation must avoid inventing analytics results when Google credentials or data are unavailable. The admin should show a clear connection state and empty-state explanation.

## 10. Attribution and tracking

Every generated link should support:

- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_content`
- Build ID or article ID
- Content template ID
- Creative variant ID

Report traffic separately as:

- Organic social
- Paid advertising
- Newsletter/email
- Search
- Referral
- Owned website promotion
- Direct
- Unattributed

Do not treat all direct traffic as a known advertising source.

## 11. Analytics MVP dashboard

Show, where data is available:

- Sessions from social media
- Top referring channels
- Top-performing posts
- Build page views from social
- 3D viewer opens
- Newsletter signups
- Enquiries
- Add-to-cart events
- Purchases
- Revenue attributed to social content
- Best-performing templates
- Recent trend comparison

Include date range selection and channel/content filters.

## 12. Automation safety

Required controls:

- Global pause
- Per-channel pause
- Per-workflow pause
- Daily and weekly frequency limits
- Duplicate-content detection
- Link validation
- Media validation
- Availability validation
- Brand-policy checks
- Publishing failure logs
- Full audit trail

Default publishing modes:

| Content type | MVP default |
|---|---|
| New build announcement | Approval or automatic, configurable |
| Curated build rotation | Approval or automatic, configurable |
| Price or availability update | Approval initially |
| Current news/editorial | Not in MVP; approval required later |
| Replies and direct messages | Not automatic |

## 13. Future capabilities

### Phase 2: Content Studio

- Unified content calendar
- Blog drafting and publishing workflow
- Social posts generated from articles
- Content pillars
- Creative variations
- SEO recommendations
- Search Console insights

### Phase 3: Newsletter

- Subscriber management
- Weekly digest
- New-build announcements
- Blog promotion
- Welcome sequence
- Back-in-stock campaigns
- Email attribution

### Phase 4: Advertising

- Google Ads
- Meta Ads
- Reddit Ads
- X Ads
- TikTok Ads
- Campaigns, audiences and budgets
- Creative testing
- Conversion tracking
- ROAS and CPA reporting

OpenAI advertising integrations should be treated as conditional on an approved advertising surface and API being available.

### Phase 5: Growth intelligence

- Trend detection
- Demand-informed campaigns
- Creator and affiliate tracking
- Referral programme
- Customer lifecycle automation
- Personalised recommendations
- User-generated content
- Community and reputation monitoring
- Marketing copilot

## 14. Future advertising model

Paid advertising and owned promotion must share the same content and attribution foundations.

Owned placements may include:

- Homepage hero
- Featured-build slots
- Product recommendations
- Blog article modules
- Newsletter placements
- Welcome emails
- Post-purchase pages
- Website announcement bars
- Configurator recommendations

These should be tracked as owned promotion, not incorrectly mixed with paid advertising or direct traffic.

## 15. Suggested data entities

- `MarketingBrandProfile`
- `SocialConnection`
- `SocialChannel`
- `ContentTemplate`
- `ContentAsset`
- `ContentItem`
- `AutomationWorkflow`
- `PublicationJob`
- `BuildCollection`
- `TrackingLink`
- `PerformanceMetric`
- Future: `Campaign`, `BlogArticle`, `NewsletterCampaign`, `AdAccount`, `OwnedPlacement`

## 16. MVP acceptance criteria

The MVP is complete when:

1. The Marketing section is visible in the admin navigation.
2. Social Media is the first/default tab.
3. A social profile can be connected, viewed and disabled.
4. A new eligible build can generate a platform-specific post.
5. The post contains the correct image, copy and website link.
6. The link contains tracking parameters.
7. A curated collection can rotate builds on a schedule.
8. Sold and unavailable builds are skipped.
9. Posts can be approved, scheduled, published, paused and retried.
10. Failed jobs are visible with an understandable error.
11. Google Analytics 4 connection state is visible.
12. Website events and campaign attribution are documented and testable.
13. The dashboard reports available analytics without fabricating unavailable data.
14. A global pause prevents new publishing jobs from being sent.
15. Automated tests cover eligibility, scheduling, tracking and failure handling.

## 17. Product principles

- Automate repetitive work, not accountability.
- Every promotion must link to a measurable outcome.
- Never promote unavailable products.
- Keep organic, paid, owned and direct traffic distinguishable.
- Make generated content editable and explainable.
- Treat current news as a source-verification problem.
- Build adapters so new channels do not require rewriting the content engine.
