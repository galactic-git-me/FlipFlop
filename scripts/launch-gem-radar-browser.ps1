param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dev', 'live')]
    [string]$Target,
    [string]$ExtensionRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '..\FlipFlopXtension')
)

$ErrorActionPreference = 'Stop'

function Test-DevApi {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:4311/health' -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if ($Target -eq 'dev' -and -not (Test-DevApi)) {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $backendRoot = Join-Path $projectRoot 'flipflop-api'
    $python = Join-Path $backendRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Development Python environment not found at $python."
    }

    $env:FLIPFLOP_RUNTIME_ENV = 'development'
    $env:EBAY_ENVIRONMENT = 'production'
    $env:EBAY_LISTING_ENVIRONMENT = 'sandbox'
    $env:AMAZON_SP_API_ENVIRONMENT = 'production'
    $env:AMAZON_SP_API_ENDPOINT = 'https://sellingpartnerapi-eu.amazon.com'
    $env:ADMIN_FRONTEND_URL = 'http://localhost:4312'
    $env:FRONTEND_URL = 'http://localhost:4313'

    Start-Process -FilePath $python `
        -ArgumentList @('run_dev.py', '--host', '127.0.0.1', '--port', '4311') `
        -WorkingDirectory $backendRoot `
        -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline -and -not (Test-DevApi)) {
        Start-Sleep -Seconds 1
    }
    if (-not (Test-DevApi)) {
        throw 'Development API did not become healthy on 127.0.0.1:4311.'
    }
}

$chromeCandidates = @(
    (Join-Path ${env:ProgramFiles} 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:LOCALAPPDATA} 'Google\Chrome\Application\chrome.exe')
)
$chrome = $chromeCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $chrome) { throw 'Google Chrome was not found.' }

$extensionPath = [IO.Path]::GetFullPath((Join-Path $ExtensionRoot "dist\$Target"))
if (-not (Test-Path -LiteralPath (Join-Path $extensionPath 'manifest.json'))) {
    throw "Built $Target extension not found at $extensionPath. Run npm run build:$Target first."
}

$profileRoot = Join-Path $env:LOCALAPPDATA "FlipFlop\gem-radar-chrome\$Target"
New-Item -ItemType Directory -Force -Path $profileRoot | Out-Null

$arguments = @(
    "--user-data-dir=$profileRoot",
    "--load-extension=$extensionPath",
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-session-crashed-bubble',
    '--start-minimized',
    'about:blank'
)
Start-Process -FilePath $chrome -ArgumentList $arguments
