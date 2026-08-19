#Requires -RunAsAdministrator

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$backupRoot = (Resolve-Path -LiteralPath 'C:\Users\mclar\db-backups\pcflipper').Path
$pgRoot = 'C:\Program Files\PostgreSQL\18'
$pgData = Join-Path $pgRoot 'data'
$pgRestore = Join-Path $pgRoot 'bin\pg_restore.exe'
$psql = Join-Path $pgRoot 'bin\psql.exe'
$serviceName = 'postgresql-x64-18'
$taskName = 'PCFlipperDBBackup'

Write-Host 'Pausing database backups...'
Disable-ScheduledTask -TaskName $taskName -ErrorAction Stop | Out-Null

$files = @(
    Get-ChildItem -LiteralPath $backupRoot -File -Filter 'pcflipper_*.dump' -Force |
        Sort-Object LastWriteTime -Descending
)
if ($files.Count -lt 1) {
    throw 'No database backups were found; refusing to continue.'
}

$unsafe = @(
    $files | Where-Object {
        -not $_.FullName.StartsWith($backupRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $_.PSIsContainer -or
        ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
    }
)
if ($unsafe.Count -gt 0) {
    throw "Unsafe backup targets detected: $($unsafe.Count)"
}

$keep = @(
    $files |
        Group-Object { $_.LastWriteTime.Date } |
        ForEach-Object { $_.Group | Sort-Object LastWriteTime -Descending | Select-Object -First 1 } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 7
)
if ($keep.Count -lt 1) {
    throw 'No daily recovery points were selected; refusing to continue.'
}

Write-Host "Validating $($keep.Count) retained daily recovery points..."
foreach ($dump in $keep) {
    & $pgRestore --list $dump.FullName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Backup validation failed: $($dump.FullName)"
    }
}

$keepSet = @{}
$keep | ForEach-Object { $keepSet[$_.FullName] = $true }
$delete = @($files | Where-Object { -not $keepSet.ContainsKey($_.FullName) })
$deleteBytes = ($delete | Measure-Object Length -Sum).Sum

Write-Host ("Deleting {0} redundant dumps ({1:N2} GB); {2} validated daily dumps remain..." -f `
    $delete.Count, ($deleteBytes / 1GB), $keep.Count)
foreach ($dump in $delete) {
    $resolved = (Resolve-Path -LiteralPath $dump.FullName -ErrorAction Stop).Path
    if (-not $resolved.StartsWith($backupRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Delete target escaped backup directory: $resolved"
    }
    $item = Get-Item -LiteralPath $resolved -Force -ErrorAction Stop
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Delete target is not a regular file: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Force -ErrorAction Stop
}

$remaining = @(Get-ChildItem -LiteralPath $backupRoot -File -Filter 'pcflipper_*.dump' -Force)
if ($remaining.Count -ne $keep.Count) {
    throw "Unexpected remaining backup count: expected $($keep.Count), found $($remaining.Count)"
}

$postgresConfig = Join-Path $pgData 'postgresql.conf'
$activeArchiveSettings = @(
    Get-Content -LiteralPath $postgresConfig -ErrorAction Stop |
        Where-Object { $_ -match '^\s*archive_mode\s*=' -and $_ -notmatch '^\s*#' }
)
if ($activeArchiveSettings.Count -ne 1 -or $activeArchiveSettings[0] -notmatch '^\s*archive_mode\s*=\s*off(?:\s|#|$)') {
    throw "PostgreSQL archive_mode is not safely staged as off in $postgresConfig"
}

Write-Host 'Restarting PostgreSQL so retained WAL can be recycled...'
Restart-Service -Name $serviceName -Force -ErrorAction Stop
$service = Get-Service -Name $serviceName
$service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
if ($service.Status -ne 'Running') {
    throw "PostgreSQL failed to return to Running state: $($service.Status)"
}

$env:PGPASSWORD = 'flipper'
$activeMode = (& $psql -h 127.0.0.1 -p 5432 -U flipper -d pcflipper -X -Atqc 'SHOW archive_mode;').Trim()
if ($LASTEXITCODE -ne 0 -or $activeMode -ne 'off') {
    throw "PostgreSQL restarted but archive_mode is not off: $activeMode"
}
& $psql -h 127.0.0.1 -p 5432 -U flipper -d pcflipper -X -c 'CHECKPOINT;'
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'The flipper role cannot request CHECKPOINT; waiting for PostgreSQL automatic checkpoint.'
}

$walPath = Join-Path $pgData 'pg_wal'
$walBytes = [long]::MaxValue
$deadline = (Get-Date).AddMinutes(7)
do {
    $walBytes = (
        Get-ChildItem -LiteralPath $walPath -File -Force -ErrorAction Stop |
            Measure-Object Length -Sum
    ).Sum
    Write-Host ("Waiting for WAL recycling: {0:N2} GB currently..." -f ($walBytes / 1GB))
    if ($walBytes -le 2GB) {
        break
    }
    Start-Sleep -Seconds 15
} while ((Get-Date) -lt $deadline)

if ($walBytes -gt 2GB) {
    throw ("WAL did not recycle within seven minutes; current size is {0:N2} GB. Backups remain disabled." -f ($walBytes / 1GB))
}

Enable-ScheduledTask -TaskName $taskName -ErrorAction Stop | Out-Null
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"

Write-Host 'Recovery completed successfully.'
Write-Host ("Remaining backups: {0}" -f $remaining.Count)
Write-Host ("Current pg_wal size: {0:N2} GB" -f ($walBytes / 1GB))
Write-Host ("Current C: free space: {0:N2} GB" -f ($disk.FreeSpace / 1GB))
Write-Host 'Backup schedule: daily at 23:00 (enabled)'
