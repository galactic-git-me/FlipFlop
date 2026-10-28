$ErrorActionPreference = 'Stop'
foreach ($target in @('DEV', 'LIVE')) {
    $taskName = "FlipFlop Gem Radar ($target)"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed $taskName" -ForegroundColor Yellow
}
