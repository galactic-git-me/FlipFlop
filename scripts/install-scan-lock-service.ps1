# Optional coordinator for machines that do NOT run the local DEV API.
# The full DEV API owns port 4311 and already exposes the scan-lock endpoints.
# Never install this service alongside FlipFlopDevBackend on the same machine.
#
# Requires elevation (installing a service needs admin rights).
$ErrorActionPreference = 'Stop'
if (Get-Service FlipFlopDevBackend -ErrorAction SilentlyContinue) {
    throw 'The DEV API owns port 4311 and already provides scan coordination.'
}
if (Get-NetTCPConnection -LocalPort 4311 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 4311 is already in use; refusing to install a conflicting coordinator.'
}
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
