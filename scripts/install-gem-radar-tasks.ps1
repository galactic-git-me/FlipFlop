# Registers two Windows Scheduled Tasks that each prepare the environment
# (start-all-servers.ps1 -RunMode ...) and then launch the matching Gem Radar
# Chrome extension (start-gem-radar-chrome.ps1) via run-scheduled-scan.ps1:
#
#   FlipFlopGemRadarProd  -> live mode,        10:00 and 22:00 daily
#   FlipFlopGemRadarDev   -> development mode, 04:00 and 16:00 daily
#
# Deliberately offset by 6h from each other so DEV always starts 6h after the
# preceding PROD run and PROD always starts 6h after the preceding DEV run --
# this spaces the two out evenly across the day. start-gem-radar-chrome.ps1
# enforces mutual exclusion itself (lock file + closing the other mode's
# Chrome), so even if both fire close together only one will actually scrape.
#
# Each task also has a LogonTrigger with StartWhenAvailable, so a run missed
# because the PC was off fires as soon as you next log in. Chrome needs a
# real interactive desktop to render scan windows, so these run under
# InteractiveToken (not S4U) -- they cannot fire before Windows login, only
# once you're logged on (see conversation: accepted tradeoff over auto-login).
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repo 'scripts\run-scheduled-scan.ps1'
$user = "$env:USERDOMAIN\$env:USERNAME"

function Register-GemRadarTask {
    param(
        [string]$TaskName,
        [string]$Mode,
        [string[]]$DailyTimes,
        [string]$Description
    )

    $calendarTriggers = ($DailyTimes | ForEach-Object {
        @"
    <CalendarTrigger>
      <Enabled>true</Enabled>
      <StartBoundary>2026-01-01T$($_):00</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
"@
    }) -join "`n"

    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$Description</Description>
  </RegistrationInfo>
  <Triggers>
$calendarTriggers
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$user</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$user</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT15M</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT5M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$script" -Mode $Mode</Arguments>
    </Exec>
  </Actions>
</Task>
"@

    $xmlPath = Join-Path $env:TEMP "flipflop-gem-radar-task-$Mode.xml"
    Set-Content -Path $xmlPath -Value $xml -Encoding Unicode
    schtasks /create /tn $TaskName /xml $xmlPath /f
    Write-Host "Registered '$TaskName' ($Mode) at $($DailyTimes -join ', '), plus logon catch-up."
}

Register-GemRadarTask -TaskName 'FlipFlopGemRadarProd' -Mode 'live' -DailyTimes @('10:00', '22:00') `
    -Description 'Prepares production environment (Andromeda backend) and launches the LIVE Gem Radar extension. Runs 10:00 and 22:00 daily; catches up on next logon if missed.'

Register-GemRadarTask -TaskName 'FlipFlopGemRadarDev' -Mode 'development' -DailyTimes @('04:00', '16:00') `
    -Description 'Prepares local development environment and launches the DEV Gem Radar extension. Runs 04:00 and 16:00 daily (6h offset from PROD); catches up on next logon if missed.'

Write-Host ""
Write-Host "Both tasks registered. Start one now to test, e.g.:"
Write-Host "  schtasks /run /tn FlipFlopGemRadarProd"
Write-Host "  schtasks /run /tn FlipFlopGemRadarDev"
Write-Host ""
Write-Host "DEV and PROD Chrome/extension instances are mutually exclusive via a lock file"
Write-Host "in start-gem-radar-chrome.ps1 -- only one mode's extension scrapes at a time."
