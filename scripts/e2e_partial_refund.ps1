# scripts\e2e_partial_refund.ps1
# --------------------------------------------
# E2E: reserve(qty=2) -> pay -> refund preview(qty=1) -> refund execute(qty=1)
# - preview/execute 파라미터(특히 quantity_refund)를 1:1로 맞춘다.
# - 기본은 offer_id=1(재고 10) 사용. 필요하면 -OfferId로 지정.
# --------------------------------------------

param(
  [string]$BaseUrl = "http://127.0.0.1:9000",
  [int]$BuyerId = 1,
  [int]$OfferId = 1,
  [int]$Qty = 2,
  [int]$PartialQty = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Py {
  param(
    [Parameter(Mandatory=$true)][string]$PyCode,
    [Parameter()][string[]]$PyArgs = @()
  )
  $tmp = Join-Path $env:TEMP ("yp_tmp_" + [Guid]::NewGuid().ToString("N") + ".py")
  try {
    [System.IO.File]::WriteAllText($tmp, $PyCode, [System.Text.Encoding]::UTF8)
    $out = & python $tmp @PyArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
      throw ($out | Out-String)
    }
    return ($out | Out-String).Trim()
  } finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
  }
}

function Get-OfferRow {
  param([int]$Id)
  $code = @"
import sqlite3,sys
db=r'C:\dev\yp-ver2\app\ypver2.db'
oid=int(sys.argv[1])
con=sqlite3.connect(db); cur=con.cursor()
cur.execute('select id,deal_id,total_available_qty,sold_qty,reserved_qty,price from offers where id=?',(oid,))
print(cur.fetchone())
con.close()
"@
  return (Invoke-Py -PyCode $code -PyArgs @("$Id"))
}

function Get-ReservationRow {
  param([int]$Rid)
  $code = @"
import sqlite3,sys
db=r'C:\dev\yp-ver2\app\ypver2.db'
rid=int(sys.argv[1])
con=sqlite3.connect(db); cur=con.cursor()
cur.execute('select id,status,qty,refunded_qty,refunded_amount_total,amount_goods,amount_shipping,amount_total,paid_at,cancelled_at from reservations where id=?',(rid,))
print(cur.fetchone())
con.close()
"@
  return (Invoke-Py -PyCode $code -PyArgs @("$Rid"))
}

function Get-PaymentsForRid {
  param([int]$Rid)
  $code = @"
import sqlite3,sys
db=r'C:\dev\yp-ver2\app\ypver2.db'
rid=int(sys.argv[1])
con=sqlite3.connect(db); cur=con.cursor()
cur.execute('select id,reservation_id,paid_amount,pg_fee_amount,currency,paid_at from reservation_payments where reservation_id=? order by id desc',(rid,))
print(cur.fetchall())
con.close()
"@
  return (Invoke-Py -PyCode $code -PyArgs @("$Rid"))
}

function Get-SettlementsForRid {
  param([int]$Rid)
  $code = @"
import sqlite3,sys
db=r'C:\dev\yp-ver2\app\ypver2.db'
rid=int(sys.argv[1])
con=sqlite3.connect(db); cur=con.cursor()
cur.execute('select id,reservation_id,deal_id,offer_id,seller_id,buyer_id,buyer_paid_amount,pg_fee_amount,platform_commission_amount,seller_payout_amount,status from reservation_settlements where reservation_id=? order by id desc',(rid,))
print(cur.fetchall())
con.close()
"@
  return (Invoke-Py -PyCode $code -PyArgs @("$Rid"))
}

# --------------------------------------------
# 0) offer / deal / price 확인
# --------------------------------------------
$offerBefore = Get-OfferRow -Id $OfferId
if (-not $offerBefore) { throw "Offer not found: offer_id=$OfferId" }

# tuple: (id, deal_id, total, sold, reserved, price)
$parts = $offerBefore.Trim("()").Split(",").ForEach({ $_.Trim() })
$dealId = [int]$parts[1]
$price  = [int][double]$parts[5]

"Using deal_id=$dealId offer_id=$OfferId price=$price offer(total=$($parts[2]) sold=$($parts[3]) reserved=$($parts[4]))" | Write-Host
"OFFER_BEFORE= $offerBefore" | Write-Host

if ($Qty -lt 1) { throw "Qty must be >= 1" }
if ($PartialQty -lt 1 -or $PartialQty -ge $Qty) { throw "PartialQty must be in [1..Qty-1]. Qty=$Qty PartialQty=$PartialQty" }

# --------------------------------------------
# 1) 예약 생성 (qty=2)
# --------------------------------------------
$body = @{
  deal_id  = $dealId
  offer_id = $OfferId
  buyer_id = $BuyerId
  qty      = $Qty
} | ConvertTo-Json

$res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations" -ContentType "application/json" -Body $body
$rid = [int]$res.id
"RID=$rid" | Write-Host

"OFFER_AFTER_RESERVE= $(Get-OfferRow -Id $OfferId)" | Write-Host

# --------------------------------------------
# 2) 결제 (amount_total = price * qty)
# --------------------------------------------
$paidAmount = $price * $Qty

$pay = @{
  reservation_id = $rid
  buyer_id       = $BuyerId
  paid_amount    = $paidAmount
} | ConvertTo-Json

$paid = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations/pay" -ContentType "application/json" -Body $pay
"PAID_OK rid=$rid paid_amount=$paidAmount status=$($paid.status) amount_total=$($paid.amount_total)" | Write-Host
"OFFER_AFTER_PAY= $(Get-OfferRow -Id $OfferId)" | Write-Host

# --------------------------------------------
# 3) ✅ refund preview (부분환불 qty=1)  <<<<<< 핵심: execute와 동일 qty로 맞춤
#    - /admin/refund/preview 는 qty를 못 넣어서 부분환불 검증에 부적합
#    - /v3_6/reservations/refund/preview 를 사용
# --------------------------------------------
try {
  $previewBody = @{
    reservation_id = $rid
    actor          = "buyer_cancel"
    quantity_refund = $PartialQty
    shipping_refund_override = $null
    shipping_refund_override_reason = $null
  } | ConvertTo-Json

  $preview = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $previewBody
  "PREVIEW_OK uri=$BaseUrl/v3_6/reservations/refund/preview (qty=$PartialQty)" | Write-Host
  ($preview | ConvertTo-Json -Depth 30) | Write-Host
} catch {
  "PREVIEW_CALL_FAILED uri=$BaseUrl/v3_6/reservations/refund/preview err=$($_.Exception.Message)" | Write-Host
}

# --------------------------------------------
# 4) refund execute (부분환불 qty=1)
# --------------------------------------------
$refundBody = @{
  reservation_id = $rid
  quantity_refund = $PartialQty
  reason         = "e2e test partial refund"
  requested_by   = "BUYER"
} | ConvertTo-Json

$refunded = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $refundBody
"REFUND_OK rid=$rid status=$($refunded.status) refunded_qty=$($refunded.refunded_qty) refunded_amount_total=$($refunded.refunded_amount_total) phase=$($refunded.phase)" | Write-Host

# --------------------------------------------
# 5) DB 확인
# --------------------------------------------
"RESV_ROW= $(Get-ReservationRow -Rid $rid)" | Write-Host
"PAYMENTS_FOR_RID= $(Get-PaymentsForRid -Rid $rid)" | Write-Host
"SETTLEMENTS_FOR_RID= $(Get-SettlementsForRid -Rid $rid)" | Write-Host
"OFFER_AFTER_REFUND= $(Get-OfferRow -Id $OfferId)" | Write-Host