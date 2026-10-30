param([switch]$Once)
$ErrorActionPreference = 'Stop'
$workerState = Join-Path $env:LOCALAPPDATA 'FlipFlop\BrowserWorker'
$config = Get-Content -LiteralPath (Join-Path $workerState 'config.json') -Raw | ConvertFrom-Json
$workerCredential = Import-Clixml -LiteralPath (Join-Path $workerState 'worker-key.xml')
$env:FF_WORKER_API = $config.api
$env:FF_WORKER_KEY = $workerCredential.GetNetworkCredential().Password
$env:FF_BROWSER_STATE_DIR = $workerState
$env:FF_ADMIN_DIR = $config.adminDirectory
$env:FF_CREDENTIALS_FILE = $config.credentialsFile
if (-not $env:FF_CREDENTIALS_FILE) { throw 'Configure credentialsFile to point to the local .env.local file.' }

try {
    $workerArgs = @((Join-Path $PSScriptRoot 'worker.mjs'))
    if ($Once) { $workerArgs += '--once' }
    & node @workerArgs
    if ($LASTEXITCODE -ne 0) { throw "Browser worker exited with code $LASTEXITCODE" }
} finally {
    Remove-Item Env:FF_WORKER_KEY -ErrorAction SilentlyContinue
}
