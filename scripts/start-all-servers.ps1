# FlipFlop local development launcher (Windows)
# Starts only development services. Production runs on andromeda-ts.

param(
    [switch]$NoBackend,
    [switch]$NoAdmin,
    [switch]$NoFrontend,
    [switch]$GemRadarStandalone,
    [switch]$NoOllamaGateway,
    [switch]$BuildExtension,
    [switch]$CheckOnly,
    [switch]$AllowBranch
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$storefrontRoot = Join-Path (Split-Path -Parent $projectRoot) 'FlipFlop.shop'
$logsDir = Join-Path $projectRoot 'logs'
$apiRoot = Join-Path $projectRoot 'flipflop-api'
$launcherRunId = "$(Get-Date -Format 'yyyyMMdd-HHmmss')-$PID"

function Get-ApiEnvironmentValue([string]$Name) {
    if ($Name -eq 'OLLAMA_BASE_URL') {
        $devProcessValue = [Environment]::GetEnvironmentVariable('DEV_OLLAMA_BASE_URL')
        if (-not [string]::IsNullOrWhiteSpace($devProcessValue)) { return $devProcessValue.Trim() }
    } else {
        $processValue = [Environment]::GetEnvironmentVariable($Name)
        if (-not [string]::IsNullOrWhiteSpace($processValue)) { return $processValue.Trim() }
    }

    foreach ($fileName in @('.env.local', '.env')) {
        $filePath = Join-Path $apiRoot $fileName
        if (-not (Test-Path -LiteralPath $filePath)) { continue }
        foreach ($line in Get-Content -LiteralPath $filePath) {
            if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*?)\s*$") {
                $value = $Matches[1].Trim().Trim('"').Trim("'")
                if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
            }
        }
    }
    if ($Name -eq 'OLLAMA_BASE_URL') {
        $processValue = [Environment]::GetEnvironmentVariable($Name)
        if (-not [string]::IsNullOrWhiteSpace($processValue)) { return $processValue.Trim() }
        return 'http://127.0.0.1:11435'
    }
    if ($Name -eq 'OLLAMA_MODEL') { return 'qwen2.5:7b-instruct' }
    throw "$Name must be set in the process environment or flipflop-api/.env.local/.env."
}

function Get-ApiLocalEnvironmentValue([string]$Name) {
    $filePath = Join-Path $apiRoot '.env.local'
    if (-not (Test-Path -LiteralPath $filePath)) {
        throw "Development-only $Name must be set in flipflop-api/.env.local."
    }
    foreach ($line in Get-Content -LiteralPath $filePath) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*?)\s*$") {
            $value = $Matches[1].Trim().Trim('"').Trim("'")
            if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
        }
    }
    throw "Development-only $Name must be set in flipflop-api/.env.local; refusing to fall back to .env."
}

function Assert-DevelopmentPrerequisites {
    $required = @()
    if (-not $NoBackend) { $required += Join-Path $projectRoot 'flipflop-api\.venv\Scripts\python.exe' }
    if (-not $NoAdmin) { $required += Join-Path $projectRoot 'flipflop-admin\package.json' }
    if (-not $NoFrontend) { $required += Join-Path $storefrontRoot 'package.json' }
    foreach ($path in $required) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Development prerequisite is missing: $path" }
    }
    if ((-not $NoAdmin -or -not $NoFrontend) -and -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw 'npm.cmd is not available on PATH.'
    }

    Assert-LatestDevelopmentSource
}

# DEV must include the latest origin/dev. Branch names do not establish whether
# the checked-out code is stale; feature branches based on current dev are safe.
function Assert-LatestDevelopmentSource {
    $branch = (& git -C $projectRoot branch --show-current 2>$null).Trim()
    & git -C $projectRoot fetch origin dev --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[WARN] Could not fetch origin/dev; cannot confirm this is the latest DEV source.' -ForegroundColor Yellow
        return
    }
    $head = (& git -C $projectRoot rev-parse HEAD).Trim()
    $latest = (& git -C $projectRoot rev-parse origin/dev).Trim()

    if (& git -C $projectRoot merge-base --is-ancestor origin/dev HEAD) {
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Serving $branch at $($head.Substring(0,9)); includes origin/dev @ $($latest.Substring(0,9))" -ForegroundColor Green
            return
        }
    }

    if ($branch -eq 'dev') {
        if ($head -eq $latest) {
        Write-Host "[OK] Serving origin/dev @ $($head.Substring(0,9))" -ForegroundColor Green
        return
        }
        if (& git -C $projectRoot status --porcelain --untracked-files=no) {
            throw "dev is behind origin/dev ($($head.Substring(0,9)) vs $($latest.Substring(0,9))) and has uncommitted changes; commit or stash, then re-run."
        }
        & git -C $projectRoot merge --ff-only origin/dev
        if ($LASTEXITCODE -ne 0) { throw 'Local dev has diverged from origin/dev and cannot fast-forward; fix before starting DEV.' }
        Write-Host "[OK] Fast-forwarded dev to origin/dev @ $((& git -C $projectRoot rev-parse --short HEAD).Trim())" -ForegroundColor Green
        return
    }

    $label = if ($branch) { $branch } else { 'detached HEAD' }
    throw "DEV checkout '$label' at $($head.Substring(0,9)) does not include latest origin/dev @ $($latest.Substring(0,9)); update this branch before starting DEV."
}

function Stop-PortListener([int]$Port) {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($ownerPid in @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
        if ($ownerPid -and $ownerPid -ne 0) {
            & taskkill.exe /PID $ownerPid /T /F 2>&1 | Out-Null
            Write-Host "  [OK] Freed development port $Port" -ForegroundColor Green
        }
    }
}

function Stop-FlipFlopProcessTree([int]$ProcessId) {
    if (-not $ProcessId -or $ProcessId -eq $PID) { return }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $process) { return }
    $commandLine = [string]$process.CommandLine
    $owned = $commandLine -match [regex]::Escape($projectRoot) -or
        $commandLine -match 'run_dev\.py|next dev|next-server|uvicorn'
    if (-not $owned) { throw "Refusing to stop unrelated PID $ProcessId ($commandLine) on a DEV port." }
    & taskkill.exe /PID $ProcessId /T /F 2>&1 | Out-Null
}

function Stop-DevelopmentProcesses([int[]]$Ports) {
    foreach ($port in $Ports) {
        $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($ownerPid in @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
            if ($ownerPid -and $ownerPid -ne 0) {
                Stop-FlipFlopProcessTree -ProcessId $ownerPid
                Write-Host "  [OK] Stopped FlipFlop process tree on DEV port $port" -ForegroundColor Green
            }
        }
    }
    # Killing only the listening reloader worker leaves its supervisor alive.
    # Its launcher command includes this checkout's per-run log path.
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'run_dev\.py' -and $_.CommandLine -match '--port\s+4314' } |
        ForEach-Object {
            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.ParentProcessId)" -ErrorAction SilentlyContinue
            if ($parent -and $parent.CommandLine -match [regex]::Escape($projectRoot) -and $parent.CommandLine -match 'run_dev\.py') {
                Stop-FlipFlopProcessTree -ProcessId $parent.ProcessId
            }
        }
}

function Test-ListeningPort([int]$Port) {
    # Get-NetTCPConnection can briefly miss active listeners during rapid
    # Next.js reloads. Confirm readiness by opening a short loopback TCP socket.
    $client = [System.Net.Sockets.TcpClient]::new()
    $waitHandle = $null
    try {
        $connect = $client.BeginConnect([System.Net.IPAddress]::Loopback, $Port, $null, $null)
        $waitHandle = $connect.AsyncWaitHandle
        if (-not $waitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($connect)
        return $client.Connected
    } catch {
        return $false
    } finally {
        if ($waitHandle) { $waitHandle.Dispose() }
        $client.Dispose()
    }
}

function Get-OllamaServiceFailures {
    $failures = @()
    try {
        $engine = Invoke-RestMethod -Uri 'http://127.0.0.1:11433/api/version' -TimeoutSec 2
        if ([string]::IsNullOrWhiteSpace([string]$engine.version)) { $failures += 'engine:11433' }
    } catch {
        $failures += 'engine:11433'
    }

    foreach ($gateway in @(
        @{ Port = 11434; Priority = 'other' },
        @{ Port = 11435; Priority = 'dev' },
        @{ Port = 11436; Priority = 'production' }
    )) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$($gateway.Port)/health" -TimeoutSec 2
            if ($health.status -ne 'ok' -or
                $health.priority -ne $gateway.Priority -or
                $health.generation_concurrency -ne 4 -or
                $health.ollama_num_parallel -ne 4 -or
                $health.gpu_only -ne $true) {
                $failures += "gateway:$($gateway.Port)"
            }
        } catch {
            $failures += "gateway:$($gateway.Port)"
        }
    }
    return $failures
}

function Ensure-OllamaPriorityGateway {
    if ($NoOllamaGateway) {
        Write-Host '[SKIP] Ollama priority gateway check disabled.' -ForegroundColor Yellow
        return
    }

    $failures = @(Get-OllamaServiceFailures)
    $gatewayProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match '(?i)ollama-priority-gateway[\\/]server\.py'
    })
    $duplicateOrMissingGateway = $gatewayProcesses.Count -ne 1
    $needsRestart = $failures.Count -gt 0 -or $duplicateOrMissingGateway
    if ($needsRestart) {
        $reason = if ($duplicateOrMissingGateway) { "gateway process count: $($gatewayProcesses.Count)" } else { "unhealthy services: $($failures -join ', ')" }
        Write-Host "[*] Starting/reconfiguring Ollama for four concurrent requests ($reason)..." -ForegroundColor Cyan
        & (Join-Path $projectRoot 'services\ollama-priority-gateway\start-prometheus-services.ps1') -ForceRestart
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        $failures = @(Get-OllamaServiceFailures)
        if ($failures.Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($failures.Count -gt 0) {
        throw "Ollama priority services did not become healthy. Check: $($failures -join ', ')"
    }
    Write-Host '[OK] Ollama: engine 11433; DEV gateway and Ollama each allow four concurrent generations.' -ForegroundColor Green
}

function Warm-OllamaModel([string]$BaseUrl, [string]$Model) {
    if ($NoOllamaGateway) { return }

    $uri = "$($BaseUrl.TrimEnd('/'))/api/chat"
    $payload = @{
        model = $Model
        messages = @(@{ role = 'user'; content = 'Reply OK.' })
        stream = $false
        keep_alive = -1
        options = @{ num_predict = 1 }
    } | ConvertTo-Json -Depth 5 -Compress

    Write-Host "[*] Loading Ollama model '$Model' and keeping it resident..." -ForegroundColor Cyan
    try {
        Invoke-RestMethod -Uri $uri -Method Post -ContentType 'application/json' `
            -Body $payload -TimeoutSec 180 | Out-Null
        Write-Host "[OK] Ollama model '$Model' is loaded and will stay resident until Ollama stops." -ForegroundColor Green
    } catch {
        Write-Host "[WARN] Could not warm Ollama model '$Model': $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host '[WARN] The API can still use its configured cloud fallback; check the model name and Ollama logs.' -ForegroundColor Yellow
    }
}

function Start-DevelopmentServer {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [int]$Port,
        [ConsoleColor]$Color
    )

    # Each launcher run gets independent files. An abandoned DEV child can
    # keep its redirected log open after its listening port has gone away.
    $logFile = Join-Path $logsDir "$Name-$launcherRunId.log"
    $arguments = @('/d', '/s', '/c', "$Command > `"$logFile`" 2>&1")
    $process = Start-Process -FilePath 'cmd.exe' -ArgumentList $arguments -WorkingDirectory $WorkingDirectory -NoNewWindow -PassThru
    return @{ Name = $Name; Process = $process; Port = $Port; Color = $Color; LogFile = $logFile }
}

Assert-DevelopmentPrerequisites

if ($CheckOnly) {
    Write-Host '[OK] Development launcher syntax and prerequisites are valid.' -ForegroundColor Green
    exit 0
}

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '              FLIPFLOP DEVELOPMENT SERVERS' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host 'Environment: DEV on prometheus-ts (hot reload enabled)' -ForegroundColor Yellow
Write-Host 'Production:  untouched on andromeda-ts' -ForegroundColor Gray
Write-Host ''

if ($BuildExtension) {
    & (Join-Path $PSScriptRoot 'prepare-extension.ps1') -Mode development -ProjectRoot $projectRoot
}

Ensure-OllamaPriorityGateway
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$portsToClean = @()
if (-not $NoBackend) { $portsToClean += 4314 }
if (-not $NoAdmin) { $portsToClean += 4312 }
if (-not $NoFrontend) { $portsToClean += 4313 }
if ($GemRadarStandalone) { $portsToClean += 18000 }

Write-Host '[*] Clearing selected development ports...' -ForegroundColor Cyan
Stop-DevelopmentProcesses -Ports $portsToClean

$env:FLIPFLOP_RUNTIME_ENV = 'development'
$env:EBAY_ENVIRONMENT = 'production'
$env:EBAY_LISTING_ENVIRONMENT = 'sandbox'
$env:AMAZON_SP_API_ENVIRONMENT = 'sandbox'
$env:AMAZON_SP_API_ENDPOINT = 'https://sandbox.sellingpartnerapi-eu.amazon.com'
$env:AMAZON_SP_API_SELLER_ID = 'SANDBOX_SELLER_ID'
if (-not $NoBackend) {
    foreach ($name in @(
        'AMAZON_SP_API_CLIENT_ID',
        'AMAZON_SP_API_CLIENT_SECRET',
        'AMAZON_SP_API_REFRESH_TOKEN',
        'AMAZON_SP_API_MARKETPLACE_ID'
    )) {
        [Environment]::SetEnvironmentVariable($name, (Get-ApiLocalEnvironmentValue $name), 'Process')
    }
}
$ollamaBaseUrl = Get-ApiEnvironmentValue 'OLLAMA_BASE_URL'
$ollamaModel = Get-ApiEnvironmentValue 'OLLAMA_MODEL'
$env:OLLAMA_BASE_URL = $ollamaBaseUrl
$env:OLLAMA_MODEL = $ollamaModel
Warm-OllamaModel -BaseUrl $ollamaBaseUrl -Model $ollamaModel

$servers = @()
$apiUrl = 'http://127.0.0.1:4314'

if (-not $NoBackend) {
    $command = "set `"FLIPFLOP_RUNTIME_ENV=development`" && set `"OLLAMA_BASE_URL=$ollamaBaseUrl`" && set `"OLLAMA_MODEL=$ollamaModel`" && set `"EBAY_ENVIRONMENT=production`" && set `"EBAY_LISTING_ENVIRONMENT=sandbox`" && set `"AMAZON_SP_API_ENVIRONMENT=sandbox`" && set `"AMAZON_SP_API_ENDPOINT=https://sandbox.sellingpartnerapi-eu.amazon.com`" && set `"AMAZON_SP_API_SELLER_ID=SANDBOX_SELLER_ID`" && set `"ADMIN_FRONTEND_URL=http://localhost:4312`" && set `"FRONTEND_URL=http://localhost:4313`" && .venv\Scripts\python.exe run_dev.py --host 127.0.0.1 --port 4314"
    $servers += Start-DevelopmentServer -Name 'backend' -WorkingDirectory (Join-Path $projectRoot 'flipflop-api') -Command $command -Port 4314 -Color Yellow
}

if ($GemRadarStandalone) {
    $command = "set `"FLIPFLOP_RUNTIME_ENV=development`" && set `"OLLAMA_BASE_URL=$ollamaBaseUrl`" && set `"OLLAMA_MODEL=$ollamaModel`" && set `"PYTHONUNBUFFERED=1`" && .venv\Scripts\python.exe -m uvicorn app.gem_radar_standalone:app --host 127.0.0.1 --port 18000 --reload --reload-dir app"
    $servers += Start-DevelopmentServer -Name 'gemradar-api' -WorkingDirectory (Join-Path $projectRoot 'flipflop-api') -Command $command -Port 18000 -Color Blue
}

if (-not $NoAdmin) {
    $command = "set `"NODE_ENV=development`" && set `"BACKEND_URL=$apiUrl`" && set `"NEXT_PUBLIC_API_URL=$apiUrl`" && set `"NEXT_PUBLIC_FLIPFLOP_ENV=development`" && set `"EBAY_OPS_BACKEND_URL=$apiUrl`" && set `"GEMRADAR_URL=$apiUrl`" && set `"NEXT_PUBLIC_OLLAMA_BASE_URL=$ollamaBaseUrl`" && set `"NEXT_PUBLIC_OLLAMA_MODEL=$ollamaModel`" && npm.cmd run dev -- -p 4312 -H 127.0.0.1"
    $servers += Start-DevelopmentServer -Name 'admin' -WorkingDirectory (Join-Path $projectRoot 'flipflop-admin') -Command $command -Port 4312 -Color Green
}

if (-not $NoFrontend) {
    $command = "set `"NODE_ENV=development`" && set `"BACKEND_URL=$apiUrl`" && set `"NEXT_PUBLIC_API_URL=$apiUrl`" && set `"NEXT_PUBLIC_FLIPFLOP_ENV=development`" && set `"NEXT_PUBLIC_OLLAMA_BASE_URL=$ollamaBaseUrl`" && set `"NEXT_PUBLIC_OLLAMA_MODEL=$ollamaModel`" && npm.cmd run dev -- --webpack -p 4313 -H 127.0.0.1"
    $servers += Start-DevelopmentServer -Name 'frontend' -WorkingDirectory $storefrontRoot -Command $command -Port 4313 -Color Magenta
}

Write-Host '[*] Waiting for development servers...' -ForegroundColor Cyan
$deadline = [DateTime]::UtcNow.AddSeconds(30)
do {
    $pending = @($servers | Where-Object { -not (Test-ListeningPort $_.Port) })
    if ($pending.Count -eq 0) { break }
    Start-Sleep -Milliseconds 500
} while ([DateTime]::UtcNow -lt $deadline)

Write-Host ''
foreach ($server in $servers) {
    if (Test-ListeningPort $server.Port) {
        Write-Host "[RUNNING] $($server.Name.PadRight(14)) http://127.0.0.1:$($server.Port)" -ForegroundColor $server.Color
    } else {
        Write-Host "[FAILED]  $($server.Name.PadRight(14)) See $($server.LogFile)" -ForegroundColor Red
    }
}
Write-Host "[INFO] DEV uses production marketplace reads, sandbox eBay listing writes, and Ollama gateway $ollamaBaseUrl (second priority: after production, before other apps)." -ForegroundColor Yellow
Write-Host '[INFO] Press Ctrl+C to stop the development servers started here.' -ForegroundColor Gray

$serverListeningState = @{}
foreach ($server in $servers) {
    $serverListeningState[$server.Name] = Test-ListeningPort $server.Port
}

try {
    while ($true) {
        Start-Sleep -Seconds 5
        foreach ($server in $servers) {
            $isListening = Test-ListeningPort $server.Port
            $wasListening = $serverListeningState[$server.Name]

            if (-not $isListening -and $wasListening) {
                Write-Host "[WARN] $($server.Name) is not listening; see $($server.LogFile)" -ForegroundColor Yellow
            } elseif ($isListening -and -not $wasListening) {
                Write-Host "[RUNNING] $($server.Name) is listening again at http://127.0.0.1:$($server.Port)" -ForegroundColor $server.Color
            }

            $serverListeningState[$server.Name] = $isListening
        }
    }
} finally {
    Write-Host ''
    Write-Host '[*] Stopping development servers...' -ForegroundColor Yellow
    foreach ($server in $servers) {
        if (-not $server.Process.HasExited) { Stop-FlipFlopProcessTree -ProcessId $server.Process.Id }
    }
    Write-Host '[OK] Development servers stopped. Ollama and its shared gateway remain running.' -ForegroundColor Green
}
