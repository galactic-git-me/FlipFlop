# Ensures a Chrome instance is running with the LIVE Gem Radar extension loaded,
# using a dedicated persistent profile so the extension keeps a stable identity
# and storage (last-run times, config) across restarts.
#
# The extension's own background worker (src/background/scheduler.ts) re-arms
# a chrome.alarms tick on every onStartup/onInstalled and drives all scanning
# from there with no further input. This script's only job is keeping a real,
# visible Chrome window open with that extension loaded — not headless, since
# the scan pipeline itself requires a real rendering window (see
# FlipFlopXtension/docs and src/background/index.ts openScanWindow()).
#
# Idempotent: if a Chrome process already owns the dedicated profile, this
# script exits without launching a second instance (avoids duplicate scan
# windows fighting over the 127.0.0.1:4311 scan lease).
$ErrorActionPreference = 'Stop'

$extensionPath = Join-Path $env:LOCALAPPDATA 'FlipFlop\extension-live'
$profilePath = Join-Path $env:LOCALAPPDATA 'FlipFlop\chrome-gem-radar-profile'
$logDir = Join-Path $env:LOCALAPPDATA 'FlipFlop\logs'
$logFile = Join-Path $logDir 'gem-radar-chrome.log'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $profilePath | Out-Null

function Write-Log([string]$message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

if (-not (Test-Path -LiteralPath (Join-Path $extensionPath 'manifest.json'))) {
    Write-Log "ERROR: LIVE extension not found at $extensionPath. Run FlipFlopXtension/scripts/update-live.ps1 first."
    exit 1
}

# Detect whether Chrome is already running against this specific profile so
# repeated triggers (boot + logon + hourly watchdog) don't stack instances.
$existing = Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*$profilePath*" }

if ($existing) {
    Write-Log "Chrome already running with gem-radar profile (PID $($existing[0].ProcessId)); nothing to do."
    exit 0
}

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$chromeExe = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $chromeExe) {
    Write-Log "ERROR: chrome.exe not found in any known install location."
    exit 1
}

# --no-first-run/--no-default-browser-check keep this unattended launch from
# blocking on setup dialogs. Window is real (not headless/minimized) because
# the scraper's own IntersectionObserver-dependent extraction requires it.
$arguments = @(
    "--load-extension=`"$extensionPath`""
    "--user-data-dir=`"$profilePath`""
    "--no-first-run"
    "--no-default-browser-check"
    "--disable-session-crashed-bubble"
    "--disable-features=Translate"
    "about:blank"
)

Write-Log "Launching Chrome with gem-radar profile: $chromeExe"
Start-Process -FilePath $chromeExe -ArgumentList $arguments -WindowStyle Minimized
Write-Log "Launch command issued."
