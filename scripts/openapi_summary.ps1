param([string]$Base="http://127.0.0.1:9000")
$op = irm "$Base/openapi.json"
$p = @($op.paths.PSObject.Properties)
"Total paths: {0}" -f $p.Count
$p |
  ? { $_.Name -match '^(?:/admin/deposit|/reservations|/offers)' } |
  % { '{0} -> {1}' -f $_.Name, ($_.Value.PSObject.Properties.Name -join ', ') } |
  Set-Content .\openapi_summaries.txt -Encoding utf8
Get-Content .\openapi_summaries.txt