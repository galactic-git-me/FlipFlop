# PRD Gap Closure Implementation Plan

## Phase 1: Data reliability + observability (in progress)
- [x] Add per-term search telemetry capture during scrape runs
- [x] Add API endpoints to inspect telemetry by source and term
- [x] Add frontend diagnostics panel for source/term result quality
- [x] Add persistent telemetry storage (DB table + retention policy)
- [x] Add source health scoring + auto backoff policy

## Phase 2: Demand intelligence
- [x] Integrate external demand signals scaffold (Reddit live + Google Trends/Steam adapters stubbed)
- [x] Build demand-normalized pricing multipliers per component tier

## Phase 3: Compatibility intelligence
- [x] Explicit compatibility rules engine foundation (socket/memory/PSU/headroom)
- [x] Confidence score + hard-fail incompatibility reasons in wizard

## Phase 4: Autonomous playbook evolution
- [x] Nightly playbook proposal generation from sold-flip outcomes
- [ ] Human-approval lane with rollback + A/B scoring

## Phase 5: Closed-loop orchestration
- [x] End-to-end autonomous loop orchestration with checkpoints
- [ ] Outcome capture + retraining triggers

## Current deliverables (this session)
- Backend telemetry API:
  - `GET /api/search-telemetry/recent`
  - `GET /api/search-telemetry/by-source`
- Telemetry includes term-level `found`, `new`, `error`, timestamp, source, run id.
