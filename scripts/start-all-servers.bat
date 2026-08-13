@echo off
REM FlipFlop Platform - Start All Servers (Batch wrapper)

cd /d "%~dp0.."

echo.
echo ========================================
echo FlipFlop Platform - Starting Servers
echo ========================================
echo.

REM Run the PowerShell script
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all-servers.ps1" %*

pause
