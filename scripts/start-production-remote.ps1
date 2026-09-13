$ErrorActionPreference = "Stop"
$remoteScript = Join-Path $PSScriptRoot "start-production-remote.sh"
Get-Content -LiteralPath $remoteScript -Raw | & ssh -o BatchMode=yes -o ConnectTimeout=15 mac@andromeda-ts "tr -d '\r' | bash -s"
if ($LASTEXITCODE -ne 0) { throw "Andromeda production checks/startup failed. Local application servers were not started." }
