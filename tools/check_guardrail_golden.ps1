. "$PSScriptRoot/_guardrail_snapshot.ps1"
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

# ✅ “변하면 안 되는” 핵심만 추출해서 비교(시간/문구/설명은 제외)
function StableDealSnapshot($j) {
  return [pscustomobject]@{
    ok = $j.ok
    entity = $j.entity
    id = $j.id
    target_price = $j.pack.deal.target_price
    guardrail_level = $j.pack.pricing.guardrail.level
    guardrail_reasons = @($j.pack.pricing.guardrail.reason_codes)
  }
}

function StableOfferSnapshot($j) {
  return [pscustomobject]@{
    ok = $j.ok
    entity = $j.entity
    id = $j.id
    deal_id = $j.pack.offer.deal_id
    offer_price = $j.pack.offer.price

    # pricing 핵심 숫자
    p_base   = $j.pack.pricing.reference.p_base
    p_target = $j.pack.pricing.reference.p_target
    p_anchor = $j.pack.pricing.reference.p_anchor
    p_group  = $j.pack.pricing.groupbuy.p_group
    q_room   = $j.pack.pricing.groupbuy.q_room
    q_offer  = $j.pack.pricing.groupbuy.q_offer
    offer_cap_qty = $j.pack.pricing.groupbuy.offer_cap_qty
    p_expected = $j.pack.pricing.offer_evaluation.expected_price_under_offer_conditions

    # guardrail 핵심
    guardrail_level = $j.pack.pricing.guardrail.level
    guardrail_reasons = @($j.pack.pricing.guardrail.reason_codes)
  }
}

function Canon($obj) {
  # ConvertTo-Json은 순서/공백 영향 줄이기 위해 depth 크게 + Compress
  return ($obj | ConvertTo-Json -Depth 30 -Compress)
}

$goldDir = "tools\golden"
$goldDealPath = "$goldDir\deal_preview.json"
$goldOfferPath = "$goldDir\offer_preview.json"

if (-not (Test-Path $goldDealPath)) { throw "Missing $goldDealPath. Run golden_guardrail_snapshot.ps1 first." }
if (-not (Test-Path $goldOfferPath)) { throw "Missing $goldOfferPath. Run golden_guardrail_snapshot.ps1 first." }

Write-Host "=== Golden Check (stable fields) ==="

# 1) golden 로드 -> stable snapshot화
$dealGoldRaw = Get-Content $goldDealPath -Raw | ConvertFrom-Json
$offerGoldRaw = Get-Content $goldOfferPath -Raw | ConvertFrom-Json
$dealGold = Canon (StableDealSnapshot $dealGoldRaw)
$offerGold = Canon (StableOfferSnapshot $offerGoldRaw)

# 2) 현재 실행 -> stable snapshot화
Reset-DB
Set-Target 777
Set-Anchor 1000 80 1.0

$dealNowRaw = Get-DealJson
$offerNowRaw = Get-OfferJson
$dealNow = Canon (StableDealSnapshot $dealNowRaw)
$offerNow = Canon (StableOfferSnapshot $offerNowRaw)

if ($dealNow -ne $dealGold) {
  Write-Host "FAIL: deal stable snapshot differs from golden" -ForegroundColor Red
  Write-Host "GOLD: $dealGold"
  Write-Host "NOW : $dealNow"
  exit 1
}

if ($offerNow -ne $offerGold) {
  Write-Host "FAIL: offer stable snapshot differs from golden" -ForegroundColor Red
  Write-Host "GOLD: $offerGold"
  Write-Host "NOW : $offerNow"
  exit 1
}

Write-Host "PASS: golden match (stable fields)" -ForegroundColor Green