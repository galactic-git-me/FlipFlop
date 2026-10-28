# FlipFlop product strategy

**Status:** Current strategy  
**Last reviewed:** 2026-10-22
**Customer-safe:** Partly; customer wording must come from the support knowledge base

## Product thesis

FlipFlop sells Playbook-aligned PCs and PC transformation services. Every recommendation and sellable machine must trace to a customer use case and capability cell, or demonstrate all required workload capabilities of that cell.

The Playbook is a matrix:

- rows are customer types or use cases;
- columns are capability levels (Essential, Enhanced and Advanced), with benefit-led names within each use case;
- one segment means one cell in that matrix;
- each cell defines customer outcomes, measurable workload acceptance criteria, required capabilities, sensible compromises, recommended software, and two appropriate optional upgrades.

**Owner-approved product direction, 22 October 2026:** capability defines the second dimension;
customer budget filters suitable offers and selling price is a derived commercial result. Choose the
least expensive balanced build that reliably meets the required capability, then establish a viable
price from full costs and comparable market evidence. Do not add parts merely to fill a price band.
A higher tier needs a meaningful customer benefit, not just a higher benchmark, capacity or price.
Not every row needs three offers. Workload branches such as gaming are explicit; a higher tier is not
automatically a superset for every specialist application.

The [versioned specification draft](../playbook/specifications/2026-10-22/README.md) records the
capability profiles and legacy cell mapping. Its individual names, tests, BOMs, tier dispositions and
prices remain proposals. Operational code still uses Budget/Mid-range/High-end; migration is planned,
not delivered. Retain cell IDs, existing software/order associations and existing commercial floors
until a separately reviewed implementation changes them. This decision does not approve any offer.

The commercial advantage is trusted advice. FlipFlop should explain why money has been allocated in a particular way and warn customers when a requested component is poor value for their stated use.

## Core propositions

### Ready-to-Ship

A completed and tested machine sold as-is. It is aligned to one Playbook cell by meeting its required workload capabilities and compatibility constraints; a higher benchmark alone is insufficient. It may originate from a manually specified build, an uploaded build file, or an AI-proposed opportunity using the full catalogue and approved marketplace opportunities.

### Curated-for-you

The customer answers plain-English questions. FlipFlop selects the matching Playbook cell and offers a pre-designed, compatible build with a small set of approved choices. Each component category may expose the two most appropriate Playbook-authored upgrades selected for usefulness, popularity, and price point.

### Made-by-you

The customer starts with an empty 3D build and chooses from the same Curated catalogue used by Playbook builds. There is no separate Custom catalogue. The recommendation engine actively explains compatibility, value, and allocation. Customers may override advice where the build remains safe and compatible. The system must clearly explain when reallocating spend would better meet their stated use.

### Flip Refresh

Working name for the send-in transformation service: inspect an existing customer PC, agree work and take payment before shipment, start the operational clock when the PC is received, then upgrade, clean, cable-manage, case-transplant or beautify it according to the relevant Playbook cell and delivery mode. The system must be able to recommend that no work is worthwhile. Final public name remains a product decision.

### Responsible flips

FlipFlop may buy undervalued PCs, improve them with targeted components and a strong visual finish, and resell them as Ready-to-Ship machines. Components recovered from potential flips may supply Ready-to-Ship builds or Flexible-delivery customer builds only, and still must satisfy condition, compatibility, benchmark, disclosure, and warranty rules.

## Five customer promises

1. We choose the complicated parts for you.
2. Your PC does not have to look like everyone else's.
3. Custom built does not have to mean a long wait.
4. We show where your money is going.
5. We do not encourage you to waste money.

These are operating rules, not just homepage copy. The storefront, chatbot, configurators, admin reviews, and build documents must provide evidence for them.

The direct storefront must make the delivery choice part of the proposition: for an eligible Playbook build, customers can pay for Fast Track and a shorter, prioritised build, choose Standard, or choose Flexible for a lower price and longer wait. Show the price and realistic delivery range side by side, explain the trade-off in plain English, and only show choices that current sourcing and workshop evidence supports. This is a core commercial distinction, not a checkout footnote.

## Software and AI services

Software is part of each Playbook cell even where the catalogue is shared. Customers see a recommended app set for their use case, an indicative time-saving estimate, and the ability to add or remove allowed apps until components are ordered. FlipFlop's selection and installation service is included with the build at no extra charge; any separately licensed third-party software must be identified and priced before the customer commits.

Optional paid services may include:

- Windows 11 Pro where a valid licence is supplied or purchased;
- a tailored productivity application setup;
- a locally installed assistant such as Hermes or an approved alternative;
- a personal knowledge and memory workspace;
- a local language model setup on suitable hardware;
- approved automations explained before purchase.

AI services require explicit scope, price, hardware eligibility, privacy disclosures, credentials handling, and human review. Local-model offers that need GPU acceleration require at least 12 GB VRAM unless a reviewed model-specific profile says otherwise.

## Channel strategy

The direct storefront supports the full guided experience, software and AI choices, portal linkage, and upsells. Indirect channels should use native configurators only where they can accurately represent FlipFlop's rules. Otherwise:

- list clear Ready-to-Ship products;
- list curated fixed configurations where commercially useful;
- direct custom builds to the direct channel only where marketplace terms permit;
- never use marketplace messaging to circumvent channel rules;
- provide a compliant post-purchase claim path or a physical QR leaflet when direct links are restricted.

## Commercial principles

Delivery flexibility is a core commercial proposition: customers choose between paying more for an eligible Fast Track build, Standard delivery, or waiting longer for a genuinely cheaper Flexible quote for the same selected specification. Show this choice while browsing and configuring, not only at payment. Savings and dates must come from current validated quotes; never advertise an unevidenced discount or guaranteed date.

The Playbook is the central commercial authority for each segment: core build, eligible upgrades and services, complete prices by delivery mode, profit constraints, promotions, supplier eligibility and evidence-backed recommendations to change or retire offers. Shared services calculate these decisions from versioned Playbook policy; storefronts and workers must not maintain competing pricing rules. See [commercial engine requirements](./playbook-commercial-engine.md). This is required behaviour, not a claim that the complete engine is operational.

- Customer payment funds made-to-order procurement only after the payment-safe gate.
- Prices include standard outbound postage and delivery insurance where offered; these costs belong in the price model.
- True cost includes parts, labour, packaging, payment fees, delivery, insurance, returns allowance, warranty reserve, expected failures, and overhead.
- The versioned Playbook owns every segment's core and upsell prices, delivery-mode prices, margin floors, and promotion constraints. Fast Track, Standard, and Flexible must each be viable for the relevant segment after their distinct sourcing, priority, and delivery costs; a promotion is only recommended where the complete offer remains within its approved margin floor.
- Automated market learning should use first-party storefront searches and outcomes, FlipFlop orders/returns, observed supplier prices/availability/sales-rank signals, and approved external demand/trend sources where collection and use are permitted. It proposes evidence-backed Playbook updates and emerging use-case opportunities; deterministic cost, stock, compatibility, and margin rules gate offers, and changes to live prices or promises require the configured approval.
- A 5% warranty reserve is the provisional starting assumption for new builds. It must be recalibrated from actual claims and repair costs; it is not an industry rule.
- The provisional reserve becomes releasable 12 months after recorded delivery, subject to open claims and accounting policy.
