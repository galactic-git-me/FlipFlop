$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ollama = (Get-Command ollama.exe -ErrorAction Stop).Source
$python = (Get-Command python.exe -ErrorAction Stop).Source

# The Ollama desktop app otherwise claims the public 11434 port. The gateway
# owns that port, so run Ollama's server privately behind it instead.
Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$env:OLLAMA_HOST = '127.0.0.1:11433'
Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
Start-Sleep -Seconds 2

if (-not (Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $python `
        -ArgumentList 'services/ollama-priority-gateway/server.py' `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden
}
