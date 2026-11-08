# Exercise only the cleanup function, with all process operations mocked.
$script:stoppedIds = @()
$ollama = 'C:\Ollama\ollama.exe'
$expected = 'C:\Ollama\lib\ollama\llama-server.exe'
function Get-CimInstance { param($Filter) @(
    [pscustomobject]@{ProcessId=1;ParentProcessId=10;ExecutablePath=$expected},
    [pscustomobject]@{ProcessId=2;ParentProcessId=40;ExecutablePath=$expected},
    [pscustomobject]@{ProcessId=3;ParentProcessId=30;ExecutablePath='C:\Other\llama-server.exe'},
    [pscustomobject]@{ProcessId=4;ParentProcessId=50;ExecutablePath=$null}
) }
function Get-Process { [CmdletBinding()]param([int]$Id) if($Id -eq 40){[pscustomobject]@{Id=40}} }
function Stop-Process { [CmdletBinding()]param([int]$Id,[switch]$Force) $script:stoppedIds += $Id }
$tokens=$null
$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'start-prometheus-services.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Startup script failed to parse'}
$cleanup=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Stop-OrphanedOllamaRunners'},$true)
Invoke-Expression $cleanup.Extent.Text
Stop-OrphanedOllamaRunners
if($stoppedIds.Count -ne 1 -or $stoppedIds[0] -ne 1){throw 'Cleanup stopped an active, unrelated or unreadable process'}
'{"orphan_cleanup_checks_passed":4,"real_processes_stopped":0}'
