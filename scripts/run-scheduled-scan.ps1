# Scheduled, unattended entry point that prepares the environment for a given
# mode (live/production or development) and then launches that mode's
# Gem Radar Chrome extension so its own internal chrome.alarms scheduler
# takes over scanning. Intended to be called by Windows Task Scheduler --
# see scripts/install-gem-radar-tasks.ps1.
#
# Order matters: environment/services must be confirmed healthy BEFORE the
# extension is allowed to start scraping into it, otherwise scans could hit a
# backend that is mid-restart, on the wrong branch, or pointed at the wrong
# eBay/Amazon environment.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("live", "development")]
    [string]$Mode
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$baseDir = Join-Path $env:LOCALAPPDATA 'FlipFlop'
$logDir = Join-Path $baseDir 'logs'
$logFile = Join-Path $logDir 'scheduled-scan.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log([string]$message) {
    $line = "[{0}] [$Mode] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

try {
    Write-Log "Starting scheduled scan run."

    Write-Log "Preparing environment via start-all-servers.ps1 -RunMode $Mode ..."
    & (Join-Path $repo 'scripts\start-all-servers.ps1') -RunMode $Mode
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        throw "start-all-servers.ps1 exited with code $LASTEXITCODE"
    }
    Write-Log "Environment ready for $Mode mode."

    Write-Log "Launching $Mode Gem Radar Chrome extension..."
    & (Join-Path $PSScriptRoot 'start-gem-radar-chrome.ps1') -Mode $Mode
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        throw "start-gem-radar-chrome.ps1 exited with code $LASTEXITCODE"
    }

    Write-Log "Scheduled scan run complete; extension's own scheduler now drives scanning."
} catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    throw
}
