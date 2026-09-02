<#
.SYNOPSIS
Applies and verifies Alembic migrations on both peer PostgreSQL databases.

.DESCRIPTION
Schema migrations are deliberately separate from app-level peer_sync, which
copies selected rows only.  This script uses the same local/remote connection
settings as run-peer-sync.ps1, runs every pending Alembic migration on each
database, then confirms both databases are at every current Alembic head.

The remote URL normally targets the SSH forward on port 15432 established by
start-peer-sync-tunnel.ps1.  It never prints connection strings or secrets.
#>
[CmdletBinding()]
param(
    [ValidateSet('Both', 'Local', 'Remote')]
    [string]$Target = 'Both',
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$api = Join-Path $repo 'flipflop-api'

if (-not (Test-Path (Join-Path $api 'alembic.ini'))) {
    throw "Could not find Alembic configuration under $api"
}

$localUrl = if ($env:PEER_LOCAL_DATABASE_URL) {
    $env:PEER_LOCAL_DATABASE_URL
} else {
    'postgresql://flipper:flipper@127.0.0.1:5432/pcflipper'
}
$remoteUrl = if ($env:PEER_REMOTE_DATABASE_URL) {
    $env:PEER_REMOTE_DATABASE_URL
} else {
    'postgresql://flipper:flipper@127.0.0.1:15432/pcflipper'
}

function Invoke-AlembicForDatabase {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$ConnectionString
    )

    # Alembic env.py uses SYNC_DATABASE_URL to construct its synchronous
    # engine. Restore the caller's value afterwards so starting peer sync is
    # not affected by this script.
    $previousSyncUrl = $env:SYNC_DATABASE_URL
    try {
        $env:SYNC_DATABASE_URL = $ConnectionString
        Push-Location $api
        try {
            if (-not $VerifyOnly) {
                Write-Host "Applying migrations to $Name database..." -ForegroundColor Cyan
                & python -m alembic upgrade head
                if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade failed for $Name database" }
            }

            Write-Host "Verifying $Name database revision..." -ForegroundColor Cyan
            $current = (& python -m alembic current 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) { throw "Alembic revision check failed for $Name database" }
            if ($current -notmatch '\(head\)') {
                throw "$Name database is not at an Alembic head. Output: $($current.Trim())"
            }
            Write-Host "$Name database is at head: $($current.Trim())" -ForegroundColor Green
        }
        finally {
            Pop-Location
        }
    }
    finally {
        if ($null -eq $previousSyncUrl) {
            Remove-Item Env:SYNC_DATABASE_URL -ErrorAction SilentlyContinue
        } else {
            $env:SYNC_DATABASE_URL = $previousSyncUrl
        }
    }
}

if ($Target -in @('Both', 'Local')) {
    Invoke-AlembicForDatabase -Name 'local' -ConnectionString $localUrl
}
if ($Target -in @('Both', 'Remote')) {
    Invoke-AlembicForDatabase -Name 'remote' -ConnectionString $remoteUrl
}

Write-Host 'Peer database schema verification completed.' -ForegroundColor Green
