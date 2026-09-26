# vNext implementation status

The two vNext PRDs in `docs/prd/` set the product direction. This file records delivered work and the remaining gates. Existing order, payment, catalogue, playbook, and MES data remain authoritative.

## Delivered foundation

- `POST /api/recommendations/envelope` accepts primary use, budget, condition policy and relevant workload answers.
- A deterministic service returns a version-labelled, SKU-free performance envelope with hard minimums, preferred memory/storage targets and customer-facing budget reasoning.
- The endpoint is explicitly `requirements_only`: it cannot be used as a quote or to initiate checkout.

## Next implementation slices

1. Version and persist customer requirements, Playbook rules and envelope decisions. Add the guided Find My PC journey and recommendation reveal.
2. Connect approved SKUs and compatibility rules; form compliant BOM candidates and ready-to-ship matches. Suppress recommendations when evidence is missing.
3. Add supplier offers, condition policies, landed costs, full cost stack, contribution floors, market evidence and immutable quote snapshots.
4. Gate Priority, Standard and Flexible by actual suppliers, stock, workshop capacity and sourcing policy. Add honest customer ETA ranges and approval events.
5. Connect payment safe-to-procure state, refunds, upgrade assessment and the customer tracking portal. Extend Gem Hunter scoring with all-in cost and max-buy evidence.

No vNext recommendation should be sold until the procurement, market, margin, fulfilment and payment gates above are complete and verified.
