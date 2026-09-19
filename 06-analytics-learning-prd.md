# FlipFlop Growth Engine — Analytics and Learning PRD

**Depends on:** MVP, Editorial, Newsletter, Offers, Paid Acquisition, Order Service  
**Release:** Analytics and Learning  
**Primary outcome:** Turn observed growth activity into clearly labelled attribution, experiments and evidence-backed recommendations

**Authority:** This phase governs analytics and learning scope and acceptance. The Master Mega-PRD governs cross-cutting rules. Order, consent and analytics services govern source records.

## 1. Scope

- Event collection and identity resolution.
- Tracking links and conversion events.
- First-touch, last-touch, time-decay and assisted reporting.
- Revenue and contribution-profit allocation.
- Refund and delayed-settlement reconciliation.
- Experiment definitions and holdouts.
- Learning observations and confidence.
- Recommendations for future content, channels, offers and campaigns.

## 2. Attribution rules

Reports must state identity basis, attribution model, channel window, data freshness and whether revenue is observed, attributed, assisted or incremental.

Default windows are configurable; initial defaults are 7 days for social clicks, 30 days for paid search, 7 days for retargeting/email clicks and 30 days for organic article clicks. View-through is disabled initially.

Anonymous events remain anonymous unless joined through an approved first-party mechanism or authenticated account.

## 3. Incrementality boundary

Ordinary attribution does not prove causation. Incremental revenue or profit may be reported only when a valid holdout, randomised experiment, geo test or documented statistical estimate exists. Otherwise use “attributed” or “associated with”.

## 4. Event model

- `conversion_event`
- `attribution_touch`
- `revenue_attribution`
- `profitability_snapshot`
- `experiment`
- `experiment_variant`
- `learning_observation`
- `insight_feedback`

Events contain source, subject reference, session/campaign identifiers, timestamp, consent state, order reference where applicable and schema version.

## 5. Experiments

Every experiment defines hypothesis, primary metric, guardrails, population, exclusions, randomisation key, variants, holdout, minimum sample, run duration, stopping rule, contamination handling and analysis method.

The system must not stop or optimise an experiment before its evidence threshold.

## 6. Learning observations

Store sample size, period, completeness, method, confounders, confidence, classification as descriptive/predictive/causal, model version and human feedback.

Example: “Build photography was associated with higher saves” is valid descriptive language; “Build photography caused more sales” is not valid without an appropriate experiment.

## 7. Acceptance criteria

- Attribution reports cannot omit model or window.
- Refunds and delayed orders revise prior attribution rather than duplicate it.
- Unattributed revenue remains visible.
- Assisted revenue is never labelled incremental.
- Experiments preserve holdout and variant identity.
- Insights display evidence, confidence and sample size.
- Human feedback can accept, reject or correct an insight.

## 8. Launch gate

Run a synthetic end-to-end dataset containing anonymous sessions, authenticated sessions, email clicks, social clicks, paid clicks, marketplace orders, refunds and unattributed sales. All totals and labels must reconcile.
