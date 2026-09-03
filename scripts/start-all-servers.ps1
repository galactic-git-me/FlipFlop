   # FlipFlop Platform - Start All Servers
# Spawns server processes directly (no PM2)
# Press Ctrl+C to stop all servers

param(
    [switch]$Verbose = $false,
    [switch]$NoOllama = $false,
    # The production API and PostgreSQL database run on Andromeda. These
    # switches are only for explicitly testing the legacy local services.
    [switch]$LocalBackend = $false,
    [switch]$LocalGemRadar = $false,
    # Start the customer site locally for development; use -NoFrontend when
    # only the admin tool is needed.
    [switch]$LocalFrontend = $true,
    [switch]$NoBackend = $false,
    [switch]$NoGemRadar = $false,
    [switch]$NoAdmin = $false,
    [switch]$NoFrontend = $false,
    [switch]$NoExtensionBuild = $false
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

# Set Ollama GPU environment variables for optimal performance
$env:CUDA_VISIBLE_DEVICES = "0"
$env:OLLAMA_NUM_PARALLEL = "4"
$env:OLLAMA_KEEP_ALIVE = "-1"

Write-Host "[*] FlipFlop Platform - Starting all servers" -ForegroundColor Cyan
Write-Host "    Project root: $projectRoot" -ForegroundColor Gray
Write-Host ""

# Ollama native Windows setup
function Ensure-Ollama {
    Write-Host "[*] Starting Ollama on port 11434..." -ForegroundColor Cyan

    # Start Ollama in background on port 11434 (GPU settings configured globally above)
    $env:OLLAMA_HOST = "0.0.0.0:11434"

    # Kill ANY existing Ollama processes (multiple waves).
    # Ollama's "serve" parent spawns a SEPARATE llama-server.exe child per
    # loaded model to actually run inference. Killing only ollama* leaves
    # those runner children orphaned (each holding several GB of RAM) any
    # time the parent gets killed/restarted while a model is loaded -- so
    # llama-server must be swept alongside ollama* in every wave below.
    Write-Host "[*] Killing any existing Ollama processes (incl. orphaned llama-server runners)..." -ForegroundColor Yellow

    # Wave 1: Kill via Get-Process
    Get-Process -Name ollama*, llama-server -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    # Wave 2: Kill via taskkill (catch all variants)
    & cmd /c "taskkill /F /IM ollama.exe 2>&1" -ErrorAction SilentlyContinue | Out-Null
    & cmd /c "taskkill /F /IM ollama-server.exe 2>&1" -ErrorAction SilentlyContinue | Out-Null
    & cmd /c "taskkill /F /IM ollama 2>&1" -ErrorAction SilentlyContinue | Out-Null
    & cmd /c "taskkill /F /IM llama-server.exe 2>&1" -ErrorAction SilentlyContinue | Out-Null
    Start-Sleep -Seconds 3

    # Wave 3: Verify and force-kill any stragglers
    $attempt = 0
    while ($attempt -lt 3) {
        $remaining = Get-Process -Name ollama*, llama-server -ErrorAction SilentlyContinue
        if (-not $remaining) {
            break
        }
        Write-Host "[!] Ollama/llama-server still running, killing again (attempt $($attempt + 1))..." -ForegroundColor Yellow
        $remaining | Stop-Process -Force -ErrorAction SilentlyContinue
        & cmd /c "taskkill /F /IM ollama.exe /IM ollama-server.exe /IM ollama /IM llama-server.exe 2>&1" -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Seconds 2
        $attempt++
    }

    $finalCheck = Get-Process -Name ollama*, llama-server -ErrorAction SilentlyContinue
    if ($finalCheck) {
        Write-Host "[ERROR] Could not kill all Ollama/llama-server processes after 3 attempts" -ForegroundColor Red
        $finalCheck | Select-Object Name, Id
        return
    }
    Write-Host "[OK] All Ollama processes killed (including orphaned llama-server runners)" -ForegroundColor Green

    # Start SINGLE Ollama instance with GPU enabled
    Write-Host "[*] Starting Ollama serve..." -ForegroundColor Cyan
    Start-Process -FilePath "ollama" -ArgumentList "serve" -NoNewWindow -RedirectStandardOutput "$env:TEMP\ollama.log" -RedirectStandardError "$env:TEMP\ollama.err"

    # Wait for Ollama to start
    Write-Host "[!] Waiting for Ollama to start..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    $ollama_ready = $false

    while ($attempt -lt $maxAttempts -and -not $ollama_ready) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            $ollama_ready = $true
            Write-Host "[OK] Ollama is up on port 11434" -ForegroundColor Green
        } catch {
            $attempt++
            Start-Sleep -Seconds 1
        }
    }

    if (-not $ollama_ready) {
        Write-Host "[ERROR] Ollama failed to start after 30 seconds" -ForegroundColor Red
        return
    }

    # Check if model is already pulled
    try {
        $models = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        $modelList = ($models.Content | ConvertFrom-Json).models

        # Clean up old qwen2.5:7b (non-instruct) if it exists
        if ($modelList.name -contains "qwen2.5:7b") {
            Write-Host "[!] Removing old qwen2.5:7b model..." -ForegroundColor Yellow
            & ollama rm qwen2.5:7b 2>&1 | Out-Null
        }

        if ($modelList.name -contains "qwen2.5:7b-instruct") {
            Write-Host "[OK] qwen2.5:7b-instruct model already available" -ForegroundColor Green
        } else {
            Write-Host "[!] Pulling qwen2.5:7b-instruct model (one-time, takes a few minutes)..." -ForegroundColor Yellow
            & ollama pull qwen2.5:7b-instruct | Out-Null
            Write-Host "[OK] Model pulled and ready" -ForegroundColor Green
        }
    } catch {
        Write-Host "[!] Could not verify model, attempting to pull..." -ForegroundColor Yellow
        & ollama pull qwen2.5:7b-instruct | Out-Null
    }
}

# Ensure Redis (or a Redis-compatible server, e.g. Memurai on native Windows)
# is running on port 6379 -- required by flipflop-api's sold-comps 7-day cache.
function Test-RedisPort {
    try {
        $socket = New-Object System.Net.Sockets.TcpClient
        $socket.Connect("localhost", 6379)
        $socket.Close()
        return $true
    } catch {
        return $false
    }
}

function Wait-ForRedisPort {
    param([int]$MaxAttempts = 20)
    $attempt = 0
    while ($attempt -lt $MaxAttempts) {
        if (Test-RedisPort) { return $true }
        $attempt++
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Ensure-Redis {
    Write-Host "[*] Checking Redis on port 6379..." -ForegroundColor Cyan

    if (Test-RedisPort) {
        Write-Host "[OK] Redis is already running on port 6379" -ForegroundColor Green
        return
    }
    Write-Host "[!] Redis not running, attempting to start..." -ForegroundColor Yellow

    # Memurai (native Windows, Redis-compatible) installs as a Windows Service
    # rather than a foreground redis-server process -- check for it first.
    $memuraiService = Get-Service -Name "Memurai*" -ErrorAction SilentlyContinue
    if ($memuraiService) {
        try {
            if ($memuraiService.Status -ne "Running") {
                Write-Host "[*] Starting Memurai service..." -ForegroundColor Cyan
                Start-Service -Name $memuraiService.Name
            }
            if (Wait-ForRedisPort) {
                Write-Host "[OK] Memurai is up on port 6379" -ForegroundColor Green
                return
            }
            Write-Host "[ERROR] Memurai service started but port 6379 never came up" -ForegroundColor Red
            return
        } catch {
            Write-Host "[ERROR] Could not start Memurai service: $_" -ForegroundColor Red
            return
        }
    }

    # Fall back to a redis-server binary on PATH (WSL/Docker-installed native builds).
    $redisServerCmd = Get-Command redis-server -ErrorAction SilentlyContinue
    if ($redisServerCmd) {
        try {
            Write-Host "[*] Starting redis-server..." -ForegroundColor Cyan
            Start-Process -FilePath "redis-server" -NoNewWindow -RedirectStandardOutput "$env:TEMP\redis.log" -RedirectStandardError "$env:TEMP\redis.err"
            if (Wait-ForRedisPort) {
                Write-Host "[OK] Redis is up on port 6379" -ForegroundColor Green
                return
            }
            Write-Host "[ERROR] Redis failed to start after 10 seconds" -ForegroundColor Red
            return
        } catch {
            Write-Host "[ERROR] Could not start redis-server: $_" -ForegroundColor Red
            return
        }
    }

    Write-Host "[ERROR] No Redis-compatible server found (checked Memurai service + redis-server on PATH)" -ForegroundColor Red
    Write-Host "[!] Install one of:" -ForegroundColor Yellow
    Write-Host "    - Memurai (native Windows service): https://www.memurai.com/get-memurai" -ForegroundColor Gray
    Write-Host "    - WSL: wsl -e bash -c 'sudo apt install redis-server'" -ForegroundColor Gray
    Write-Host "    - Docker: docker run -d -p 6379:6379 --name flipflop-redis --restart unless-stopped redis" -ForegroundColor Gray
}

# Ensure the manually-authenticated eBay CDP browser (used by the
# flipflop-api/experiments/ebay_sold_scrape_experiment.py sold-comps
# investigation) is running on port 9222 and still signed in. Direct HTTP
# and headless Playwright both get bounced to eBay's sign-in wall on
# LH_Sold=1&LH_Complete=1 searches -- only a real, manually-authenticated,
# headed browser gets through (see experiments/ebay_manual_login_scrape.py
# docstring for why headless must never touch this same profile). This
# reuses the SAME profile dir every restart, so once you've signed in once
# it should stay signed in across restarts until the session expires --
# you'll only be prompted to sign in again when it actually does.
function Ensure-EbayCdpBrowser {
    Write-Host "[*] Checking eBay CDP browser on port 9222..." -ForegroundColor Cyan

    $chromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    # This is a clean, persistent Chrome profile solely for eBay.  It is not
    # Playwright's Chromium and does not share the user's everyday cookies or
    # extensions, which makes Google OAuth behave like a fresh Incognito
    # session while allowing eBay's signed-in session to persist.
    $profileDir = Join-Path $projectRoot "flipflop-api\data\ebay-cdp-profile"
    $checkScript = Join-Path $projectRoot "flipflop-api\.venv\Scripts\python.exe"

    if (-not (Test-Path $chromeExe)) {
        Write-Host "[!] Chrome not found at expected path -- skipping eBay CDP browser setup" -ForegroundColor Yellow
        return
    }

    $portOpen = $false
    try {
        $socket = New-Object System.Net.Sockets.TcpClient
        $socket.Connect("localhost", 9222)
        $socket.Close()
        $portOpen = $true
    } catch { $portOpen = $false }

    if (-not $portOpen) {
        Write-Host "[*] Launching eBay CDP browser (port 9222)..." -ForegroundColor Cyan
        Start-Process -FilePath $chromeExe -ArgumentList @(
            "--remote-debugging-port=9222",
            "--user-data-dir=`"$profileDir`"",
            "--new-window",
            "https://www.ebay.co.uk/myb/WatchList"
        )
        Start-Sleep -Seconds 3
    } else {
        Write-Host "[OK] eBay CDP browser already running on port 9222" -ForegroundColor Green
    }

    # Only bother the user if a sign-in is actually needed -- this check
    # itself never touches credentials, it just inspects whether a
    # protected page redirects to signin (see check_ebay_login.py).
    if (Test-Path $checkScript) {
        Push-Location (Join-Path $projectRoot "flipflop-api")
        try {
            $result = & $checkScript -u -m experiments.check_ebay_login 2>&1
            $lastLine = ($result | Select-Object -Last 1)
            if ($lastLine -eq "SIGNED_IN") {
                Write-Host "[OK] eBay CDP session is signed in -- sold-comps ready" -ForegroundColor Green
            } elseif ($lastLine -eq "NOT_SIGNED_IN") {
                Write-Host "[!] eBay CDP session needs sign-in -- browser window opened to the sign-in page" -ForegroundColor Yellow
                Write-Host "    Sign in there when convenient; sold-comps fetching will fail until you do." -ForegroundColor Gray
            } else {
                Write-Host "[!] Could not determine eBay CDP sign-in status" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[!] eBay CDP sign-in check failed: $_" -ForegroundColor Yellow
        } finally {
            Pop-Location
        }
    }
}

# Setup logging directory
Write-Host "[*] Setting up logging..." -ForegroundColor Cyan
$logsDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
# Clean old logs
Get-ChildItem -Path $logsDir -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "  [OK] Logs directory: $logsDir" -ForegroundColor Green
Write-Host ""

# Clean up lingering processes on the ports selected for this run.
# The normal target setup only runs the admin tool locally; the API/database
# and customer-facing website remain on Andromeda.
Write-Host "[*] Cleaning up lingering processes on dev ports..." -ForegroundColor Cyan
$devPorts = @(4312, 5173)
if ($LocalBackend) { $devPorts += 4311 }
if ($LocalGemRadar) { $devPorts += 18000 }
if ($LocalFrontend) { $devPorts += 4313 }
foreach ($port in $devPorts) {
    $processes = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
    if ($processes) {
        foreach ($proc in $processes) {
            try {
                Stop-Process -Id $proc.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "  [OK] Freed port ${port}" -ForegroundColor Green
            } catch {}
        }
    }
}

# A previous launcher can leave its cmd.exe wrapper behind after Ctrl+C (the
# child Next process exits, but the wrapper still owns the redirected log
# handle).  That stale wrapper has no listening port, so port cleanup above
# cannot find it and the next launch fails with a file-lock error.  Remove
# only wrappers that explicitly belong to this project's admin server.
$staleAdminLaunchers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -ieq "cmd.exe" -and
        $_.CommandLine -match "flipflop-admin" -and
        $_.CommandLine -match "next dev.*4312|npm run dev.*4312"
    }
foreach ($launcher in $staleAdminLaunchers) {
    Write-Host "  [*] Removing stale admin launcher (PID: $($launcher.ProcessId))" -ForegroundColor Gray
    & cmd /c "taskkill /PID $($launcher.ProcessId) /T /F 2>&1" | Out-Null
}
if ($staleAdminLaunchers) {
    Start-Sleep -Milliseconds 300
}
Write-Host ""

if (-not $NoOllama) {
    Ensure-Ollama
    Write-Host ""
}

# Ensure Redis is running (required for pricing cache)
# DISABLED: Using database-based cache instead of Redis
# Ensure-Redis
Write-Host ""

# Ensure the eBay CDP browser is up and signed in (required for sold-comps experiment)
Ensure-EbayCdpBrowser
Write-Host ""

# Extension build
if (-not $NoExtensionBuild) {
    $extensionRoot = Join-Path (Split-Path -Parent $projectRoot) "FlipFlopXtension"
    if (Test-Path $extensionRoot) {
        Write-Host "[*] Building Chrome extension..." -ForegroundColor Cyan
        Push-Location $extensionRoot
        try {
            npm run build 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] Extension build succeeded" -ForegroundColor Green
            } else {
                Write-Host "[ERROR] Extension build failed" -ForegroundColor Red
            }
        } finally {
            Pop-Location
        }
        Write-Host ""
    }
}

# Server configuration
$servers = @(
    @{
        name     = "backend"
        cmdArgs  = @("/c", "cd flipflop-api && set OLLAMA_BASE_URL=http://localhost:11434 && set OLLAMA_MODEL=qwen2.5:7b-instruct && .venv\Scripts\python.exe run_dev.py --host 0.0.0.0 --port 4311")
        port     = 4311
        color    = "Yellow"
        skip     = $NoBackend -or (-not $LocalBackend)
    },
    @{
        name     = "gemradar-api"
        cmdArgs  = @("/c", "cd flipflop-api && set OLLAMA_BASE_URL=http://localhost:11434 && set OLLAMA_MODEL=qwen2.5:7b-instruct && set PYTHONUNBUFFERED=1 && .venv\Scripts\python.exe -m uvicorn app.gem_radar_standalone:app --host 0.0.0.0 --port 18000")
        port     = 18000
        color    = "Blue"
        skip     = $NoGemRadar -or (-not $LocalGemRadar)
    },
    @{
        name     = "admin"
        cmdArgs  = @("/c", "cd flipflop-admin && set ""BACKEND_URL=https://admin.theflipflop.shop"" && set ""NEXT_PUBLIC_API_URL=https://admin.theflipflop.shop"" && set ""NEXT_PUBLIC_OLLAMA_MODEL=qwen2.5:7b-instruct"" && npm run dev -- -p 4312 -H 0.0.0.0")
        port     = 4312
        color    = "Green"
        skip     = $NoAdmin
    },
    @{
        name     = "frontend"
        cmdArgs  = @("/c", "cd ..\FlipFlop.shop && set ""BACKEND_URL=https://admin.theflipflop.shop"" && set ""NEXT_PUBLIC_API_URL=https://admin.theflipflop.shop"" && set ""NEXT_PUBLIC_OLLAMA_MODEL=qwen2.5:7b-instruct"" && npm run dev -- -p 4313 -H 0.0.0.0")
        port     = 4313
        color    = "Magenta"
        skip     = $NoFrontend
    },
    @{
        name     = "performance-card"
        cmdArgs  = @("/c", "cd /d ""C:\Users\mclar\CODING\FlipFlop\Personalised Website"" && python -m http.server 5173")
        port     = 5173
        color    = "Cyan"
        skip     = $false
    }
)

# Start servers
Write-Host "[*] Starting servers..." -ForegroundColor Cyan
Write-Host ""

$processes = @()
foreach ($server in $servers) {
    if ($server.skip) {
        continue
    }

    Write-Host "Starting $($server.name)..." -ForegroundColor $server.color
    Write-Host "  Port: $($server.port)" -ForegroundColor Gray

    try {
        $logFile = Join-Path $logsDir "$($server.name).log"

        # Redirect output to log file using cmd.exe redirection
        $cmdWithLogging = $server.cmdArgs + @(">", $logFile, "2>&1")

        $process = Start-Process `
            -FilePath "cmd.exe" `
            -ArgumentList $cmdWithLogging `
            -WorkingDirectory $projectRoot `
            -NoNewWindow `
            -PassThru

        Write-Host "[OK] $($server.name) started (PID: $($process.Id))" -ForegroundColor $server.color
        Write-Host "      Log: $logFile" -ForegroundColor Gray
        $processes += @{
            name    = $server.name
            process = $process
            port    = $server.port
            color   = $server.color
            logFile = $logFile
        }
    }
    catch {
        Write-Host "[ERROR] Failed to start $($server.name): $_" -ForegroundColor Red
    }

    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Servers Running:" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

foreach ($proc in $processes) {
    $status = if ($proc.process.HasExited) { "[STOPPED]" } else { "[RUNNING]" }
    Write-Host "$status $($proc.name.PadRight(15)) | Port $($proc.port)" -ForegroundColor $proc.color
}

Write-Host ""
Write-Host "URLs to Access:" -ForegroundColor Cyan
Write-Host "  eBay CDP browser:  localhost:9222" -ForegroundColor Cyan
Write-Host "  Ollama:            http://localhost:11434" -ForegroundColor Cyan
Write-Host "  Admin:             http://localhost:4312" -ForegroundColor Green
Write-Host "  Performance Card:  http://localhost:5173" -ForegroundColor Cyan
if ($LocalBackend -and -not $NoBackend) { Write-Host "  Legacy backend:     http://localhost:4311" -ForegroundColor Yellow }
if ($LocalGemRadar -and -not $NoGemRadar) { Write-Host "  Legacy Gem Radar:   http://localhost:18000" -ForegroundColor Blue }
if ($LocalFrontend -and -not $NoFrontend) { Write-Host "  Local frontend:     http://localhost:4313" -ForegroundColor Magenta }
Write-Host ""
Write-Host "Log Files:" -ForegroundColor Cyan
foreach ($proc in $processes) {
    Write-Host "  $($proc.name).log" -ForegroundColor Gray
}
Write-Host ""
Write-Host "View logs (example):" -ForegroundColor Cyan
Write-Host "  Get-Content $logsDir\admin.log -Tail 50 -Wait" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Gray
Write-Host ""

# Keep servers alive
try {
    $lastKnownRunning = @{}
    foreach ($proc in $processes) {
        $lastKnownRunning[$proc.name] = $true
    }
    while ($true) {
        Start-Sleep -Seconds 10
        # cmd/npm/python launchers can hand work to child processes and exit.
        # The listening port is the authoritative health signal for each server.
        foreach ($proc in $processes) {
            $isRunning = [bool](Get-NetTCPConnection -LocalPort $proc.port -State Listen -ErrorAction SilentlyContinue)
            if (-not $isRunning -and $lastKnownRunning[$proc.name]) {
                Write-Host "[WARN] $($proc.name) has exited" -ForegroundColor Yellow
            } elseif ($isRunning -and -not $lastKnownRunning[$proc.name]) {
                Write-Host "[OK] $($proc.name) is running again" -ForegroundColor $proc.color
            }
            $lastKnownRunning[$proc.name] = $isRunning
        }
    }
} finally {
    Write-Host ""
    Write-Host "Stopping all servers..." -ForegroundColor Yellow
    foreach ($proc in $processes) {
        if (-not $proc.process.HasExited) {
            # Each server was launched as "cmd.exe /c ... && python/npm ...", so the
            # actual long-running process (uvicorn, npm dev server) is a CHILD of the
            # tracked cmd.exe process, not the process itself. Process.Kill() only
            # terminates the single tracked process on Windows -- it does not recurse
            # into children -- so the real server kept running orphaned after the cmd
            # window closed. taskkill /T kills the whole process tree instead.
            & cmd /c "taskkill /PID $($proc.process.Id) /T /F 2>&1" | Out-Null
            Write-Host "Stopped $($proc.name)" -ForegroundColor Gray
        }
    }
    Write-Host "All servers stopped." -ForegroundColor Green
}
