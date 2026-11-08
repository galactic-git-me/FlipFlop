param(
    [switch]$InstallDisabled,
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$taskName = 'FlipFlop Ollama Generation Watchdog'
$watchdog = Join-Path $PSScriptRoot 'ollama-recovery-watchdog.ps1'
$pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { throw 'PowerShell 7 (pwsh.exe) is required by the Ollama recovery watchdog.' }
$maintenanceState = Join-Path $env:LOCALAPPDATA 'FlipFlop'
New-Item -ItemType Directory -Path $maintenanceState -Force | Out-Null
$maintenanceToken = Join-Path $maintenanceState 'ollama-gateway-maintenance-token.txt'
if (-not (Test-Path -LiteralPath $maintenanceToken)) {
    throw 'The gateway maintenance token is not initialized. Start the updated Ollama priority gateway first.'
}
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$argument = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watchdog`" -ProjectRoot `"$ProjectRoot`""
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $argument
$logon = New-ScheduledTaskTrigger -AtLogOn -User $user
$recurring = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($logon, $recurring) `
    -Settings $settings -Principal $principal `
    -Description 'Probe idle DEV Ollama generation and recover repeated upstream stalls with cooldown.' -Force | Out-Null

if ($InstallDisabled) {
    Disable-ScheduledTask -TaskName $taskName | Out-Null
    Write-Output "Installed '$taskName' disabled. Enable it after reviewing the task action."
} else {
    Start-ScheduledTask -TaskName $taskName
    Write-Output "Installed and started '$taskName'. It probes every two minutes when the gateway is idle."
}
