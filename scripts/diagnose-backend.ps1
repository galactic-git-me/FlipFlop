# Diagnostic script to capture backend startup errors

$projectRoot = Split-Path -Parent $PSScriptRoot
$logFile = "$projectRoot\backend-startup.log"

Write-Host "[*] Starting backend with error capture..." -ForegroundColor Cyan
Write-Host "[*] Logs will be saved to: $logFile" -ForegroundColor Cyan
Write-Host ""

# Try to start backend and capture all output
try {
    $process = Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList @("/c", "cd flipflop-api && .venv\Scripts\python.exe run_dev.py --host 0.0.0.0 --port 4311") `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput "$logFile.out" `
        -RedirectStandardError "$logFile.err" `
        -PassThru `
        -NoNewWindow

    Write-Host "[OK] Backend started with PID: $($process.Id)" -ForegroundColor Green
    Write-Host "[*] Waiting 10 seconds to capture startup errors..." -ForegroundColor Cyan

    Start-Sleep -Seconds 10

    if ($process.HasExited) {
        Write-Host "[ERROR] Backend exited unexpectedly" -ForegroundColor Red
        Write-Host ""
        Write-Host "=== STDOUT ===" -ForegroundColor Yellow
        Get-Content "$logFile.out" -ErrorAction SilentlyContinue | Write-Host
        Write-Host ""
        Write-Host "=== STDERR ===" -ForegroundColor Yellow
        Get-Content "$logFile.err" -ErrorAction SilentlyContinue | Write-Host
    } else {
        Write-Host "[OK] Backend is still running - no immediate crash" -ForegroundColor Green
        Write-Host "[*] Stopping backend..." -ForegroundColor Cyan
        $process.Kill()
        Start-Sleep -Seconds 2
    }
} catch {
    Write-Host "[ERROR] Failed to start backend: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "[*] Complete logs saved to: $logFile.out and $logFile.err" -ForegroundColor Cyan
