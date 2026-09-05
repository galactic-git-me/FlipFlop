# FlipFlop Services Startup Script
# Start both services and optionally tail their logs

# ============================================================================
# LOG FILE PATHS & TAIL COMMANDS
# ============================================================================
#
# GemRadar API logs:
#   Tail:  Get-Content "C:\Users\mclar\CODING\FlipFlop\logs\gemradar-api.log" -Tail 100 -Wait
#
# Admin Dashboard logs:
#   Tail:  Get-Content "C:\Users\mclar\CODING\FlipFlop\logs\admin.log" -Tail 100 -Wait
#
# Backend logs:
#   Tail:  Get-Content "C:\Users\mclar\CODING\FlipFlop\logs\backend.log" -Tail 100 -Wait
#
# Frontend logs:
#   Tail:  Get-Content "C:\Users\mclar\CODING\FlipFlop\logs\frontend.log" -Tail 100 -Wait
#
# Performance Card logs:
#   Tail:  Get-Content "C:\Users\mclar\CODING\FlipFlop\logs\performance-card.log" -Tail 100 -Wait
#
# ============================================================================

param(
  [ValidateSet("start", "stop", "logs", "status")]
  [string]$Action = "start",
  [switch]$TailAll
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogsDir = Join-Path $RootDir "logs"
$FlipFlopApiDir = Join-Path $RootDir "flipflop-api"
$AdminDir = Join-Path $RootDir "flipflop-admin"

# ============================================================================
# Log file paths
# ============================================================================
$GebradarLog = Join-Path $LogsDir "gemradar-api.log"
$AdminLog = Join-Path $LogsDir "admin.log"

function Start-Services {
  Write-Host "Starting FlipFlop services..." -ForegroundColor Cyan

  # Start GemRadar API
  # Wrapped in a restart loop: the backend's own stall-watchdog thread used
  # to kill the whole process on the assumption "Docker's restart policy"
  # would bring up a clean one — but this deployment has never run under
  # Docker/PM2/any supervisor, so the first time it fired, the API died and
  # stayed dead for days with nothing noticing (see git history around
  # 2026-09-02). That watchdog no longer kills the process, but this loop
  # is a second line of defense against ANY future crash (OOM, unhandled
  # exception, etc.) — if uvicorn exits for any reason, relaunch it after a
  # few seconds instead of silently leaving the API dead.
  Write-Host "  → Starting GemRadar API (port 18000, auto-restart on crash)..." -ForegroundColor Yellow
  # Start-Job was tried here first but is scoped to the PowerShell PROCESS
  # that creates it — if that process exits (e.g. a non-interactive command
  # invocation finishing), the job and everything under it dies too, which
  # defeats the entire point of a supervisor loop. A genuinely detached
  # child process (Start-Process, hidden window) survives independently of
  # whatever launched it, the same way the admin dashboard's own `npm run
  # dev &` background invocation already does.
  $watchdogScript = Join-Path $FlipFlopApiDir "_gemradar_watchdog.ps1"
  @"
Set-Location '$FlipFlopApiDir'
while (`$true) {
  "`$(Get-Date -Format o) [watchdog] starting uvicorn..." | Out-File -FilePath '$GebradarLog' -Append -Encoding utf8
  & python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --log-level info *>> '$GebradarLog'
  "`$(Get-Date -Format o) [watchdog] uvicorn exited (code `$LASTEXITCODE) - restarting in 5s..." | Out-File -FilePath '$GebradarLog' -Append -Encoding utf8
  Start-Sleep -Seconds 5
}
"@ | Set-Content -Path $watchdogScript -Encoding utf8
  Start-Process -FilePath "pwsh.exe" -ArgumentList @("-NoProfile", "-WindowStyle", "Hidden", "-File", $watchdogScript) -WindowStyle Hidden | Out-Null

  # Start Admin Dashboard
  Write-Host "  → Starting Admin Dashboard (port 3002)..." -ForegroundColor Yellow
  cd $AdminDir
  npm run dev 2>&1 | Tee-Object -FilePath $AdminLog -Append &

  Write-Host ""
  Write-Host "Services started!" -ForegroundColor Green
  Write-Host "  GemRadar API : http://localhost:18000" -ForegroundColor Cyan
  Write-Host "  Admin Dashboard : http://localhost:3002" -ForegroundColor Cyan
  Write-Host ""
  Write-Host "View logs:" -ForegroundColor Gray
  Write-Host "  Get-Content logs\gemradar-api.log -Tail 50 -Wait" -ForegroundColor Gray
  Write-Host "View logs:" -ForegroundColor Gray
  Write-Host "  Get-Content logs\admin.log -Tail 50 -Wait" -ForegroundColor Gray
  Write-Host "View logs:" -ForegroundColor Gray
  Write-Host "  Get-Content logs\backend.log -Tail 50 -Wait" -ForegroundColor Gray
  Write-Host "View logs:" -ForegroundColor Gray
  Write-Host "  Get-Content logs\frontend.log -Tail 50 -Wait" -ForegroundColor Gray
  Write-Host "View logs:" -ForegroundColor Gray
  Write-Host "  Get-Content logs\performance-card.log -Tail 50 -Wait" -ForegroundColor Gray
}

function Tail-Logs {
  Write-Host "Tailing all logs (Ctrl+C to exit)..." -ForegroundColor Cyan
  Write-Host ""

  # Create background jobs for each log
  $jobs = @()

  Write-Host "GemRadar API (gemradar-api.log):"
  $jobs += Start-Job -ScriptBlock {
    Get-Content "C:\Users\mclar\CODING\FlipFlop\logs\gemradar-api.log" -Tail 20 -Wait
  }

  Write-Host "Admin Dashboard (admin.log):"
  $jobs += Start-Job -ScriptBlock {
    Get-Content "C:\Users\mclar\CODING\FlipFlop\logs\admin.log" -Tail 20 -Wait
  }

  # Wait for all jobs
  Get-Job | Wait-Job
}

function Show-Status {
  Write-Host "Checking service status..." -ForegroundColor Cyan

  $processes = Get-Process | Where-Object {
    $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*"
  }

  if ($processes) {
    Write-Host "Running processes:" -ForegroundColor Green
    $processes | Select-Object ProcessId, ProcessName, @{
      Name="CPU%"; Expression={[math]::Round($_.CPU, 2)}
    }, @{
      Name="Memory(MB)"; Expression={[math]::Round($_.WorkingSet/1MB, 2)}
    } | Format-Table -AutoSize
  } else {
    Write-Host "No services running" -ForegroundColor Yellow
  }
}

function Stop-Services {
  Write-Host "Stopping FlipFlop services..." -ForegroundColor Yellow

  # Stop the watchdog process FIRST — otherwise it just relaunches uvicorn
  # the moment Stop-Process kills it below.
  Get-CimInstance Win32_Process -Filter "Name='pwsh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "_gemradar_watchdog\.ps1" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

  Get-Process | Where-Object {
    $_.ProcessName -eq "python" -or $_.ProcessName -eq "node"
  } | Stop-Process -Force -ErrorAction SilentlyContinue

  Write-Host "Services stopped." -ForegroundColor Green
}

switch ($Action) {
  "start" { Start-Services }
  "stop"  { Stop-Services }
  "logs"  { Tail-Logs }
  "status" { Show-Status }
}
