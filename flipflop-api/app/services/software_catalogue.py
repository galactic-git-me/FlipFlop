"""Reviewed WinGet identifiers offered in FlipFlop's getting-started flow.

These identifiers select current publisher packages; the service never
bundles installers. Estimated minutes are internal planning estimates for
avoided download/search and installer clicks, not measured guarantees.
"""

from pathlib import Path
from urllib.parse import urlsplit

from app.template_paths import dispatch_template_path

DISPATCH_TEMPLATE_ROOT = dispatch_template_path()

SOFTWARE_CATALOGUE = [
    {"package_id": "7zip.7zip", "name": "7-Zip", "category": "Utilities", "estimated_minutes_saved": 4, "license_note": "Free/open-source; check the publisher's terms for the current package.", "install_scope": "machine"},
    {"package_id": "Google.Chrome", "name": "Google Chrome", "category": "Browser", "estimated_minutes_saved": 4, "license_note": "Free to use; Google terms apply.", "install_scope": "machine"},
    {"package_id": "Mozilla.Firefox", "name": "Mozilla Firefox", "category": "Browser", "estimated_minutes_saved": 4, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "VideoLAN.VLC", "name": "VLC media player", "category": "Media", "estimated_minutes_saved": 4, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "ShareX.ShareX", "name": "ShareX", "category": "Capture", "estimated_minutes_saved": 5, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "Notepad++.Notepad++", "name": "Notepad++", "category": "Utilities", "estimated_minutes_saved": 5, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "Git.Git", "name": "Git", "category": "Developer", "estimated_minutes_saved": 6, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "Microsoft.VisualStudioCode", "name": "Visual Studio Code", "category": "Developer", "estimated_minutes_saved": 7, "license_note": "Free; Microsoft product terms apply.", "install_scope": "machine"},
    {"package_id": "Python.Python.3.12", "name": "Python 3.12", "category": "Developer", "estimated_minutes_saved": 7, "license_note": "Free/open-source; version availability may change.", "install_scope": "machine"},
    {"package_id": "GIMP.GIMP", "name": "GIMP", "category": "Creative", "estimated_minutes_saved": 6, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "BlenderFoundation.Blender", "name": "Blender", "category": "Creative / 3D", "estimated_minutes_saved": 8, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "OBSProject.OBSStudio", "name": "OBS Studio", "category": "Streaming / capture", "estimated_minutes_saved": 6, "license_note": "Free/open-source.", "install_scope": "machine"},
    {"package_id": "Discord.Discord", "name": "Discord", "category": "Communication", "estimated_minutes_saved": 4, "license_note": "Free tier available; Discord terms apply. Installed for the customer's Windows profile at first sign-in.", "install_scope": "customer_profile"},
    {"package_id": "Valve.Steam", "name": "Steam", "category": "Gaming", "estimated_minutes_saved": 5, "license_note": "Free client; game purchases and game licences are separate.", "install_scope": "machine"},
]

SOFTWARE_BY_ID = {item["package_id"]: item for item in SOFTWARE_CATALOGUE}
_EMPTY_SOFTWARE_SELECTION = "__flipflop_no_optional_apps__"

_PLAYBOOK_SOFTWARE_DEFAULTS = {
    "great-value gaming": (
        ["Valve.Steam", "Discord.Discord", "VideoLAN.VLC", "7zip.7zip"],
        "A practical gaming starter set for installing a game library, joining gaming communities, playing common media formats and handling downloaded files. Steam and Discord accounts are optional and remain under the customer's control.",
    ),
    "high-performance gaming": (
        ["Valve.Steam", "Discord.Discord", "OBSProject.OBSStudio", "VideoLAN.VLC", "7zip.7zip"],
        "A gaming starter set with optional streaming and capture tools, plus media playback and archive utilities. Steam and Discord accounts are optional and remain under the customer's control.",
    ),
    "student hybrid": (
        ["Mozilla.Firefox", "Notepad++.Notepad++", "VideoLAN.VLC", "7zip.7zip"],
        "A lightweight set for research, notes and code snippets, media playback and common downloaded archives. It avoids assuming a paid productivity licence or a specific school account.",
    ),
    "business & office": (
        ["Mozilla.Firefox", "Notepad++.Notepad++", "ShareX.ShareX", "7zip.7zip"],
        "A practical office starter set for web work, plain-text notes, screenshots and archive handling. It does not include a paid office suite or connect to a work account.",
    ),
    "content creation": (
        ["GIMP.GIMP", "BlenderFoundation.Blender", "OBSProject.OBSStudio", "VideoLAN.VLC", "7zip.7zip"],
        "A free creative starter set for image editing, 3D work, recording or streaming, media review and archive handling. Each application is optional and has its own publisher terms.",
    ),
    "ai workstation": (
        ["Microsoft.VisualStudioCode", "Git.Git", "Python.Python.3.12", "BlenderFoundation.Blender", "7zip.7zip"],
        "A local-AI and technical-work starter set for editing code, source control, Python workflows, 3D tasks and archives. These applications do not install an AI model or connect to a cloud AI account.",
    ),
    "software development": (
        ["Microsoft.VisualStudioCode", "Git.Git", "Python.Python.3.12", "7zip.7zip"],
        "A development starter set for editing code, source control, Python projects and archives. It does not install project dependencies or connect to a code-hosting account.",
    ),
    "family & home": (
        ["Mozilla.Firefox", "VideoLAN.VLC", "ShareX.ShareX", "7zip.7zip"],
        "A general home-computing set for web browsing, media playback, screenshots and downloaded archives. It avoids adding communication or gaming accounts without the customer's choice.",
    ),
}


def default_software_profile_for_playbook(playbook_name: str) -> dict[str, object]:
    """Return the reviewed starter profile for a canonical customer-use Playbook."""
    normalized = " ".join(str(playbook_name or "").strip().casefold().split())
    package_ids, rationale = _PLAYBOOK_SOFTWARE_DEFAULTS.get(
        normalized,
        (["7zip.7zip", "Mozilla.Firefox", "VideoLAN.VLC"],
         "A small general-purpose starter set for archive handling, web browsing and media playback. Customers can remove or add any available app before setup."),
    )
    return {
        "recommended_package_ids": validate_package_ids(package_ids),
        "rationale": rationale,
        "profile_source": "reviewed_default_v1",
    }


def effective_software_profile_for_playbook(playbook_name: str, authored_profile: dict | None = None) -> dict[str, object]:
    """Prefer an admin-authored profile, falling back to reviewed defaults."""
    profile = normalize_software_profile(authored_profile) if authored_profile else None
    return profile or default_software_profile_for_playbook(playbook_name)


def software_profile_for_curated_cell(
    build_id: str,
    playbook_name: str,
    base_profile: dict | None = None,
) -> dict[str, object]:
    """Resolve a curated matrix cell to a Playbook profile and cell context."""
    from app.services.curated_build_policy import definitions

    cell = next((item for item in definitions().get("builds", []) if item.get("id") == build_id), None)
    if cell is None:
        raise ValueError(f"Unknown curated Playbook cell: {build_id}")
    if str(cell.get("segment", "")).strip().casefold() != str(playbook_name or "").strip().casefold():
        raise ValueError("Curated Playbook cell does not match the selected customer type")

    profile = effective_software_profile_for_playbook(playbook_name, base_profile)
    tier = str(cell.get("tier") or "").strip()
    profile.update({
        "profile_source": "reviewed_curated_cell_default_v1",
        "curated_build_id": build_id,
        "budget_tier": tier,
        "rationale": f"{profile['rationale']} This recommendation is for the {tier} {playbook_name} Playbook cell.",
    })
    return profile


def estimate_saved_minutes(package_ids: list[str]) -> int:
    """Sum the catalogue's indicative per-app setup time estimates."""
    return sum(SOFTWARE_BY_ID[package_id]["estimated_minutes_saved"] for package_id in package_ids if package_id in SOFTWARE_BY_ID)


def validate_package_ids(package_ids: list[str]) -> list[str]:
    unknown = sorted(set(package_ids) - SOFTWARE_BY_ID.keys())
    if unknown:
        raise ValueError(f"Unsupported software package IDs: {', '.join(unknown)}")
    return list(dict.fromkeys(package_ids))


def serialize_customer_software_selection(package_ids: list[str]) -> str:
    """Encode a selection as non-empty Stripe metadata, including an empty list."""
    selected = validate_package_ids(package_ids)
    return ",".join(selected) if selected else _EMPTY_SOFTWARE_SELECTION


def deserialize_customer_software_selection(value: str | None) -> list[str] | None:
    """Decode saved metadata; None means no saved selection, sentinel means none."""
    if value is None:
        return None
    if value == _EMPTY_SOFTWARE_SELECTION:
        return []
    return validate_package_ids([item for item in value.split(",") if item])


def customer_software_selection_from_metadata(
    payment_metadata: dict,
    recommended_ids: list[str],
) -> list[str]:
    """Use saved choices when present, otherwise use the reviewed recommendation."""
    if "software_package_ids" not in payment_metadata:
        return validate_package_ids(recommended_ids)
    raw_value = payment_metadata.get("software_package_ids")
    saved_ids = deserialize_customer_software_selection(
        None if raw_value is None else str(raw_value)
    )
    return validate_package_ids(recommended_ids if saved_ids is None else saved_ids)


def initial_customer_software_selection(
    submitted_ids: list[str] | None,
    recommended_ids: list[str],
) -> list[str]:
    """Default only an omitted first choice; an explicit empty list means none."""
    return validate_package_ids(recommended_ids if submitted_ids is None else submitted_ids)


def updated_customer_software_selection(
    submitted_ids: list[str] | None,
    payment_metadata: dict,
    recommended_ids: list[str],
) -> list[str]:
    """Resolve a later edit while preserving saved choices when omitted."""
    if submitted_ids is not None:
        candidates = submitted_ids
    else:
        return customer_software_selection_from_metadata(payment_metadata, recommended_ids)
    return validate_package_ids(candidates)


def normalize_software_profile(profile: dict | None) -> dict | None:
    """Validate admin-authored recommendations against the installer allow-list."""
    if profile is None:
        return None
    if not isinstance(profile, dict):
        raise ValueError("Software profile must be an object")
    package_ids = profile.get("recommended_package_ids", [])
    if not isinstance(package_ids, list) or any(not isinstance(item, str) for item in package_ids):
        raise ValueError("recommended_package_ids must be a list of package ID strings")
    if len(package_ids) > len(SOFTWARE_CATALOGUE):
        raise ValueError(f"Choose no more than {len(SOFTWARE_CATALOGUE)} recommended applications")
    rationale = profile.get("rationale", "")
    if not isinstance(rationale, str) or len(rationale) > 2000:
        raise ValueError("Software recommendation rationale must be 2,000 characters or fewer")
    return {
        **profile,
        "recommended_package_ids": validate_package_ids(package_ids),
        "rationale": rationale.strip(),
    }


def create_software_install_script(package_ids: list[str]) -> str:
    """Render machine-scoped installs for the technician's Audit Mode session."""
    selected = validate_package_ids(package_ids)
    machine_scope_ids = [
        package_id for package_id in selected
        if SOFTWARE_BY_ID[package_id].get("install_scope", "machine") == "machine"
    ]
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$ProgressPreference = 'SilentlyContinue'",
        "$logPath = Join-Path $PSScriptRoot 'software-install.log'",
        "$failedPackages = @()",
        "Start-Transcript -Path $logPath -Append | Out-Null",
        "try {",
    ]
    if machine_scope_ids:
        lines.extend([
            "  if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {",
            "    throw 'Windows Package Manager (winget) is not available. Install or update App Installer, then rerun this script.'",
            "  }",
        ])
    for package_id in machine_scope_ids:
        lines.extend([
            f"  Write-Host 'Installing {SOFTWARE_BY_ID[package_id]['name']} ({package_id})'",
            f"  winget install --id '{package_id}' --exact --source winget --scope machine --accept-source-agreements --silent --disable-interactivity",
            f"  if ($LASTEXITCODE -ne 0) {{ $failedPackages += '{package_id}'; Write-Warning ('winget returned exit code ' + $LASTEXITCODE + ' for {package_id}') }}",
        ])
    lines.extend([
        "  if ($failedPackages.Count -gt 0) { throw ('Selected packages failed: ' + ($failedPackages -join ', ')) }",
        "  Write-Host 'Selected software setup finished. Review any package-specific licence or first-run steps.'",
        "} finally {",
        "  Stop-Transcript | Out-Null",
        "}",
    ])
    return "\r\n".join(lines) + "\r\n"


def create_customer_profile_software_install_script(package_ids: list[str]) -> str:
    """Render selected user-scoped installs to run inside the customer's profile."""
    selected = validate_package_ids(package_ids)
    customer_profile_ids = [
        package_id for package_id in selected
        if SOFTWARE_BY_ID[package_id].get("install_scope") == "customer_profile"
    ]
    if not customer_profile_ids:
        raise ValueError("No customer-profile software selections were provided")
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$ProgressPreference = 'SilentlyContinue'",
        "$identity = [Security.Principal.WindowsIdentity]::GetCurrent()",
        "if ($identity.User.Value.EndsWith('-500')) { exit 0 }",
        "$stateRoot = Join-Path $env:LOCALAPPDATA 'FlipFlop\\GettingReady'",
        "New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null",
        "$successMarker = Join-Path $stateRoot 'customer-apps-installed.json'",
        "if (Test-Path -LiteralPath $successMarker -PathType Leaf) { exit 0 }",
        "$logPath = Join-Path $stateRoot 'customer-app-install.log'",
        "$failedPackages = @()",
        "Start-Transcript -Path $logPath -Append | Out-Null",
        "try {",
        "  if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) { throw 'WinGet is not available for this customer profile. Connect to the internet and contact FlipFlop support for help.' }",
    ]
    for package_id in customer_profile_ids:
        lines.extend([
            f"  Write-Host 'Installing {SOFTWARE_BY_ID[package_id]['name']} ({package_id}) for this Windows profile'",
            f"  winget install --id '{package_id}' --exact --source winget --scope user --silent",
            f"  if ($LASTEXITCODE -ne 0) {{ $failedPackages += '{package_id}'; Write-Warning ('winget returned exit code ' + $LASTEXITCODE + ' for {package_id}') }}",
        ])
    lines.extend([
        "  if ($failedPackages.Count -gt 0) { throw ('Some selected apps need attention: ' + ($failedPackages -join ', ')) }",
        "  [ordered]@{ completed_at = (Get-Date).ToUniversalTime().ToString('o'); installed_package_ids = @(" + ", ".join(f"'{package_id}'" for package_id in customer_profile_ids) + ") } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $successMarker -Encoding UTF8",
        "  Write-Host 'Your selected profile apps are ready.'",
        "} catch {",
        "  Write-Error $_",
        "  Write-Host 'FlipFlop will retry this setup at your next sign-in. You can also contact support from your build portal.'",
        "  exit 1",
        "} finally {",
        "  Stop-Transcript | Out-Null",
        "}",
    ])
    return "\r\n".join(lines) + "\r\n"


def create_rainmeter_skin(*, build_name: str, portal_url: str | None) -> str:
    """Render the centrally maintained, per-build Rainmeter skin safely."""
    if portal_url:
        parsed = urlsplit(portal_url)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
            raise ValueError("Build portal URL must use HTTPS outside local development")
        if parsed.username or parsed.password or any(ch in portal_url for ch in '\"\r\n[]#'):
            raise ValueError("Build portal URL contains unsupported characters")
    safe_name = "".join(ch for ch in build_name if ch not in '\"\r\n[]{}#;')
    safe_name = safe_name.strip()[:100] or "Your FlipFlop build"
    template_path = DISPATCH_TEMPLATE_ROOT / "rainmeter" / "FlipFlop.ini"
    template = template_path.read_text(encoding="utf-8")
    portal_label = "OPEN YOUR PERSONAL BUILD PORTAL  →" if portal_url else "YOUR BUILD PORTAL WILL APPEAR HERE"
    portal_action = f'LeftMouseUpAction=["{portal_url}"]' if portal_url else ""
    return (
        template.replace("{{BUILD_NAME}}", safe_name)
        .replace("{{PORTAL_URL}}", portal_url or "")
        .replace("{{PORTAL_LABEL}}", portal_label)
        .replace("{{PORTAL_ACTION}}", portal_action)
    )


def create_rainmeter_install_script() -> str:
    """Install Rainmeter machine-wide and make the FlipFlop skin available to the customer profile."""
    return r'''$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$skinSource = Join-Path $scriptRoot 'Rainmeter\Skins\FlipFlop\FlipFlop.ini'
if (-not (Test-Path -LiteralPath $skinSource -PathType Leaf)) { throw 'The FlipFlop Rainmeter skin is missing.' }
if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) { throw 'WinGet is required to install Rainmeter.' }
winget install --id Rainmeter.Rainmeter --exact --source winget --scope machine --accept-source-agreements --accept-package-agreements --silent --disable-interactivity
if ($LASTEXITCODE -ne 0) { throw "Rainmeter installation failed with exit code $LASTEXITCODE." }
$rainmeter = @(
  (Join-Path $env:ProgramFiles 'Rainmeter\Rainmeter.exe'),
  (Join-Path ${env:ProgramFiles(x86)} 'Rainmeter\Rainmeter.exe')
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $rainmeter) { throw 'Rainmeter was installed but its executable could not be located.' }
$rainmeterDirectory = Split-Path -Parent $rainmeter
$skinDirectory = Join-Path $rainmeterDirectory 'Skins\FlipFlop'
New-Item -ItemType Directory -Path $skinDirectory -Force | Out-Null
Copy-Item -LiteralPath $skinSource -Destination (Join-Path $skinDirectory 'FlipFlop.ini') -Force
$commonStartup = [Environment]::GetFolderPath('CommonStartup')
if (-not $commonStartup -or -not (Test-Path -LiteralPath $commonStartup -PathType Container)) { throw 'The shared Windows Startup folder is unavailable.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $commonStartup 'FlipFlop Rainmeter Theme.lnk'))
$shortcut.TargetPath = $rainmeter
$shortcut.Arguments = '!ActivateConfig "FlipFlop" "FlipFlop.ini"'
$shortcut.WorkingDirectory = $rainmeterDirectory
$shortcut.Save()
$rainmeterProcess = Start-Process -FilePath $rainmeter -ArgumentList '!ActivateConfig "FlipFlop" "FlipFlop.ini"' -PassThru
Start-Sleep -Seconds 3
if (-not (Get-Process -Id $rainmeterProcess.Id -ErrorAction SilentlyContinue) -and -not (Get-Process -Name Rainmeter -ErrorAction SilentlyContinue)) {
  throw 'Rainmeter did not remain running after the FlipFlop skin activation command.'
}
Write-Host 'The FlipFlop skin is installed machine-wide and will activate for the next customer Windows profile.'
'''


def create_master_setup_script(
    *, build_name: str, portal_url: str | None, windows_license_key_present: bool = False,
    customer_profile_apps_selected: bool = False,
) -> str:
    """Create the reviewed post-install workshop entry point.

    This does not partition disks or install Windows. It can apply an assigned
    Windows Pro key only through a separately confirmed helper; activation
    verification, firmware, AI and RGB remain operator-reviewed steps.
    """
    def ps_literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    if portal_url and not (
        portal_url.startswith("https://") or portal_url.startswith("http://localhost")
    ):
        raise ValueError("Build portal URL must use HTTPS outside local development")

    build_name_literal = ps_literal(build_name)
    portal_url_literal = ps_literal(portal_url or "")
    license_expected_literal = "$true" if windows_license_key_present else "$false"
    customer_profile_apps_literal = "$true" if customer_profile_apps_selected else "$false"
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$ProgressPreference = 'SilentlyContinue'",
        f"$BuildName = {build_name_literal}",
        f"$PortalUrl = {portal_url_literal}",
        f"$WindowsLicenseKeyPresent = {license_expected_literal}",
        f"$CustomerProfileAppsSelected = {customer_profile_apps_literal}",
        "$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path",
        "$LogPath = Join-Path $ScriptRoot 'master-setup.log'",
        "Start-Transcript -Path $LogPath -Append | Out-Null",
        "try {",
        "  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()",
        "  $principal = [Security.Principal.WindowsPrincipal]::new($identity)",
        "  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {",
        "    throw 'Run this workshop script from an administrator PowerShell window.'",
        "  }",
        "  $windows = Get-CimInstance Win32_OperatingSystem",
        "  $edition = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').EditionID",
        "  if ($windows.Caption -notmatch 'Windows 11' -or $edition -ne 'Professional') {",
        "    throw 'This build must first have Windows 11 Pro installed by the reviewed workshop deployment process.'",
        "  }",
        "  if ((Get-WinSystemLocale).Name -ne 'en-GB') { throw 'This build must be configured for English (United Kingdom) before running workshop setup.' }",
        "  $confirmation = Read-Host ('Preparing ' + $BuildName + '. Type RUN to continue')",
        "  if ($confirmation -cne 'RUN') { throw 'Operator cancelled setup.' }",
        "  $licenseScript = Join-Path $ScriptRoot 'install-windows-license.ps1'",
        "  if ($WindowsLicenseKeyPresent -and -not (Test-Path -LiteralPath $licenseScript -PathType Leaf)) { throw 'This order has an assigned Windows Pro key. Download the private activation helper from Dispatch Centre and place it beside this script before running setup.' }",
        "  $appsScript = Join-Path $ScriptRoot 'install-selected-apps.ps1'",
        "  if (-not (Test-Path -LiteralPath $appsScript -PathType Leaf)) { throw 'The reviewed app installer is missing from this USB.' }",
        "  $process = Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File \"{0}\"' -f $appsScript) -Wait -PassThru -NoNewWindow",
        "  if ($process.ExitCode -ne 0) { throw ('The selected-app installer failed with exit code ' + $process.ExitCode) }",
        "  $customerAppsStatus = 'not_required'",
        "  if ($CustomerProfileAppsSelected) {",
        "    $customerAppsScript = Join-Path $ScriptRoot 'install-customer-profile-apps.ps1'",
        "    if (-not (Test-Path -LiteralPath $customerAppsScript -PathType Leaf)) { throw 'The customer-profile app installer is missing from this USB.' }",
        "    $customerAppsRoot = Join-Path $env:ProgramData 'FlipFlop\\GettingReady'",
        "    New-Item -ItemType Directory -Path $customerAppsRoot -Force | Out-Null",
        "    $customerAppsDestination = Join-Path $customerAppsRoot 'install-customer-profile-apps.ps1'",
        "    Copy-Item -LiteralPath $customerAppsScript -Destination $customerAppsDestination -Force",
        "    $commonStartup = [Environment]::GetFolderPath('CommonStartup')",
        "    if (-not $commonStartup -or -not (Test-Path -LiteralPath $commonStartup -PathType Container)) { throw 'The shared Windows Startup folder is unavailable for customer-profile apps.' }",
        "    $shell = New-Object -ComObject WScript.Shell",
        "    $profileAppsShortcut = $shell.CreateShortcut((Join-Path $commonStartup 'FlipFlop Customer Apps.lnk'))",
        "    $profileAppsShortcut.TargetPath = Join-Path $PSHOME 'powershell.exe'",
        "    $profileAppsShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File ' + [char]34 + $customerAppsDestination + [char]34",
        "    $profileAppsShortcut.WorkingDirectory = $customerAppsRoot",
        "    $profileAppsShortcut.Save()",
        "    $customerAppsStatus = 'scheduled_for_customer_first_sign_in'",
        "  }",
        "  $themeScript = Join-Path $ScriptRoot 'install-flipflop-theme.ps1'",
        "  if (-not (Test-Path -LiteralPath $themeScript -PathType Leaf)) { throw 'The FlipFlop theme installer is missing from this USB.' }",
        "  $themeProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File \"{0}\"' -f $themeScript) -Wait -PassThru -NoNewWindow",
        "  if ($themeProcess.ExitCode -ne 0) { throw ('The FlipFlop theme installer failed with exit code ' + $themeProcess.ExitCode) }",
        "  if ($PortalUrl) {",
        "    $safeBuildName = $BuildName",
        "    foreach ($character in [IO.Path]::GetInvalidFileNameChars()) { $safeBuildName = $safeBuildName.Replace($character, '_') }",
        "    $safeBuildName = $safeBuildName.Trim()",
        "    if (-not $safeBuildName) { $safeBuildName = 'FlipFlop build' }",
        "    if ($safeBuildName.Length -gt 100) { $safeBuildName = $safeBuildName.Substring(0, 100) }",
        "    $desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')",
        "    if (-not $desktop) { $desktop = [Environment]::GetFolderPath('DesktopDirectory') }",
        "    $shortcut = Join-Path $desktop ($safeBuildName + ' - FlipFlop.url')",
        "    Set-Content -LiteralPath $shortcut -Value ('[InternetShortcut]' + [Environment]::NewLine + 'URL=' + $PortalUrl) -Encoding ASCII",
        "  }",
        "  $evidenceScript = Join-Path $ScriptRoot 'collect-windows-deployment-evidence.ps1'",
        "  if (-not (Test-Path -LiteralPath $evidenceScript -PathType Leaf)) { throw 'The Windows deployment evidence collector is missing from this USB.' }",
        "  $evidenceProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File \"{0}\"' -f $evidenceScript) -Wait -PassThru -NoNewWindow",
        "  if ($evidenceProcess.ExitCode -ne 0) { throw ('Windows evidence collection failed with exit code ' + $evidenceProcess.ExitCode) }",
        "  $licenseStatus = 'not_included'",
        "  if ($WindowsLicenseKeyPresent) {",
        "    $licenseProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File \"{0}\"' -f $licenseScript) -Wait -PassThru -NoNewWindow",
        "    if ($licenseProcess.ExitCode -ne 0) { throw ('Windows licence installation failed with exit code ' + $licenseProcess.ExitCode) }",
        "    Remove-Item -LiteralPath $licenseScript -Force",
        "    $licenseStatus = 'key_installed_activation_check_required'",
        "  }",
        "  $report = [ordered]@{ build_name = $BuildName; completed_at = (Get-Date).ToUniversalTime().ToString('o'); software_installer = 'machine_scope_complete'; customer_profile_apps = $customerAppsStatus; rainmeter_theme = 'complete'; portal_shortcut = [bool]$PortalUrl; windows_deployment = 'evidence_collected_pending_admin_confirmation'; windows_evidence_report = 'windows-deployment-evidence.json'; windows_license = $licenseStatus; drivers_firmware = 'operator_review_required'; rgb_theme = 'operator_setup_required'; ai_services = 'operator_setup_required' }",
        "  $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $ScriptRoot 'master-setup-report.json') -Encoding UTF8",
        "  Write-Host 'Supported setup steps completed. Review master-setup-report.json and the remaining operator actions.'",
        "  exit 0",
        "} catch {",
        "  Write-Error $_",
        "  exit 1",
        "} finally {",
        "  Stop-Transcript | Out-Null",
        "}",
    ]
    return "\r\n".join(lines) + "\r\n"


def create_windows_deployment_evidence_script(*, build_id: int, build_name: str) -> str:
    """Generate a read-only collector for the installed OS and its system disk."""
    def ps_literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$BuildId = {int(build_id)}",
        f"$BuildName = {ps_literal(build_name)}",
        "$OutputPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'windows-deployment-evidence.json'",
        "$os = Get-CimInstance Win32_OperatingSystem",
        "$editionId = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').EditionID",
        "$locale = (Get-WinSystemLocale).Name",
        "if ($os.Caption -notmatch 'Windows 11' -or $editionId -ne 'Professional') { throw 'This is not an installed Windows 11 Pro system.' }",
        "if ($locale -ne 'en-GB') { throw 'The system locale is not en-GB.' }",
        "$systemDriveLetter = $env:SystemDrive.TrimEnd(':')",
        "$partitions = @(Get-Partition -DriveLetter $systemDriveLetter)",
        "$diskNumbers = @($partitions | Select-Object -ExpandProperty DiskNumber -Unique)",
        "if ($diskNumbers.Count -ne 1) { throw 'Could not resolve exactly one physical system disk.' }",
        "$disk = Get-Disk -Number ([int]$diskNumbers[0])",
        "$serial = ([string]$disk.SerialNumber).Trim()",
        "if (-not $serial) { throw 'The system disk does not expose a serial number; record this case for manual review.' }",
        "$report = [ordered]@{ schema_version = '1.0'; build_id = $BuildId; build_name = $BuildName; verified_at_utc = (Get-Date).ToUniversalTime().ToString('o'); edition = 'Windows 11 Pro'; edition_id = $editionId; locale = $locale; system_drive = $env:SystemDrive; target_drive_model = [string]$disk.FriendlyName; target_drive_serial = $serial; target_drive_size_bytes = [int64]$disk.Size; verification_method = 'FlipFlop read-only post-install verification'; target_drive_confirmed = $false }",
        "$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $OutputPath -Encoding UTF8",
        "Write-Host ('Saved read-only verification report: ' + $OutputPath)",
        "Write-Host ('Windows 11 Pro / en-GB on ' + $report.target_drive_model + ' / ' + $report.target_drive_serial)",
        "Write-Host 'In Dispatch Centre, compare this system-disk serial with the drive selected before installation and confirm that match.'",
    ]
    return "\r\n".join(lines) + "\r\n"


def create_windows_license_activation_script(license_key: str) -> str:
    """Create a non-logging, separately confirmed Windows key installer."""
    import re

    normalized_key = license_key.replace("-", "").replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z0-9]{25}", normalized_key):
        raise ValueError("Windows product key must contain exactly 25 alphanumeric characters")

    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$identity = [Security.Principal.WindowsIdentity]::GetCurrent()",
        "$principal = [Security.Principal.WindowsPrincipal]::new($identity)",
        "if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this licence step from an administrator PowerShell window.' }",
        "$confirmation = Read-Host 'This will install the assigned Windows 11 Pro licence key. Type APPLY-LICENSE to continue'",
        "if ($confirmation -cne 'APPLY-LICENSE') { throw 'Operator cancelled licence installation.' }",
        f"$productKey = '{normalized_key}'",
        "try {",
        "  $licenseService = Get-CimInstance -Namespace 'root/cimv2' -ClassName SoftwareLicensingService",
        "  $result = Invoke-CimMethod -InputObject $licenseService -MethodName InstallProductKey -Arguments @{ ProductKey = $productKey }",
        "  if ($null -eq $result -or [uint32]$result.ReturnValue -ne 0) { throw 'Windows did not accept the assigned product key.' }",
        "  Write-Host 'The assigned Windows product key was installed. Verify activation in Settings before dispatch.'",
        "} finally { $productKey = $null }",
    ]
    return "\r\n".join(lines) + "\r\n"
