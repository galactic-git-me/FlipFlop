# Gem Radar automatic scanning

The DEV and LIVE extensions remain browser extensions because marketplace
scanning requires a real Chrome session. They are nevertheless unattended:
Windows starts each extension in its own minimized Chrome profile, and the
extension performs a fixed twice-daily sweep.

| Target | Local time (Europe/London) | Backend |
| --- | --- | --- |
| DEV | 04:00 and 16:00 | `http://127.0.0.1:4311` |
| LIVE | 10:00 and 22:00 | `https://www.theflipflop.shop` |

Build both targets from `C:\Users\mclar\CODING\FlipFlopXtension`:

```powershell
npm run build:dev
npm run build:live
```

Install the reversible scheduled tasks from the FlipFlop root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-gem-radar-scheduled-tasks.ps1
```

The tasks run in the logged-in Windows session, start at boot, and use
`StartWhenAvailable` so a missed time is run when the PC becomes available.
DEV and LIVE use separate Chrome profile directories and separate extension
storage. Their scan locks now coordinate with their own backend rather than a
shared localhost coordinator.

If anti-bot verification appears, the corresponding minimized profile may
need a one-time human verification. The scheduled task does not bypass that
marketplace requirement.

Remove the tasks with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall-gem-radar-scheduled-tasks.ps1
```
