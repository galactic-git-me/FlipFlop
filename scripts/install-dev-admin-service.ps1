# Installs flipflop-admin's DEV instance as an always-on Windows Service on
# port 4315 (NOT 4312 -- that's reserved for the always-on PROD admin
# instance, see install-prod-admin-service.ps1). Runs `next dev` so source
# edits are picked up live, same as local development always has.
#
# Uses its own .next build output (NEXT_DIST_DIR) so it never collides with
# the simultaneously-running PROD admin instance sharing this checkout.
#
# Requires elevation (installing a service needs admin rights).
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$admin = Join-Path $repo 'flipflop-admin'
$npmExe = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmExe) { $npmExe = (Get-Command npm -ErrorAction Stop).Source }
$logDir = Join-Path $env:LOCALAPPDATA 'FlipFlop\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

nssm install FlipFlopDevAdmin $npmExe "run dev -- -p 4315 -H 0.0.0.0"
nssm set FlipFlopDevAdmin AppDirectory $admin
nssm set FlipFlopDevAdmin Start SERVICE_AUTO_START
nssm set FlipFlopDevAdmin AppStdout (Join-Path $logDir 'dev-admin.log')
nssm set FlipFlopDevAdmin AppStderr (Join-Path $logDir 'dev-admin.log')
nssm set FlipFlopDevAdmin AppRotateFiles 1
nssm set FlipFlopDevAdmin AppRotateBytes 10485760
nssm set FlipFlopDevAdmin AppEnvironmentExtra `
    "NODE_ENV=development`r`nNEXT_DIST_DIR=.next-dev`r`nBACKEND_URL=http://localhost:4314`r`nNEXT_PUBLIC_API_URL=http://localhost:4314`r`nNEXT_PUBLIC_FLIPFLOP_ENV=development`r`nNEXT_PUBLIC_APP_MODE=dev`r`nGEMRADAR_URL=http://localhost:18000`r`nNEXT_PUBLIC_STOREFRONT_URL=https://www.theflipflop.shop`r`nNEXT_PUBLIC_STOREFRONT_DEV_URL=http://localhost:4313"
nssm set FlipFlopDevAdmin DependOnService FlipFlopDevBackend
nssm restart FlipFlopDevAdmin

Start-Sleep -Seconds 3
sc query FlipFlopDevAdmin
