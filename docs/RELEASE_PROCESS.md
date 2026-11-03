# FlipFlop release process

FlipFlop has two runtime environments, not three:

- DEV runs on `prometheus-ts` with hot reload and isolated local data.
- PROD runs on `andromeda-ts` as Docker services.
- Both Gem Radar browser extensions remain on `prometheus-ts` because scanning requires an open browser.

## Workflow

1. Create a feature branch and open a pull request into `dev`. Pull requests
   into `main` are rejected by CI.
2. Wait for the DEV validation workflow and pull-request checks to pass. Merge
   the change into `dev`.
3. Run the DEV application from that exact `dev` commit and verify the affected
   user journey against DEV data and services. Record the tested commit SHA in
   the release notes or pull request.
4. Open a pull request from `dev` to `main`. CI verifies that the proposed
   commit is already present in `dev`; pull requests from feature branches are
   rejected. Merge only after the DEV runtime check is recorded.
5. Create a version tag on that DEV-to-main merge commit, for example
   `v1.0.0`. Release checks require the tag to be on `main` and its commit to
   be associated with the merged DEV-to-main pull request.
6. Run **Actions → Deploy production**, enter the tag, and type
   `DEPLOY-PRODUCTION`. The deploy workflow reruns API checks and builds the
   admin bundle before connecting to production.

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
