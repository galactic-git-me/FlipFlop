# Registers the peer-sync tunnel+runner as a Windows Scheduled Task that
# starts at boot AND logon, and restarts itself if it crashes — a Docker
# `restart: always`-style policy. Deliberately NOT PM2.
# Run this once, interactively, as the user who should own the task.
#
# LogonType S4U ("run whether user is logged on or not", no stored password)
# is what makes the BootTrigger actually fire on a cold boot before anyone
# logs in — InteractiveToken only ever runs the LogonTrigger. This requires
# the account to hold the "Log on as a batch job" right, which schtasks
# grants automatically when registering an S4U task.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repo 'scripts\start-peer-sync-tunnel.ps1'
$taskName = 'FlipFlopPeerSync'
$user = "$env:USERDOMAIN\$env:USERNAME"

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>FlipFlop peer database sync: SSH tunnel watchdog + sync runner. Restarts on failure, starts at boot and logon.</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
    </BootTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$user</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$user</UserId>
      <LogonType>S4U</LogonType>
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
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-NoProfile -ExecutionPolicy Bypass -File "$script" -Write</Arguments>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = Join-Path $env:TEMP 'flipflop-peer-sync-task.xml'
Set-Content -Path $xmlPath -Value $xml -Encoding Unicode

schtasks /create /tn $taskName /xml $xmlPath /f
Write-Host "Registered scheduled task '$taskName'. Start it now with: schtasks /run /tn $taskName"
