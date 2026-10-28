param(
    [string]$ExtensionRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '..\FlipFlopXtension')
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'launch-gem-radar-browser.ps1'
$pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell.exe).Source }

function Install-ScannerTask([string]$Target, [int[]]$Hours) {
    $taskName = "FlipFlop Gem Radar ($($Target.ToUpperInvariant()))"
    $argument = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`" -Target $Target -ExtensionRoot `"$ExtensionRoot`""
    $action = New-ScheduledTaskAction -Execute $pwsh -Argument $argument
    $triggers = @(
        (New-ScheduledTaskTrigger -AtStartup)
    )
    foreach ($hour in $Hours) {
        $triggers += New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $hour -Minute 0 -Second 0)
    }
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances Ignore -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Installed $taskName" -ForegroundColor Green
}

Install-ScannerTask 'dev' @(4, 16)
Install-ScannerTask 'live' @(10, 22)
Write-Host 'The browser processes run minimized in separate profiles. Remove them with uninstall-gem-radar-scheduled-tasks.ps1.' -ForegroundColor Cyan
