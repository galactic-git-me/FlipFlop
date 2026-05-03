# PC Flipper Backend — Local Dev Startup
# Runs on port 8088 with SQLite (no Docker needed)

$ErrorActionPreference = "Stop"
$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir

# Create venv if missing
if (-not (Test-Path ".venv")) {
    Write-Host "[setup] Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

# Activate venv
$activate = ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
} else {
    Write-Host "[warn] Could not activate venv, using system Python" -ForegroundColor Yellow
}

# Install deps if not installed
$uvicorn = ".venv\Scripts\uvicorn.exe"
if (-not (Test-Path $uvicorn)) {
    Write-Host "[setup] Installing dependencies..." -ForegroundColor Cyan
    pip install -r requirements-dev.txt -q
}

Write-Host ""
Write-Host "  PC Flipper Backend" -ForegroundColor Green
Write-Host "  Database : SQLite (pcflipper.db)" -ForegroundColor Gray
Write-Host "  Port     : 8088" -ForegroundColor Gray
Write-Host "  Docs     : http://localhost:8088/docs" -ForegroundColor Gray
Write-Host ""

# Start
uvicorn app.main:app --reload --port 8088 --host 0.0.0.0
