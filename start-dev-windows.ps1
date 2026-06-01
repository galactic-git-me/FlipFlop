param(
  [ValidateSet("start", "stop", "status")]
  [string]$Action = "start",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "pc-flipper-backend"
$FrontendDir = Join-Path $RootDir "pc-flipper"
$LogsDir = Join-Path $RootDir ".run-logs"
$PidFile = Join-Path $LogsDir "windows-dev-pids.json"

$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "4310" }
$BackendPort  = if ($env:BACKEND_PORT)  { $env:BACKEND_PORT }  else { "4311" }

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-PythonCommand {
  if (Get-Command py -ErrorAction SilentlyContinue) { return "py -3" }
  if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
  if (Get-Command python3 -ErrorAction SilentlyContinue) { return "python3" }
  throw "Python not found. Install Python 3 first."
}

function Get-ComposeCommand {
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
      docker compose version | Out-Null
      return @{ Bin = "docker"; Args = @("compose") }
    } catch {}
  }
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    return @{ Bin = "docker-compose"; Args = @() }
  }
  throw "Docker Compose not found. Install Docker Desktop."
}

function Ensure-DockerRunning {
  $compose = Get-ComposeCommand
  if ($compose.Bin -eq "docker") {
    try {
      docker info | Out-Null
      return
    } catch {
      throw "Docker Desktop is installed but the daemon is not running. Start Docker Desktop and wait for 'Engine running', then rerun."
    }
  }
}

function Invoke-ComposeBackend([string[]]$ExtraArgs) {
  Push-Location $BackendDir
  try {
    $compose = Get-ComposeCommand
    & $compose.Bin @($compose.Args + $ExtraArgs)
  } finally {
    Pop-Location
  }
}

function Sync-EnvFiles {
  $rootEnv = Join-Path $RootDir ".env.local"
  if (Test-Path $rootEnv) {
    Copy-Item $rootEnv (Join-Path $BackendDir ".env") -Force
    Copy-Item $rootEnv (Join-Path $FrontendDir ".env") -Force
  }
}

function Ensure-BackendDeps {
  $venvDir = Join-Path $BackendDir ".venv"
  $venvPython = Join-Path $venvDir "Scripts\python.exe"
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
  } finally {
    Pop-Location
  }
}

function Ensure-FrontendDeps {
  Push-Location $FrontendDir
  try {
    Write-Host "Installing frontend dependencies..."
    npm install --no-audit --no-fund
  } finally {
    Pop-Location
  }
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

  # Safety net if pid file is stale.
  Get-CimInstance Win32_Process |
    Where-Object {
      $_.CommandLine -match "uvicorn app.main:app" -or
      $_.CommandLine -match "next dev -p $FrontendPort"
    } |
    ForEach-Object {
      try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch { $null = $_ }
    }

  Write-Host "Stopped dev services."
}

function Show-Status {
  $running = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "uvicorn app.main:app" -or
    $_.CommandLine -match "next dev -p $FrontendPort"
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

  if (-not $SkipInstall) {
    Ensure-BackendDeps
    Ensure-FrontendDeps
  }

  Write-Host "Starting db/redis containers..."
  Ensure-DockerRunning
  Invoke-ComposeBackend @("up", "-d", "db", "redis") | Out-Null

  $backendLog = Join-Path $LogsDir "backend-4311.log"
  $backendErrLog = Join-Path $LogsDir "backend-4311.err.log"
  $frontendLog = Join-Path $LogsDir "frontend-4310.log"
  $frontendErrLog = Join-Path $LogsDir "frontend-4310.err.log"

  # Stop prior instances before launching.
  Stop-Dev | Out-Null

  $backendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
  $backendArgs = "-m uvicorn app.main:app --reload --host 0.0.0.0 --port $BackendPort"
  $backendProc = Start-Process -FilePath $backendPython `
    -ArgumentList $backendArgs `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrLog `
    -WindowStyle Hidden `
    -PassThru

  $frontendProc = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--webpack", "-p", $FrontendPort, "-H", "0.0.0.0") `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErrLog `
    -WindowStyle Hidden `
    -PassThru

  @{
    backendPid = $backendProc.Id
    frontendPid = $frontendProc.Id
    startedAt = (Get-Date).ToString("o")
  } | ConvertTo-Json | Set-Content -Path $PidFile

  Write-Host ""
  Write-Host "Frontend: http://localhost:$FrontendPort"
  Write-Host "Backend : http://localhost:$BackendPort"
  Write-Host "Logs:"
  Write-Host "  $frontendLog"
  Write-Host "  $frontendErrLog"
  Write-Host "  $backendLog"
  Write-Host "  $backendErrLog"
  Write-Host ""
  Write-Host "Commands:"
  Write-Host "  .\start-dev-windows.ps1 status"
  Write-Host "  .\start-dev-windows.ps1 stop"
}

switch ($Action) {
  "start" { Start-Dev }
  "stop" { Stop-Dev }
  "status" { Show-Status }
}
