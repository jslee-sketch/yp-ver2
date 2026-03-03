$ErrorActionPreference = "Stop"

function Reset-DB { curl.exe -s -X POST "http://127.0.0.1:9000/admin/simulate/fullflow?reset_db=true" | Out-Null }
function Set-Target([double]$p) {
  Invoke-RestMethod -Method Patch `
    -Uri "http://127.0.0.1:9000/deals/1/target" `
    -ContentType "application/json" `
    -Body ("{`"target_price`": $p}") | Out-Null
}
function Set-Anchor([double]$anchor, [int]$evidence=80, [double]$conf=1.0) {
  Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:9000/admin/anchor/deal/1" `
    -ContentType "application/json" `
    -Body ("{`"anchor_price`": $anchor, `"evidence_score`": $evidence, `"anchor_confidence`": $conf}") | Out-Null
}
function Get-DealJson { return (curl.exe -s "http://127.0.0.1:9000/preview/deal/1?user_id=1&role=BUYER" | ConvertFrom-Json) }
function Get-OfferJson { return (curl.exe -s "http://127.0.0.1:9000/preview/offer/2?user_id=1&role=BUYER" | ConvertFrom-Json) }

Write-Host "=== Golden Snapshot Build ==="

Reset-DB
Set-Target 777
Set-Anchor 1000 80 1.0

$deal = Get-DealJson
$offer = Get-OfferJson

# 비교에 민감한 시간/latency 제거 (항상 바뀜)
$deal.times = $null
$deal.latency_ms = $null
$offer.times = $null
$offer.latency_ms = $null

# guardrail이 ALLOW면 payload 비는 정책이라, 확인용으로 pricing/guardrail만 남기고 줄이는 것도 가능
# 일단은 전체 pack 저장(디버깅에 더 좋음)

$outDir = "tools\golden"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$deal | ConvertTo-Json -Depth 50 | Out-File -Encoding utf8 "$outDir\deal_preview.json"
$offer | ConvertTo-Json -Depth 50 | Out-File -Encoding utf8 "$outDir\offer_preview.json"

Write-Host "Wrote:"
Write-Host " - $outDir\deal_preview.json"
Write-Host " - $outDir\offer_preview.json"
Write-Host "DONE"