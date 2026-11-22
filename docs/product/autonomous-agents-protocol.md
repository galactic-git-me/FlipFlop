# Autonomous agent operating protocol

The backend has three domain workers: Demand collects and labels observations; Pricing computes evidence-backed market ranges and emits material price-change events; Playbook consumes those events and owns compatible BOM, availability, margin, and storefront decisions. Each worker loads its procedure from `flipflop-api/app/agent_skills/<agent>/SKILL.md` and uses `app.schemas.autonomous_agents.AgentEvent` for handoffs.

## Event lifecycle

1. A collector or pricing cycle commits source evidence.
2. The producing worker writes an idempotent row in `agent_handoff_events`, with evidence references and a correlation ID.
3. Playbook validates the event and calls the existing `refresh_playbooks(..., maintain_live_offers=True)` path. This preserves the existing compatibility, commercial, stock, publication, and per-cell gates.
4. The run records its event references, skill hash, decisions, and blockers in `playbook_refresh_runs`; duplicate events do not trigger a second refresh.

Steam is collected as a monthly Steam Hardware & Software Survey snapshot. Preserve all returned categories and item rows, report each category leader, and retain publication month and source/parser provenance. Its percentages describe survey prevalence, not sales.

## Policy and evidence boundaries

- Autonomous price changes are allowed within the configured movement cap (10% default, 25% absolute maximum) and only when the existing commercial gate proves at least 15% contribution margin.
- Component socket, memory, case/form-factor, and other compatibility checks remain deterministic gates owned by existing Playbook services.
- Fast Track and Standard delivery limits and Flexible auction/fallback calculations must be enforced by the sourcing implementation; a skill statement alone does not establish that capability.
- External demand is currently recorded as linked evidence, but the current deterministic candidate selector does not yet consume the normalized external signals. The system must not claim that external demand changed a BOM until that selector is implemented.
- A component subtotal is not a full-PC market valuation. A full-build valuation needs comparable full-build evidence or a clearly labeled estimate.
- Failed sources, stale stock, insufficient samples, failed compatibility, or missed margins become explicit blockers. Workers must not fill gaps with invented values or bypass existing publication controls.
