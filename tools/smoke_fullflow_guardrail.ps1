$ErrorActionPreference = "Stop"

function Assert($condition, $message) {
    if (-not $condition) {
        Write-Host "❌ FAIL: $message" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "✅ PASS: $message" -ForegroundColor Green
    }
}

Write-Host "`n=== 0) Reset DB ==="
curl.exe -s -X POST "http://127.0.0.1:9000/admin/simulate/fullflow?reset_db=true" | Out-Null

Write-Host "`n=== 1) Target Update (S2) ==="
Invoke-RestMethod -Method Patch `
  -Uri "http://127.0.0.1:9000/deals/1/target" `
  -ContentType "application/json" `
  -Body '{"target_price": 777}' | Out-Null

Write-Host "`n=== 2) Anchor Inject (S3) ==="
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:9000/admin/anchor/deal/1" `
  -ContentType "application/json" `
  -Body '{"anchor_price": 1000, "evidence_score": 80, "anchor_confidence": 1.0}' | Out-Null

Write-Host "`n=== 3) Deal Preview Check ==="
$deal = curl.exe -s "http://127.0.0.1:9000/preview/deal/1?user_id=1&role=BUYER" | ConvertFrom-Json

Assert ($deal.pack.pricing.guardrail.level -eq "ALLOW") "Deal guardrail level is ALLOW"
Assert ($deal.pack.pricing.guardrail.reason_codes.Count -gt 0) "Deal reason_codes exists"

Write-Host "`n=== 4) Offer Preview Check ==="
$offer = curl.exe -s "http://127.0.0.1:9000/preview/offer/2?user_id=1&role=BUYER" | ConvertFrom-Json

Assert ($offer.pack.pricing.reference.p_anchor -eq 1000) "Anchor propagated to offer pricing"
Assert ($offer.pack.pricing.groupbuy.p_group -gt 0) "Group price computed"
Assert ($offer.pack.pricing.offer_evaluation.expected_price_under_offer_conditions -gt 0) "Expected price computed"
Assert ($offer.pack.pricing.guardrail.level -eq "ALLOW") "Offer guardrail level is ALLOW"

Write-Host "`n🔥 ALL SMOKE TESTS PASSED"