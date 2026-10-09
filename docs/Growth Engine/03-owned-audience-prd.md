# FlipFlop Growth Engine — Owned Audience and Newsletter PRD

**Parent specification:** `flipflop-growth-engine-mega-prd.md` v1.2  
**Depends on:** Marketing MVP, Editorial Expansion, Consent Service, Customer Service  
**Release:** Owned Audience  
**Primary outcome:** Create and send a consent-safe weekly newsletter and lifecycle communications

**Authority:** This phase governs owned-audience scope and acceptance. The Master Mega-PRD governs cross-cutting rules. Provider-specific implementation briefs govern concrete email-provider details.

## 1. Scope

### Included

- Weekly newsletter planning and AI drafting.
- Article, build, product, review and offer sections.
- Consent-aware audience selection.
- Preview, approval, scheduling and sending.
- Bounce, complaint, unsubscribe and suppression handling.
- Tracked links and newsletter performance.
- Abandoned-cart event capture, without automatic discounts in the first owned-audience release.
- Holiday, no-content and provider-outage behaviour.

### Excluded

- Paid advertising.
- Automatic high-value incentives.
- Loyalty balance changes.
- Sending to customers without an approved purpose and consent/lawful basis.

## 2. Audience and consent contract

The Consent Service is authoritative. Each audience evaluation checks purpose, status, channel permission, suppression, freshness, frequency cap and jurisdiction.

Consent records include purpose, status, notice version, source, timestamp and connector propagation state. Withdrawal stops new sends and queues removal from providers.

## 3. Newsletter workflow

1. Newsletter Agent reviews approved articles, products, builds, campaign priorities and customer lifecycle rules.
2. It proposes the edition structure, subject and preview text.
3. It creates copy and selects approved media.
4. It generates tracked links.
5. It validates consent, suppression, accessibility, sender identity, links, images and plain-text fallback.
6. Michael reviews the exact audience and rendered preview.
7. Approved edition is scheduled or sent.
8. Delivery, bounce, complaint, unsubscribe, click and conversion events are reconciled.

No-content or holiday default: skip and notify rather than send filler content.

## 4. Newsletter lifecycle

`draft → content_ready → compliance_review → approval → approved → scheduled → sending → sent/partially_sent/failed`.

An approved content or audience change creates a new revision and requires reapproval.

## 5. Deliverability requirements

Define sender identity, domain authentication, provider, API scopes, bounce handling, complaint suppression, unsubscribe propagation, frequency caps, template versions, client rendering tests and provider outage recovery.

## 6. Data model

- `newsletter_edition`
- `newsletter_revision`
- `newsletter_section`
- `newsletter_audience_snapshot`
- `delivery_event`
- `consent_record`
- `suppression_event`
- `tracking_link`
- `newsletter_performance_snapshot`

## 7. Acceptance criteria

- Only consent-eligible recipients are included.
- Suppressed recipients cannot be sent a message.
- The exact audience, content and links are visible before approval.
- Unsubscribe, bounce and complaint events update suppression.
- Duplicate send is prevented on retry.
- A failed or skipped edition is explicit and actionable.
- Newsletter clicks and website sessions are measured without claiming causality.

## 8. Launch gate

Run a controlled test edition with a seeded audience, test inboxes, bounce/complaint fixtures, unsubscribe propagation, rendering checks and provider outage simulation.
