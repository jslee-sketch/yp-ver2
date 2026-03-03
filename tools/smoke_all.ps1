# tools/smoke_all.ps1
# Run: .\tools\smoke_all.ps1
# 목적: fullflow + guardrail + golden(단일/매트릭스)까지 원샷 스모크

param(
  [string]$BaseUrl = "http://127.0.0.1:9000"
)

$ErrorActionPreference = "Stop"

function Step($title) {
  Write-Host ""
  Write-Host ("=== {0} ===" -f $title)
}

function Run($cmd) {
  Write-Host ("-> {0}" -f $cmd)
  Invoke-Expression $cmd | Out-Host
}

try {
  Step "0) Reset DB + Fullflow"
  # -s는 curl.exe에서만 의미있지만, 어쨌든 조용히
  Run "curl.exe -s -X POST `"$BaseUrl/admin/simulate/fullflow?reset_db=true`" | Out-Null"

  Step "1) Smoke: Fullflow Guardrail"
  Run ".\tools\smoke_fullflow_guardrail.ps1"

  Step "2) Smoke: Guardrail Matrix (runtime assertions)"
  Run ".\tools\smoke_guardrail_matrix.ps1"

  Step "3) Golden: Single (stable fields)"
  Run ".\tools\gen_guardrail_golden.ps1"
  Run ".\tools\check_guardrail_golden.ps1"

  Step "4) Golden: Matrix (stable fields)"
  Run ".\tools\gen_guardrail_matrix_golden.ps1"
  Run ".\tools\check_guardrail_matrix_golden.ps1"

  Step "DONE"
  Write-Host "✅ ALL SMOKE + GOLDEN PASSED"
  exit 0
}
catch {
  Write-Host ""
  Write-Host "❌ FAILED"
  Write-Host $_
  exit 1
}