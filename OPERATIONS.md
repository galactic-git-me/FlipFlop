# Operations router

- `startup.ps1`, `start-*.sh`, and `start-*.ps1` — local service startup and developer launch flows.
- `docker-compose*.yml` — local, development, production, autosync, and Gem Radar containers.
- `scripts/` — diagnostics, sync, refresh, deployment, monitoring, and recovery utilities.
- `.github/workflows/cleanup-merged-branch-worktree.yml` and `scripts/cleanup-merged-branch-worktree.ps1` — remove a clean local branch worktree after its PR merges into `dev` or `main`; requires the Windows runner described in `docs/operations/merged-worktree-cleanup.md`.
- `deploy/` — production compose and deployment assets.
- `ecosystem.config.js` — PM2 process definitions.
- `DEV_SETUP.md`, `DOCKER_SETUP.md`, `DEPLOYMENT_GUIDE.md`, and `LAUNCH_CHECKLIST.md` — environment and release procedures.
