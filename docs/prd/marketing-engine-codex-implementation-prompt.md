# Codex Implementation Prompt: FlipFlop Marketing Engine MVP

You are working in the FlipFlop repository at:

`C:\Users\mclar\CODING\FlipFlop`

Implement the first vertical slice of the Marketing Engine described in:

`docs/prd/marketing-engine-prd.md`

## Objective

Build an initial Marketing section in the existing admin tool focused on:

1. Social Media management
2. Automated promotion of eligible pre-built builds
3. Curated build rotation
4. Website traffic and conversion analytics foundations
5. Google Analytics 4 connection/configuration state

Do not implement paid advertising, newsletter sending, automated blog generation or automatic replies in this phase. Design the interfaces and data models so those features can be added later.

## Required working method

1. Inspect the existing repository before editing anything.
2. Identify the current Next.js admin navigation, build APIs, manual/pre-built build lifecycle, storefront URLs, image/photo handling, 3D model fields and scheduler conventions.
3. Identify the existing backend framework, database models, migrations and API style.
4. Reuse existing UI components, styling tokens, authentication, API helpers and scheduling patterns.
5. Do not replace or rewrite unrelated systems.
6. Do not add fake credentials or pretend that external social APIs are connected.
7. If provider credentials are absent, build an explicit disconnected/mock-safe state and document the integration boundary.

## Scope

### Admin navigation

Add a top-level `Marketing` section to the existing sidebar. The default route should be the Social Media page.

Suggested routes, adapted to the existing conventions:

```text
/marketing/social
/marketing/analytics
```

### Social Media page

Implement:

- Connected profile cards
- Connection status
- Enable/disable publishing
- Automation status
- New-build workflow summary
- Curated rotation summary
- Upcoming queue
- Approval queue
- Recent publication results
- Failed publication results
- Global pause/resume control

Use Lucide or the existing icon system. Do not use emoji as UI icons.

### Content templates

Implement storage and UI for at least:

- Template name
- Content type
- Platform
- Body text
- Enabled/disabled state
- Automatic/approval mode
- Supported variables

Support variables such as:

```text
{{build_name}}
{{price}}
{{key_specs}}
{{availability_status}}
{{product_url}}
{{interactive_3d_url}}
{{hero_image}}
```

Render a preview with sample data and real build data where available.

### New-build workflow

Create a workflow that can be triggered when a build becomes eligible for promotion. It must:

- Confirm the build is complete and available.
- Confirm a valid website URL exists.
- Select the best available media asset.
- Generate content from a template.
- Build a tracked URL.
- Queue the publication.
- Respect automatic versus approval mode.
- Record status and errors.

Use the existing build and storefront data models rather than creating duplicate build records.

### Curated build rotation

Implement a collection/rotation configuration with:

- Selected builds
- Manual or random mode
- Optional weighted random mode if easy to support cleanly
- Cadence
- Time window
- Minimum repeat interval
- Maximum promotion count
- Available-only filter
- Template selection
- Enabled/disabled state

Sold or unavailable builds must be skipped automatically.

### Tracking links

Create a reusable tracking-link builder. At minimum support:

- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_content`
- Build ID
- Template ID
- Creative variant ID

Ensure links are URL-safe and preserve the canonical website URL.

### Analytics page

Implement an Analytics page with:

- Google Analytics 4 connection state
- Measurement ID/configuration state where appropriate
- Clear disconnected state when credentials/configuration are absent
- Date range selector
- Channel filter
- Traffic summary cards
- Social sessions
- Build/product views
- 3D viewer opens if the website emits this event
- Configurator starts if available
- Enquiries
- Newsletter signups
- Add-to-cart and purchase events if available
- Attributed revenue where available
- Top-performing posts/content items

Do not fabricate analytics values. Use explicit unavailable/empty states when data cannot be fetched.

### Website event contract

Document and implement the event contract required by the storefront for:

- `page_view`
- `build_view`
- `viewer_3d_open`
- `configurator_start`
- `add_to_cart`
- `checkout_start`
- `purchase`
- `newsletter_signup`
- `contact_submit`
- `blog_view`
- `outbound_marketplace_click`

Reuse existing analytics infrastructure if present. If not present, create a minimal, well-documented abstraction rather than tightly coupling the admin UI to one provider.

## Provider integration boundaries

Create provider interfaces/adapters so future integrations can be added without changing workflow logic:

```text
SocialPublisher
AnalyticsProvider
TrackingProvider
```

The first implementation may use a safe development adapter where real OAuth credentials are unavailable, but production code must clearly distinguish:

- connected
- disconnected
- not configured
- unsupported
- failed

Do not store access tokens in plaintext. Follow the repository’s existing secrets and OAuth conventions.

## Safety and operational controls

Implement:

- Global publishing pause
- Per-channel pause
- Per-workflow pause
- Frequency limits
- Link validation
- Availability validation
- Duplicate-content guard where practical
- Audit log for generated, approved, queued, published and failed states
- Retry action for failed jobs

Do not implement automated comment replies, direct messages or current-news auto-publishing in this phase.

## UI requirements

Follow the existing FlipFlop admin visual language and components. The design should feel like a control centre:

- Clear status hierarchy
- Strong empty states
- Obvious pause controls
- High contrast
- Keyboard-accessible controls
- Visible focus states
- Responsive layout
- No emoji icons
- Use existing Lucide icons or equivalent SVG icons

The first screen should answer:

1. What is connected?
2. What is active?
3. What is scheduled?
4. What needs attention?
5. Is publishing paused?
6. Is traffic and conversion tracking working?

## Testing requirements

Add or update tests for:

- Eligible versus ineligible build detection
- Sold/unavailable build exclusion
- Template variable rendering
- Tracked URL generation
- Manual versus automatic mode
- Rotation cadence and repeat prevention
- Global pause
- Failed publication state
- Retry handling
- Analytics disconnected state
- Analytics event naming and payload validation

Run the relevant type checks, linting, unit tests and targeted end-to-end tests. Report any unrelated pre-existing failures separately.

## Delivery requirements

Before finishing:

1. Summarise the files changed.
2. Explain the implemented user workflow.
3. Explain any external credentials or provider setup still required.
4. List tests run and their results.
5. List any intentionally deferred work.
6. Do not claim that social publishing or Google Analytics is live unless it was actually configured and verified.

The implementation should leave the repository ready for later phases: Content Studio, Newsletter, Advertising and Owned Website Placements.
