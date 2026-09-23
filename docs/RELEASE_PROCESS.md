# FlipFlop release process

FlipFlop has two runtime environments, not three:

- DEV runs on `prometheus-ts` with hot reload and isolated local data.
- PROD runs on `andromeda-ts` as Docker services.
- Both Gem Radar browser extensions remain on `prometheus-ts` because scanning requires an open browser.

## Workflow

1. Create a branch and open a pull request into `dev` or `main`.
2. GitHub Actions runs environment checks, API tests, and the admin production build.
3. Merge approved work to `main`.
4. Create a version tag, for example `v1.0.0`.
5. The release workflow verifies that the tag points to `main` and reruns checks.
6. Test the corresponding code locally in DEV.
7. Run **Actions → Deploy production**, enter the tag, and type `DEPLOY-PRODUCTION`.

Production is never deployed merely because code was pushed to `main`.

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
