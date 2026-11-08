param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$StatePath = (Join-Path $PSScriptRoot 'ollama-recovery-state.json'),
    [string]$GatewayHealthUrl = 'http://127.0.0.1:11435/health',
    [string]$GatewayGenerationUrl = 'http://127.0.0.1:11435/api/chat',
    [string[]]$GatewayHealthUrls = @('http://127.0.0.1:11434/health', 'http://127.0.0.1:11435/health', 'http://127.0.0.1:11436/health'),
    [string]$GatewayMaintenanceUrl = 'http://127.0.0.1:11435/_maintenance',
    [string]$MaintenanceTokenPath = (Join-Path $env:LOCALAPPDATA 'FlipFlop\ollama-gateway-maintenance-token.txt'),
    [string]$Model = 'qwen3:4b',
    [int]$FailureThreshold = 3,
    [int]$CooldownMinutes = 10,
    [switch]$NoRestart
)

$ErrorActionPreference = 'Stop'
if ($FailureThreshold -lt 1) { throw 'FailureThreshold must be at least 1' }
if ($CooldownMinutes -lt 1) { throw 'CooldownMinutes must be at least 1' }
$logPath = Join-Path $ProjectRoot 'logs\ollama-recovery-watchdog.log'

function Write-WatchdogLog([string]$Message) {
    $directory = Split-Path -Parent $logPath
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath $logPath
}

function Read-WatchdogState {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return @{ consecutive_failures = 0; last_restart_epoch = $null }
    }
    try {
        $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json -AsHashtable
        if ($null -eq $state.consecutive_failures) { $state.consecutive_failures = 0 }
        return $state
    } catch {
        Write-WatchdogLog "WARN invalid state file; resetting counters: $($_.Exception.GetType().Name)"
        return @{ consecutive_failures = 0; last_restart_epoch = $null }
    }
}

function Save-WatchdogState($State) {
    $parent = Split-Path -Parent $StatePath
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $State | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Get-MaintenanceToken {
    if (-not (Test-Path -LiteralPath $MaintenanceTokenPath)) {
        throw 'Gateway maintenance token is missing; start the updated Ollama gateway before enabling recovery.'
    }
    $token = (Get-Content -LiteralPath $MaintenanceTokenPath -Raw).Trim()
    if (-not $token) { throw 'Gateway maintenance token is empty' }
    return $token
}

function Invoke-GenerationProbe {
    $health = Invoke-RestMethod -Uri $GatewayHealthUrl -TimeoutSec 5
    if ($health.status -ne 'ok') { throw 'DEV gateway health is not ok' }
    if ($health.admission_paused) { return 'busy' }

    # Never compete with customer or scan traffic. The real probe runs only
    # while the shared gateway has no waiting or active generations.
    if ([int]$health.queue_depth -ne 0 -or [int]$health.active_generations -ne 0) {
        return 'busy'
    }

    $body = @{
        model = $Model
        messages = @(@{ role = 'user'; content = 'Reply with OK.' })
        stream = $false
        keep_alive = -1
        think = $false
        options = @{ num_predict = 2 }
    } | ConvertTo-Json -Depth 5 -Compress
    $response = Invoke-RestMethod -Method Post -Uri $GatewayGenerationUrl `
        -Headers @{ 'X-Ollama-Maintenance-Token' = (Get-MaintenanceToken); 'X-Ollama-Watchdog-Timeout-Seconds' = '20' } `
        -ContentType 'application/json' -Body $body -TimeoutSec 25
    if (-not $response.message.content) { throw 'DEV gateway generation probe returned no content' }
    return 'ok'
}

function Invoke-GatewayMaintenance([string]$Action) {
    $token = Get-MaintenanceToken
    return Invoke-RestMethod -Method Post -Uri "$GatewayMaintenanceUrl/$Action" `
        -Headers @{ 'X-Ollama-Maintenance-Token' = $token } -ContentType 'application/json' `
        -Body '{}' -TimeoutSec 5
}

function Test-AllGatewaysIdleAndPaused {
    foreach ($url in $GatewayHealthUrls) {
        $health = Invoke-RestMethod -Uri $url -TimeoutSec 5
        if ($health.status -ne 'ok' -or -not $health.admission_paused -or
            [int]$health.queue_depth -ne 0 -or [int]$health.active_generations -ne 0) {
            return $false
        }
    }
    return $true
}

$state = Read-WatchdogState
try {
    $probe = Invoke-GenerationProbe
    if ($probe -eq 'busy') {
        Write-WatchdogLog "INFO generation probe skipped because the shared queue is active; preserving failure streak $([int]$state.consecutive_failures)"
        exit 0
    }
    if ([int]$state.consecutive_failures -gt 0) {
        Write-WatchdogLog 'RECOVERED Ollama generation probe succeeded; clearing failure streak'
    }
    $state.consecutive_failures = 0
    Save-WatchdogState $state
    Write-WatchdogLog 'INFO idle generation probe succeeded'
    exit 0
} catch {
    $state.consecutive_failures = [int]$state.consecutive_failures + 1
    Save-WatchdogState $state
    Write-WatchdogLog "WARN generation probe failed ($($state.consecutive_failures)/$FailureThreshold): $($_.Exception.GetType().Name)"
}

if ([int]$state.consecutive_failures -lt $FailureThreshold) { exit 0 }
if ($NoRestart) {
    Write-WatchdogLog 'DRYRUN restart threshold reached; no shared process was restarted'
    exit 0
}

if ($state.last_restart_epoch) {
    $elapsed = ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [int64]$state.last_restart_epoch) / 60
    if ($elapsed -lt $CooldownMinutes) {
        Write-WatchdogLog "COOLDOWN restart skipped; last restart was $([Math]::Round($elapsed, 1)) minutes ago"
        exit 0
    }
}

$launcher = Join-Path $ProjectRoot 'services\ollama-priority-gateway\start-prometheus-services.ps1'
if (-not (Test-Path -LiteralPath $launcher)) { throw "Ollama startup script not found: $launcher" }
$admissionPaused = $false
try {
    $pauseResult = Invoke-GatewayMaintenance 'pause'
    if (-not $pauseResult.admission_paused) { throw 'Gateway did not confirm paused admission' }
    $admissionPaused = $true
    if (-not (Test-AllGatewaysIdleAndPaused)) {
        Invoke-GatewayMaintenance 'resume' | Out-Null
        $admissionPaused = $false
        Write-WatchdogLog 'DEFERRED recovery because queued or active work remained after admission was paused'
        exit 0
    }
    Write-WatchdogLog 'CRITICAL repeated idle generation failures; admission paused and all priorities idle; restarting Ollama and gateway'
    & $launcher -ForceRestart
    if (-not $?) { throw 'Ollama restart script failed' }
    $admissionPaused = $false # the restarted gateway has reopened admission
    $state.consecutive_failures = 0
    $state.last_restart_epoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    Save-WatchdogState $state
    Write-WatchdogLog 'RECOVERY restart command completed; startup script verified all gateway listeners'
} catch {
    if ($admissionPaused) {
        try { Invoke-GatewayMaintenance 'resume' | Out-Null }
        catch { Write-WatchdogLog "ERROR could not resume gateway admission after failed recovery: $($_.Exception.GetType().Name)" }
    }
    throw
}
