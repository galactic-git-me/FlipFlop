# FlipFlop release process

FlipFlop has two runtime environments, not three:

- DEV runs on `prometheus-ts` with hot reload and isolated local data.
- PROD runs on `andromeda-ts` as Docker services.
- Both Gem Radar browser extensions remain on `prometheus-ts` because scanning requires an open browser.

## Workflow

1. Create a feature branch from the latest `origin/dev` and open a pull request
   into `dev`. GitHub requires pull requests and the `checks` status on both
   `dev` and `main`; force pushes and branch deletion are disabled. Keep the
   branch current with its base before merging.
2. Wait for the DEV validation workflow and pull-request checks to pass. Merge
   the change into `dev`.
3. Run the DEV application from that exact `dev` commit and verify the affected
   user journey against DEV data and services. The launcher safely
   fast-forwards a clean local `dev` from `origin/dev`; otherwise it reports
   the commit and preserves local work. The API health response and admin
   header expose their running source commits and flag mismatches.
4. Open a production pull request whose complete tracked source tree matches
   the validated DEV tree. CI rejects application, migration, configuration,
   or data differences from DEV while ignoring generated build and local tool
   artifacts. Merge only after the DEV runtime check is recorded.
5. Create a version tag on that DEV-to-main merge commit, for example
   `v1.0.0`. Release checks require the tag to be on `main` and its commit to
   be associated with the merged production pull request and its successful
   DEV-parity CI run.
6. Run **Actions → Deploy production**, enter the tag, and type
   `DEPLOY-PRODUCTION`. The deploy workflow reruns API checks and builds the
   admin bundle before connecting to production. The deployment stamps the
   release commit into API and admin builds and verifies the live API reports
   that exact commit before it reports success.

Production is never deployed merely because code was pushed to `main`.
The DEV runtime check happens before promotion; CI build success alone is not
evidence that the live DEV journey was exercised. GitHub branch protection on
`main` requires pull requests and the `checks` status check, including for
administrators, so a direct production push cannot bypass this path.

## Secrets

GitHub Secrets contain deployment-only values such as the restricted Andromeda
SSH key. Application runtime secrets remain in environment-specific secret
files on the target machines and are never committed. Local `.env` files are
ignored; `.env.example` files document names without values.

Scanning uses production eBay API credentials in both environments. Listing
credentials remain sandbox-only in DEV and production-only in PROD. Stripe
test and live credentials are separate modes. Delivery-insurance and Post2Go
credentials remain marked as DEV credentials until production credentials are
created.

## Required GitHub configuration

The repository administrator must configure these Actions secrets:

- `ANDROMEDA_HOST`
- `ANDROMEDA_USER`
- `ANDROMEDA_PORT` (optional; defaults to `22`)
- `ANDROMEDA_SSH_KEY`
- `ANDROMEDA_HOST_KEY`
- `FLIPFLOP_EXTENSION_DISPATCH_TOKEN`

The `production` environment should be enabled even on plans where required
reviewers are unavailable. The explicit workflow confirmation remains the
final deployment gate.

The Andromeda checkout must contain `FlipFlop.shop` beside the main checkout
or at `$REPO_DIR/FlipFlop.shop`; the production compose build uses that sibling
repository as the storefront build context. Install the Caddy site blocks from
`deploy/andromeda.Caddyfile.example` before the first full-stack deployment.
