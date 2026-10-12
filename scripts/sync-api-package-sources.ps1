param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$sources = @(
    [pscustomobject]@{
        Canonical = "templates/dispatch/getting-ready-package-prompt.md"
        Packaged  = "flipflop-api/app/templates/dispatch/getting-ready-package-prompt.md"
    },
    [pscustomobject]@{
        Canonical = "templates/dispatch/dispatch-checklist.md"
        Packaged  = "flipflop-api/app/templates/dispatch/dispatch-checklist.md"
    },
    [pscustomobject]@{
        Canonical = "templates/dispatch/rainmeter/FlipFlop.ini"
        Packaged  = "flipflop-api/app/templates/dispatch/rainmeter/FlipFlop.ini"
    },
    [pscustomobject]@{
        Canonical = "docs/support/customer-support-knowledge-base.md"
        Packaged  = "flipflop-api/app/knowledge/customer-support-knowledge-base.md"
    },
    [pscustomobject]@{
        Canonical = "docs/playbook/software-playbook.md"
        Packaged  = "flipflop-api/app/knowledge/software-playbook.md"
    }
)

$drifted = [System.Collections.Generic.List[string]]::new()
foreach ($source in $sources) {
    $canonicalPath = Join-Path $repositoryRoot $source.Canonical
    $packagedPath = Join-Path $repositoryRoot $source.Packaged
    if (-not (Test-Path -LiteralPath $canonicalPath -PathType Leaf)) {
        throw "Canonical source is missing: $canonicalPath"
    }

    $canonicalHash = (Get-FileHash -LiteralPath $canonicalPath -Algorithm SHA256).Hash
    $packagedHash = if (Test-Path -LiteralPath $packagedPath -PathType Leaf) {
        (Get-FileHash -LiteralPath $packagedPath -Algorithm SHA256).Hash
    } else {
        $null
    }

    if ($canonicalHash -eq $packagedHash) {
        continue
    }
    if ($Check) {
        $drifted.Add($source.Packaged)
        continue
    }

    $packagedDirectory = Split-Path -Parent $packagedPath
    New-Item -ItemType Directory -Path $packagedDirectory -Force | Out-Null
    Copy-Item -LiteralPath $canonicalPath -Destination $packagedPath -Force
    $copiedHash = (Get-FileHash -LiteralPath $packagedPath -Algorithm SHA256).Hash
    if ($canonicalHash -ne $copiedHash) {
        throw "Packaged copy does not match its canonical source: $($source.Packaged)"
    }
}

if ($drifted.Count -gt 0) {
    throw "API package source copies are stale: $($drifted -join ', '). Run scripts/sync-api-package-sources.ps1."
}

if ($Check) {
    Write-Host "All $($sources.Count) API package sources match their canonical files."
} else {
    Write-Host "Synchronized and verified all $($sources.Count) API package sources."
}
