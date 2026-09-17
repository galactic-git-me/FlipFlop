$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot "flipflop-api\.env.local"
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Local API environment file not found: $envPath"
}

# Only non-secret production eBay configuration is eligible for this sync.
# OAuth access/refresh tokens are deliberately excluded: the live seller
# connection is encrypted and stored in the production AppSettings row after
# completing OAuth in the production admin UI.
$allowedKeys = @(
    "EBAY_ENVIRONMENT",
    "EBAY_APP_ID",
    "EBAY_CLIENT_SECRET",
    "EBAY_RU_NAME",
    "EBAY_PRODUCTION_PAYMENT_POLICY_ID",
    "EBAY_PRODUCTION_RETURN_POLICY_ID",
    "EBAY_PRODUCTION_FULFILLMENT_POLICY_ID"
)
$requiredKeys = @(
    "EBAY_APP_ID",
    "EBAY_CLIENT_SECRET",
    "EBAY_PRODUCTION_PAYMENT_POLICY_ID",
    "EBAY_PRODUCTION_RETURN_POLICY_ID",
    "EBAY_PRODUCTION_FULFILLMENT_POLICY_ID"
)

function Test-PresentEnvValue([string]$value) {
    $trimmed = $value.Trim()
    return $trimmed -and $trimmed -notin @("''", '""')
}

$sourceLines = Get-Content -LiteralPath $envPath
$selectedLines = New-Object System.Collections.Generic.List[string]
$presentKeys = New-Object System.Collections.Generic.HashSet[string]
foreach ($line in $sourceLines) {
    if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') { continue }
    $key = $Matches[1]
    if ($key -notin $allowedKeys) { continue }
    $value = $line.Substring($line.IndexOf('=') + 1)
    if (-not (Test-PresentEnvValue $value)) { continue }
    [void]$presentKeys.Add($key)
    [void]$selectedLines.Add($line)
}

$missing = @($requiredKeys | Where-Object { -not $presentKeys.Contains($_) })
if ($missing.Count -gt 0) {
    throw "Cannot sync production eBay settings; local .env.local is missing values for: $($missing -join ', ')"
}

$payload = ($selectedLines -join "`n") + "`n"
$remotePython = @'
import datetime
import os
import re
import shutil
import sys
from pathlib import Path

path = Path('/home/mac/CODING/FlipFlop-production/.env.local')
allowed = {
    'EBAY_ENVIRONMENT', 'EBAY_APP_ID', 'EBAY_CLIENT_SECRET', 'EBAY_RU_NAME',
    'EBAY_PRODUCTION_PAYMENT_POLICY_ID', 'EBAY_PRODUCTION_RETURN_POLICY_ID',
    'EBAY_PRODUCTION_FULFILLMENT_POLICY_ID',
}
required = {
    'EBAY_APP_ID', 'EBAY_CLIENT_SECRET',
    'EBAY_PRODUCTION_PAYMENT_POLICY_ID', 'EBAY_PRODUCTION_RETURN_POLICY_ID',
    'EBAY_PRODUCTION_FULFILLMENT_POLICY_ID',
}
incoming = {}
for raw in sys.stdin:
    line = raw.rstrip('\r\n')
    match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
    if match and match.group(1) in allowed:
        incoming[match.group(1)] = line
missing = sorted(required - incoming.keys())
if missing:
    raise SystemExit('Refusing production env sync; missing keys: ' + ','.join(missing))
if not path.exists():
    raise SystemExit('Production env file does not exist: ' + str(path))

stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup = path.with_name(path.name + '.bak-' + stamp)
shutil.copy2(path, backup)
existing = path.read_text(encoding='utf-8').splitlines(keepends=True)
seen = set()
updated = []
for line in existing:
    match = re.match(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=).*?(\r?\n)?$', line)
    key = match.group(2) if match else None
    if key in incoming:
        newline = '\r\n' if line.endswith('\r\n') else '\n'
        updated.append(incoming[key] + newline)
        seen.add(key)
    else:
        updated.append(line)
for key in sorted(incoming.keys() - seen):
    updated.append(incoming[key] + '\n')
temporary = path.with_name(path.name + '.sync-tmp')
temporary.write_text(''.join(updated), encoding='utf-8', newline='')
os.chmod(temporary, 0o600)
os.replace(temporary, path)
os.chmod(path, 0o600)
print('Production eBay environment updated: ' + ','.join(sorted(incoming)))
print('Previous environment backed up to: ' + str(backup))
'@
$encodedPython = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remotePython))
$remoteCommand = "python3 -c 'import base64,sys;exec(base64.b64decode(sys.argv[1]))' $encodedPython"
$payload | & ssh -o BatchMode=yes -o ConnectTimeout=15 andromeda $remoteCommand
if ($LASTEXITCODE -ne 0) {
    throw "Production eBay environment sync failed."
}

& ssh -o BatchMode=yes -o ConnectTimeout=15 andromeda "docker compose -f /home/mac/CODING/FlipFlop-production/deploy/andromeda-api.compose.yml up -d --no-deps --force-recreate api gemradar-worker"
if ($LASTEXITCODE -ne 0) {
    throw "Production API/worker restart failed after environment sync."
}

$healthCommand = 'for i in $(seq 1 30); do if curl --fail --silent --show-error --max-time 10 http://127.0.0.1:4311/health >/dev/null 2>&1; then curl --fail --silent --show-error --max-time 20 https://www.theflipflop.shop/api/ebay/oauth/callback >/dev/null && exit 0; fi; sleep 2; done; exit 1'
& ssh -o BatchMode=yes -o ConnectTimeout=15 andromeda $healthCommand
if ($LASTEXITCODE -ne 0) {
    throw "Production health or eBay callback check failed after environment sync."
}

Write-Host "[OK] Production eBay environment synced and services restarted." -ForegroundColor Green
