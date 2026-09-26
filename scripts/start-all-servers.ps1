# FlipFlop local development launcher (Windows)
# Starts only development services. Production runs on andromeda-ts.

param(
    [switch]$NoBackend,
    [switch]$NoAdmin,
    [switch]$NoFrontend,
    [switch]$GemRadarStandalone,
    [switch]$NoOllamaGateway,
    [switch]$BuildExtension,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$storefrontRoot = Join-Path (Split-Path -Parent $projectRoot) 'FlipFlop.shop'
$logsDir = Join-Path $projectRoot 'logs'
$apiRoot = Join-Path $projectRoot 'flipflop-api'

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
    }
    if ($Name -eq 'OLLAMA_MODEL') { return 'qwen2.5:7b-instruct' }
    throw "$Name must be set in the process environment or flipflop-api/.env.local/.env."
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

    $branch = (& git -C $projectRoot branch --show-current 2>$null).Trim()
    if ($branch -and $branch -ne 'dev') {
        Write-Host "[WARN] FlipFlop is on branch '$branch'; development normally uses 'dev'." -ForegroundColor Yellow
        Write-Host '[WARN] The launcher will not switch branches or modify your working tree.' -ForegroundColor Yellow
    }
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

function Test-ListeningPort([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Ensure-OllamaPriorityGateway {
    if ($NoOllamaGateway) {
        Write-Host '[SKIP] Ollama priority gateway check disabled.' -ForegroundColor Yellow
        return
    }

    $requiredPorts = @(11433, 11434, 11435, 11436)
    $missingPorts = @($requiredPorts | Where-Object { -not (Test-ListeningPort $_) })
    if ($missingPorts.Count -gt 0) {
        Write-Host "[*] Starting Ollama and its priority gateway (missing ports: $($missingPorts -join ', '))..." -ForegroundColor Cyan
        & (Join-Path $projectRoot 'services\ollama-priority-gateway\start-prometheus-services.ps1')
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        $missingPorts = @($requiredPorts | Where-Object { -not (Test-ListeningPort $_) })
        if ($missingPorts.Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($missingPorts.Count -gt 0) {
        throw "Ollama priority services did not become ready. Missing ports: $($missingPorts -join ', ')"
    }
    Write-Host '[OK] Ollama: engine 11433; other 11434; DEV 11435; PROD 11436.' -ForegroundColor Green
}

function Start-DevelopmentServer {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [int]$Port,
        [ConsoleColor]$Color
    )

    $logFile = Join-Path $logsDir "$Name.log"
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
if (-not $NoBackend) { $portsToClean += 4311 }
if (-not $NoAdmin) { $portsToClean += 4312 }
if (-not $NoFrontend) { $portsToClean += 4313 }
if ($GemRadarStandalone) { $portsToClean += 18000 }

Write-Host '[*] Clearing selected development ports...' -ForegroundColor Cyan
foreach ($port in $portsToClean) { Stop-PortListener $port }

$env:FLIPFLOP_RUNTIME_ENV = 'development'
$env:EBAY_ENVIRONMENT = 'production'
$env:EBAY_LISTING_ENVIRONMENT = 'sandbox'
$env:AMAZON_SP_API_ENVIRONMENT = 'production'
$env:AMAZON_SP_API_ENDPOINT = 'https://sellingpartnerapi-eu.amazon.com'
$ollamaBaseUrl = Get-ApiEnvironmentValue 'OLLAMA_BASE_URL'
$ollamaModel = Get-ApiEnvironmentValue 'OLLAMA_MODEL'
$env:OLLAMA_BASE_URL = $ollamaBaseUrl
$env:OLLAMA_MODEL = $ollamaModel

$servers = @()
$apiUrl = 'http://127.0.0.1:4311'

if (-not $NoBackend) {
    $command = "set `"FLIPFLOP_RUNTIME_ENV=development`" && set `"OLLAMA_BASE_URL=$ollamaBaseUrl`" && set `"OLLAMA_MODEL=$ollamaModel`" && set `"EBAY_ENVIRONMENT=production`" && set `"EBAY_LISTING_ENVIRONMENT=sandbox`" && set `"AMAZON_SP_API_ENVIRONMENT=production`" && set `"AMAZON_SP_API_ENDPOINT=https://sellingpartnerapi-eu.amazon.com`" && set `"ADMIN_FRONTEND_URL=http://localhost:4312`" && set `"FRONTEND_URL=http://localhost:4313`" && .venv\Scripts\python.exe run_dev.py --host 127.0.0.1 --port 4311"
    $servers += Start-DevelopmentServer -Name 'backend' -WorkingDirectory (Join-Path $projectRoot 'flipflop-api') -Command $command -Port 4311 -Color Yellow
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
Write-Host "[INFO] DEV uses production marketplace reads, sandbox eBay listing writes, and Ollama gateway $ollamaBaseUrl (priority 1)." -ForegroundColor Yellow
Write-Host '[INFO] Press Ctrl+C to stop the development servers started here.' -ForegroundColor Gray

try {
    while ($true) {
        Start-Sleep -Seconds 5
        foreach ($server in $servers) {
            if (-not (Test-ListeningPort $server.Port)) {
                Write-Host "[WARN] $($server.Name) is not listening; see $($server.LogFile)" -ForegroundColor Yellow
            }
        }
    }
} finally {
    Write-Host ''
    Write-Host '[*] Stopping development servers...' -ForegroundColor Yellow
    foreach ($server in $servers) {
        if (-not $server.Process.HasExited) { & taskkill.exe /PID $server.Process.Id /T /F 2>&1 | Out-Null }
    }
    Write-Host '[OK] Development servers stopped. Ollama and its shared gateway remain running.' -ForegroundColor Green
}
