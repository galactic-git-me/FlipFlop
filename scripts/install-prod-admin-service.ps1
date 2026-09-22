# Installs flipflop-admin's PROD instance as an always-on Windows Service on
# port 4312, pointed at Andromeda's real backend (https://www.theflipflop.shop).
# This is the "keep production always running" piece the whole dev/prod
# split exists for -- scheduled scrapes need a live admin to scrape into.
#
# Runs a production build (next build && next start), matching how LIVE mode
# always worked in the old start-all-servers.ps1 (Build-Admin). Uses its own
# .next build output (NEXT_DIST_DIR) so it never collides with the
# simultaneously-running DEV admin instance sharing this checkout.
#
# No git branch switch here -- Andromeda deploys from its own separate
# checkout independent of this machine's local branch (see the dev/prod
# split plan's git-decoupling section); this only builds/serves the admin
# frontend from whatever's currently checked out locally.
#
# Requires elevation (installing a service needs admin rights).
$ErrorActionPreference = 'Stop'
Start-Transcript -Path (Join-Path $env:TEMP 'install-prod-admin-transcript.log') -Force
$repo = Split-Path -Parent $PSScriptRoot
$admin = Join-Path $repo 'flipflop-admin'
$npmExe = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmExe) { $npmExe = (Get-Command npm -ErrorAction Stop).Source }
$logDir = Join-Path $env:LOCALAPPDATA 'FlipFlop\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "[*] Building PROD admin (next build)..." -ForegroundColor Cyan
Push-Location $admin
try {
    $env:NEXT_DIST_DIR = '.next-prod'
    & $npmExe run build
    if ($LASTEXITCODE -ne 0) { throw "PROD admin build failed" }
} finally {
    Remove-Item Env:\NEXT_DIST_DIR -ErrorAction SilentlyContinue
    Pop-Location
}

nssm install FlipFlopProdAdmin $npmExe "run start -- -p 4312 -H 0.0.0.0"
nssm set FlipFlopProdAdmin AppDirectory $admin
nssm set FlipFlopProdAdmin Start SERVICE_AUTO_START
nssm set FlipFlopProdAdmin AppStdout (Join-Path $logDir 'prod-admin.log')
nssm set FlipFlopProdAdmin AppStderr (Join-Path $logDir 'prod-admin.log')
nssm set FlipFlopProdAdmin AppRotateFiles 1
nssm set FlipFlopProdAdmin AppRotateBytes 10485760
nssm set FlipFlopProdAdmin AppEnvironmentExtra "NODE_ENV=production`r`nNEXT_DIST_DIR=.next-prod"
nssm restart FlipFlopProdAdmin

Start-Sleep -Seconds 3
sc query FlipFlopProdAdmin
Stop-Transcript
