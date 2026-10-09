# FlipFlop Growth Engine — Controlled Optimisation PRD

**Parent specification:** `flipflop-growth-engine-mega-prd.md` v1.2  
**Depends on:** All preceding phase PRDs, Agent Runtime, Approval Service, Analytics and Learning  
**Release:** Controlled Optimisation  
**Primary outcome:** Allow limited autonomous recommendations and low-risk actions without giving AI unrestricted control

**Authority:** This phase governs controlled-optimisation scope and acceptance. The Master Mega-PRD governs cross-cutting rules. The Approval Service and versioned automation policies govern executable authority.

## 1. Scope

- Cross-channel campaign sequencing.
- Organic-to-paid amplification recommendations.
- Predictive audience and offer recommendations.
- Budget reallocation recommendations.
- Content calendar optimisation.
- Low-risk automatic actions within explicit policies.
- Continuous evaluation and rollback.

## 2. Explicit safety boundary

The AI may recommend or execute only actions covered by a versioned policy. It may never bypass consent, eligibility, approval, spend, margin, connector or brand rules.

Default mode is recommendation-only. Automatic action must be separately enabled per action type, channel and budget range.

## 3. Policy-controlled automatic actions

Possible low-risk actions:

- Create an internal content suggestion.
- Resize an already-approved asset.
- Generate a draft variant.
- Pause a campaign when a hard spend cap is reached.
- Stop a scheduled publication before it is sent when a source becomes invalid.
- Create a review task when performance or consent data changes.

Actions requiring approval remain manual:

- Public publication.
- Newsletter send.
- Paid budget increase.
- New audience activation.
- High-value discount.
- Loyalty balance change.
- Material claim or price change.

## 4. Agent runtime controls

Each run has tool permissions, maximum duration, token/cost budget, retry limit, PII policy, model fallback, output schema, confidence threshold and escalation route. Side effects require idempotency keys and confirmation.

## 5. Optimisation workflow

1. Detect an opportunity from validated observations.
2. Produce a recommendation with evidence, expected impact, cost and risk.
3. Validate against policy, consent and profitability services.
4. Request approval if required.
5. Execute only the approved action.
6. Monitor result and rollback/stop if guardrails are breached.
7. Record outcome and human feedback.

## 6. Acceptance criteria

- Recommendation explains evidence and confidence.
- Policy prevents actions outside configured scope.
- Automatic actions are fully auditable.
- Every external side effect is idempotent.
- Budget and discount caps cannot be bypassed by an agent.
- A user can pause all optimisation immediately.
- A failed action is visible and resumable without duplication.
- The system distinguishes predictive recommendations from causal claims.

## 7. Launch gate

Run in shadow mode first. Enable automatic actions only after a defined observation period with zero policy bypasses, zero duplicate side effects and acceptable agent cost/error rates.
