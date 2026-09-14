param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("development", "live")]
    [string]$Mode,
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = "Stop"
$extensionRoot = Join-Path (Split-Path -Parent $ProjectRoot) "FlipFlopXtension"
if (-not (Test-Path -LiteralPath $extensionRoot -PathType Container)) {
    throw "Extension repository missing: $extensionRoot"
}
if ($Mode -eq "development") {
    Write-Host "[*] Building DEV extension from local working files..." -ForegroundColor Cyan
    Push-Location $extensionRoot
    try {
        & npm run build:dev
        if ($LASTEXITCODE -ne 0) { throw "DEV extension build failed; startup stopped." }
    } finally {
        Pop-Location
    }
    $extensionPath = Join-Path $extensionRoot "dist/dev"
    $expectedName = "FlipFlopOS Gem Radar DEV"
    $expectedApi = "http://127.0.0.1:4311/*"
    $forbiddenApi = 'theflipflop\.shop'
    $other = "LIVE"
} else {
    # Check the extension repository locally; never update the application checkout here.
    & git -C $extensionRoot fetch --quiet origin
    if ($LASTEXITCODE -ne 0) { throw "Extension GitHub fetch failed" }
    $branch = (& git -C $extensionRoot branch --show-current).Trim()
    if (-not $branch) { throw "Extension checkout is detached" }
    $localRevision = & git -C $extensionRoot rev-parse HEAD
    $remoteRevision = & git -C $extensionRoot rev-parse "origin/$branch"
    if ($LASTEXITCODE -ne 0) { throw "Extension remote branch is missing" }
    if ($localRevision -ne $remoteRevision) {
        Write-Host "[INFO] Extension working checkout differs from GitHub; LIVE uses only the successful GitHub artifact." -ForegroundColor Yellow
    } else {
        Write-Host "[OK] Extension checkout revision matches GitHub." -ForegroundColor Green
    }
    Write-Host "[*] Updating LIVE extension from the successful GitHub release build..." -ForegroundColor Cyan
    $ghCommand = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $ghCommand) {
        # Winget's per-user install may not be visible until a new shell is
        # opened. Add the known user-scope install location for this process.
        $wingetGhRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
        $wingetGh = Get-ChildItem -LiteralPath $wingetGhRoot -Filter gh.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\GitHub\.cli_[^\\]+\\bin\\gh\.exe$' } |
            Select-Object -First 1
        if ($wingetGh) {
            $env:Path = "$($wingetGh.Directory.FullName);$env:Path"
            $ghCommand = Get-Command gh -ErrorAction SilentlyContinue
        }
    }
    if (-not $ghCommand) {
        throw "LIVE extension update needs GitHub CLI (gh) installed and authenticated with gh auth login. No local source will be built for LIVE."
    }
    & (Join-Path $extensionRoot "scripts/update-live.ps1")
    $extensionPath = Join-Path $env:LOCALAPPDATA "FlipFlop/extension-live"
    $expectedName = "FlipFlopOS Gem Radar"
    $expectedApi = "https://www.theflipflop.shop/*"
    $forbiddenApi = 'localhost|127\.0\.0\.1'
    $other = "DEV"
}
$manifest = Get-Content -LiteralPath (Join-Path $extensionPath "manifest.json") -Raw | ConvertFrom-Json
if ($manifest.name -ne $expectedName -or $manifest.host_permissions -notcontains $expectedApi -or ($manifest.host_permissions -match $forbiddenApi)) {
    throw "Extension manifest does not match selected $Mode environment; startup stopped."
}
Write-Host "[OK] $expectedName ready: $extensionPath" -ForegroundColor Green
Write-Host "[BROWSER] Load/reload this extension and disable the other environment ($other) and any obsolete installations for this session." -ForegroundColor Yellow
Write-Host "[BROWSER] Startup does not switch extensions already enabled in Chrome/Edge." -ForegroundColor Yellow
