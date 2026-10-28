param(
    [int]$CommandTimeoutSeconds = 10
)

$ErrorActionPreference = 'Stop'
$logRoot = Join-Path $env:ProgramData 'FlipFlop\logs'
$logPath = Join-Path $logRoot 'tailscale-watchdog.log'
$restartMarker = Join-Path $logRoot 'tailscale-last-restart.txt'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

function Write-WatchdogLog([string]$Message) {
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -LiteralPath $logPath -Value $line
    Write-Output $line
}

function Invoke-TimedProcess([string]$FilePath, [string[]]$Arguments, [int]$TimeoutSeconds) {
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    foreach ($argument in $Arguments) {
        $startInfo.ArgumentList.Add($argument)
    }

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    [void]$process.Start()
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill($true)
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = 124; StdOut = ''; StdErr = 'command timed out' }
    }

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        StdOut = $process.StandardOutput.ReadToEnd()
        StdErr = $process.StandardError.ReadToEnd()
    }
}

$tailscale = (Get-Command tailscale.exe -ErrorAction Stop).Source

function Get-TailscaleHealth {
    $result = Invoke-TimedProcess $tailscale @('status', '--json') $CommandTimeoutSeconds
    if ($result.ExitCode -ne 0) {
        return [pscustomobject]@{ Healthy = $false; BackendState = 'Unresponsive'; Reason = "status exit $($result.ExitCode): $($result.StdErr.Trim())" }
    }
    try {
        $status = $result.StdOut | ConvertFrom-Json
    } catch {
        return [pscustomobject]@{ Healthy = $false; BackendState = 'InvalidStatus'; Reason = 'status returned invalid JSON' }
    }
    $healthMessages = @($status.Health | Where-Object { $_ })
    $healthy = $status.BackendState -eq 'Running' -and $status.Self.Online -eq $true -and $healthMessages.Count -eq 0
    $reason = if ($healthy) { 'online' } else { "backend=$($status.BackendState), selfOnline=$($status.Self.Online), health=$($healthMessages -join ' | ')" }
    return [pscustomobject]@{ Healthy = $healthy; BackendState = $status.BackendState; Reason = $reason }
}

$initial = Get-TailscaleHealth
if ($initial.Healthy) {
    Write-WatchdogLog 'OK: Tailscale is online.'
    exit 0
}

Write-WatchdogLog "WARN: Tailscale unhealthy ($($initial.Reason)); restarting the Windows service."
$service = Get-Service -Name Tailscale
if ($service.Status -in @('StartPending', 'StopPending', 'PausePending', 'ContinuePending')) {
    Write-WatchdogLog "DEFERRED: Tailscale service is transitioning ($($service.Status)); no restart attempted."
    exit 1
}

if (Test-Path -LiteralPath $restartMarker) {
    $lastRestartText = Get-Content -LiteralPath $restartMarker -Raw -ErrorAction SilentlyContinue
    $lastRestart = [datetime]::MinValue
    if ([datetime]::TryParse($lastRestartText, [ref]$lastRestart) -and $lastRestart -gt (Get-Date).AddMinutes(-15)) {
        Write-WatchdogLog "COOLDOWN: A restart was attempted at $($lastRestart.ToString('o')); waiting before another attempt."
        exit 1
    }
}

(Get-Date).ToString('o') | Set-Content -LiteralPath $restartMarker
Restart-Service -Name Tailscale -Force
for ($attempt = 1; $attempt -le 12; $attempt++) {
    Start-Sleep -Seconds 5
    $final = Get-TailscaleHealth
    if ($final.Healthy) {
        Write-WatchdogLog 'RECOVERED: Tailscale service restarted and the node is online.'
        exit 0
    }
    if ($final.BackendState -in @('NeedsLogin', 'NoState')) {
        Write-WatchdogLog "AUTH_REQUIRED: Tailscale backend is $($final.BackendState); interactive account authentication is required."
        exit 2
    }
}

Write-WatchdogLog "ERROR: Tailscale did not recover within 60 seconds ($($final.Reason))."
exit 1
