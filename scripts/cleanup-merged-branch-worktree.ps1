param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [ValidateSet('dev', 'main')]
    [string]$TargetBranch,

    [Parameter(Mandatory = $true)]
    [string]$SourceBranch,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$SourceSha
)

$ErrorActionPreference = 'Stop'

$repoPath = [System.IO.Path]::GetFullPath($RepositoryRoot).TrimEnd('\')
$cleanupRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $repoPath)).TrimEnd('\')
if (-not (Test-Path -LiteralPath $repoPath -PathType Container)) {
    throw "Configured FlipFlop repository does not exist: $repoPath"
}

$gitRoot = (& git -C $repoPath rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or [System.IO.Path]::GetFullPath($gitRoot).TrimEnd('\') -ne $repoPath) {
    throw "Configured path is not the FlipFlop Git repository root: $repoPath"
}

if ([string]::IsNullOrWhiteSpace($SourceBranch) -or $SourceBranch -in @('dev', 'main')) {
    Write-Output "Skipping protected or empty source branch '$SourceBranch'."
    exit 0
}

$expectedBranch = "refs/heads/$SourceBranch"
$worktrees = (& git -C $repoPath worktree list --porcelain 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw 'Could not enumerate registered FlipFlop worktrees.'
}

$records = [System.Collections.Generic.List[object]]::new()
$record = @{}
foreach ($line in $worktrees) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        if ($record.ContainsKey('worktree')) { $records.Add([pscustomobject]$record) }
        $record = @{}
        continue
    }
    $key, $value = $line -split ' ', 2
    if ($key -in @('worktree', 'HEAD', 'branch')) { $record[$key] = $value }
}
if ($record.ContainsKey('worktree')) { $records.Add([pscustomobject]$record) }

$matches = @($records | Where-Object {
    $_.branch -eq $expectedBranch -and $_.HEAD -eq $SourceSha
})
if ($matches.Count -eq 0) {
    Write-Output "No registered worktree matches $expectedBranch at $SourceSha; nothing removed."
    exit 0
}
if ($matches.Count -ne 1) {
    throw "Found $($matches.Count) matching worktrees; refusing ambiguous cleanup."
}

$targetPath = [System.IO.Path]::GetFullPath($matches[0].worktree).TrimEnd('\')
if ($targetPath -eq $repoPath) {
    Write-Output 'The matching branch is the primary checkout; preserving it.'
    exit 0
}

$cleanupPrefix = $cleanupRoot + '\'
if (-not $targetPath.StartsWith($cleanupPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Matching worktree is outside the configured CODING directory; refusing removal: $targetPath"
}

$worktreeBranch = (& git -C $targetPath branch --show-current 2>$null).Trim()
$worktreeHead = (& git -C $targetPath rev-parse HEAD 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or $worktreeBranch -ne $SourceBranch -or $worktreeHead -ne $SourceSha) {
    throw "Worktree identity changed during cleanup; preserving $targetPath"
}

$changes = @(& git -C $targetPath status --porcelain --untracked-files=all 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw "Could not verify worktree status; preserving $targetPath"
}
if ($changes.Count -gt 0) {
    Write-Warning "Worktree has local changes; preserving $targetPath"
    exit 0
}

# Deliberately omit --force: Git must refuse removal if it detects local data.
& git -C $repoPath worktree remove -- $targetPath
if ($LASTEXITCODE -ne 0) {
    throw "Git refused to remove the worktree; it was preserved: $targetPath"
}

Write-Output "Removed merged $TargetBranch worktree for $SourceBranch at $targetPath."
