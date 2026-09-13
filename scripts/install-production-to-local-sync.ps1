$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'run-production-to-local-sync.ps1'
$shell = (Get-Command pwsh).Source
$action = New-ScheduledTaskAction -Execute $shell -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At '04:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'FlipFlopProductionToLocalRefresh' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Complete production-to-local PostgreSQL mirror at 04:00; staged restore and local backup; never writes production.' -Force | Select-Object TaskName,State
if (Get-ScheduledTask -TaskName 'FlipFlopPeerSync' -ErrorAction SilentlyContinue) {
    Disable-ScheduledTask -TaskName 'FlipFlopPeerSync' | Out-Null
}
