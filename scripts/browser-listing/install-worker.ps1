param(
    [Parameter(Mandatory)][string]$Api,
    [Parameter(Mandatory)][SecureString]$WorkerKey,
    [string]$AdminDirectory = (Join-Path $PSScriptRoot '..\..\flipflop-admin'),
    [string]$CredentialsFile
)
$ErrorActionPreference = 'Stop'
if (-not $Api.StartsWith('https://')) { throw 'Use the HTTPS production API worker URL.' }
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
if (-not $CredentialsFile) {
    $candidates = @((Join-Path $repoRoot '.env.local'), (Join-Path (Split-Path $repoRoot -Parent) 'FlipFlop\.env.local'))
    $CredentialsFile = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $CredentialsFile -or -not (Test-Path -LiteralPath $CredentialsFile)) { throw 'Set -CredentialsFile to the ignored .env.local containing seller credentials.' }
$workerState = Join-Path $env:LOCALAPPDATA 'FlipFlop\BrowserWorker'
New-Item -ItemType Directory -Path $workerState -Force | Out-Null
# Encrypt the dedicated queue key with Windows DPAPI for this user/machine.
[PSCredential]::new('flipflop-browser-worker', $WorkerKey) | Export-Clixml -LiteralPath (Join-Path $workerState 'worker-key.xml')
@{ api = $Api.TrimEnd('/'); adminDirectory = (Resolve-Path -LiteralPath $AdminDirectory).Path; credentialsFile = [IO.Path]::GetFullPath($CredentialsFile) } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workerState 'config.json')
$workerScript = Join-Path $PSScriptRoot 'start-worker.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -File "' + $workerScript + '"')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'FlipFlop Codex Browser Listings' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Output 'Desktop worker installed. Start it after verifying the API and local credential variables.'
