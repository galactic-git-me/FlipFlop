## PM2 Services

| Port | Name | Type |
|------|------|------|
| 18000 | gemradar-api-18000 | Python (FastAPI/uvicorn, SQLite-backed gem_radar_standalone) |
| 3002 | flipflop-admin-3002 | Next.js (admin dashboard) |

**Terminal Commands:**
```bash
pm2 start ecosystem.config.cjs   # First time
pm2 start all                    # After first time
pm2 stop all / pm2 restart all
pm2 start gemradar-api-18000 / pm2 stop gemradar-api-18000
pm2 start flipflop-admin-3002 / pm2 stop flipflop-admin-3002
pm2 logs / pm2 status / pm2 monit
pm2 save                         # Save process list
pm2 resurrect                    # Restore saved list
```

Auto-start on boot is registered via `pm2-startup install` (pm2-windows-startup) — the saved
process list (`pm2 save`) is resurrected automatically at Windows login, no manual step needed
after a reboot. Re-run `pm2 save` any time the ecosystem config changes.
## Agent skills

### Issue tracker

Issues live in this repository's GitHub Issues and are managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default canonical triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository using root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.
