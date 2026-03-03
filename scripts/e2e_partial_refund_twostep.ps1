# scripts/e2e_partial_refund_twostep.ps1
# - code change 없이: reserve(2) -> pay -> preview(qty=1) -> refund(qty=1) -> preview(qty=1) -> refund(qty=1 full) -> DB verify

$ErrorActionPreference = "Stop"

$BaseUrl = "http://127.0.0.1:9000"
$DbPath  = "C:\dev\yp-ver2\app\ypver2.db"

function Invoke-SqliteOneLine {
  param(
    [Parameter(Mandatory=$true)][string]$Sql
  )
  # python -c 한 줄로만 실행 (quoting 최소화)
  $code = "import sqlite3; con=sqlite3.connect(r'$DbPath'); cur=con.cursor(); cur.execute(r'''$Sql'''); r=cur.fetchall(); print(r); con.close()"
  & python -c $code
}

function Get-AvailableOffer {
  # sold+reserved < total 인 offer 중 1개 뽑기 + deal_id + price + counters
  $out = Invoke-SqliteOneLine @"
select id, deal_id, coalesce(price,0), total_available_qty, coalesce(sold_qty,0), coalesce(reserved_qty,0)
from offers
where total_available_qty > (coalesce(sold_qty,0) + coalesce(reserved_qty,0))
order by id asc
limit 1
"@
  if (-not $out) { throw "No available offer found (all sold out: total <= sold+reserved for all offers)" }
  # out example: [(1, 1, 1000.0, 10, 0, 0)]
  $m = [regex]::Match($out, "\[\((\d+),\s*(\d+),\s*([0-9\.]+),\s*(\d+),\s*(\d+),\s*(\d+)\)\]")
  if (-not $m.Success) { throw "Failed to parse offer row: $out" }

  return @{
    offer_id = [int]$m.Groups[1].Value
    deal_id  = [int]$m.Groups[2].Value
    price    = [int][double]$m.Groups[3].Value
    total    = [int]$m.Groups[4].Value
    sold     = [int]$m.Groups[5].Value
    reserved = [int]$m.Groups[6].Value
  }
}

function Get-OfferRow([int]$OfferId) {
  Invoke-SqliteOneLine "select id, deal_id, total_available_qty, coalesce(sold_qty,0), coalesce(reserved_qty,0), coalesce(price,0) from offers where id=$OfferId"
}

function Get-ResvRow([int]$Rid) {
  Invoke-SqliteOneLine "select id, status, qty, refunded_qty, refunded_amount_total, amount_goods, amount_shipping, amount_total, paid_at, cancelled_at from reservations where id=$Rid"
}

function Get-Payments([int]$Rid) {
  Invoke-SqliteOneLine "select id, reservation_id, paid_amount, pg_fee_amount, currency, paid_at from reservation_payments where reservation_id=$Rid order by id desc"
}

function Get-Settlements([int]$Rid) {
  Invoke-SqliteOneLine "select id, reservation_id, deal_id, offer_id, seller_id, buyer_id, buyer_paid_amount, pg_fee_amount, platform_commission_amount, seller_payout_amount, status from reservation_settlements where reservation_id=$Rid order by id desc"
}

# ------------------------------------------------------------
# 0) Offer 선택
# ------------------------------------------------------------
$pick = Get-AvailableOffer
$offerId = $pick.offer_id
$dealId  = $pick.deal_id
$unitPrice = $pick.price

"Using deal_id=$dealId offer_id=$offerId price=$unitPrice offer(total=$($pick.total) sold=$($pick.sold) reserved=$($pick.reserved))" | Write-Host
"OFFER_BEFORE= $(Get-OfferRow $offerId)" | Write-Host

if ($unitPrice -le 0) { throw "Invalid offer.price for offer_id=$offerId => $unitPrice" }

# ------------------------------------------------------------
# 1) 예약 생성 (qty=2)
# ------------------------------------------------------------
$body = @{ deal_id=$dealId; offer_id=$offerId; buyer_id=1; qty=2 } | ConvertTo-Json
$res  = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations" -ContentType "application/json" -Body $body
$rid = [int]$res.id
"RID=$rid" | Write-Host
"OFFER_AFTER_RESERVE= $(Get-OfferRow $offerId)" | Write-Host

# ------------------------------------------------------------
# 2) 결제 (paid_amount = unitPrice*2)
# ------------------------------------------------------------
$paidAmount = $unitPrice * 2
$payBody = @{ reservation_id=$rid; buyer_id=1; paid_amount=$paidAmount } | ConvertTo-Json
$paid = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations/pay" -ContentType "application/json" -Body $payBody
"PAID_OK rid=$rid paid_amount=$paidAmount status=$($paid.status) amount_total=$($paid.amount_total)" | Write-Host
"OFFER_AFTER_PAY= $(Get-OfferRow $offerId)" | Write-Host

# ------------------------------------------------------------
# 3) Preview (qty=1) — v3.6 preview endpoint 우선 사용
# ------------------------------------------------------------
$prevBody = @{ reservation_id=$rid; quantity_refund=1 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody
"PREVIEW_OK uri=$BaseUrl/v3_6/reservations/refund/preview (qty=1)" | Write-Host

# ------------------------------------------------------------
# 4) Refund step1 (qty=1)
# ------------------------------------------------------------
$refundBody1 = @{
  reservation_id = $rid
  quantity_refund = 1
  reason = "e2e partial refund step1"
  requested_by = "BUYER"
} | ConvertTo-Json
$r1 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $refundBody1
"REFUND1_OK rid=$rid status=$($r1.status) refunded_qty=$($r1.refunded_qty) refunded_amount_total=$($r1.refunded_amount_total) phase=$($r1.phase)" | Write-Host
"OFFER_AFTER_REFUND1= $(Get-OfferRow $offerId)" | Write-Host


# (CHECK) Settlement snapshot right after REFUND1
$st1 = python -c "import sqlite3,sys; rid=int(sys.argv[1]); db=r'C:\dev\yp-ver2\app\ypver2.db'; con=sqlite3.connect(db); cur=con.cursor(); cur.execute('select id,reservation_id,buyer_paid_amount,pg_fee_amount,platform_commission_amount,seller_payout_amount,status from reservation_settlements where reservation_id=? order by id desc limit 1',(rid,)); print(cur.fetchone()); con.close()" $rid
"SETTLEMENT_AFTER_REFUND1= $st1" | Write-Host


# ------------------------------------------------------------
# 5) Preview again (qty=1) — 잔여 1개 환불 가능 확인
# ------------------------------------------------------------
Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody
"PREVIEW2_OK (qty=1)" | Write-Host

# ------------------------------------------------------------
# 6) Refund step2 (qty=1) => full refund (CANCELLED)
# ------------------------------------------------------------
$refundBody2 = @{
  reservation_id = $rid
  quantity_refund = 1
  reason = "e2e partial refund step2 (full)"
  requested_by = "BUYER"
} | ConvertTo-Json
$r2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $refundBody2
"REFUND2_OK rid=$rid status=$($r2.status) refunded_qty=$($r2.refunded_qty) refunded_amount_total=$($r2.refunded_amount_total) phase=$($r2.phase)" | Write-Host
"OFFER_AFTER_REFUND2= $(Get-OfferRow $offerId)" | Write-Host

# ------------------------------------------------------------
# 7) DB verify
# ------------------------------------------------------------
"RESV_ROW= $(Get-ResvRow $rid)" | Write-Host
"PAYMENTS_FOR_RID= $(Get-Payments $rid)" | Write-Host
"SETTLEMENTS_FOR_RID= $(Get-Settlements $rid)" | Write-Host

# ------------------------------------------------------------
# 8) 간단 체크(사람이 보기 쉽게)
# ------------------------------------------------------------
"--- CHECKLIST ---" | Write-Host
"* After pay: offer.sold_qty increased by 2, reserved_qty decreased by 2" | Write-Host
"* After refund1: offer.sold_qty decreased by 1, reservation still PAID, refunded_qty=1" | Write-Host
"* After refund2: offer.sold_qty decreased by 1 more, reservation CANCELLED, refunded_qty=2" | Write-Host
"* Settlement row should reflect remaining gross if you sync (3.9) and status CANCELLED when remaining_gross=0" | Write-Host
"OK" | Write-Host