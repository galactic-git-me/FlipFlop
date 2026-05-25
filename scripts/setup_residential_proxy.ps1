param(
  [string]$AndromedaHost = "andromeda-ts",
  [string]$AndromedaUser = "mac",
  [string]$RepoRoot = "/home/mac/CODING/FlipFlop",
  [int]$ProxyPort = 8888
)

$ErrorActionPreference = "Stop"

Write-Host "== FlipFlop Residential Proxy Setup ==" -ForegroundColor Cyan
Write-Host "Windows host user should be: mclar"
Write-Host "This script configures 3proxy locally and updates backend on $AndromedaUser@$AndromedaHost"

$baseDir = Join-Path $env:USERPROFILE "3proxy"
$zipPath = Join-Path $baseDir "3proxy.zip"
$cfgPath = Join-Path $baseDir "3proxy.cfg"
$logPath = Join-Path $baseDir "3proxy.log"
$zipUrl = "https://github.com/3proxy/3proxy/releases/download/0.9.4/3proxy-0.9.4-x64.zip"

New-Item -ItemType Directory -Force -Path $baseDir | Out-Null

Write-Host "Downloading 3proxy..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath

Write-Host "Extracting 3proxy..." -ForegroundColor Yellow
Expand-Archive $zipPath -DestinationPath $baseDir -Force

$proxyExe = Get-ChildItem -Path $baseDir -Recurse -Filter "3proxy.exe" | Select-Object -First 1
if (-not $proxyExe) {
  throw "3proxy.exe not found after extraction."
}

$cfg = @"
nserver 1.1.1.1
nserver 8.8.8.8
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
daemon
log $logPath D
auth none
allow *
proxy -p$ProxyPort
"@

Set-Content -Path $cfgPath -Value $cfg -Encoding ascii

Write-Host "Ensuring firewall rule for TCP/$ProxyPort..." -ForegroundColor Yellow
try {
  netsh advfirewall firewall add rule name="3proxy-$ProxyPort" dir=in action=allow protocol=TCP localport=$ProxyPort | Out-Null
} catch {
  Write-Host "Firewall rule may already exist; continuing." -ForegroundColor DarkYellow
}

Write-Host "Stopping old 3proxy processes if any..." -ForegroundColor Yellow
Get-Process -Name "3proxy" -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Starting 3proxy..." -ForegroundColor Yellow
Start-Process -FilePath $proxyExe.FullName -ArgumentList "`"$cfgPath`"" -WindowStyle Hidden
Start-Sleep -Seconds 2

Write-Host "Testing local proxy..." -ForegroundColor Yellow
& curl.exe -I -x "http://127.0.0.1:$ProxyPort" "https://www.ebay.co.uk" | Out-Host

Write-Host "Configuring backend on $AndromedaUser@$AndromedaHost..." -ForegroundColor Yellow
$remoteCmd = @"
set -e
sed -i 's|^EBAY_PROXY_URL=.*|EBAY_PROXY_URL=http://prometheus-ts:$ProxyPort|' $RepoRoot/pc-flipper-backend/.env.local
cd $RepoRoot
ATTACH_TMUX=0 ./start-dev-quiet-ports.sh
"@

ssh "$AndromedaUser@$AndromedaHost" $remoteCmd

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Proxy is running on this machine: http://prometheus-ts:$ProxyPort"
Write-Host "Backend has been pointed to that proxy and restarted on andromeda."
