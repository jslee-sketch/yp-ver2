# tools/check_guardrail_matrix_golden.ps1
$ErrorActionPreference = "Stop"

# ---- Defaults (override by editing here if needed) ----
$BaseUrl = "http://127.0.0.1:9000"
$DealId  = 1
$OfferId = 2
$UserId  = 1
$Role    = "BUYER"

function Get-DealGuardrailFromPreview($dealPreview) {
  $g = $null
  try { $g = $dealPreview.pack.pricing.guardrail } catch {}
  if (-not $g) { try { $g = $dealPreview.pack.guardrail } catch {} }
  return $g
}

function Get-StableDealSnapshot($dealPreview) {
  $g = Get-DealGuardrailFromPreview $dealPreview
  $deal = $dealPreview.pack.deal
  return [ordered]@{
    entity = "deal"
    id     = [int]$dealPreview.id
    deal   = [ordered]@{
      id           = [int]$deal.id
      status       = [string]$deal.status
      target_price = $deal.target_price
      qty_target   = $deal.qty_target
    }
    guardrail = if ($g) {
      [ordered]@{
        level        = [string]$g.level
        reason_codes = @($g.reason_codes)
        badge        = [string]$g.badge
        short_title  = [string]$g.short_title
        short_body   = [string]$g.short_body
      }
    } else { $null }
  }
}

function Get-StableOfferSnapshot($offerPreview) {
  $offer = $offerPreview.pack.offer
  $deal  = $offerPreview.pack.deal
  $pr    = $offerPreview.pack.pricing

  return [ordered]@{
    entity = "offer"
    id     = [int]$offerPreview.id
    offer  = [ordered]@{
      id           = [int]$offer.id
      deal_id      = [int]$offer.deal_id
      seller_id    = [int]$offer.seller_id
      price        = $offer.price
      shipping_fee = $offer.shipping_fee
      status       = [string]$offer.status
    }
    deal   = [ordered]@{
      id           = [int]$deal.id
      status       = [string]$deal.status
      target_price = $deal.target_price
      qty_target   = $deal.qty_target
    }
    pricing = if ($pr) {
      [ordered]@{
        reference = [ordered]@{
          p_base   = $pr.reference.p_base
          p_target = $pr.reference.p_target
          p_anchor = $pr.reference.p_anchor
        }
        groupbuy = [ordered]@{
          p_group       = $pr.groupbuy.p_group
          q_room        = $pr.groupbuy.q_room
          q_offer       = $pr.groupbuy.q_offer
          offer_cap_qty = $pr.groupbuy.offer_cap_qty
        }
        offer_evaluation = [ordered]@{
          seller_offer_price = $pr.offer_evaluation.seller_offer_price
          expected_price_under_offer_conditions = $pr.offer_evaluation.expected_price_under_offer_conditions
          phrases = [ordered]@{
            vs_expected           = $pr.offer_evaluation.phrases.vs_expected
            vs_groupbuy_offer_cap = $pr.offer_evaluation.phrases.vs_groupbuy_offer_cap
          }
        }
        guardrail = if ($pr.guardrail) {
          [ordered]@{
            level        = [string]$pr.guardrail.level
            reason_codes = @($pr.guardrail.reason_codes)
            badge        = [string]$pr.guardrail.badge
            short_title  = [string]$pr.guardrail.short_title
            short_body   = [string]$pr.guardrail.short_body
          }
        } else { $null }
      }
    } else { $null }
  }
}

function Call-FullflowReset() {
  Invoke-RestMethod -Method Post -Uri "$BaseUrl/admin/simulate/fullflow?reset_db=true" | Out-Null
}
function Call-SetTarget([double]$target) {
  Invoke-RestMethod -Method Patch -Uri "$BaseUrl/deals/$DealId/target" -ContentType "application/json" `
    -Body (@{ target_price = $target } | ConvertTo-Json) | Out-Null
}
function Call-InjectAnchor([double]$anchor, [int]$evidence, [double]$conf) {
  Invoke-RestMethod -Method Post -Uri "$BaseUrl/admin/anchor/deal/$DealId" -ContentType "application/json" `
    -Body (@{ anchor_price = $anchor; evidence_score = $evidence; anchor_confidence = $conf } | ConvertTo-Json) | Out-Null
}
function Call-PreviewDeal() {
  return Invoke-RestMethod -Method Get -Uri "$BaseUrl/preview/deal/${DealId}?user_id=${UserId}&role=${Role}"
}
function Call-PreviewOffer() {
  return Invoke-RestMethod -Method Get -Uri "$BaseUrl/preview/offer/${OfferId}?user_id=${UserId}&role=${Role}"
}

function Load-JsonFile([string]$path) {
  if (-not (Test-Path $path)) { throw "Missing golden file: $path" }
  $raw = Get-Content -Raw -Encoding utf8 $path
  return $raw | ConvertFrom-Json
}

function Canon([object]$obj) {
  return ($obj | ConvertTo-Json -Depth 20 -Compress)
}

$Cases = @(
  [ordered]@{ name="A_anchor_missing_target_valid_evidence0"; target=777; inject_anchor=$false; anchor=1000; evidence=0;  conf=1.0 },
  [ordered]@{ name="B_target_invalid0_even_with_anchor";      target=0;   inject_anchor=$true;  anchor=1000; evidence=80; conf=1.0 },
  [ordered]@{ name="C_huge_gap_low_evidence_block";           target=1;   inject_anchor=$true;  anchor=1000; evidence=0;  conf=1.0 },
  [ordered]@{ name="D_moderate_gap_high_evidence_relax_allow";target=777; inject_anchor=$true;  anchor=1000; evidence=80; conf=1.0 }
)

$MatrixDir = Join-Path $PSScriptRoot "golden\matrix"
Write-Host "=== Guardrail Matrix Golden Check ==="
Write-Host "GoldenDir=$MatrixDir"

$fail = $false

foreach ($c in $Cases) {
  $name = $c.name
  Write-Host ""
  Write-Host "--- CASE $name ---"

  $goldDealPath  = Join-Path $MatrixDir ("{0}.deal.json" -f $name)
  $goldOfferPath = Join-Path $MatrixDir ("{0}.offer.json" -f $name)

  $goldDeal  = Load-JsonFile $goldDealPath
  $goldOffer = Load-JsonFile $goldOfferPath

  Call-FullflowReset
  Call-SetTarget ([double]$c.target)
  if ($c.inject_anchor) { Call-InjectAnchor ([double]$c.anchor) ([int]$c.evidence) ([double]$c.conf) }

  $dealPrev  = Call-PreviewDeal
  $offerPrev = Call-PreviewOffer

  $nowDeal  = Get-StableDealSnapshot $dealPrev
  $nowOffer = Get-StableOfferSnapshot $offerPrev

  if ((Canon $goldDeal) -ne (Canon $nowDeal)) { Write-Host "FAIL: deal differs";  $fail = $true } else { Write-Host "PASS: deal matches" }
  if ((Canon $goldOffer) -ne (Canon $nowOffer)) { Write-Host "FAIL: offer differs"; $fail = $true } else { Write-Host "PASS: offer matches" }
}

Write-Host ""
if ($fail) { Write-Host "❌ MATRIX GOLDEN CHECK FAILED"; exit 1 }
Write-Host "✅ MATRIX GOLDEN CHECK PASSED"
exit 0