# FlipFlop product documentation

- [The Playbook operational book](./playbook-operations-book.md) — central matrix,
  operational pages, evidence semantics, approvals, history and distribution.

**Status:** Canonical documentation map  
**Last reviewed:** 2026-09-29  
**Applies to:** FlipFlop, FlipFlop.shop, FlipFlopXtension, and customer support content

## Why this structure exists

The product has accumulated several useful PRDs from different stages of the business. Some describe shipped code, some describe a future platform, and some contain customer-policy language. Those purposes must remain separate so that implementation teams and support automation do not treat a proposal as a live promise.

## Document precedence

When documents disagree, use this order:

1. Applicable law and an approved published customer contract or policy.
2. [`customer-policies.md`](./customer-policies.md) for FlipFlop's intended customer commitments.
3. [`product-strategy.md`](./product-strategy.md) and [`catalogues-playbooks-and-fulfilment.md`](./catalogues-playbooks-and-fulfilment.md) for current product decisions.
4. The relevant current sub-PRD, including [`../prd/getting-ready-service-prd.md`](../prd/getting-ready-service-prd.md).
5. [`implementation-status.md`](./implementation-status.md) for what can be claimed as available now.
6. Dated or superseded PRDs for history and design rationale only.

The implementation status register never overrides product intent. It prevents unshipped intent from being represented as working software.

## Canonical document set

| Document | Purpose | Primary audience |
|---|---|---|
| [Product strategy](./product-strategy.md) | Propositions, commercial model, customer promise | Product, engineering, marketing |
| [Product image standard](./product-image-standard.md) | Originals, channel formats, review and publishing rules | Product, engineering, marketing |
| [Playbooks, catalogues and fulfilment](./catalogues-playbooks-and-fulfilment.md) | Recommendation, tagging, sourcing, and delivery rules | Product, engineering, operations |
| [Playbook commercial engine](./playbook-commercial-engine.md) | Delivery value proposition, complete segment economics, autonomous maintenance and learning requirements | Product, engineering, marketing |
| [Order and build lifecycle](./order-and-build-lifecycle.md) | State and portal behaviour from registration to aftercare | Engineering, operations, support |
| [Customer policies](./customer-policies.md) | Returns, cancellations, warranty, postage, delivery, insurance | Operations, storefront, support |
| [Implementation status](./implementation-status.md) | Evidence-based delivery status and remaining gates | Product, engineering |
| [PRD register](../prd/README.md) | Current and historical PRD classification | Product, engineering |
| [Getting Ready service PRD](../prd/getting-ready-service-prd.md) | Workshop preparation and dispatch requirements | Engineering, operations |
| [Support knowledge base](../support/customer-support-knowledge-base.md) | Approved first-line answers and escalation rules | Support chatbot, support staff |
| [Software Playbook](../playbook/software-playbook.md) | Reviewed app recommendations; only its labelled customer-safe section may be ingested | Product, operations, support chatbot |
| [UK sole-trader legal research](../research/uk-sole-trader-online-pc-retail-legal-obligations.md) | Primary-source legal/regulatory review and launch obligations | Product, operations, legal adviser |
| [Indirect-channel portal access review](../research/indirect-channel-portal-access-2026-09-29.md) | Current eBay/Vinted link-sharing guidance and printed claim-leaflet route | Operations, customer support |
| [Current Curated Playbook](../playbook/current-curated-playbook.md) | Current 24-cell build matrix and source specifications; not a price, stock, or publish approval | Product, buying, engineering |
| [Shared 3D asset requirements](../playbook/shared-3d-asset-requirements.md) | Deduplicated selected-build asset candidates and links to the live variant queues | Product, 3D production, engineering |

## Required update process

For every material product change:

1. Update the relevant strategy, policy, lifecycle, or sub-PRD decision.
2. Update implementation status separately when the behaviour is actually delivered and verified.
3. Update the support knowledge base only when the answer is safe to give customers.
4. Record the review date and source evidence.
5. Keep draft or gated functionality labelled as such everywhere.

## Chatbot ingestion rule

The support chatbot may ingest only documents or sections marked `Customer-safe: yes`. It must prefer the support knowledge base over PRDs, attach the source document/version to each answer, and refuse to invent dates, prices, stock, order status, warranty outcomes, or legal conclusions. Order-specific answers require authenticated live data.
