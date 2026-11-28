param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCommit,

    [string]$RepositoryRoot = $env:FLIPFLOP_WORKTREE_REPO
)

$ErrorActionPreference = 'Stop'

function Write-Host {
    [CmdletBinding()]
    param(
        [Parameter(Position = 0, ValueFromPipeline = $true)]
        [AllowNull()]
        [object]$Object,
        [ConsoleColor]$ForegroundColor,
        [ConsoleColor]$BackgroundColor,
        [switch]$NoNewline,
        [object]$Separator = ' '
    )
    process {
        $lines = ([string]$Object -split "`r?`n")
        foreach ($line in $lines) {
            $parameters = @{
                Object = "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss.fffK')] $line"
                NoNewline = $NoNewline
                Separator = $Separator
            }
            if ($PSBoundParameters.ContainsKey('ForegroundColor')) { $parameters.ForegroundColor = $ForegroundColor }
            if ($PSBoundParameters.ContainsKey('BackgroundColor')) { $parameters.BackgroundColor = $BackgroundColor }
            Microsoft.PowerShell.Utility\Write-Host @parameters
        }
    }
}

trap {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Join-Path $env:USERPROFILE 'CODING\FlipFlop'
}
$repo = [System.IO.Path]::GetFullPath($RepositoryRoot).TrimEnd('\')
$runtime = Join-Path (Split-Path -Parent $repo) 'FlipFlop-dev-runtime'
if (-not (Test-Path -LiteralPath $repo -PathType Container)) { throw "DEV repository does not exist: $repo" }
Write-Host "[DEV] Push received for commit $ExpectedCommit; validating exact origin/dev source."

function Invoke-Git([string[]]$Arguments, [string]$WorkingDirectory = $repo) {
    $output = & git -C $WorkingDirectory @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed in $WorkingDirectory`: $($output -join "`n")" }
    return ($output -join "`n").Trim()
}

if ([System.IO.Path]::GetFullPath((Invoke-Git @('rev-parse', '--show-toplevel'))).TrimEnd('\') -ine $repo) {
    throw "Configured path is not the FlipFlop repository root: $repo"
}
Invoke-Git @('fetch', '--quiet', 'origin', 'dev:refs/remotes/origin/dev') | Out-Null
$remoteDev = Invoke-Git @('rev-parse', 'origin/dev')
if ($remoteDev -cne $ExpectedCommit) { throw "Validated commit $ExpectedCommit is no longer origin/dev ($remoteDev); refusing stale deployment." }
Invoke-Git @('cat-file', '-e', "$ExpectedCommit^{commit}") | Out-Null
Write-Host "[DEV] Commit $ExpectedCommit is present at origin/dev. Preparing the isolated runtime checkout."

# Use one reusable detached worktree so deployments never touch the developer's
# primary checkout or create a new branch for every deployment.
if (-not (Test-Path -LiteralPath $runtime)) {
    Invoke-Git @('worktree', 'add', '--detach', $runtime, $ExpectedCommit) | Write-Host
} else {
    $registeredWorktrees = Invoke-Git @('worktree', 'list', '--porcelain')
    $runtimeFullPath = [System.IO.Path]::GetFullPath($runtime).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $runtimeIsRegistered = $false
    foreach ($line in ($registeredWorktrees -split "`r?`n")) {
        if (-not $line.StartsWith('worktree ', [StringComparison]::Ordinal)) { continue }
        $registeredPath = $line.Substring('worktree '.Length)
        $registeredFullPath = [System.IO.Path]::GetFullPath($registeredPath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
        if ([string]::Equals($registeredFullPath, $runtimeFullPath, [StringComparison]::OrdinalIgnoreCase)) {
            $runtimeIsRegistered = $true
            break
        }
    }
    if (-not $runtimeIsRegistered) { throw "Runtime path exists but is not a registered worktree; refusing to modify it: $runtime" }
    $runtimeStatePath = 'flipflop-api/data/component-manual-discovery.json'
    $runtimeStatus = Invoke-Git @('status', '--porcelain', '--untracked-files=all') $runtime
    $unexpectedRuntimeChanges = @()
    $hasGeneratedRuntimeState = $false
    foreach ($entry in ($runtimeStatus -split "`r?`n")) {
        if ([string]::IsNullOrWhiteSpace($entry)) { continue }
        if ($entry.Length -lt 4) { $unexpectedRuntimeChanges += $entry; continue }
        $changeCode = $entry.Substring(0, 2)
        $changePath = $entry.Substring(3).Trim('"')
        if ($changePath -ceq $runtimeStatePath -and $changeCode -ceq ' M') {
            $hasGeneratedRuntimeState = $true
            continue
        }
        $unexpectedRuntimeChanges += $entry
    }
    if ($unexpectedRuntimeChanges.Count -gt 0) {
        throw "DEV runtime worktree has local changes; preserving them and refusing deployment: $runtime"
    }
    if (-not [string]::IsNullOrWhiteSpace((Invoke-Git @('branch', '--show-current') $runtime))) { throw 'DEV runtime worktree must remain detached.' }
    $runtimeHead = Invoke-Git @('rev-parse', 'HEAD') $runtime
    if ($hasGeneratedRuntimeState) {
        $currentStateBlob = Invoke-Git @('rev-parse', "HEAD:$runtimeStatePath") $runtime
        $targetStateBlob = Invoke-Git @('rev-parse', "$($ExpectedCommit):$runtimeStatePath") $runtime
        if ($currentStateBlob -cne $targetStateBlob) {
            throw "DEV runtime cache '$runtimeStatePath' has local changes and the target commit changes its source blob; preserving the cache and refusing deployment."
        }
    }
    & git -C $runtime merge-base --is-ancestor $runtimeHead $ExpectedCommit
    if ($LASTEXITCODE -ne 0) { throw "Runtime worktree cannot fast-forward from $runtimeHead to $ExpectedCommit." }
    if ($runtimeHead -cne $ExpectedCommit) { Invoke-Git @('checkout', '--detach', $ExpectedCommit) $runtime | Write-Host }
}

function Ensure-Junction([string]$Target, [string]$Source) {
    if (-not (Test-Path -LiteralPath $Source)) { throw "Required shared dependency is missing: $Source" }
    if (Test-Path -LiteralPath $Target) {
        $item = Get-Item -LiteralPath $Target -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -or $item.Target -ne $Source) {
            throw "Runtime dependency path exists and is not the expected junction: $Target"
        }
        return
    }
    New-Item -ItemType Junction -Path $Target -Target $Source | Out-Null
}

Ensure-Junction (Join-Path $runtime 'flipflop-api\.venv') (Join-Path $repo 'flipflop-api\.venv')
Ensure-Junction (Join-Path $runtime 'flipflop-admin\node_modules') (Join-Path $repo 'flipflop-admin\node_modules')
$sourceEnv = Join-Path $repo 'flipflop-api\.env.local'
$targetEnv = Join-Path $runtime 'flipflop-api\.env.local'
if (-not (Test-Path -LiteralPath $sourceEnv -PathType Leaf)) { throw 'Primary checkout flipflop-api/.env.local is required for DEV runtime configuration.' }
if (-not (Test-Path -LiteralPath $targetEnv)) { New-Item -ItemType HardLink -Path $targetEnv -Target $sourceEnv | Out-Null }
elseif ((Get-FileHash -LiteralPath $targetEnv).Hash -cne (Get-FileHash -LiteralPath $sourceEnv).Hash) { throw 'Runtime .env.local differs from the primary checkout; refusing to overwrite either file.' }
$sourceEnvBase = Join-Path $repo 'flipflop-api\.env'
if (Test-Path -LiteralPath $sourceEnvBase -PathType Leaf) {
    $targetEnvBase = Join-Path $runtime 'flipflop-api\.env'
    if (-not (Test-Path -LiteralPath $targetEnvBase)) { New-Item -ItemType HardLink -Path $targetEnvBase -Target $sourceEnvBase | Out-Null }
    elseif ((Get-FileHash -LiteralPath $targetEnvBase).Hash -cne (Get-FileHash -LiteralPath $sourceEnvBase).Hash) { throw 'Runtime .env differs from the primary checkout; refusing to overwrite either file.' }
}

$storefront = Join-Path (Split-Path -Parent $repo) 'FlipFlop.shop'
if (-not (Test-Path -LiteralPath $storefront -PathType Container) -or -not (Test-Path -LiteralPath (Join-Path $storefront '.git'))) { throw "DEV storefront checkout is missing or not a Git checkout: $storefront" }
$storefrontDefaultRef = Invoke-Git @('symbolic-ref', '--short', 'refs/remotes/origin/HEAD') $storefront
if ($storefrontDefaultRef -notmatch '^origin/(.+)$') { throw "Could not resolve storefront default branch from $storefrontDefaultRef." }
$storefrontDefault = $Matches[1]
if ((Invoke-Git @('branch', '--show-current') $storefront) -cne $storefrontDefault -or
    -not [string]::IsNullOrWhiteSpace((Invoke-Git @('status', '--porcelain', '--untracked-files=all') $storefront))) {
    throw 'DEV storefront must be clean and on its origin default branch; preserving existing changes.'
}
Invoke-Git @('fetch', '--quiet', 'origin', "${storefrontDefault}:refs/remotes/origin/${storefrontDefault}") $storefront | Out-Null
if ((Invoke-Git @('rev-parse', 'HEAD') $storefront) -cne (Invoke-Git @('rev-parse', "origin/$storefrontDefault") $storefront)) { throw 'DEV storefront is stale; refusing deployment.' }
Write-Host "[DEV] Runtime source and storefront prerequisites are ready for commit $ExpectedCommit."

$launcher = Join-Path $runtime 'scripts\start-all-servers.ps1'
$logs = Join-Path $runtime '.run-logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$runId = "dev-deploy-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$PID"
$stdout = Join-Path $logs "$runId.out.log"
$stderr = Join-Path $logs "$runId.err.log"
$pwsh = Join-Path $PSHOME 'pwsh.exe'
if (-not (Test-Path -LiteralPath $launcher) -or -not (Test-Path -LiteralPath $pwsh)) { throw 'DEV launcher or PowerShell executable is unavailable.' }

$env:FLIPFLOP_EXPECTED_SOURCE_COMMIT = $ExpectedCommit
$env:FLIPFLOP_WORKTREE_REPO = $repo
Write-Host '[DEV] Checking launcher prerequisites.'
& $pwsh -NoProfile -ExecutionPolicy Bypass -File $launcher -AllowDetachedDev -CheckOnly
if ($LASTEXITCODE -ne 0) { throw "DEV launcher preflight failed with exit code $LASTEXITCODE; ports were not intentionally changed." }

Write-Host "[DEV] Starting shared DEV services for commit $ExpectedCommit."
$process = Start-Process -FilePath $pwsh -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $launcher, '-AllowDetachedDev') `
    -WorkingDirectory $runtime -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$deadline = [DateTime]::UtcNow.AddMinutes(12)
$verified = $false
do {
    if ($process.HasExited) { throw "DEV launcher exited with code $($process.ExitCode). See $stdout and $stderr." }
    try {
        $api = Invoke-RestMethod -Uri 'http://127.0.0.1:4311/health' -TimeoutSec 5
        $admin = Invoke-RestMethod -Uri 'http://127.0.0.1:4312/build-info' -TimeoutSec 5
        $storeResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:4313/' -TimeoutSec 5 -UseBasicParsing
        if ($api.status -eq 'ok' -and $api.source_commit -ceq $ExpectedCommit -and $admin.source_commit -ceq $ExpectedCommit -and $storeResponse.StatusCode -ge 200 -and $storeResponse.StatusCode -lt 400) { $verified = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
} while ([DateTime]::UtcNow -lt $deadline)
if (-not $verified) { throw "DEV runtime did not report API/admin source $ExpectedCommit and a healthy storefront before timeout. See $stdout and $stderr." }
Write-Host "[DEV] Deployment verified: API and admin report $ExpectedCommit; storefront responds on port 4313."
