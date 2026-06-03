param(
  [ValidateSet("start", "stop", "status")]
  [string]$Action = "start",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RootDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "pc-flipper-backend"
$FrontendDir= Join-Path $RootDir "pc-flipper"
$LogsDir    = Join-Path $RootDir ".run-logs"
$PidFile    = Join-Path $LogsDir "windows-dev-pids.json"

$FrontendPort  = if ($env:FRONTEND_PORT)  { $env:FRONTEND_PORT }  else { "4310" }
$BackendPort   = if ($env:BACKEND_PORT)   { $env:BACKEND_PORT }   else { "4311" }
$AutoDashboard = if ($env:RICH_DASHBOARD_AUTO_LAUNCH) { $env:RICH_DASHBOARD_AUTO_LAUNCH } else { "1" }

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path | Out-Null }
}

function Get-PythonCommand {
  if (Get-Command py     -ErrorAction SilentlyContinue) { return "py -3" }
  if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
  if (Get-Command python3 -ErrorAction SilentlyContinue) { return "python3" }
  throw "Python not found. Install Python 3 first."
}

function Sync-EnvFiles {
  $rootEnv = Join-Path $RootDir ".env.local"
  if (Test-Path $rootEnv) {
    Copy-Item $rootEnv (Join-Path $BackendDir  ".env") -Force
    Copy-Item $rootEnv (Join-Path $FrontendDir ".env") -Force
  }
}

function Ensure-BackendDeps {
  $venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
  $py = Get-PythonCommand
  Push-Location $BackendDir
  try {
    if (-not (Test-Path $venvPython)) {
      Write-Host "Creating backend virtualenv..."
      cmd /c "$py -m venv .venv"
    }
    Write-Host "Installing backend dependencies..."
    & $venvPython -m pip install --upgrade pip | Out-Null
    & $venvPython -m pip install -r requirements.txt
    Write-Host "Installing Playwright Chromium..."
    & $venvPython -m playwright install chromium
  } finally { Pop-Location }
}

function Ensure-FrontendDeps {
  Push-Location $FrontendDir
  try {
    Write-Host "Installing frontend dependencies..."
    npm install --no-audit --no-fund
  } finally { Pop-Location }
}

function Stop-Dev {
  if (Test-Path $PidFile) {
    $state = Get-Content $PidFile -Raw | ConvertFrom-Json
    foreach ($name in @("backendPid", "frontendPid")) {
      $procId = $state.$name
      if ($procId) {
        try { Stop-Process -Id $procId -Force -ErrorAction Stop } catch { $null = $_ }
      }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  }
  # Safety net for stale processes
  Get-CimInstance Win32_Process |
    Where-Object {
      $_.CommandLine -match "uvicorn app.main:app" -or
      $_.CommandLine -match "next dev"
    } |
    ForEach-Object {
      try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch { $null = $_ }
    }
  Write-Host "Stopped dev services."
}

function Show-Status {
  $running = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "uvicorn app.main:app" -or $_.CommandLine -match "next dev"
  }
  if ($running) {
    Write-Host "Running processes:"
    $running | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize
  } else {
    Write-Host "No dev app processes found."
  }
}

function Start-Dev {
  Ensure-Dir $LogsDir
  Sync-EnvFiles
  Stop-Dev | Out-Null

  if (-not $SkipInstall) {
    Ensure-BackendDeps
    Ensure-FrontendDeps
  }

  $backendLog    = Join-Path $LogsDir "backend-$BackendPort.log"
  $backendErrLog = Join-Path $LogsDir "backend-$BackendPort.err.log"
  $frontendLog   = Join-Path $LogsDir "frontend-$FrontendPort.log"
  $frontendErrLog= Join-Path $LogsDir "frontend-$FrontendPort.err.log"

  Write-Host "Starting backend (uvicorn --reload) on port $BackendPort..."
  $backendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
  $backendProc = Start-Process -FilePath $backendPython `
    -ArgumentList "run_dev.py --host 0.0.0.0 --port $BackendPort" `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError  $backendErrLog `
    -WindowStyle Hidden `
    -PassThru

  Write-Host "Starting frontend (next dev) on port $FrontendPort..."
  $frontendProc = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "-p", $FrontendPort, "-H", "0.0.0.0") `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError  $frontendErrLog `
    -WindowStyle Hidden `
    -PassThru

  @{
    backendPid  = $backendProc.Id
    frontendPid = $frontendProc.Id
    startedAt   = (Get-Date).ToString("o")
  } | ConvertTo-Json | Set-Content -Path $PidFile

  if ($AutoDashboard -in @("1","true","True","yes","YES")) {
    $dashboardScript = Join-Path $RootDir "scripts\rich_dashboard.py"
    if ((Test-Path $backendPython) -and (Test-Path $dashboardScript)) {
      $cmd = "cd `"$RootDir`"; & `"$backendPython`" `"$dashboardScript`" --base-url http://localhost:$BackendPort"
      Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $cmd) | Out-Null
    }
  }

  Write-Host ""
  Write-Host "  Frontend : http://localhost:$FrontendPort"
  Write-Host "  Backend  : http://localhost:$BackendPort"
  Write-Host "  Logs     : $LogsDir"
  Write-Host ""
  Write-Host "  NOTE: Postgres and Redis must already be running locally."
  Write-Host "        Configure DATABASE_URL / REDIS_URL in .env.local if needed."
  Write-Host ""
  Write-Host "  .\start-dev-windows.ps1 stop     <- stop all"
  Write-Host "  .\start-dev-windows.ps1 status   <- check processes"
}

switch ($Action) {
  "start"  { Start-Dev }
  "stop"   { Stop-Dev }
  "status" { Show-Status }
}
