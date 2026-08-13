# Kill processes holding development ports

$ports = @(4311, 18000, 4312, 4313)

Write-Host "Cleaning up development ports..." -ForegroundColor Cyan

foreach ($port in $ports) {
    $processes = netstat -ano | Select-String ":$port "

    if ($processes) {
        Write-Host "  Port ${port} is in use:" -ForegroundColor Yellow

        # Extract PID from netstat output (format: "  TCP    0.0.0.0:4311           0.0.0.0:0              LISTENING       12345")
        foreach ($line in $processes) {
            $parts = $line -split '\s+' | Where-Object { $_ }
            $processId = $parts[-1]

            if ($processId -and $processId -match '^\d+$') {
                Write-Host "    Killing PID ${processId}..." -ForegroundColor Yellow
                try {
                    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                    Write-Host "    [OK] Killed PID ${processId}" -ForegroundColor Green
                } catch {
                    Write-Host "    [ERROR] Failed to kill PID ${processId}" -ForegroundColor Red
                }
            }
        }
    } else {
        Write-Host "  Port ${port}: free" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Cleanup complete. Waiting 2 seconds for ports to release..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Current port usage:" -ForegroundColor Cyan
foreach ($port in $ports) {
    $processes = netstat -ano | Select-String ":$port "
    if ($processes) {
        Write-Host "  Port ${port}: STILL IN USE" -ForegroundColor Red
    } else {
        Write-Host "  Port ${port}: free" -ForegroundColor Green
    }
}
