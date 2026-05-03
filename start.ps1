# PC Flipper - Dev Launcher
# Kills anything on ports 3000 + 8001, starts backend + frontend, opens browser

$ErrorActionPreference = "SilentlyContinue"

$FrontendPort = 3000
$BackendPort  = 8088
$FrontendDir  = "$PSScriptRoot\pc-flipper"
$BackendDir   = "$PSScriptRoot\pc-flipper-backend"
$FrontendUrl  = "http://localhost:$FrontendPort"

function Kill-Port([int]$Port) {
    $lines = netstat -ano | Select-String ":$Port\s"
    $pids  = $lines | ForEach-Object { ($_ -split '\s+')[-1] } |
             Sort-Object -Unique | Where-Object { $_ -match '^\d+$' }
    foreach ($p in $pids) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Killing $($proc.Name) (PID $p) on port $Port" -ForegroundColor Yellow
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host ""
Write-Host "  PC Flipper Dev Launcher" -ForegroundColor Cyan
Write-Host "  ---------------------------------" -ForegroundColor DarkGray
Write-Host ""

# 1 - Free ports + kill any stale uvicorn/node processes
Write-Host "[1/4] Freeing ports and stale processes..." -ForegroundColor Cyan

# Kill any Python processes running uvicorn (handles --reload multi-process stacking)
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    ($_.CommandLine -match "uvicorn" -or $_.MainWindowTitle -match "pcflipper") -or $true
} | ForEach-Object {
    Write-Host "  Killing Python PID $($_.Id)" -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

Kill-Port $BackendPort
Kill-Port $FrontendPort
Start-Sleep -Milliseconds 1000

# 2 - Start backend
Write-Host "[2/4] Starting backend  (port $BackendPort)..." -ForegroundColor Cyan

if (-not (Test-Path "$BackendDir\.venv\Scripts\uvicorn.exe")) {
    Write-Host "  venv not found - installing..." -ForegroundColor Yellow
    Push-Location $BackendDir
    python -m venv .venv
    & ".\.venv\Scripts\pip.exe" install -r requirements-dev.txt -q
    Pop-Location
}

# Write helper scripts so paths with spaces don't break the child window
$backendScript = "$env:TEMP\pcflipper_backend.ps1"
$frontendScript = "$env:TEMP\pcflipper_frontend.ps1"

Set-Content -Path $backendScript -Value @"
Set-Location '$BackendDir'
Write-Host 'Backend running on port $BackendPort' -ForegroundColor Green
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --port $BackendPort --host 0.0.0.0 --reload
"@

Set-Content -Path $frontendScript -Value @"
Set-Location '$FrontendDir'
Write-Host 'Frontend running on port $FrontendPort' -ForegroundColor Green
npm run dev
"@

Start-Process powershell.exe -ArgumentList "-NoExit", "-File", $backendScript

# 3 - Start frontend
Write-Host "[3/4] Starting frontend (port $FrontendPort)..." -ForegroundColor Cyan

Start-Process powershell.exe -ArgumentList "-NoExit", "-File", $frontendScript

# 4 - Poll until ready then open browser
Write-Host "[4/4] Waiting for frontend..." -ForegroundColor Cyan

$timeout  = 60
$elapsed  = 0
$interval = 2
$ready    = $false

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds $interval
    $elapsed += $interval
    try {
        $r = Invoke-WebRequest -Uri $FrontendUrl -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -lt 500) { $ready = $true; break }
    } catch { }
    Write-Host "  ...waiting ($elapsed s)" -ForegroundColor DarkGray
}

Write-Host ""
if ($ready) {
    Write-Host "  Ready! Opening $FrontendUrl" -ForegroundColor Green
} else {
    Write-Host "  Timed out - opening anyway" -ForegroundColor Yellow
}

Start-Process $FrontendUrl

Write-Host ""
Write-Host "  Frontend : $FrontendUrl" -ForegroundColor Gray
Write-Host "  Backend  : http://prometheus:$BackendPort/docs" -ForegroundColor Gray
Write-Host ""
