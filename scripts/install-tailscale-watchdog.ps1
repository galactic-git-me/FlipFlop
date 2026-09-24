#requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'
$taskName = 'FlipFlop Tailscale Watchdog'
$watchdog = Join-Path $PSScriptRoot 'ensure-tailscale-online.ps1'
$pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell.exe -ErrorAction Stop).Source }

# Tailscale's supported Windows unattended mode keeps the node connected when
# no interactive user is signed in. The watchdog handles the separate failure
# mode where the service remains running but its backend becomes unresponsive.
& tailscale.exe up --unattended=true
if ($LASTEXITCODE -ne 0) { throw 'Unable to enable Tailscale unattended mode.' }

$action = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$watchdog`""
$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$recurringTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger @($startupTrigger, $recurringTrigger) `
    -Settings $settings `
    -Principal $principal `
    -Description 'Restarts a hung/offline Tailscale service and restores unattended mode for FlipFlop production connectivity.' `
    -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Write-Output "Installed and started '$taskName'. Logs: $env:ProgramData\FlipFlop\logs\tailscale-watchdog.log"
