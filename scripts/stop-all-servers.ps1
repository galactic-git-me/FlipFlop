# FlipFlop Platform - Stop Local Servers
# Stops the local processes used by start-all-servers.ps1.

param(
    # Also stop the legacy local API, Gem Radar API, and local customer site.
    [switch]$IncludeLegacyLocalApi = $false,
    # Optional because Ollama and the eBay browser are useful outside the app.
    [switch]$StopOllama = $false,
    [switch]$StopEbayCdp = $false
)

$ErrorActionPreference = "SilentlyContinue"

function Stop-PortListener {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $pids = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($ownerPid in $pids) {
        if ($ownerPid -and $ownerPid -ne 0) {
            & taskkill.exe /PID $ownerPid /T /F 2>&1 | Out-Null
            Write-Host "[OK] Stopped listener on port $Port (PID $ownerPid)" -ForegroundColor Green
        }
    }
}

Write-Host "[*] Stopping FlipFlop local servers..." -ForegroundColor Cyan

$ports = @(4312, 5173)
if ($IncludeLegacyLocalApi) { $ports += @(4311, 18000, 4313) }
foreach ($port in $ports) { Stop-PortListener -Port $port }

if ($StopOllama) {
    Get-Process -Name ollama*, llama-server -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Stopped Ollama and llama-server processes" -ForegroundColor Green
}

if ($StopEbayCdp) {
    Stop-PortListener -Port 9222
}

Write-Host "[OK] Local FlipFlop servers stopped." -ForegroundColor Green
