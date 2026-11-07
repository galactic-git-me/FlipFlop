$tokens=$null
$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot '../../scripts/start-all-servers.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Launcher failed to parse'}
$function=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-PriorityGatewayInstanceCount'},$true)
Invoke-Expression $function.Extent.Text
$pair=@([pscustomobject]@{ProcessId=1;ParentProcessId=99},[pscustomobject]@{ProcessId=2;ParentProcessId=1})
if((Get-PriorityGatewayInstanceCount $pair) -ne 1){throw 'A venv launcher pair was mistaken for two services'}
$two=$pair+@([pscustomobject]@{ProcessId=3;ParentProcessId=99},[pscustomobject]@{ProcessId=4;ParentProcessId=3})
if((Get-PriorityGatewayInstanceCount $two) -ne 2){throw 'Duplicate services were not detected'}
if((Get-PriorityGatewayInstanceCount @()) -ne 0){throw 'Missing service was not detected'}
if((Get-PriorityGatewayInstanceCount @($pair[0])) -ne 1){throw 'A direct interpreter was not detected'}
'{"gateway_instance_checks_passed":4,"services_restarted":0}'
