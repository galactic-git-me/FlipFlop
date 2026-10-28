param([switch]$ForceRestart)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ollama = (Get-Command ollama.exe -ErrorAction Stop).Source
$python = (Get-Command python.exe -ErrorAction Stop).Source

# The Ollama desktop app otherwise claims the public 11434 port. The gateway
# owns that port, so run Ollama's server privately behind it instead.
if ($ForceRestart) {
    $gatewayPids = Get-NetTCPConnection -LocalPort 11434,11435,11436 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($gatewayPid in $gatewayPids) {
        $gatewayProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $gatewayPid" -ErrorAction SilentlyContinue
        if ($gatewayProcess -and $gatewayProcess.CommandLine -match 'ollama-priority-gateway[\\/]server\.py') {
            Stop-Process -Id $gatewayPid -Force -ErrorAction SilentlyContinue
        } elseif ($gatewayProcess) {
            throw "Refusing to restart Ollama: port listener PID $gatewayPid is not the priority gateway."
        }
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while (Get-NetTCPConnection -LocalPort 11434,11435,11436 -State Listen -ErrorAction SilentlyContinue) {
        if ([DateTime]::UtcNow -gt $deadline) {
            throw 'Old gateway listeners did not stop; refusing to start duplicate listeners.'
        }
        Start-Sleep -Milliseconds 250
    }
}

Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$env:OLLAMA_HOST = '127.0.0.1:11433'
$env:OLLAMA_NUM_PARALLEL = '4'
$env:OLLAMA_GATEWAY_CONCURRENCY = '4'
$logRoot = Join-Path $repoRoot 'logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logRoot "ollama-$stamp.out.log") `
    -RedirectStandardError (Join-Path $logRoot "ollama-$stamp.err.log")
Start-Sleep -Seconds 2

if (-not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $python `
        -ArgumentList 'services/ollama-priority-gateway/server.py' `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logRoot "ollama-gateway-$stamp.out.log") `
        -RedirectStandardError (Join-Path $logRoot "ollama-gateway-$stamp.err.log")
}
