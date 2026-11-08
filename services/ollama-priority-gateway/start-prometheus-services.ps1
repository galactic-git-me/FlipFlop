param([switch]$ForceRestart)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ollama = (Get-Command ollama.exe -ErrorAction Stop).Source
$python = (Get-Command python.exe -ErrorAction Stop).Source

function Get-PriorityGatewayProcesses {
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match '(?i)ollama-priority-gateway[\\/]server\.py'
    })
}

function Get-PriorityGatewayListeners {
    return @(Get-NetTCPConnection -LocalPort 11434,11435,11436 -State Listen -ErrorAction SilentlyContinue)
}

function Get-OllamaUpstreamListeners {
    return @(Get-NetTCPConnection -LocalPort 11433 -State Listen -ErrorAction SilentlyContinue)
}

function Stop-OrphanedOllamaRunners {
    # Windows can leave the model runner alive after ollama.exe exits. Stop only
    # the runner shipped with this Ollama install and only after its parent died.
    $expectedRunner = Join-Path (Split-Path $ollama -Parent) 'lib\ollama\llama-server.exe'
    foreach ($runner in @(Get-CimInstance Win32_Process -Filter "name='llama-server.exe'" -ErrorAction SilentlyContinue)) {
        if ($runner.ExecutablePath -ne $expectedRunner) { continue }
        if (Get-Process -Id ([int]$runner.ParentProcessId) -ErrorAction SilentlyContinue) { continue }
        Stop-Process -Id ([int]$runner.ProcessId) -Force -ErrorAction Stop
        Write-Host "[OK] Stopped orphan Ollama model runner $($runner.ProcessId)."
    }
}

# The Ollama desktop app otherwise claims the public 11434 port. The gateway
# owns that port, so run Ollama's server privately behind it instead.
if ($ForceRestart) {
    $gatewayProcesses = @(Get-PriorityGatewayProcesses)
    $gatewayPids = @($gatewayProcesses | ForEach-Object { [int]$_.ProcessId })
    foreach ($listener in (Get-PriorityGatewayListeners)) {
        if ($listener.OwningProcess -notin $gatewayPids) {
            throw "Refusing to restart Ollama: port $($listener.LocalPort) is owned by unrelated PID $($listener.OwningProcess)."
        }
    }
    foreach ($listener in (Get-OllamaUpstreamListeners)) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$listener.OwningProcess)" -ErrorAction SilentlyContinue
        if (-not $owner -or $owner.ExecutablePath -ne $ollama) {
            throw "Refusing to restart Ollama: private upstream port 11433 is owned by unrelated PID $($listener.OwningProcess)."
        }
    }
    foreach ($gatewayProcess in $gatewayProcesses) {
        Stop-Process -Id ([int]$gatewayProcess.ProcessId) -Force -ErrorAction SilentlyContinue
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        $remainingProcesses = @(Get-PriorityGatewayProcesses)
        $remainingListeners = @(Get-PriorityGatewayListeners)
        if ($remainingProcesses.Count -eq 0 -and $remainingListeners.Count -eq 0) { break }
        if ([DateTime]::UtcNow -gt $deadline) {
            $remainingIds = @($remainingProcesses | ForEach-Object { $_.ProcessId }) -join ', '
            throw "Old gateway processes/listeners did not stop (processes: $remainingIds); refusing to start duplicates."
        }
        Start-Sleep -Milliseconds 250
    } while ($true)
}

$ollamaDirectory = [IO.Path]::GetDirectoryName($ollama)
foreach ($process in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '(?i)^ollama(?: app)?\.exe$' -and
    $_.ExecutablePath -and [IO.Path]::GetDirectoryName($_.ExecutablePath) -eq $ollamaDirectory
})) {
    Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Stop-OrphanedOllamaRunners

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

$gatewayProcesses = @(Get-PriorityGatewayProcesses)
if ($gatewayProcesses.Count -eq 0) {
    $listeners = @(Get-PriorityGatewayListeners)
    if ($listeners.Count -gt 0) {
        $owners = @($listeners | ForEach-Object { "port $($_.LocalPort)=PID $($_.OwningProcess)" }) -join ', '
        throw "Cannot start priority gateway because ports are already occupied: $owners"
    }
    Start-Process -FilePath $python `
        -ArgumentList 'services/ollama-priority-gateway/server.py' `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logRoot "ollama-gateway-$stamp.out.log") `
        -RedirectStandardError (Join-Path $logRoot "ollama-gateway-$stamp.err.log")
} else {
    Write-Host "[OK] Existing priority gateway process found (PID(s): $(@($gatewayProcesses | ForEach-Object { $_.ProcessId }) -join ', '))." -ForegroundColor Green
}

$expected = @(@{ Port = 11434; Priority = 'other' }, @{ Port = 11435; Priority = 'dev' }, @{ Port = 11436; Priority = 'production' })
$deadline = [DateTime]::UtcNow.AddSeconds(30)
do {
    $healthy = $true
    foreach ($endpoint in $expected) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$($endpoint.Port)/health" -TimeoutSec 2
            if ($health.status -ne 'ok' -or $health.priority -ne $endpoint.Priority -or
                $health.generation_concurrency -ne 4 -or $health.ollama_num_parallel -ne 4 -or $health.gpu_only -ne $true) {
                $healthy = $false
            }
        } catch { $healthy = $false }
    }
    if ($healthy) { break }
    Start-Sleep -Milliseconds 500
} while ([DateTime]::UtcNow -lt $deadline)
if (-not $healthy) {
    throw 'Priority gateway did not become healthy on all three ports with the expected priorities and GPU-only limits. Check the timestamped gateway logs.'
}
