# FlipFlop project instructions

These instructions apply to agents working on FlipFlop code. Follow the user's current request and the repository's actual code, configuration, and tests. If a fact below conflicts with the current implementation, inspect the discrepancy and report it; do not silently redesign the system to match this document.

## Product and scope

FlipFlop (`theflipflop.shop`) helps UK customers find, buy, receive, and later upgrade PCs. Its customer promise is **“The right PC. Without needing to become a PC expert.”** Its brand line is **“Beautiful machines, built to be admired.”** The intended experience starts with a customer's use, budget, and constraints, explains the recommendation, and offers honest fulfilment choices. An expert route and exact technical details remain available.

The latest Core Commerce & Intelligence and Storefront & Customer Experience PRDs describe a proposed evolution from fixed curated builds to dynamic Playbooks, performance envelopes, live procurement plans, true-cost pricing, and made-to-order fulfilment. They are design inputs, not evidence that every feature is already implemented. Inspect the code and current requirements before changing behavior. Preserve existing inventory, catalogue, playbooks, builds, pricing, MES, and customer data as sources of truth unless a scoped migration explicitly changes them.

For any task, finish the requested slice. Put adjacent ideas in a short follow-up note rather than implementing them without need. If a new request arrives mid-task, reconcile it with the original objective before dropping work.

## Repository orientation

At the start of a change, inspect the current branch, working tree, repository-specific instructions, package scripts, relevant routes/modules, tests, migrations, and deployment configuration. Do not infer paths, commands, services, or production topology from the PRDs. Search for an existing implementation before creating a parallel one. Preserve unrelated edits.

This monorepo includes `flipflop-admin` (Next.js), Python backend services in `pc-flipper-backend`, and separate storefront code. Inspect the specific package and its own instructions before changing it. `flipflop-admin` exposes `npm run build`, `npm run lint`, `npm run test`, and `npm run test:e2e`; run the relevant subset from that directory. Existing launch scripts, Docker Compose configurations, and PM2 documentation are environment-specific; inspect them before running services. For Next.js 16 code, consult relevant documentation in `node_modules/next/dist/docs/` before changing framework APIs or conventions, and heed deprecations. Use the exact installed versions and package manager recorded in the repository.

## Product invariants

- Playbooks express workload capabilities and hard minimums; no recommendation, substitution, or optimisation may silently go below them. Version important rules, quotes, and decisions so they can be explained and replayed.
- Recommend only sensible Save, Recommended, and Stretch choices. Do not manufacture three options or push an upgrade without a material benefit for the customer's workload. An existing PC upgrade or a Ready-to-Ship match may be the best answer.
- Keep technical compatibility, arithmetic, cost and margin floors, stock, condition eligibility, payment state, and order transitions deterministic. AI may interpret free text, classify evidence, and explain choices; it must not invent stock, prices, benchmarks, delivery promises, or finance eligibility.
- Treat supplier listings and market references as time-stamped evidence. Distinguish active asking prices from sold prices, and new from refurbished or used. Include fees, delivery, required upgrades, build labour, payment costs, warranty/return reserves, and other relevant costs in commercial decisions.
- Default to new components. Refurbished or used parts require the customer's explicit condition choice and visible warranty/condition disclosure. A New Only order cannot receive a non-new part.
- Fast Track/Priority: Amazon and Overclockers UK only; target 3 working days and default £49 premium, each subject to current eligibility, capacity, stock and configuration. Standard: approved retail suppliers, target 5 working days when eligible. Flexible: approved wider sourcing, potentially eBay/Vinted/Gumtree where permitted; communicate an estimate/range, sourcing window, progress, and failure policy, never a guaranteed fixed date. Ready-to-Ship uses real completed inventory and its own dispatch eligibility. Keep supplier pool details internal to customer copy where appropriate.
- Freeze an auditable quote snapshot before checkout. Never increase a paid customer's committed price, downgrade specifications, substitute materially, or start procurement before the configured safe-to-procure payment state without the required approval and state transition.
- Gem Hunter decisions use all-in acquisition, required work, conservative resale, fees, net contribution, risk and maximum buy price. It must not autonomously purchase beyond explicit authority or speculative-capital limits.
- Order, refund, return, and approval workflows must handle retries, duplicate events, partial failures, and reconciliation. Maintain an audit trail for consequential transitions.

## Customer experience

Use plain English first. The Find My PC journey should work without component knowledge, retain answers, skip irrelevant questions, and explain why key questions are asked. Show why money was allocated as it was, exact components or a clear substitution policy, condition, total price, delivery terms, support, and approval needs before payment. Never fabricate progress, scarcity, discounts, benchmark results, reviews, or finance approval.

Maintain a premium dark visual language with restrained orange/blue accents, NASA-inspired headings where established, real hardware imagery, and measured motion. Respect mobile layouts, keyboard use, contrast, reduced motion, and a functional fallback without heavy 3D/WebGL. Validate the rendered interface for meaningful UI changes.

## Engineering workflow

1. Identify the exact requested outcome and relevant acceptance criteria. For larger changes, state a brief implementation and verification approach.
2. Trace the existing data flow and interfaces. Follow established code conventions and prefer the smallest change that safely solves the problem.
3. Implement with clear types and bounded modules. Keep pricing, compatibility, and approval logic in one authoritative place; avoid duplicate business rules in UI and background jobs.
4. Add focused tests for meaningful rules, especially pricing, fulfilment eligibility, condition consent, payment gates, substitutions, and state transitions. Avoid tests that merely restate implementation.
5. Run relevant repository checks (tests, typecheck, lint, build, and browser/runtime validation as supported by the actual scripts). Report exactly what passed and what could not run.
6. Update the relevant docs when behavior, setup, contracts, or workflow changes. Compare completed behavior with the applicable PRD acceptance criteria; flag gaps rather than declaring a whole phase complete.

Do not introduce new infrastructure, libraries, services, or broad refactors for speculative scale. Consider API and LLM cost, maintainability, and a solopreneur's operational burden.

## Data, security, and release controls

Keep secrets out of code, logs, screenshots, commits, and client bundles. Validate external input and webhook authenticity; enforce authorization on server-side writes. Preserve persistent data with reviewed migrations and a recovery path. Handle UK currency, VAT, shipping, warranty, refund, and finance disclosures from implemented policy and provider rules; do not guess legal or commercial terms.

Use the repository's actual branching and CI rules. Prefer a scoped branch and pull request for substantive changes, with checks before merge and staging validation before a production release where those environments exist. Never infer that a push to `master` is safe to deploy. Production deployment, destructive data changes, shared-history rewrites, and live purchases require explicit authorization unless already granted for that precise action.

At handoff, report: what changed, checks actually run, any unverified behavior or material risks, and only the next step needed to finish the current objective.
