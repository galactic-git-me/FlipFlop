param([switch]$Write)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repo 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$tunnelLog = Join-Path $logDir 'tunnel.log'

function Write-TunnelLog($msg) {
    Add-Content $tunnelLog "$(Get-Date -Format o) $msg"
}

function Test-TunnelUp {
    try {
        $result = Test-NetConnection -ComputerName 127.0.0.1 -Port 15432 -WarningAction SilentlyContinue
        return $result.TcpTestSucceeded
    } catch {
        return $false
    }
}

function Start-Tunnel {
    $existing = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*15432:172.23.0.3:5432*' }
    if ($existing) {
        foreach ($p in $existing) {
            Write-TunnelLog "killing stale ssh pid $($p.ProcessId)"
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Write-TunnelLog 'starting ssh tunnel (forward 15432 -> andromeda:5432, reverse 15433 -> local:5432)'
    Start-Process ssh -ArgumentList @(
        '-o','BatchMode=yes',
        '-o','ServerAliveInterval=30',
        '-o','ServerAliveCountMax=3',
        '-N',
        '-L','15432:172.23.0.3:5432',
        '-R','15433:127.0.0.1:5432',
        'andromeda'
    ) -WindowStyle Hidden
}

if (-not (Test-TunnelUp)) { Start-Tunnel }
# Give the tunnel a moment to come up before the sync loop tries to use it.
Start-Sleep -Seconds 3

# Peer sync replicates rows only; apply schema changes to both peers before
# starting it so a newly deployed worker never writes against an old schema.
& (Join-Path $PSScriptRoot 'migrate-peer-databases.ps1')

$runnerArgs = @('-File', (Join-Path $PSScriptRoot 'run-peer-sync.ps1'))
if ($Write) { $runnerArgs += '-Write' }
$runner = Start-Process powershell -ArgumentList $runnerArgs -WindowStyle Hidden -PassThru

# Watchdog: check every 30s, restart the tunnel if the forward port is down,
# and restart the sync runner if its process has died.
while ($true) {
    Start-Sleep -Seconds 30
    if (-not (Test-TunnelUp)) {
        Write-TunnelLog 'tunnel down, restarting'
        Start-Tunnel
    }
    if ($runner.HasExited) {
        Write-TunnelLog 'sync runner process exited, restarting'
        $runner = Start-Process powershell -ArgumentList $runnerArgs -WindowStyle Hidden -PassThru
    }
}
