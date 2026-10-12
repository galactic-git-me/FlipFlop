"""Deterministic assembly of an admin-reviewed Getting Ready package.

The LLM manifest supplies reviewed prose and evidence references. This module
owns file names, executable content, checksums and ZIP creation. It never
downloads drivers/manuals, installs software, exposes licence keys or performs
an externally charged action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from base64 import b64encode
from hashlib import sha256
from html import escape
import json
from pathlib import Path, PurePosixPath
import re
from textwrap import dedent
from typing import Any
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile
from io import BytesIO

import qrcode
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A5, landscape
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from app.services.software_catalogue import (
    create_customer_profile_software_install_script,
    create_master_setup_script,
    create_rainmeter_install_script,
    create_rainmeter_skin,
    create_software_install_script,
    create_windows_deployment_evidence_script,
    SOFTWARE_BY_ID,
    validate_package_ids,
)
from app.services.ai_setup_offers import AI_SETUP_OFFER_DEFINITIONS
from app.template_paths import dispatch_template_path


PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "data" / "getting-ready-packages"
DISPATCH_CHECKLIST_TEMPLATE = dispatch_template_path("dispatch-checklist.md")


class GettingReadyPackageError(RuntimeError):
    pass


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _text_bytes(value: str) -> bytes:
    return (value.rstrip() + "\n").encode("utf-8")


def _validate_getting_started_guide_provenance(
    guide: str,
    metadata: Any,
) -> None:
    """Reject changed guide snapshots when generation recorded a source hash."""
    if not isinstance(metadata, dict) or not metadata.get("sha256"):
        # Legacy reviewed manifests may predate guide provenance metadata.
        return
    if metadata.get("source") not in {
        "admin_settings_upload",
        "generation_request",
        "generated_manifest_intro",
    }:
        raise GettingReadyPackageError("The Getting Started guide source is invalid; regenerate and review the manifest")
    actual_hash = sha256(_text_bytes(guide)).hexdigest()
    if metadata["sha256"] != actual_hash:
        raise GettingReadyPackageError("The Getting Started guide changed after manifest generation; regenerate and review the manifest")


def _windows_setup_answer_file() -> bytes:
    """Return a non-destructive Windows Setup answer file for en-GB Audit Mode.

    It deliberately does not define DiskConfiguration, InstallTo, a product
    key, a local account, or any OOBE bypass. The technician must pick Pro and
    the target disk in the official Windows Setup UI.
    """
    xml = dedent('''\
        <?xml version="1.0" encoding="utf-8"?>
        <unattend xmlns="urn:schemas-microsoft-com:unattend">
          <settings pass="windowsPE">
            <component name="Microsoft-Windows-International-Core-WinPE" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
              <SetupUILanguage><UILanguage>en-GB</UILanguage></SetupUILanguage>
              <UILanguage>en-GB</UILanguage>
            </component>
          </settings>
          <settings pass="specialize">
            <component name="Microsoft-Windows-International-Core" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
              <InputLocale>en-GB</InputLocale>
              <SystemLocale>en-GB</SystemLocale>
              <UILanguage>en-GB</UILanguage>
              <UserLocale>en-GB</UserLocale>
            </component>
          </settings>
          <settings pass="oobeSystem">
            <component name="Microsoft-Windows-Deployment" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
              <Reseal><Mode>Audit</Mode></Reseal>
            </component>
          </settings>
        </unattend>
    ''').strip() + "\n"
    return xml.encode("utf-8")


def is_customer_package_document_name(name: str) -> bool:
    if not isinstance(name, str):
        return False
    fixed_names = {
        "01-build-plaque.pdf",
        "01-build-plaque.json",
        "02-build-specification.pdf",
        "02-build-specification.json",
        "03-benchmark-results.pdf",
        "03-benchmark-results.json",
        "04-getting-started-guide.md",
        "08-upgrade-path.html",
        "10-personalized-portal-leaflet.pdf",
    }
    if name in fixed_names:
        return True
    if "\\" in name:
        return False
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and str(path) == name
        and len(path.parts) == 2
        and path.parts[0] == "07-component-manuals"
        and path.parts[1] not in {"", ".", ".."}
        and path.parts[1].lower().endswith(".pdf")
    )


def _windows_deployment_script(
    *, build_id: int, build_name: str,
    target_drive_model: str | None = None,
    target_drive_serial: str | None = None,
    target_drive_inspected_at_utc: str | None = None,
) -> str:
    """Build the gated WinPE installer bound to the reviewed target identity."""
    encoded_name = b64encode(str(build_name).encode("utf-8")).decode("ascii")
    encoded_model = b64encode(str(target_drive_model or "").encode("utf-8")).decode("ascii")
    encoded_serial = b64encode(str(target_drive_serial or "").encode("utf-8")).decode("ascii")
    encoded_inspected_at = b64encode(str(target_drive_inspected_at_utc or "").encode("utf-8")).decode("ascii")
    return r'''param(
    [Parameter(Mandatory = $true)][string]$MediaRoot
)
$ErrorActionPreference = 'Stop'
$buildId = __BUILD_ID__
$buildName = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__BUILD_NAME_B64__'))
$expectedModel = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__TARGET_MODEL_B64__'))
$expectedSerial = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__TARGET_SERIAL_B64__'))
$targetInspectedAtText = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__TARGET_INSPECTED_AT_B64__'))
$logPath = Join-Path $PSScriptRoot ('windows-install-' + $buildId + '.log')
try { Start-Transcript -LiteralPath $logPath -Append | Out-Null } catch { }

function Assert-ExitCode([string]$Name) {
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE. Do not reboot; review this log." }
}
function Normalize-Identity([string]$Value) {
    return (($Value -replace '\s+', ' ').Trim())
}
function Get-FreeLetter {
    $used = (Get-Volume | Where-Object DriveLetter | ForEach-Object { [string]$_.DriveLetter })
    foreach ($letter in @('R','S','T','U','V','W','Y','Z')) {
        if ($used -notcontains $letter) { return $letter }
    }
    throw 'No temporary drive letter is available for recovery setup.'
}

try {
    if (-not (Test-Path 'HKLM:\SYSTEM\CurrentControlSet\Control\MiniNT')) { throw 'Boot into the approved Windows PE workshop environment before running this installer.' }
    if (-not [Environment]::Is64BitProcess) { throw 'This installer requires 64-bit Windows PE.' }
    $firmwareMode = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\PEFirmwareType' -ErrorAction SilentlyContinue).PEFirmwareType
    if ($firmwareMode -ne 2) { throw 'Boot this device in UEFI mode. The installer will not prepare legacy BIOS boot.' }
    foreach ($command in @('Get-Disk','Get-Partition','Get-Volume','Clear-Disk','Initialize-Disk','New-Partition','Format-Volume','Add-PartitionAccessPath','Remove-PartitionAccessPath','Set-Partition','Get-CimInstance')) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Required WinPE command '$command' is unavailable. Rebuild WinPE with Microsoft PowerShell and StorageWMI optional components." }
    }
    foreach ($tool in @('dism.exe','bcdboot.exe','reagentc.exe')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Required Windows deployment tool '$tool' is unavailable." }
    }
    $expectedModel = Normalize-Identity $expectedModel
    $expectedSerial = $expectedSerial.Trim()
    if (-not $expectedModel -or -not $expectedSerial -or -not $targetInspectedAtText) { throw 'This package has no reviewed target drive identity and inspection time. Record the intended drive in Dispatch Centre and regenerate the package.' }
    try { $targetInspectedAt = [DateTimeOffset]::Parse($targetInspectedAtText, [Globalization.CultureInfo]::InvariantCulture).ToUniversalTime() }
    catch { throw 'The reviewed target inspection time is invalid; reconfirm the drive and regenerate the package.' }
    $targetInspectionAge = [DateTimeOffset]::UtcNow - $targetInspectedAt
    if ($targetInspectionAge.TotalSeconds -lt -300 -or $targetInspectionAge.TotalDays -gt 30) { throw 'The reviewed target inspection is older than 30 days or from the future. Reconfirm the drive in Dispatch Centre and regenerate the package.' }

    $mediaPath = (Resolve-Path -LiteralPath $MediaRoot -ErrorAction Stop).Path
    $answerFile = Join-Path $PSScriptRoot 'Autounattend.xml'
    if (-not (Test-Path -LiteralPath $answerFile -PathType Leaf)) { throw 'The reviewed Autounattend.xml is missing from this build package.' }
    $imageFile = @((Join-Path $mediaPath 'sources\install.wim'), (Join-Path $mediaPath 'sources\install.esd')) |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $imageFile) { throw 'The official Windows media must contain sources\install.wim or sources\install.esd.' }
    $imageInfo = (& dism.exe /English /Get-WimInfo "/WimFile:$imageFile" 2>&1 | Out-String)
    Assert-ExitCode 'DISM image inspection'
    $imageEntries = [regex]::Matches($imageInfo, '(?ms)^\s*Index\s*:\s*(\d+)\s*\r?\n\s*Name\s*:\s*(.+?)\s*(?:\r?\n|$)')
    $proIndexes = @($imageEntries | ForEach-Object {
        $name = $_.Groups[2].Value.Trim()
        if ($name -ceq 'Windows 11 Pro') { [int]$_.Groups[1].Value }
    } | Where-Object { $_ })
    if ($proIndexes.Count -eq 0) { throw 'No exact Windows 11 Pro image was found. Select official English International media containing Windows 11 Pro.' }
    $imageIndex = $proIndexes[0]
    if ($proIndexes.Count -gt 1) {
        $answer = Read-Host ("Windows 11 Pro image indexes: {0}. Type the exact index to use" -f ($proIndexes -join ', '))
        if ($answer -notmatch '^\d+$' -or [int]$answer -notin $proIndexes) { throw 'The selected image index is not an exact Windows 11 Pro image.' }
        $imageIndex = [int]$answer
    }
    $selectedImageInfo = (& dism.exe /English /Get-WimInfo "/WimFile:$imageFile" "/Index:$imageIndex" 2>&1 | Out-String)
    Assert-ExitCode 'DISM selected image language inspection'
    if ($selectedImageInfo -notmatch '(?im)^\s*Languages\s*:\s*.*\ben-GB\b') { throw 'The selected Windows 11 Pro image does not report the required en-GB language. Use official English International media.' }

    $physicalByIndex = @{}
    foreach ($physical in Get-CimInstance -ClassName Win32_DiskDrive) {
        $physicalByIndex[[int]$physical.Index] = $physical
    }
    $inventory = @(Get-Disk | ForEach-Object {
        $physical = $physicalByIndex[[int]$_.Number]
        [pscustomobject]@{
            Number = [int]$_.Number
            Model = Normalize-Identity ([string]$physical.Model)
            Serial = ([string]$physical.SerialNumber).Trim()
            SizeBytes = [int64]$_.Size
            BusType = [string]$_.BusType
            IsBoot = [bool]$_.IsBoot
            IsSystem = [bool]$_.IsSystem
        }
    })
    Write-Host "Target build: $buildName (#$buildId)"
    $inventory | Format-Table Number, Model, Serial, SizeBytes, BusType, IsBoot, IsSystem -AutoSize | Out-Host
    $diskMatches = @($inventory | Where-Object {
        $_.Serial -and [string]::Equals($_.Serial, $expectedSerial, [StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals($_.Model, $expectedModel, [StringComparison]::OrdinalIgnoreCase)
    })
    if ($diskMatches.Count -ne 1) { throw 'The pre-recorded target model/serial did not match exactly one physical disk. Stop and reconcile in Dispatch Centre.' }
    $target = $diskMatches[0]
    if ($target.IsBoot -or $target.IsSystem -or $target.BusType -in @('USB','SD')) { throw 'The recorded target is a boot/system/removable disk and cannot be erased by this installer.' }
    if ($target.SizeBytes -lt 80GB) { throw 'The recorded Windows target is below the supported minimum size.' }

    Write-Host ''
    Write-Host "This operation erases every partition on disk $($target.Number): $($target.Model) / $($target.Serial) / $($target.SizeBytes) bytes."
    Write-Host 'The entire physical disk is erased. Verify it is the new build drive, not a customer return or data disk.' -ForegroundColor Yellow
    $typedSerial = Read-Host 'Re-enter the exact recorded serial number'
    if (-not [string]::Equals($typedSerial.Trim(), $target.Serial, [StringComparison]::OrdinalIgnoreCase)) { throw 'Serial confirmation did not match; no disk changes were made.' }
    $erasePhrase = "ERASE-DISK $($target.Serial)"
    if ((Read-Host "Type exactly '$erasePhrase' to approve erasing this disk") -cne $erasePhrase) { throw 'Operator did not approve disk erasure.' }
    $installPhrase = "INSTALL WINDOWS 11 PRO ON BUILD $buildId"
    if ((Read-Host "Type exactly '$installPhrase' to start installation") -cne $installPhrase) { throw 'Operator did not approve Windows installation.' }

    Clear-Disk -Number $target.Number -RemoveData -RemoveOEM -Confirm:$false
    Initialize-Disk -Number $target.Number -PartitionStyle GPT
    $efi = New-Partition -DiskNumber $target.Number -Size 260MB -GptType '{C12A7328-F81F-11D2-BA4B-00A0C93EC93B}' -AssignDriveLetter
    Format-Volume -Partition $efi -FileSystem FAT32 -NewFileSystemLabel 'SYSTEM' -Confirm:$false | Out-Null
    New-Partition -DiskNumber $target.Number -Size 16MB -GptType '{E3C9E316-0B5C-4DB8-817D-F92DF00215AE}' | Out-Null
    $osSize = [int64]$target.SizeBytes - 260MB - 16MB - 1024MB - 8MB
    if ($osSize -lt 70GB) { throw 'Insufficient space remains for the Windows partition after creating required boot/recovery partitions.' }
    $os = New-Partition -DiskNumber $target.Number -Size $osSize -GptType '{EBD0A0A2-B9E5-4433-87C0-68B6B72699C7}' -AssignDriveLetter
    Format-Volume -Partition $os -FileSystem NTFS -NewFileSystemLabel 'Windows' -Confirm:$false | Out-Null
    $recovery = New-Partition -DiskNumber $target.Number -UseMaximumSize -GptType '{DE94BBA4-06D1-4D40-A16A-BFD50179D6AC}' -NoDefaultDriveLetter
    $recoveryLetter = Get-FreeLetter
    Add-PartitionAccessPath -DiskNumber $target.Number -PartitionNumber $recovery.PartitionNumber -AccessPath "${recoveryLetter}:\"
    Format-Volume -DriveLetter $recoveryLetter -FileSystem NTFS -NewFileSystemLabel 'Windows RE' -Confirm:$false | Out-Null

    $osRoot = "$($os.DriveLetter):\"
    $recoveryRoot = "${recoveryLetter}:\"
    & dism.exe /Apply-Image "/ImageFile:$imageFile" "/Index:$imageIndex" "/ApplyDir:$osRoot" /CheckIntegrity /Verify
    Assert-ExitCode 'DISM image application'
    $panther = Join-Path $osRoot 'Windows\Panther'
    New-Item -ItemType Directory -Path $panther -Force | Out-Null
    Copy-Item -LiteralPath $answerFile -Destination (Join-Path $panther 'Unattend.xml') -Force
    & bcdboot.exe (Join-Path $osRoot 'Windows') /s "$($efi.DriveLetter):" /f UEFI /l en-GB
    Assert-ExitCode 'UEFI boot file creation'

    $winreSource = Join-Path $osRoot 'Windows\System32\Recovery\Winre.wim'
    if (Test-Path -LiteralPath $winreSource -PathType Leaf) {
        $winreDirectory = Join-Path $recoveryRoot 'Recovery\WindowsRE'
        New-Item -ItemType Directory -Path $winreDirectory -Force | Out-Null
        Copy-Item -LiteralPath $winreSource -Destination (Join-Path $winreDirectory 'Winre.wim') -Force
        & reagentc.exe /SetReImage /Path $winreDirectory /Target (Join-Path $osRoot 'Windows')
        Assert-ExitCode 'Windows Recovery Environment registration'
        & reagentc.exe /Enable /Target (Join-Path $osRoot 'Windows')
        Assert-ExitCode 'Windows Recovery Environment enablement'
    } else {
        Write-Warning 'The image contains no Winre.wim; Windows will install but Recovery Environment must be reviewed by the technician.'
    }
    Set-Partition -DiskNumber $target.Number -PartitionNumber $recovery.PartitionNumber -GptType '{DE94BBA4-06D1-4D40-A16A-BFD50179D6AC}' -IsHidden $true -NoDefaultDriveLetter $true
    Remove-PartitionAccessPath -DiskNumber $target.Number -PartitionNumber $recovery.PartitionNumber -AccessPath "${recoveryLetter}:\"

    $record = [ordered]@{
        build_id = $buildId; build_name = $buildName; installed_edition = 'Windows 11 Pro'
        locale = 'en-GB'; target_drive_model = $target.Model; target_drive_serial = $target.Serial
        target_drive_size_bytes = $target.SizeBytes; target_disk_number_at_install = $target.Number
        installation_method = 'gated_winpe_dism_apply'; image_source = [IO.Path]::GetFileName($imageFile)
        image_index = $imageIndex; approved_at_utc = [DateTime]::UtcNow.ToString('o')
        operator_confirmed_disk_erasure = $true
    }
    $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('windows-install-' + $buildId + '.json')) -Encoding UTF8
    Write-Host 'Windows 11 Pro was applied to the recorded target. Review the log and report, then boot the build and verify its target serial in Dispatch Centre before any later setup or dispatch.' -ForegroundColor Green
    Write-Host 'The separate Audit Mode master setup and customer OOBE approval steps still apply.'
} catch {
    Write-Error $_
    Write-Host 'Installation stopped. Do not reboot until the technician has reviewed the log and current disk state.' -ForegroundColor Red
    exit 1
} finally {
    try { Stop-Transcript | Out-Null } catch { }
}
'''.replace('__BUILD_ID__', str(int(build_id))).replace('__BUILD_NAME_B64__', encoded_name).replace(
        '__TARGET_MODEL_B64__', encoded_model
    ).replace('__TARGET_SERIAL_B64__', encoded_serial).replace(
        '__TARGET_INSPECTED_AT_B64__', encoded_inspected_at
    )


def _prepare_customer_oobe_script() -> str:
    """Create the explicit final transition from workshop Audit Mode to OOBE."""
    return r'''$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this handover step from an elevated workshop session.' }
if (-not $identity.User.Value.EndsWith('-500')) { throw 'This action is only available from the built-in Audit Mode Administrator session.' }
$edition = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').EditionID
if ($edition -ne 'Professional' -or (Get-WinSystemLocale).Name -ne 'en-GB') { throw 'Verify Windows 11 Pro and en-GB before preparing customer OOBE.' }
$reportPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'master-setup-report.json'
if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) { throw 'The master setup report is missing; complete and review workshop setup first.' }
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.software_installer -ne 'machine_scope_complete' -or $report.rainmeter_theme -ne 'complete') { throw 'The machine-wide software and FlipFlop desktop setup must be complete before customer handover.' }
$sysprep = Join-Path $env:WINDIR 'System32\Sysprep\Sysprep.exe'
if (-not (Test-Path -LiteralPath $sysprep -PathType Leaf)) { throw 'Microsoft Sysprep is not available.' }
$confirmation = Read-Host 'This will shut down Windows and present customer first-run setup at the next power-on. Type PREPARE-FOR-CUSTOMER to continue'
if ($confirmation -cne 'PREPARE-FOR-CUSTOMER') { throw 'Operator cancelled customer OOBE preparation.' }
$process = Start-Process -FilePath $sysprep -ArgumentList '/oobe /shutdown' -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Sysprep did not complete successfully (exit code $($process.ExitCode)). Review Windows setup logs before dispatch." }
'''


def _paid_ai_setup_runbook(purchases: Any) -> str | None:
    """Render operator steps only for webhook-confirmed, supported purchases."""
    if purchases in (None, []):
        return None
    if not isinstance(purchases, list):
        raise GettingReadyPackageError("Paid AI setup records must be a list")

    definitions = {item["id"]: item for item in AI_SETUP_OFFER_DEFINITIONS}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for purchase in purchases:
        if not isinstance(purchase, dict) or purchase.get("payment_status") != "paid":
            raise GettingReadyPackageError("The AI setup runbook can include only confirmed paid purchases")
        offer_id = str(purchase.get("id") or "")
        definition = definitions.get(offer_id)
        if not definition or offer_id in seen:
            raise GettingReadyPackageError("The AI setup runbook contains an unknown or duplicate offer")
        if purchase.get("name") != definition["name"]:
            raise GettingReadyPackageError("An AI setup purchase no longer matches its reviewed offer")
        seen.add(offer_id)
        selected.append(definition)

    lines = [
        "# Paid AI setup — operator runbook",
        "",
        "This runbook is generated from confirmed paid order records. It describes the scope to prepare; it does not install software or authorize account access. Complete it on the workshop machine only after the customer and an administrator approve the specific application, version, permissions and data location.",
        "",
        "## Before installing anything",
        "",
        "1. Match every section below to the paid order and the build name on this package.",
        "2. Confirm the customer has approved the exact application/model and any cloud account, storage location, integrations or permissions it needs. Ask the customer to enter their own credentials; never request, copy or store passwords, API keys or recovery codes.",
        "3. Use the vendor's official distribution source and current supported release. Record the application/model, version and source in the Dispatch Centre completion note. Do not run installers supplied by a research result or by an unverified link.",
        "4. Test with sample data first. Do not enable sending messages, publishing, purchasing, deleting files, code execution or unattended actions without the customer's separate, specific approval.",
        "5. If an app, model, licence, permission or data boundary is not settled below, stop and obtain customer approval before proceeding. Do not mark Paid AI services complete until each purchased scope is installed, checked and recorded.",
        "",
    ]
    for definition in selected:
        lines.extend([f"## {definition['name']}", "", str(definition["description"]), ""])
        offer_id = definition["id"]
        if offer_id == "ai_assistant_automation_pack":
            lines.extend([
                "### Confirm the assistant choice",
                "",
                "The paid record does not name a specific assistant application. Agree the application with the customer before downloading it; do not assume Hermes, OpenClaw or another product was selected.",
                "",
                "### Included starter automations",
                "",
            ])
            for automation in definition.get("included_automations") or []:
                lines.append(f"- **{automation['name']}:** {automation['benefit']}")
            lines.extend([
                "",
                "Keep these automations in draft/review mode. Ask before connecting mail, calendars or personal folders, and do not enable automatic replies or external actions by default.",
                "",
            ])
        elif offer_id == "personal_ai_second_brain":
            lines.extend([
                "Confirm whether the customer wants local or hosted storage, which folders may be indexed, whether synchronisation is enabled, and how they will export or delete the memory store. Do not ingest existing personal files until the customer selects them.",
                "",
            ])
        elif offer_id == "local_llm_setup":
            lines.extend([
                "### Confirm the model and local boundary",
                "",
                "The paid record does not name a specific model. Confirm the exact model with the customer and review its current licence before downloading. Verify the build's measured GPU VRAM is at least 12 GB before starting. Configure local-only access unless the customer separately approves network exposure or cloud services; explain that local inference still uses electricity and does not remove model licence terms.",
                "",
            ])
        lines.extend([
            "### Record completion",
            "",
            "Record the installed application/model and version, official source, customer-approved configuration boundary, sample-data test result and operator name/date in the Dispatch Centre AI services completion note. Do not include credentials or customer content.",
            "",
        ])
    return "\n".join(lines)


def _upgrade_html(build_name: str, upgrade_path: dict[str, Any]) -> str:
    items = upgrade_path.get("items") if isinstance(upgrade_path, dict) else []
    cards = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = escape(str(item.get("title") or item.get("component") or "Upgrade review"))
        timing = escape(str(item.get("timing") or item.get("when") or "Review when your needs change"))
        reason = escape(str(item.get("reason") or item.get("description") or "Confirm compatibility and measured need before upgrading."))
        cards.append(f'<article><h2>{title}</h2><p class="timing">{timing}</p><p>{reason}</p></article>')
    if not cards:
        cards.append('<article><h2>No dated upgrade is prescribed</h2><p>Review upgrades when workload, compatibility, faults or measured performance justify a change.</p></article>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(build_name)} upgrade path</title><style>
body{{margin:0;background:#07111f;color:#e8f4ff;font:16px/1.6 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:48px 24px}}
h1{{font-size:clamp(2rem,6vw,4rem);margin:0 0 12px}}.intro{{color:#9db4c8}}article{{margin-top:20px;padding:24px;border:1px solid #28425a;border-radius:18px;background:#0e1b2b}}
h2{{margin:0 0 8px}}.timing{{color:#67dcff;font-weight:700}}footer{{margin-top:32px;color:#8299ad;font-size:.85rem}}
</style></head><body><main><p>FLIPFLOP BUILD CARE</p><h1>{escape(build_name)}</h1><p class="intro">A compatibility-led upgrade guide. Dates are guidance only; inspect the exact build before purchasing parts.</p>{''.join(cards)}<footer>Generated from the reviewed build record. Statutory rights and the FlipFlop warranty are unaffected.</footer></main></body></html>"""


def render_dispatch_checklist(build_name: str) -> str:
    if not DISPATCH_CHECKLIST_TEMPLATE.is_file():
        raise GettingReadyPackageError(f"Dispatch checklist template is missing: {DISPATCH_CHECKLIST_TEMPLATE}")
    safe_name = escape(" ".join(str(build_name).split()), quote=False)
    return DISPATCH_CHECKLIST_TEMPLATE.read_text(encoding="utf-8").replace("{{build_name}}", safe_name)


def _plaque_pdf(build_name: str, plaque: dict[str, Any]) -> bytes:
    """Render a compact customer-facing plaque from the reviewed manifest."""
    def printable(value: Any) -> str:
        # ReportLab's built-in Helvetica fonts use WinAnsi. Preserve common
        # punctuation while ensuring arbitrary LLM/customer text cannot make
        # PDF creation fail on unsupported glyphs.
        return str(value or "").encode("cp1252", errors="replace").decode("cp1252")

    title = printable(plaque.get("title") or "Your FlipFlop build")
    subtitle = printable(plaque.get("subtitle") or "Thoughtfully matched to your needs")
    segment = printable(plaque.get("segment_label") or "")
    name = printable(plaque.get("build_name") or build_name)

    buffer = BytesIO()
    width, height = landscape(A5)
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setFillColor(HexColor("#07152d"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#67dcff"))
    pdf.roundRect(28, 28, width - 56, height - 56, 18, fill=0, stroke=1)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(48, height - 56, "FLIPFLOP  /  BUILD PLAQUE")

    title_lines = simpleSplit(title, "Helvetica-Bold", 14, width - 96)[:2]
    y = height - 100
    pdf.setFillColor(HexColor("#a8bed4"))
    pdf.setFont("Helvetica-Bold", 14)
    for line in title_lines:
        pdf.drawString(48, y, line)
        y -= 19

    name_size = 34
    while name_size > 18 and max((pdfmetrics.stringWidth(line, "Helvetica-Bold", name_size) for line in simpleSplit(name, "Helvetica-Bold", name_size, width - 96)), default=0) > width - 96:
        name_size -= 1
    name_lines = simpleSplit(name, "Helvetica-Bold", name_size, width - 96)[:2]
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", name_size)
    for line in name_lines:
        pdf.drawString(48, y, line)
        y -= name_size + 7

    pdf.setFillColor(HexColor("#67dcff"))
    pdf.setFont("Helvetica", 12)
    for line in simpleSplit(subtitle, "Helvetica", 12, width - 96)[:2]:
        pdf.drawString(48, y - 2, line)
        y -= 17
    if segment:
        pdf.setFillColor(HexColor("#c9d8e8"))
        pdf.setFont("Helvetica", 9)
        for index, line in enumerate(simpleSplit(f"Playbook: {segment}", "Helvetica", 9, width - 96)[:2]):
            pdf.drawString(48, 70 - (index * 12), line)

    pdf.setFillColor(HexColor("#8399ad"))
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - 48, 43, "Specification and measured results are provided separately.")
    pdf.save()
    return buffer.getvalue()


def _summary_pdf(*, title: str, build_name: str, value: Any, empty_message: str) -> bytes:
    """Render reviewed build data as a readable PDF while retaining JSON."""
    def printable(text: Any) -> str:
        return str(text).encode("cp1252", errors="replace").decode("cp1252")

    lines: list[str] = []

    def flatten(label: str, item: Any, depth: int = 0) -> None:
        if len(lines) >= 600:
            return
        if isinstance(item, dict):
            if not item:
                lines.append(f"{'  ' * depth}{label}: no recorded details")
                return
            for key, child in item.items():
                flatten(f"{label} · {key}" if label else str(key), child, depth + 1)
        elif isinstance(item, list):
            if not item:
                lines.append(f"{'  ' * depth}{label}: none recorded")
                return
            for index, child in enumerate(item, 1):
                child_label = f"{label} {index}" if label else f"Item {index}"
                flatten(child_label, child, depth + 1)
        else:
            rendered = json.dumps(item, ensure_ascii=False) if item is None or isinstance(item, (bool, int, float)) else str(item)
            lines.append(f"{'  ' * depth}{label}: {rendered}" if label else rendered)

    flatten("", value)
    if not lines:
        lines = [empty_message]
    if len(lines) >= 600:
        lines[-1] = "Further detail is available in the accompanying JSON file."

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A5)
    width, height = A5
    left, right = 38, width - 38
    y = height - 44

    def start_page() -> None:
        nonlocal y
        pdf.setFillColor(HexColor("#07152d"))
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#67dcff"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(left, height - 25, "FLIPFLOP  /  BUILD RECORD")
        pdf.setFillColor(white)
        pdf.setFont("Helvetica-Bold", 18)
        title_lines = simpleSplit(printable(title), "Helvetica-Bold", 18, right - left)
        for index, line in enumerate(title_lines[:2]):
            pdf.drawString(left, height - 54 - (20 * index), line)
        pdf.setFillColor(HexColor("#a8bed4"))
        pdf.setFont("Helvetica", 10)
        pdf.drawString(left, height - 100, printable(build_name)[:100])
        pdf.setStrokeColor(HexColor("#28425a"))
        pdf.line(left, height - 112, right, height - 112)
        y = height - 130

    start_page()
    pdf.setFont("Helvetica", 8.5)
    for raw_line in lines:
        safe_line = printable(raw_line)
        wrapped = simpleSplit(safe_line, "Helvetica", 8.5, right - left)
        for part in wrapped or [""]:
            if y < 36:
                pdf.showPage()
                start_page()
                pdf.setFont("Helvetica", 8.5)
            pdf.setFillColor(HexColor("#d8e5f2"))
            pdf.drawString(left, y, part)
            y -= 12
    pdf.save()
    return buffer.getvalue()


def _portal_leaflet_pdf(*, build_name: str, access_url: str, claim_code: bool) -> bytes:
    """Render the two-sided, order-specific A5 portal leaflet."""
    if not access_url.startswith("https://") and not access_url.startswith("http://localhost"):
        raise GettingReadyPackageError("Portal URL must use HTTPS outside local development")
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(access_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="#0f1419", back_color="white")
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format="PNG")

    pdf_buffer = BytesIO()
    width, height = A5
    pdf = canvas.Canvas(pdf_buffer, pagesize=A5)
    charcoal = HexColor("#0f1419")
    card = HexColor("#1a1f2b")
    gold = HexColor("#d4af37")
    primary = HexColor("#f4f5f7")
    secondary = HexColor("#c7ccd6")
    muted = HexColor("#a0a8c0")
    site = urlsplit(access_url).netloc or "flipflop.shop"

    def start_page() -> None:
        pdf.setFillColor(charcoal)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setStrokeColor(gold)
        pdf.setLineWidth(1.1)
        pdf.rect(14, 14, width - 28, height - 28, fill=0, stroke=1)

    def draw_paragraph(
        value: str,
        x: float,
        y: float,
        max_width: float,
        *,
        font_size: float,
        leading: float,
        color=secondary,
    ) -> float:
        pdf.setFillColor(color)
        pdf.setFont("Helvetica", font_size)
        for line in simpleSplit(value, "Helvetica", font_size, max_width):
            pdf.drawString(x, y, line)
            y -= leading
        return y

    # Front: customer/build identity and the order-specific QR claim or sign-in.
    start_page()
    pdf.setStrokeColor(gold)
    pdf.roundRect(34, height - 59, 128, 20, 4, fill=0, stroke=1)
    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(98, height - 52, "FLIPFLOP · YOUR BUILD")

    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(34, height - 112, "Your PC has its")
    pdf.drawString(34, height - 140, "own home.")
    draw_paragraph(
        f"{build_name} has a private, personalised build portal.",
        34,
        height - 170,
        width - 68,
        font_size=10.5,
        leading=14,
    )
    draw_paragraph(
        "Scan the QR code printed for your build to open its portal.",
        34,
        height - 203,
        width - 68,
        font_size=10,
        leading=13,
    )

    qr_size = 158
    qr_x = (width - qr_size) / 2
    qr_y = 171
    pdf.setStrokeColor(gold)
    pdf.setLineWidth(1.2)
    pdf.roundRect(qr_x - 8, qr_y - 8, qr_size + 16, qr_size + 16, 5, fill=0, stroke=1)
    pdf.drawImage(
        ImageReader(BytesIO(qr_buffer.getvalue())),
        qr_x,
        qr_y,
        qr_size,
        qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf.setFillColor(gold)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(width / 2, qr_y - 22, "OPEN YOUR PRIVATE BUILD PORTAL")

    if claim_code:
        draw_paragraph(
            "Marketplace order: scan to claim this build portal in your browser.",
            34,
            126,
            width - 68,
            font_size=8.5,
            leading=11,
            color=secondary,
        )
    else:
        draw_paragraph(
            f"Already have an account? Sign in at {site} and open My Builds.",
            34,
            126,
            width - 68,
            font_size=8.5,
            leading=11,
            color=secondary,
        )
    pdf.setStrokeColor(gold)
    pdf.line(34, 65, width - 34, 65)
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawCentredString(width / 2, 49, "Your portal is private to your account or claim link.")

    # Back: make the portal's actual contents clear without promising a fixed ETA.
    pdf.showPage()
    start_page()
    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 21)
    pdf.drawString(34, height - 58, "Inside your portal")
    draw_paragraph("Useful details for this PC, all in one place.", 34, height - 80, width - 68, font_size=9.5, leading=12)

    sections = (
        ("01", "Your build", "Specification, benchmark results, component manuals and an upgrade path."),
        ("02", "Delivery", "Follow tracking updates as your parcel moves, when tracking is available."),
        ("03", "Getting started", "Find your guide and the software setup selected for your build."),
        ("04", "Aftercare", "Review support, returns and warranty information for this build."),
    )
    row_top = height - 111
    row_height = 78
    row_gap = 8
    for number, heading, body in sections:
        row_y = row_top - row_height
        pdf.setFillColor(card)
        pdf.setStrokeColor(gold)
        pdf.roundRect(30, row_y, width - 60, row_height, 6, fill=1, stroke=1)
        pdf.setFillColor(gold)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawCentredString(55, row_y + 43, number)
        pdf.setFillColor(primary)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(76, row_y + 49, heading)
        draw_paragraph(
            body,
            76,
            row_y + 32,
            width - 120,
            font_size=8.5,
            leading=11,
        )
        row_top = row_y - row_gap

    footer_y = row_top - 8
    footer_text = (
        "Marketplace buyers: use the private QR claim flow. Direct account customers: sign in at "
        f"{site}."
    )
    footer_y = draw_paragraph(footer_text, 34, footer_y, width - 68, font_size=8, leading=10, color=secondary)
    pdf.setStrokeColor(gold)
    pdf.line(34, footer_y - 8, width - 34, footer_y - 8)
    draw_paragraph(
        "Your portal is private to your account or claim link. Statutory rights are "
        "unaffected by portal access or the FlipFlop warranty.",
        34,
        footer_y - 22,
        width - 68,
        font_size=7.2,
        leading=9,
        color=muted,
    )
    pdf.save()
    return pdf_buffer.getvalue()


def assemble_getting_ready_package(
    *,
    build_id: int,
    build_name: str,
    version: int,
    specification: list[dict[str, Any]],
    benchmark_results: Any,
    manifest: dict[str, Any],
    software_package_ids: list[str],
    source_inputs: dict[str, Any],
    portal_url: str | None,
    target_drive_model: str,
    target_drive_serial: str,
    target_drive_inspected_at_utc: str,
    portal_leaflet_path: Path | None = None,
    cached_component_manuals: list[dict[str, Any]] | None = None,
    windows_license_key_present: bool = False,
) -> dict[str, Any]:
    if not manifest or manifest.get("status") != "ready_for_admin_review":
        raise GettingReadyPackageError("Generate a valid review manifest before assembling the package")
    if manifest.get("build_name") != build_name:
        raise GettingReadyPackageError("Manifest build name does not match the build record")
    if not target_drive_model.strip() or not target_drive_serial.strip() or not target_drive_inspected_at_utc.strip():
        raise GettingReadyPackageError("Record the intended Windows target drive model, serial and inspection time before assembling this package")
    try:
        inspected_at = datetime.fromisoformat(target_drive_inspected_at_utc.replace("Z", "+00:00"))
    except ValueError as error:
        raise GettingReadyPackageError("The Windows target inspection time is invalid") from error
    if inspected_at.tzinfo is None:
        raise GettingReadyPackageError("The Windows target inspection time must include a timezone")
    target_age = datetime.now(timezone.utc) - inspected_at.astimezone(timezone.utc)
    if target_age.total_seconds() < -300 or target_age.total_seconds() > 30 * 24 * 60 * 60:
        raise GettingReadyPackageError("Reconfirm the Windows target; its inspection must be current within 30 days")
    selected = validate_package_ids(software_package_ids)
    customer_profile_package_ids = [
        package_id for package_id in selected
        if SOFTWARE_BY_ID[package_id].get("install_scope") == "customer_profile"
    ]
    generated_at = datetime.now(timezone.utc).isoformat()
    guide = source_inputs.get("getting_started_guide_text") or manifest.get("customer_copy", {}).get("getting_started_intro")
    if not guide:
        raise GettingReadyPackageError("Upload or enter the Getting Started guide before assembling the package")
    _validate_getting_started_guide_provenance(
        str(guide),
        source_inputs.get("getting_started_guide_metadata"),
    )
    if customer_profile_package_ids:
        deferred_names = ", ".join(SOFTWARE_BY_ID[item_id]["name"] for item_id in customer_profile_package_ids)
        guide = (
            str(guide).rstrip()
            + "\n\n## Finishing your selected apps\n\n"
            + f"Your selected app setup includes {deferred_names}. These apps install into your Windows profile at sign-in, so they are available in your account instead of the workshop account. Connect the PC to the internet, sign in to Windows, and leave the startup installer open until it finishes. WinGet may ask you to review source or app licence terms; FlipFlop does not accept package terms for you. Review each prompt and accept only if you agree. If you decline a required agreement, that app will not install and the setup may ask again at your next sign-in. If setup reports another problem, contact FlipFlop through your build portal.\n"
        )

    manual_matches = manifest.get("manual_library_matches") or []
    source_plaque = manifest.get("plaque")
    if source_plaque is not None and not isinstance(source_plaque, dict):
        raise GettingReadyPackageError("The reviewed build plaque must be a JSON object")
    # This identity comes from the persisted build record, never from generated
    # prose. Keep the printable plaque and its JSON source in agreement.
    plaque = {**(source_plaque or {}), "build_name": build_name}
    files: dict[str, bytes] = {
        "01-build-plaque.pdf": _plaque_pdf(build_name, plaque),
        "01-build-plaque.json": _json_bytes(plaque),
        "02-build-specification.json": _json_bytes({"build_id": build_id, "build_name": build_name, "components": specification}),
        "02-build-specification.pdf": _summary_pdf(
            title="Build specification", build_name=build_name,
            value={"build_id": build_id, "components": specification},
            empty_message="No component specification has been recorded.",
        ),
        "03-benchmark-results.json": _json_bytes(benchmark_results or {"status": "not_recorded"}),
        "03-benchmark-results.pdf": _summary_pdf(
            title="Benchmark results", build_name=build_name,
            value=benchmark_results or {"status": "not_recorded"},
            empty_message="Benchmark results have not been recorded.",
        ),
        "04-getting-started-guide.md": _text_bytes(str(guide)),
        "05-workshop-setup/run-getting-ready.ps1": create_master_setup_script(
            build_name=build_name,
            portal_url=portal_url,
            windows_license_key_present=windows_license_key_present,
            customer_profile_apps_selected=bool(customer_profile_package_ids),
        ).encode("utf-8-sig"),
        "05-workshop-setup/install-selected-apps.ps1": create_software_install_script(selected).encode("utf-8-sig"),
        "05-workshop-setup/install-flipflop-theme.ps1": create_rainmeter_install_script().encode("utf-8-sig"),
        "05-workshop-setup/collect-windows-deployment-evidence.ps1": create_windows_deployment_evidence_script(
            build_id=build_id,
            build_name=build_name,
        ).encode("utf-8-sig"),
        "05-workshop-setup/prepare-customer-oobe.ps1": _prepare_customer_oobe_script().encode("utf-8-sig"),
        "06-windows-setup/Deploy-Windows11-Pro.ps1": _windows_deployment_script(
            build_id=build_id,
            build_name=build_name,
            target_drive_model=target_drive_model,
            target_drive_serial=target_drive_serial,
            target_drive_inspected_at_utc=target_drive_inspected_at_utc,
        ).encode("utf-8-sig"),
        "06-windows-setup/Autounattend.xml": _windows_setup_answer_file(),
        "06-windows-setup/README.md": _text_bytes(
            "# Windows 11 workshop installation\n\n"
            "Use official Microsoft Windows 11 English International media containing the Windows 11 Pro image. The intended new-build SSD model and serial must be recorded in Dispatch Centre before this reviewed package is approved; the generated installer has those values and the inspection time bound into it and accepts only the separate official media root as an argument. It refuses a target record older than 30 days, even when the USB package was generated earlier. Build the branded installer USB from Microsoft's Windows ADK/WinPE add-on and include the PowerShell, StorageWMI, WMI, NetFX and Scripting WinPE optional components. Boot WinPE in UEFI mode, connect the separate official installation media and this reviewed package, then run `Deploy-Windows11-Pro.ps1` with the official media root.\n\n"
            "The installer lists every physical disk, refuses an ambiguous model/serial match, a boot/system/removable target, missing WinPE tools, non-UEFI mode, and any image that does not report exact Windows 11 Pro and en-GB. It requires the operator to re-enter the serial and type two separate approval phrases before erasing the one disk bound to this reviewed package. It then creates GPT boot/Windows/recovery partitions, applies the selected Pro image, adds the en-GB Audit Mode answer file and creates UEFI boot files. Do not run this on a customer-owned existing system, a return being repaired, or any disk containing data the customer wants kept. Stop on any mismatch or error; inspect the transcript before rebooting.\n\n"
            "After deployment boots into Audit Mode, run `run-getting-ready.ps1` from this package in an elevated PowerShell window. Finish the reviewed drivers, paid services and hardware tasks, collect/import the build-bound Windows evidence, and confirm the system-drive serial in Dispatch Centre. When all machine work is complete, run `prepare-customer-oobe.ps1` and type `PREPARE-FOR-CUSTOMER`; it verifies the built-in Audit Mode Administrator, Windows Pro/en-GB and the completed master report before asking Microsoft Sysprep to shut down into customer OOBE. It creates no account and uses no undocumented OOBE bypass.\n"
        ),
        "05-workshop-setup/Rainmeter/Skins/FlipFlop/FlipFlop.ini": create_rainmeter_skin(
            build_name=build_name,
            portal_url=portal_url,
        ).encode("utf-8"),
        "05-workshop-setup/README.md": _text_bytes(
            "# Workshop setup\n\n"
            "Copy this folder to the branded workshop USB and run `run-getting-ready.ps1` from an elevated PowerShell window while signed in to the built-in Audit Mode Administrator account on the new Windows 11 Pro installation. It requires an operator to type RUN before it installs selected machine-scope applications, installs Rainmeter machine-wide, activates the FlipFlop desktop skin and creates the build's portal shortcut. Any selected applications whose publisher installer is user-scoped are copied into ProgramData and scheduled to install into the signing-in Windows profile at first sign-in. The setup writes a local log and machine-readable report. Rainmeter is installed from its WinGet source; the generated skin displays this build name and portal link.\n\n"
            "Windows installation is launched separately from the admin-approved USB package in WinPE. The generated installer only erases the disk whose model and serial match the pre-recorded Dispatch Centre target, after two typed confirmations. The master workshop script does not repartition disks, create a user account, flash BIOS or firmware, configure RGB hardware, or install paid AI services. When the sold order has an assigned Windows Pro licence, package approval marks that an activation helper is required but never stores the key in the ZIP. After downloading the reviewed ZIP, use Dispatch Centre's separate, explicitly confirmed private-helper download and place `install-windows-license.ps1` beside the master script on the branded USB. The master script requires a separate `APPLY-LICENSE` confirmation, installs the key through Windows Software Licensing WMI without putting it on a command line, and removes the helper from the USB folder after success. Keep that helper private. The key is not sent to the LLM, stored in the ZIP, or exposed through customer portal documents. Activation still needs operator verification. After Windows is installed, run `collect-windows-deployment-evidence.ps1` in an elevated PowerShell session. It checks Windows 11 Pro/en-GB and writes the actual system drive model and serial to `windows-deployment-evidence.json`; it does not change the computer. Import that report in Dispatch Centre and confirm that its serial matches the drive recorded before installation. After completing all workshop actions, `prepare-customer-oobe.ps1` requires the built-in Audit Mode Administrator, a complete master setup report, and a separate typed confirmation before Microsoft Sysprep shuts down to customer OOBE. Review all reports and the dispatch checklist before handover."
        ),
        "06-drivers-and-firmware/review-required.json": _json_bytes(manifest.get("driver_and_firmware_review") or []),
        "07-component-manuals/research-review-index.json": _json_bytes({"matches": manual_matches, "note": "These LLM research suggestions are not cached files. Verify the exact model and source before downloading or relying on them."}),
        "08-upgrade-path.html": _text_bytes(_upgrade_html(build_name, manifest.get("upgrade_path") or {})),
    }
    if customer_profile_package_ids:
        files["05-workshop-setup/install-customer-profile-apps.ps1"] = create_customer_profile_software_install_script(
            customer_profile_package_ids
        ).encode("utf-8-sig")
    paid_ai_runbook = _paid_ai_setup_runbook(source_inputs.get("purchased_ai_services"))
    if paid_ai_runbook:
        files["05-workshop-setup/AI/paid-ai-setup-runbook.md"] = _text_bytes(paid_ai_runbook)

    cached_manual_index = []
    for manual in cached_component_manuals or []:
        content = manual.get("content")
        if not isinstance(content, bytes) or not content.startswith(b"%PDF-"):
            raise GettingReadyPackageError("A matched cached manual is missing or is not a PDF")
        if sha256(content).hexdigest() != manual.get("sha256"):
            raise GettingReadyPackageError("A matched cached manual failed its SHA-256 check")
        safe_name = re.sub(r"[^a-z0-9]+", "-", str(manual.get("component_name") or "component").casefold()).strip("-")[:80] or "component"
        archive_name = f"07-component-manuals/{int(manual['id'])}-{safe_name}.pdf"
        files[archive_name] = content
        cached_manual_index.append({
            "component_key": manual.get("component_key"),
            "component_name": manual.get("component_name"),
            "source_url": manual.get("source_url"),
            "filename": archive_name.rsplit("/", 1)[-1],
            "sha256": manual.get("sha256"),
        })
    files["07-component-manuals/cached-manual-index.json"] = _json_bytes({
        "manuals": cached_manual_index,
        "note": "Files were uploaded to the administrator-curated cache after confirmation of the official manufacturer source and included only for exact component model-key matches.",
    })
    if portal_leaflet_path is not None:
        try:
            leaflet_path = portal_leaflet_path.resolve(strict=True)
        except OSError as error:
            raise GettingReadyPackageError("The issued guest portal leaflet is missing") from error
        if PACKAGE_ROOT.resolve() not in leaflet_path.parents or leaflet_path.suffix.lower() != ".pdf":
            raise GettingReadyPackageError("The issued guest portal leaflet path is invalid")
        files["10-personalized-portal-leaflet.pdf"] = leaflet_path.read_bytes()
    elif portal_url:
        files["10-personalized-portal-leaflet.pdf"] = _portal_leaflet_pdf(
            build_name=build_name,
            access_url=portal_url,
            claim_code=False,
        )
    portal_manifest = {
        "schema_version": "1.0",
        "package_version": version,
        "build_id": build_id,
        "build_name": build_name,
        "generated_at": generated_at,
        "portal_url": portal_url,
        "review_status": "admin_approved",
        "software_package_ids": selected,
        "documents": sorted(files),
        "warnings": manifest.get("warnings") or [],
    }
    files["portal-manifest.json"] = _json_bytes(portal_manifest)
    checksums = {name: sha256(content).hexdigest() for name, content in sorted(files.items())}
    files["CHECKSUMS.sha256"] = _text_bytes("\n".join(f"{digest}  {name}" for name, digest in checksums.items()))

    build_dir = (PACKAGE_ROOT / str(build_id)).resolve()
    if PACKAGE_ROOT.resolve() not in build_dir.parents:
        raise GettingReadyPackageError("Invalid package path")
    build_dir.mkdir(parents=True, exist_ok=True)
    customer_documents = sorted(name for name in files if is_customer_package_document_name(name))
    customer_files = {name: files[name] for name in customer_documents}
    customer_checksums = {name: sha256(content).hexdigest() for name, content in sorted(customer_files.items())}
    customer_files["CHECKSUMS.sha256"] = _text_bytes(
        "\n".join(f"{digest}  {name}" for name, digest in customer_checksums.items())
    )

    customer_filename = f"flipflop-build-{build_id}-customer-documents-v{version}.zip"
    customer_destination = (build_dir / customer_filename).resolve()
    if build_dir not in customer_destination.parents:
        raise GettingReadyPackageError("Invalid customer package path")
    with ZipFile(customer_destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(customer_files.items()):
            archive.writestr(name, content)
    customer_bytes = customer_destination.read_bytes()

    workshop_filename = f"flipflop-build-{build_id}-workshop-usb-v{version}.zip"
    workshop_destination = (build_dir / workshop_filename).resolve()
    if build_dir not in workshop_destination.parents:
        raise GettingReadyPackageError("Invalid workshop package path")
    with ZipFile(workshop_destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    workshop_bytes = workshop_destination.read_bytes()
    return {
        "filename": customer_filename,
        "storage_key": f"{build_id}/{customer_filename}",
        "size_bytes": len(customer_bytes),
        "sha256": sha256(customer_bytes).hexdigest(),
        "version": version,
        "generated_at": generated_at,
        "documents": customer_documents,
        "customer_safe": True,
        "workshop_filename": workshop_filename,
        "workshop_storage_key": f"{build_id}/{workshop_filename}",
        "workshop_size_bytes": len(workshop_bytes),
        "workshop_sha256": sha256(workshop_bytes).hexdigest(),
        "workshop_documents": sorted(files),
    }


def package_path(storage_key: str) -> Path:
    path = (PACKAGE_ROOT / storage_key).resolve()
    if PACKAGE_ROOT.resolve() not in path.parents:
        raise GettingReadyPackageError("Invalid package path")
    return path


def create_portal_leaflet(*, build_id: int, build_name: str, grant_id: int, claim_url: str) -> dict[str, Any]:
    """Create a private, print-ready A5 claim leaflet after admin issuance."""
    build_dir = (PACKAGE_ROOT / str(build_id)).resolve()
    if PACKAGE_ROOT.resolve() not in build_dir.parents:
        raise GettingReadyPackageError("Invalid leaflet path")
    build_dir.mkdir(parents=True, exist_ok=True)
    filename = f"flipflop-build-{build_id}-portal-leaflet-{grant_id}.pdf"
    destination = (build_dir / filename).resolve()
    content = _portal_leaflet_pdf(build_name=build_name, access_url=claim_url, claim_code=True)
    destination.write_bytes(content)
    return {
        "filename": filename,
        "storage_key": f"{build_id}/{filename}",
        "size_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
        "grant_id": grant_id,
    }
