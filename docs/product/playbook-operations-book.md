# The Playbook: operational book

**Decision:** 15 October 2026. The Playbook tab in Curated Builds is the central
operational workspace. Its identity is always a customer-type × budget matrix.
Pages change the information in the cells, not the identity or layout of the book.
Catalogue and listing-image intake are supporting tools, not separate sources of
commercial truth.

## Pages

### Extension market discovery

The extension obtains managed build searches from
`GET /api/gem-radar/playbook-market-searches`. The feed follows active parent
Playbooks and their current suggested/approved components, falling back to the
authored default when no offer exists. It currently contains 24 cells, not a
hard-coded 28. Each cell gets a broad CPU/GPU/RAM/storage query and a narrower
motherboard query, with role-scoped ASIN/CPK tags when known and a structured
cell/BOM fingerprint. Tags describe the search target; they never establish a
returned listing's identity by themselves.

FlipFlopXtension Settings can sync these searches, and manual/scheduled sweeps
refresh them before scanning. Custom searches and disabled choices survive.
All ten supported Standard vendors supply live observations; eBay also supplies
separate sold-page captures. Retired AliExpress and Flexible-only Vinted are
excluded. `POST /api/gem-radar/playbook-market-captures` appends unapproved
cell-scoped candidates to the existing market review, deduplicated by source
identity and merged only across the same BOM and a 24-hour capture window.
Unknown postage, absent sold markers, best-offer ambiguity, wrong condition or
specifications remain blocked. Repeated searches cannot invent additional sold
samples. Capture never approves a market price or publishes a product.

This is implemented and packaged for DEV. Authenticated browser collection from
each vendor, and deployment of both the API and extension to LIVE, remain
separate verification/release work.

1. Recommended build: authored name and sourced component recommendation.
2. Market and target pricing: approved selling price, proposed Standard price,
   exact-build sold evidence, active-market comparison and walk-away threshold.
3. Costs, profit and delivery: Fast Track, Standard and Flexible prices, estimated
   full costs, contribution and timing.
4. Linked listings and availability: exact suppliers, capture freshness, stock,
   item prices, postage and arrival evidence.
5. Upsell components: alternatives and fit/performance/publication eligibility.
6. Upsell commercials: the upgraded whole build's three delivery-mode prices and
   estimated profits. These are not component price deltas.
7. Listing media: exact product galleries and their selected photos/videos.
8. 3D assets: selected products and the matching approved-photo/final-model gate.
9. Performance: model benchmarks, their sources and confidence. Do not imply a
   measured complete-system benchmark.
10. Live status: stored publication, checkout-policy and availability records,
    with outstanding proposal blockers.
11. Approvals: pending exact-revision proposals and existing source/engineering
    review actions. No view grants approval or bypasses publication checks.
12. History and decisions: persisted proposals, source/policy reviews and new
    append-only operational events, including before/after evidence and actor.
13. Distribution: stored storefront publication and channel records with an exact
    `curated_build_id` link. A parent Playbook alone cannot assign a channel record
    to a budget cell. Stored publication is not a live channel poll.
14. Compatibility: recorded fit checks and relevant engineering-review tools.
15. Software: reviewed cell software and OS sourcing, using existing use-case
    defaults where no separate cell profile exists.
16. Automation health: recorded assessment time and shared scheduler/run health.

## Interaction and evidence

The page selector, previous/next controls and compact/detailed density operate on
the same matrix. Selected cell, page and density are deep-linked using `cell`,
`slice` and `detail` query parameters. Open a cell for detailed evidence and actions;
changing page retains that cell. Narrow screens scroll the matrix horizontally
inside its own region; the customer-type column and budget headings stay fixed.

The operational API at `/api/commerce-intelligence/playbook-service/book` reads
existing definitions, proposals, approved policies, segment publication records,
audit snapshots and exact channel identities. Pending and approved offers remain
separate. Segment-wide prices are not complete-build comparisons for every tier.
Missing market observations or walk-away thresholds display as unrecorded rather
than being calculated from a different cell or an arbitrary margin.

History coverage is explicitly limited to persisted events. Older overwritten
pending drafts cannot be reconstructed. New proposal recalculations, checked
publication, manual cell edits/price application, and availability withdrawals
append operational records to the existing snapshot store in the same transaction.
This change does not add new automatic repricing, withdrawal or distribution rules.

Publication, compatibility, supplier freshness, stock, commercial cost/margin,
delivery and revision checks remain under their existing deterministic services.
Workshop build counts are planning information only and never cap checkout or
sales. The book consolidates those decisions and controls; it does not waive them.

## Evidence continuation

Delivery proposals now carry the commercial engine's minimum selling price,
net operating cost, net revenue and VAT separately. Never infer operating cost
by subtracting contribution from gross revenue: that incorrectly includes VAT.
Incomplete authored BOMs withhold these figures along with the selling price.
Proposed floors are labelled separately from the last approved floor. An approved
floor is displayed only when its recorded proposal revision, policy version,
definition hash and selected component mapping still match. The approval service
records the policy version with newly approved offers.

Distribution also reads direct Ready-to-Ship product publication and saved manual
build eBay lifecycle records. Explicit build assignments may link these records
to a cell; conflicting owner/cell identities remain unassigned. Ready-to-Ship
presence is labelled separately from the curated offer and is never an assertion
that both have the same BOM. Unassigned presence is shown in a review section with
links to the owning build. No external channel is polled or changed by this view.

Build-specific sold observations are exposed as a separate review section on the
pricing page. Their counts, build identity and observation time support review;
they do not supply a cell median. Exact specification and condition evidence is
still required before such comparisons can become cell commercial evidence.

The selected cell's Pricing and Approvals pages now provide **Collect market
comparisons**, source-linked candidates, and explicit approve/reject controls.
Collection uses the existing eBay sold adapter and Browse API (complete desktop
PC category) for new-condition comparisons. CPU/GPU model and RAM/storage title
anchors must match; missing delivery prices, defective or incomplete builds and
unknown conditions are blocked. The operator must inspect the complete source
specifications, including software, and confirm actual sold prices before
approving at least three distinct sold listings. Prices cannot be typed or
overridden. Current asking prices have a separate median and sample count.

Collections and decisions are append-only `PriceQuoteSnapshot` records, scoped
to parent and cell, with reviewer identity. Approval stores a BOM fingerprint
(variant/case IDs and titles plus definition digest); changed selections and
observations older than 30 days cannot supply current market evidence. Approval
does not change published prices or checkout. **Recalculate proposals with
approved market evidence** starts the existing saved-facts rebuild; the quote
engine applies the approved sold median as its market ceiling before the usual
final publication approval. Provider failures and insufficient samples remain
visible, without borrowing another cell's or a component's market price.

Saved-facts rebuilding reuses its local catalogue-sync result. It no longer
repeats the default sync, which could otherwise perform a remote free-OS check
despite the rebuild's no-remote-collection contract.

In commercial review, **Approve & publish this build** is the final operator
approval for that exact proposal revision. The server repeats the source,
compatibility, availability, delivery-price and publication checks,
then publishes the reviewed build at its proposed Standard price, exposes only
eligible reviewed upsells, and enables checkout. The control stays disabled
while any proposal blocker remains; approval never edits component values or
prices by hand. The server may use a current schedule estimate to describe
timing, but missing or full workshop-count evidence cannot make a product
unsellable.
