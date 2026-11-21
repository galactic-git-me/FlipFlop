# Codex Chrome listing worker

API channels: FlipFlop.shop, eBay and seller-authorized Amazon SP-API. Other
selectable channels enqueue durable Chrome jobs. Initial publishing and the
relisting scheduler use the same queue, canonical saved price/copy, reviewed
photographs, FAQs and build identity. No credentials are included in seller packs.

The API runs on Andromeda. The worker runs on the logged-in Windows desktop
with Chrome, Node 20.12+ and Codex CLI. It polls every 15 seconds and
runs one job at a time in a dedicated persistent Chrome profile. It does not
control unrelated tabs. The machine must be awake and the Windows user logged in.

## Setup

1. Apply migration `20261030_0001`. Set a strong, dedicated
   `CROSS_LISTING_WORKER_KEY` in `runtime/browser-worker.env` on the API host;
   the production compose file reads that optional file. Recreate the API
   container after changing it. Never reuse the admin key.
2. Install the desktop task with `install-worker.ps1 -Api
   https://www.theflipflop.shop/api/cross-listing/browser-worker -WorkerKey
   (Read-Host 'Worker key' -AsSecureString)`. This stores the queue key using
   Windows DPAPI and registers a task for the current user's interactive logon.
   Pass `-AdminDirectory` if the admin's installed Playwright package is elsewhere.
3. Add the variables in `credentials.env.example` to the desktop's private
   `.env.local` and set the values there. Pass `-CredentialsFile` to the
   installer to select that file; the installed config records only its path.
   Do not put vendor passwords in API requests, chat, the repository or public
   `NEXT_PUBLIC_*` variables. Amazon SP-API credentials belong on the API host.
4. Start `FlipFlop Codex Browser Listings`, or run `start-worker.ps1`.
   Use `-Once` to check the connection without polling forever.

The worker uses the existing admin Playwright dependency and installed Google
Chrome; no third-party aggregator, browser extension or marketplace SDK is added.
Codex reuses its installed CLI authentication. Each job disables shell execution,
unrelated user MCP configuration and web search; its only
browser/credential tools come from the scoped `browser-mcp.mjs` server.

## Credentials and browser boundaries

The `env_login` tool reads only the selected vendor's username/password keys
from the configured desktop `.env.local` and fills them directly into the
vendor's login fields. Values are never returned to the model, seller pack,
API, command arguments or logs. Missing variables, MFA, CAPTCHA, onboarding,
fees, seller restrictions and unsupported delivery choices block the job.
The agent may not register accounts, approve new permissions, pay fees, bypass
restrictions or enable collection/pickup.

Vinted/Marketplace eligibility for a business selling complete PCs is not
assumed. Google Shopping needs Merchant Center setup and product approval;
a submitted feed or pending moderation is not a live listing. The worker checks
these restrictions and reports them. Browser automation does not grant vendor
permission or guarantee that a vendor will accept a product.

## Results and recovery

Before a listing write, the worker rechecks its lease and current saved build.
It inspects the seller account: update an active identity, relist an ended one,
or create only after confirming it is missing. It reads the resulting item
page and verifies title, price and availability before saving the vendor URL/ID.
The pre-built page links each confirmed URL through its vendor logo in a new tab.

The next relisting date/count advance only on confirmed success. Failures retain
the previous confirmed URL and due date. A lost heartbeat expires after five
minutes into `needs_review`, never an automatic blind retry. Resume/reconcile
from Cross-listing after resolving the blocker. Pending jobs deduplicate by
channel listing, including blocked and interrupted work.

The API stores job status and audit events. The worker removes temporary packs,
downloaded photos and result files after a run; its Chrome profile remains local.
Revoke the worker key and remove the local vendor variables to disable access. Remove the scheduled
task to disable automatic startup. Do not delete browser/job state to work around
an uncertain publication: inspect the vendor first.
