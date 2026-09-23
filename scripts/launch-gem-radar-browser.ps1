param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dev', 'live')]
    [string]$Target,
    [string]$ExtensionRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '..\FlipFlopXtension')
)

$ErrorActionPreference = 'Stop'
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
