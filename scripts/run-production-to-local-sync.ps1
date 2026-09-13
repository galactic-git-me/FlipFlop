$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
& (Join-Path $repo 'flipflop-api\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'refresh-local-database.py')
if ($LASTEXITCODE -ne 0) { throw "Production-to-local refresh failed; see the database backup report." }
