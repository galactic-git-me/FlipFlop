# Installs scan-lock-service.py as an always-on Windows Service on port 4311.
# This is the ONE permanent owner of 4311 -- DEV's full backend has moved to
# 4314 to free this port up (see scripts/start-dev-stack.ps1). Both the DEV
# and LIVE Gem Radar extensions hardcode SCAN_LOCK_COORDINATOR_URL to
# 127.0.0.1:4311 (FlipFlopXtension/src/lib/environment.ts) so they can
# coordinate scan ownership regardless of which of DEV/PROD's other local
# services happen to be running.
#
# Requires elevation (installing a service needs admin rights).
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repo 'flipflop-api\.venv\Scripts\python.exe'
$script = Join-Path $repo 'scripts\scan-lock-service.py'
$logDir = Join-Path $env:LOCALAPPDATA 'FlipFlop\logs'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "flipflop-api venv python not found at $pythonExe. Set up flipflop-api's virtualenv first (needs fastapi/uvicorn/pydantic, already app dependencies)."
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

nssm install FlipFlopScanLock $pythonExe $script
nssm set FlipFlopScanLock Start SERVICE_AUTO_START
nssm set FlipFlopScanLock AppStdout (Join-Path $logDir 'scan-lock-service.log')
nssm set FlipFlopScanLock AppStderr (Join-Path $logDir 'scan-lock-service.log')
nssm set FlipFlopScanLock AppRotateFiles 1
nssm set FlipFlopScanLock AppRotateBytes 10485760
nssm set FlipFlopScanLock AppDirectory (Join-Path $repo 'flipflop-api')
nssm restart FlipFlopScanLock

Start-Sleep -Seconds 2
sc query FlipFlopScanLock
