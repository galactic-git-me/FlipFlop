# Installs ollama-dev-proxy.py as a Windows Service (NSSM) so it's always
# running alongside OllamaService itself. Requires elevation (installing a
# service needs admin rights) -- run this from an elevated PowerShell, or it
# will prompt via UAC.
#
# Only DEV's local backend (flipflop-api/.env.development.local) should ever
# point OLLAMA_BASE_URL at this proxy's port (11436). Production's Ollama
# config (Andromeda, via the SSH tunnel) talks to Ollama directly on 11434
# and needs no change -- this proxy exists purely to make dev yield the GPU
# to production, never the other way round.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repo 'flipflop-api\.venv\Scripts\python.exe'
$script = Join-Path $repo 'scripts\ollama-dev-proxy.py'
$logDir = Join-Path $env:LOCALAPPDATA 'FlipFlop\logs'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "flipflop-api venv python not found at $pythonExe. Set up flipflop-api's virtualenv first."
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

nssm install OllamaDevProxy $pythonExe $script
nssm set OllamaDevProxy Start SERVICE_AUTO_START
nssm set OllamaDevProxy AppStdout (Join-Path $logDir 'ollama-dev-proxy.log')
nssm set OllamaDevProxy AppStderr (Join-Path $logDir 'ollama-dev-proxy.log')
nssm set OllamaDevProxy AppRotateFiles 1
nssm set OllamaDevProxy AppRotateBytes 10485760
# Depend on Ollama itself so Windows starts them in the right order at boot.
nssm set OllamaDevProxy DependOnService OllamaService
nssm restart OllamaDevProxy

Start-Sleep -Seconds 2
sc query OllamaDevProxy
Write-Host ""
Write-Host "Point DEV's OLLAMA_BASE_URL at http://localhost:11436 (not 11434) to route through this proxy."
