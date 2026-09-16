param([ValidateSet('Stop','Start')][string]$Action)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$api = Join-Path $repo 'flipflop-api'
$statePath = Join-Path $env:LOCALAPPDATA 'FlipFlop\refresh-services.json'
if ($Action -eq 'Stop') {
    $running = @()
    foreach ($port in @(4311,18000)) {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $listener) { continue }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($proc.Name -ne 'python.exe' -or $proc.CommandLine -notmatch 'run_dev.py|app.gem_radar_standalone') {
            throw "Port $port is not owned by an expected FlipFlop service"
        }
        $running += @{port=$port; pid=$proc.ProcessId}
    }
    $running | ConvertTo-Json -AsArray | Set-Content -LiteralPath $statePath
    foreach ($proc in $running) { Stop-Process -Id $proc.pid -Force }
} else {
    if (-not (Test-Path -LiteralPath $statePath)) { return }
    $running = @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)
    $env:APP_ENV='development'
    $env:ENVIRONMENT='development'
    # These are local DEV services. Never let the post-refresh restart send
    # listing writes to the production eBay account.
    $env:EBAY_ENVIRONMENT='production'
    $env:EBAY_LISTING_ENVIRONMENT='sandbox'
    $env:PARCEL2GO_ENVIRONMENT='sandbox'
    $env:WEB_ONLY='true'
    foreach ($proc in $running) {
        if (Get-NetTCPConnection -LocalPort $proc.port -State Listen -ErrorAction SilentlyContinue) { continue }
        $launchArgs = if ($proc.port -eq 4311) { @('run_dev.py','--host','0.0.0.0','--port','4311') } else { @('-m','uvicorn','app.gem_radar_standalone:app','--host','0.0.0.0','--port','18000') }
        Start-Process -FilePath (Join-Path $api '.venv\Scripts\python.exe') -ArgumentList $launchArgs -WorkingDirectory $api -WindowStyle Hidden -RedirectStandardOutput (Join-Path $repo "logs\refresh-service-$($proc.port).log") -RedirectStandardError (Join-Path $repo "logs\refresh-service-$($proc.port).err")
    }
}
