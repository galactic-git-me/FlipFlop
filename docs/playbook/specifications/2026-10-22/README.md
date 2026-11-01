# Playbook specification review 0.2.1

Capability-led model and narrowed range scope approved; exact products, prices and workload claims remain gated. Observed 22 October 2026. Customer-safe: no.
Nothing here replaces active definitions, authorises procurement, publishes prices or enables automation.

Start with [assessment and decisions](assessment.md), then the generated [matrix](matrix.md).
`specifications.json` is the sole authored source for this proposed specification system;
`schema.json` defines its contract. `render_validate.py` validates and renders the matrix.
The current operational source remains `flipflop-api/data/curated_build_definitions.json`.
This deliberate draft branch of the specification is not a second live authority.

The matrix is customer use case × capability tier (Essential, Enhanced, Advanced), with benefit-led
names per use case. Budget filters viable offers; selling price is derived from configuration, full
cost and comparable market evidence. Schema 2.0.0 replaces ambiguous `tier` with `capability_tier`
and an explicit `legacy_tier` mapping. All 24 IDs remain stable. The owner approved this direction
and the narrowed scope recorded in 0.2.1. Individual profiles, tests, exact BOMs, margin changes
and prices remain proposed.
The immutable [0.1.0 snapshot](history/0.1.0.json) preserves the previous specification/schema/evidence;
old price experiments are retained as history and excluded from capability definitions.

Evidence and review:

- [Evidence register](evidence.json) records provenance and limits.
- [Hardware research](../../../research/2026-10-22-playbook-hardware-evidence.md).
- [Sourcing research](../../../research/2026-10-22-playbook-sourcing-evidence.md).
- [Market audit](../../../research/2026-10-22-playbook-market-audit.md).
- [Evolution and approvals](workflow.md), [append-only decisions](changes.jsonl).
- [Validation results](validation.json): structural checks are distinct from physical testing and commercial approval.

Run from repository root: `python docs/playbook/specifications/2026-10-22/render_validate.py`.
This only writes derived documents within this dated draft directory. No application imports these files.

## Publication work in progress

Specification 0.2.1 records the owner-approved narrowed scope. The current source is still a draft and is not a live runtime replacement. The reproducible read-only assessment command is `flipflop-api/.venv/Scripts/python.exe flipflop-api/scripts/assess_reconstructed_playbook.py`. It loads this exact specification and checks selected catalogue offers without persisting approvals or changing storefront offers. Reports are under `release/reconstructed-readiness-*.json`.

Sold collection now has deterministic checks for observed condition, primary delivery rows, split price ranges, hidden Best Offers and transaction-date freshness. Use `scripts/collect_playbook_sold_research.py` from `flipflop-api` for bounded public-card research exports; those exports still need full listing-detail and exact-BOM review and cannot approve a market price.
