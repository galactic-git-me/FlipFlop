param(
    [int]$CommandTimeoutSeconds = 10
)

$ErrorActionPreference = 'Stop'
$logRoot = Join-Path $env:ProgramData 'FlipFlop\logs'
$logPath = Join-Path $logRoot 'tailscale-watchdog.log'
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
        return [pscustomobject]@{ Healthy = $false; Reason = "status exit $($result.ExitCode): $($result.StdErr.Trim())" }
    }
    try {
        $status = $result.StdOut | ConvertFrom-Json
    } catch {
        return [pscustomobject]@{ Healthy = $false; Reason = 'status returned invalid JSON' }
    }
    $healthMessages = @($status.Health | Where-Object { $_ })
    $healthy = $status.BackendState -eq 'Running' -and $status.Self.Online -eq $true -and $healthMessages.Count -eq 0
    $reason = if ($healthy) { 'online' } else { "backend=$($status.BackendState), selfOnline=$($status.Self.Online), health=$($healthMessages -join ' | ')" }
    return [pscustomobject]@{ Healthy = $healthy; Reason = $reason }
}

$initial = Get-TailscaleHealth
if ($initial.Healthy) {
    Write-WatchdogLog 'OK: Tailscale is online.'
    exit 0
}

Write-WatchdogLog "WARN: Tailscale unhealthy ($($initial.Reason)); restarting the Windows service."
Restart-Service -Name Tailscale -Force
Start-Sleep -Seconds 5

$up = Invoke-TimedProcess $tailscale @('up', '--unattended=true') 30
$combinedOutput = "$($up.StdOut)`n$($up.StdErr)"
if ($combinedOutput -match 'https://login\.tailscale\.com/') {
    Write-WatchdogLog 'AUTH_REQUIRED: Tailscale requires interactive account authentication.'
    exit 2
}
if ($up.ExitCode -ne 0) {
    Write-WatchdogLog "ERROR: tailscale up failed with exit $($up.ExitCode): $($up.StdErr.Trim())"
    exit 1
}

Start-Sleep -Seconds 5
$final = Get-TailscaleHealth
if (-not $final.Healthy) {
    Write-WatchdogLog "ERROR: Tailscale did not recover ($($final.Reason))."
    exit 1
}

Write-WatchdogLog 'RECOVERED: Tailscale service restarted and the node is online.'
exit 0
