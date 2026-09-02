param([switch]$Write)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$api = Join-Path $repo 'flipflop-api'
$env:DATABASE_URL = if ($env:PEER_LOCAL_DATABASE_URL) {$env:PEER_LOCAL_DATABASE_URL} else {'postgresql://flipper:flipper@127.0.0.1:5432/pcflipper'}
$env:PEER_DATABASE_URL = if ($env:PEER_REMOTE_DATABASE_URL) {$env:PEER_REMOTE_DATABASE_URL} else {'postgresql://flipper:flipper@127.0.0.1:15432/pcflipper'}
$env:PEER_SYNC_NODE = if ($env:PEER_SYNC_NODE) {$env:PEER_SYNC_NODE} else {'windows-local'}
$env:PEER_SYNC_INTERVAL_SECONDS = if ($env:PEER_SYNC_INTERVAL_SECONDS) {$env:PEER_SYNC_INTERVAL_SECONDS} else {'30'}
$env:PEER_SYNC_BATCH_SIZE = if ($env:PEER_SYNC_BATCH_SIZE) {$env:PEER_SYNC_BATCH_SIZE} else {'250'}
$args = @('-m','app.services.peer_sync')
if ($Write) { $args += '--write' }
while ($true) {
  try { Push-Location $api; python @args } catch { Add-Content (Join-Path $repo 'logs\peer-sync.log') "$(Get-Date -Format o) $_" } finally { Pop-Location }
  Start-Sleep -Seconds ([int]$env:PEER_SYNC_INTERVAL_SECONDS)
}
