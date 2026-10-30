$ErrorActionPreference = 'Stop'
$workerState = Join-Path $env:LOCALAPPDATA 'FlipFlop\BrowserWorker'
New-Item -ItemType Directory -Path $workerState -Force | Out-Null
# Bitwarden prompts locally; neither the password nor the session goes to chat.
$vaultSession = (& bw unlock --raw)
if ($LASTEXITCODE -ne 0 -or -not $vaultSession) { throw 'Bitwarden CLI unlock did not complete.' }
ConvertTo-SecureString -String $vaultSession.Trim() -AsPlainText -Force |
    Export-Clixml -LiteralPath (Join-Path $workerState 'vault-session.xml')
$vaultSession = $null
Write-Output 'Vault session saved with Windows user encryption.'
if (Get-ScheduledTask -TaskName 'FlipFlop Codex Browser Listings' -ErrorAction SilentlyContinue) {
    Start-ScheduledTask -TaskName 'FlipFlop Codex Browser Listings'
}
