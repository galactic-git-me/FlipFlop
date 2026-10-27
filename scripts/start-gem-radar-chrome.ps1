# Ensures a Chrome instance is running with the Gem Radar extension (LIVE or
# DEV) loaded, using a dedicated persistent profile per mode so each keeps a
# stable identity and storage (last-run times, config) across restarts.
#
# The extension's own background worker (src/background/scheduler.ts) re-arms
# a chrome.alarms tick on every onStartup/onInstalled and drives all scanning
# from there with no further input. This script's only job is keeping a real,
# visible Chrome window open with that extension loaded — not headless, since
# the scan pipeline itself requires a real rendering window (see
# FlipFlopXtension/docs and src/background/index.ts openScanWindow()).
#
# Idempotent per mode: if a Chrome process already owns that mode's profile,
# this script exits without launching a second instance.
#
# DEV and LIVE must never scrape at the same time (docs/EXTENSION_ENVIRONMENTS.md
# describes their shared scan lease at 127.0.0.1:4311 -- running both invites
# lease contention/"fail closed" behavior, and it's also just not what we
# want operationally). This script enforces that with a lock file: it refuses
# to launch a mode while the other mode's Chrome profile is still running, and
# closes its own mode's Chrome (if running) when told to Stop.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("live", "development")]
    [string]$Mode,
    [switch]$Stop
)
$ErrorActionPreference = 'Stop'

$baseDir = Join-Path $env:LOCALAPPDATA 'FlipFlop'
$logDir = Join-Path $baseDir 'logs'
$logFile = Join-Path $logDir 'gem-radar-chrome.log'
$lockFile = Join-Path $baseDir 'gem-radar-chrome.lock'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log([string]$message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

if ($Mode -eq "live") {
    $extensionPath = Join-Path $baseDir 'extension-live'
    $profilePath = Join-Path $baseDir 'chrome-gem-radar-profile-live'
    $expectedName = "FlipFlopOS Gem Radar"
} else {
    $extensionPath = Join-Path $env:USERPROFILE 'CODING\FlipFlopXtension\dist\dev'
    $profilePath = Join-Path $baseDir 'chrome-gem-radar-profile-dev'
    $expectedName = "FlipFlopOS Gem Radar DEV"
}
$otherProfilePath = if ($Mode -eq "live") { Join-Path $baseDir 'chrome-gem-radar-profile-dev' } else { Join-Path $baseDir 'chrome-gem-radar-profile-live' }

function Get-ChromeForProfile([string]$profilePath) {
    Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$profilePath*" }
}

function Stop-ChromeForProfile([string]$profilePath, [string]$label) {
    $procs = Get-ChromeForProfile $profilePath
    if (-not $procs) { return }
    Write-Log "Stopping $label Chrome (profile: $profilePath)..."
    foreach ($p in $procs) {
        & cmd /c "taskkill /PID $($p.ProcessId) /T /F 2>&1" | Out-Null
    }
    # Release the lock only if this mode currently owns it.
    if ((Test-Path -LiteralPath $lockFile) -and (Get-Content -LiteralPath $lockFile -Raw).Trim() -eq $label) {
        Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue
    }
}

if ($Stop) {
    Stop-ChromeForProfile -profilePath $profilePath -label $Mode
    Write-Log "$Mode Chrome stopped (if it was running)."
    exit 0
}

New-Item -ItemType Directory -Force -Path $profilePath | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $extensionPath 'manifest.json'))) {
    if ($Mode -eq "live") {
        Write-Log "ERROR: LIVE extension not found at $extensionPath. Run FlipFlopXtension/scripts/update-live.ps1 first."
    } else {
        Write-Log "ERROR: DEV extension not found at $extensionPath. Run 'npm run build:dev' in FlipFlopXtension first."
    }
    exit 1
}

# Enforce the dev/live mutual exclusion lock. A stale lock left behind by a
# crashed run is detected and cleared automatically if that mode's Chrome is
# not actually running -- otherwise a hard crash could permanently wedge
# scanning for both modes.
if (Test-Path -LiteralPath $lockFile) {
    $lockOwner = (Get-Content -LiteralPath $lockFile -Raw).Trim()
    if ($lockOwner -ne $Mode) {
        $ownerProfilePath = if ($lockOwner -eq "live") { Join-Path $baseDir 'chrome-gem-radar-profile-live' } else { Join-Path $baseDir 'chrome-gem-radar-profile-dev' }
        if (Get-ChromeForProfile $ownerProfilePath) {
            Write-Log "Refusing to start $Mode - '$lockOwner' currently holds the scan lock and its Chrome is running. Stop it first (or wait for its scheduled window to end)."
            exit 1
        }
        Write-Log "Stale lock found for '$lockOwner' with no matching Chrome process; clearing it."
        Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue
    }
}

# Belt-and-braces: even if the lock file was somehow missing, never let both
# profiles' Chrome run concurrently -- close the other mode outright.
Stop-ChromeForProfile -profilePath $otherProfilePath -label $(if ($Mode -eq "live") { "development" } else { "live" })

# Detect whether Chrome is already running against this specific profile so
# repeated triggers (boot + logon + hourly watchdog) don't stack instances.
$existing = Get-ChromeForProfile $profilePath
if ($existing) {
    Write-Log "Chrome already running with $Mode gem-radar profile (PID $($existing[0].ProcessId)); nothing to do."
    Set-Content -LiteralPath $lockFile -Value $Mode
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

$manifest = Get-Content -LiteralPath (Join-Path $extensionPath 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.name -ne $expectedName) {
    Write-Log "ERROR: manifest at $extensionPath is '$($manifest.name)', expected '$expectedName'. Refusing to launch a mismatched build."
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

Write-Log "Launching $Mode Chrome ($expectedName): $chromeExe"
Start-Process -FilePath $chromeExe -ArgumentList $arguments -WindowStyle Minimized
Set-Content -LiteralPath $lockFile -Value $Mode
Write-Log "Launch command issued; lock set to '$Mode'."
