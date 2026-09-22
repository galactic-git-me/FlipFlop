# Registers a Windows Scheduled Task that keeps Chrome + the Gem Radar LIVE
# extension running so scans happen reliably without any manual action.
#
# Triggers:
#   - Two daily times (08:00 / 20:00) matching the desired ~2x/day cadence.
#   - Logon trigger, so a run missed while the PC was off fires as soon as
#     you log back in (combined with StartWhenAvailable below).
#   - Every 2 hours as a watchdog, so if Chrome/the extension gets closed or
#     crashes mid-day it's relaunched well within the same day rather than
#     waiting for the next fixed time trigger.
#
# StartWhenAvailable = "run task as soon as possible after a scheduled start
# is missed" — this is what makes a missed run catch up on next boot/logon
# rather than being silently skipped, per Microsoft's Task Scheduler docs.
#
# The launched script itself is idempotent (start-gem-radar-chrome.ps1 exits
# immediately if Chrome already owns the dedicated profile), so overlapping
# triggers never spawn duplicate Chrome instances or scan windows.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repo 'scripts\start-gem-radar-chrome.ps1'
$taskName = 'FlipFlopGemRadarChrome'
$user = "$env:USERDOMAIN\$env:USERNAME"

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Keeps Chrome running with the Gem Radar LIVE extension loaded so scheduled scraper scans (chrome.alarms, ~every 3h) run reliably without manual intervention. Catches up after reboots via StartWhenAvailable.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <Enabled>true</Enabled>
      <StartBoundary>2026-01-01T08:00:00</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
    <CalendarTrigger>
      <Enabled>true</Enabled>
      <StartBoundary>2026-01-01T20:00:00</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$user</UserId>
    </LogonTrigger>
    <TimeTrigger>
      <Enabled>true</Enabled>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Repetition>
        <Interval>PT2H</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </TimeTrigger>
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
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT5M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$script"</Arguments>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = Join-Path $env:TEMP 'flipflop-gem-radar-task.xml'
Set-Content -Path $xmlPath -Value $xml -Encoding Unicode

schtasks /create /tn $taskName /xml $xmlPath /f
Write-Host "Registered scheduled task '$taskName'."
Write-Host "Triggers: 08:00 and 20:00 daily, on logon, and every 2h as a watchdog."
Write-Host "A missed run (PC off) fires as soon as you log back in, via StartWhenAvailable."
Write-Host "Start it now with: schtasks /run /tn $taskName"
