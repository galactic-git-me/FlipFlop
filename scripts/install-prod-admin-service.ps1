# Installs flipflop-admin's PROD instance as an always-on Windows Service on
# port 4312, pointed at Andromeda's real backend (https://www.theflipflop.shop).
# This is the "keep production always running" piece the whole dev/prod
# split exists for -- scheduled scrapes need a live admin to scrape into.
#
# TEMPORARY: runs via `next dev` rather than a production build+start.
# `next build` currently fails on this machine for reasons unrelated to this
# port/service split -- confirmed two separate pre-existing Next.js 16.3.1
# bugs: Turbopack fails resolving next/font/google, and (with --webpack
# instead) a prerender crash on /cross-listing hitting a missing
# auto-generated "default-stylesheet.css" asset that persists even with
# `export const dynamic = "force-dynamic"` on that page. Neither traces to
# app code -- looks like a genuine Next.js/Turbopack bug. Investigate
# separately; swap this script to next build && next start once fixed.
#
# Uses its own .next build output (NEXT_DIST_DIR) so it never collides with
# the simultaneously-running DEV admin instance sharing this checkout.
#
# No git branch switch here -- Andromeda deploys from its own separate
# checkout independent of this machine's local branch (see the dev/prod
# split plan's git-decoupling section); this only runs the admin frontend
# from whatever's currently checked out locally.
#
# Requires elevation (installing a service needs admin rights).
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$admin = Join-Path $repo 'flipflop-admin'
$npmExe = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmExe) { $npmExe = (Get-Command npm -ErrorAction Stop).Source }
$logDir = Join-Path $env:LOCALAPPDATA 'FlipFlop\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

nssm install FlipFlopProdAdmin $npmExe "run dev -- -p 4312 -H 0.0.0.0"
nssm set FlipFlopProdAdmin AppDirectory $admin
nssm set FlipFlopProdAdmin Start SERVICE_AUTO_START
nssm set FlipFlopProdAdmin AppStdout (Join-Path $logDir 'prod-admin.log')
nssm set FlipFlopProdAdmin AppStderr (Join-Path $logDir 'prod-admin.log')
nssm set FlipFlopProdAdmin AppRotateFiles 1
nssm set FlipFlopProdAdmin AppRotateBytes 10485760
# `next dev` only ever loads .env.development.local, never
# .env.production.local, regardless of NODE_ENV -- so the PROD overrides
# (normally living in flipflop-admin/.env.production.local) must be set
# directly here instead of relying on Next.js's env-file precedence.
# .env.production.local is kept as documentation/ready-to-use once next
# build && next start works again and env-file precedence applies normally.
$adminJwtSecret = $env:ADMIN_JWT_SECRET
if ([string]::IsNullOrWhiteSpace($adminJwtSecret) -or $adminJwtSecret.Length -lt 32) {
    throw 'Set ADMIN_JWT_SECRET in the invoking environment to a stable secret of at least 32 characters.'
}
$serviceEnvironment = @(
    'NODE_ENV=development'
    'NEXT_DIST_DIR=.next-prod'
    "ADMIN_JWT_SECRET=$adminJwtSecret"
    'BACKEND_URL=https://www.theflipflop.shop'
    'NEXT_PUBLIC_API_URL=https://www.theflipflop.shop'
    'EBAY_OPS_BACKEND_URL=https://www.theflipflop.shop'
    'GEMRADAR_URL=https://www.theflipflop.shop'
    'NEXT_PUBLIC_APP_MODE=live'
    'NEXT_PUBLIC_FLIPFLOP_ENV=live'
) -join "`r`n"
nssm set FlipFlopProdAdmin AppEnvironmentExtra $serviceEnvironment
nssm restart FlipFlopProdAdmin

Start-Sleep -Seconds 5
sc query FlipFlopProdAdmin
