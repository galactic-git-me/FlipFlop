# Installs flipflop-api's local DEV backend as an always-on Windows Service
# on port 4314, per the "everything should be a service, starting with the
# PC" direction. This is DEV-only -- production's real backend runs on
# Andromeda and is never started locally (see docs/EXTENSION_ENVIRONMENTS.md
# and scripts/start-production-remote.sh).
#
# Safety-critical overrides set here, regardless of what .env/.env.local say:
#   EBAY_LISTING_ENVIRONMENT=sandbox -- dev must never write real eBay listings.
#   EBAY_ENVIRONMENT=production      -- dev still reads real inventory for sourcing.
#   OLLAMA_BASE_URL via the dev priority-proxy (11436), never Ollama (11434)
#     directly, so production's requests never wait behind dev's GPU usage.
#   FLIPFLOP_RUNTIME_ENV=development -- gates listing-write safety checks in app code.
#
# Requires elevation (installing a service needs admin rights).
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$api = Join-Path $repo 'flipflop-api'
$pythonExe = Join-Path $api '.venv\Scripts\python.exe'
$logDir = Join-Path $env:LOCALAPPDATA 'FlipFlop\logs'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "flipflop-api venv python not found at $pythonExe. Set up flipflop-api's virtualenv first."
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

nssm install FlipFlopDevBackend $pythonExe "run_dev.py --host 0.0.0.0 --port 4314"
nssm set FlipFlopDevBackend AppDirectory $api
nssm set FlipFlopDevBackend Start SERVICE_AUTO_START
nssm set FlipFlopDevBackend AppStdout (Join-Path $logDir 'dev-backend.log')
nssm set FlipFlopDevBackend AppStderr (Join-Path $logDir 'dev-backend.log')
nssm set FlipFlopDevBackend AppRotateFiles 1
nssm set FlipFlopDevBackend AppRotateBytes 10485760
nssm set FlipFlopDevBackend AppEnvironmentExtra `
    "FLIPFLOP_RUNTIME_ENV=development`r`nOLLAMA_BASE_URL=http://localhost:11436`r`nOLLAMA_MODEL=qwen2.5:7b-instruct`r`nEBAY_ENVIRONMENT=production`r`nEBAY_LISTING_ENVIRONMENT=sandbox`r`nADMIN_FRONTEND_URL=http://localhost:4315`r`nFRONTEND_URL=http://localhost:4313"
# Depend on the always-on infra this backend needs to function correctly.
nssm set FlipFlopDevBackend DependOnService OllamaService OllamaDevProxy FlipFlopScanLock
nssm restart FlipFlopDevBackend

Start-Sleep -Seconds 3
sc query FlipFlopDevBackend
