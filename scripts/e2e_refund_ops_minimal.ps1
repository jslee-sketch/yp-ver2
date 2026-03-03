# scripts/e2e_refund_ops_minimal.ps1
# 목적: 운영 베이스 검증 (NO_SHIPPING / PER_RESERVATION / PER_QTY) 3케이스를 "무조건" 모두 실행
# 원칙:
# - paid_amount SSOT = /reservations 응답 amount_total (0이면 운영 버그로 FAIL)
# - 케이스용 offer가 DB에 없으면 자동으로 생성해서라도 3케이스를 모두 실행 (SKIP 금지)
# - 각 케이스: reserve -> pay -> preview1/refund1 -> preview2/refund2 -> DB verify

param(
  [string]$BaseUrl = "http://127.0.0.1:9000",
  [string]$DbPath  = "C:\dev\yp-ver2\app\ypver2.db",
  [int]$BuyerId    = 1,
  [int]$Qty        = 2,

  # (선택) 특정 deal/seller를 강제하고 싶으면 지정 (0이면 자동 선택)
  [int]$ForceDealId   = 0,
  [int]$ForceSellerId = 0
)

$ErrorActionPreference = "Stop"

function Invoke-Py {
  param([Parameter(Mandatory=$true)][string]$Code, [string[]]$Args=@())
  $tmp = Join-Path $env:TEMP ("yp_tmp_" + [guid]::NewGuid().ToString("N") + ".py")
  Set-Content -Path $tmp -Value $Code -Encoding UTF8
  try {
    $out = & python $tmp @Args 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($out | Out-String) }
    return ($out | Out-String)
  } finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
  }
}

function Db-GetOfferRow {
  param([int]$OfferId)
  $py = @"
import sqlite3,sys
db=sys.argv[1]; oid=int(sys.argv[2])
con=sqlite3.connect(db)
cur=con.cursor()
cur.execute("""
select id,deal_id,total_available_qty,coalesce(sold_qty,0),coalesce(reserved_qty,0),
       coalesce(price,0),coalesce(shipping_mode,''),coalesce(shipping_fee_per_reservation,0),coalesce(shipping_fee_per_qty,0),
       coalesce(seller_id,0)
from offers where id=?
""",(oid,))
r=cur.fetchone()
con.close()
print("" if not r else r)
"@
  return (Invoke-Py -Code $py -Args @($DbPath, "$OfferId")).Trim()
}

function Db-FindOfferForCase {
  param([string]$CaseKey) # NO_SHIPPING | PER_RESERVATION | PER_QTY
  $py = @"
import sqlite3,sys
db=sys.argv[1]; case=sys.argv[2]
force_deal=int(sys.argv[3]); force_seller=int(sys.argv[4])
con=sqlite3.connect(db)
cur=con.cursor()

w=[]
args=[]
if force_deal>0:
  w.append("deal_id=?"); args.append(force_deal)
if force_seller>0:
  w.append("seller_id=?"); args.append(force_seller)

base_where = (" and " + " and ".join(w)) if w else ""

if case=="NO_SHIPPING":
  q=f"""
    select id,deal_id,seller_id
    from offers
    where coalesce(shipping_fee_per_reservation,0)=0 and coalesce(shipping_fee_per_qty,0)=0
      and total_available_qty > (coalesce(sold_qty,0)+coalesce(reserved_qty,0))
      {base_where}
    order by id asc limit 1
  """
elif case=="PER_RESERVATION":
  q=f"""
    select id,deal_id,seller_id
    from offers
    where coalesce(shipping_fee_per_reservation,0)>0
      and total_available_qty > (coalesce(sold_qty,0)+coalesce(reserved_qty,0))
      {base_where}
    order by id asc limit 1
  """
elif case=="PER_QTY":
  q=f"""
    select id,deal_id,seller_id
    from offers
    where coalesce(shipping_fee_per_qty,0)>0
      and total_available_qty > (coalesce(sold_qty,0)+coalesce(reserved_qty,0))
      {base_where}
    order by id asc limit 1
  """
else:
  print(""); raise SystemExit(0)

cur.execute(q, args)
r=cur.fetchone()
con.close()
print("" if not r else f"{r[0]},{r[1]},{r[2]}")
"@
  return (Invoke-Py -Code $py -Args @($DbPath, $CaseKey, "$ForceDealId", "$ForceSellerId")).Trim()
}

function Db-PickDealSellerFallback {
  # 케이스용 offer를 만들어야 할 때 사용할 deal_id/seller_id를 DB에서 안전하게 하나 고름.
  $py = @"
import sqlite3,sys
db=sys.argv[1]
con=sqlite3.connect(db)
cur=con.cursor()

# deal 하나라도 있으면 거기 붙이고, 없으면 offers의 deal_id를 재활용
cur.execute("select id from deals order by id asc limit 1")
d=cur.fetchone()
deal_id = int(d[0]) if d else None

# seller 하나라도 있으면 거기 붙이고, 없으면 offers의 seller_id를 재활용
cur.execute("select id from sellers order by id asc limit 1")
s=cur.fetchone()
seller_id = int(s[0]) if s else None

# deal/seller가 없으면 offers에서 뽑는다
if deal_id is None or seller_id is None:
  cur.execute("select deal_id, seller_id from offers where deal_id is not null and seller_id is not null order by id asc limit 1")
  r=cur.fetchone()
  if r:
    if deal_id is None: deal_id=int(r[0])
    if seller_id is None: seller_id=int(r[1])

con.close()
if deal_id is None or seller_id is None:
  print("")
else:
  print(f"{deal_id},{seller_id}")
"@
  return (Invoke-Py -Code $py -Args @($DbPath)).Trim()
}

function Db-EnsureOfferForCase {
  param([string]$CaseKey)

  $found = Db-FindOfferForCase -CaseKey $CaseKey
  if ($found) { return $found } # "offer_id,deal_id,seller_id"

  # 없으면 자동 생성
  $ds = Db-PickDealSellerFallback
  if (-not $ds) { throw "Cannot auto-create offer: no deal/seller found in DB" }
  $p = $ds.Split(",")
  $dealId = [int]$p[0]
  $sellerId = [int]$p[1]

  if ($ForceDealId -gt 0)   { $dealId = $ForceDealId }
  if ($ForceSellerId -gt 0) { $sellerId = $ForceSellerId }

  # 케이스별 shipping 설정
  $shipping_mode = ""
  $fpr = 0
  $fpq = 0
  if ($CaseKey -eq "NO_SHIPPING")     { $shipping_mode = "PER_RESERVATION"; $fpr = 0;   $fpq = 0 }
  if ($CaseKey -eq "PER_RESERVATION") { $shipping_mode = "PER_RESERVATION"; $fpr = 500; $fpq = 0 }
  if ($CaseKey -eq "PER_QTY")         { $shipping_mode = "PER_QTY";         $fpr = 0;   $fpq = 500 }

  $py = @"
import sqlite3,sys,datetime
db=sys.argv[1]
deal_id=int(sys.argv[2]); seller_id=int(sys.argv[3])
price=float(sys.argv[4]); total=int(sys.argv[5])
shipping_mode=sys.argv[6]; fpr=int(sys.argv[7]); fpq=int(sys.argv[8])

con=sqlite3.connect(db)
cur=con.cursor()
now=datetime.datetime.now(datetime.timezone.utc).isoformat(sep=' ')
cur.execute("""
insert into offers
 (deal_id,seller_id,price,total_available_qty,sold_qty,reserved_qty,shipping_mode,shipping_fee_per_reservation,shipping_fee_per_qty,is_active,created_at)
values (?,?,?,?,?,?,?,?,?,?,?)
""",(deal_id,seller_id,price,total,0,0,shipping_mode,fpr,fpq,1,now))
oid=cur.lastrowid
con.commit()
con.close()
print(f"{oid},{deal_id},{seller_id}")
"@

  # price/total은 안전하게
  $created = (Invoke-Py -Code $py -Args @($DbPath, "$dealId", "$sellerId", "200.0", "10", $shipping_mode, "$fpr", "$fpq")).Trim()
  if (-not $created) { throw "Failed to auto-create offer for case=$CaseKey" }
  return $created
}

function Db-VerifySnapshot {
  param([int]$ReservationId)

  $py = @"
import sqlite3,sys
db=sys.argv[1]; rid=int(sys.argv[2])
con=sqlite3.connect(db)
cur=con.cursor()

cur.execute("select id,status,qty,refunded_qty,refunded_amount_total,amount_goods,amount_shipping,amount_total,paid_at,cancelled_at from reservations where id=?",(rid,))
print("RESV=", cur.fetchone())

cur.execute("select offer_id from reservations where id=?",(rid,))
r=cur.fetchone()
oid=r[0] if r else None
if oid is not None:
  cur.execute("select id,deal_id,total_available_qty,coalesce(sold_qty,0),coalesce(reserved_qty,0) from offers where id=?",(oid,))
  print("OFFER=", cur.fetchone())

cur.execute("select id,reservation_id,buyer_paid_amount,pg_fee_amount,platform_commission_amount,seller_payout_amount,status from reservation_settlements where reservation_id=? order by id desc limit 1",(rid,))
print("SETTLEMENT=", cur.fetchone())
con.close()
"@
  (Invoke-Py -Code $py -Args @($DbPath, "$ReservationId")) | Write-Host
}

function Run-Case {
  param([string]$CaseKey)

  # 0) 케이스 오퍼 확보(없으면 생성)
  $triplet = Db-EnsureOfferForCase -CaseKey $CaseKey   # "offer_id,deal_id,seller_id"
  $p = $triplet.Split(",")
  $offerId = [int]$p[0]
  $dealId  = [int]$p[1]

  $offerBefore = Db-GetOfferRow -OfferId $offerId
  if (-not $offerBefore) { throw "Offer not found even after ensure: offer_id=$offerId" }

  ""
  "===============================" | Write-Host
  "CASE: $CaseKey  deal_id=$dealId offer_id=$offerId" | Write-Host
  "OFFER_BEFORE= $offerBefore" | Write-Host
  "===============================" | Write-Host

  # 1) reserve
  $resBody = @{
    deal_id  = $dealId
    offer_id = $offerId
    buyer_id = $BuyerId
    qty      = $Qty
  } | ConvertTo-Json

  $res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations" -ContentType "application/json" -Body $resBody
  $rid = [int]$res.id
  "RID=$rid" | Write-Host
  "OFFER_AFTER_RESERVE= $(Db-GetOfferRow -OfferId $offerId)" | Write-Host

  # 2) pay (운영 SSOT: API amount_total, 0이면 FAIL)
  $apiTotal = 0
  try { $apiTotal = [int]($res.amount_total) } catch { $apiTotal = 0 }
  if ($apiTotal -le 0) {
    throw "Invalid reservation.amount_total from API (<=0). In ops-base validation, this is a real bug. rid=$rid apiTotal=$apiTotal"
  }

  $payBody = @{
    reservation_id = $rid
    buyer_id       = $BuyerId
    paid_amount    = $apiTotal
  } | ConvertTo-Json

  $paid = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations/pay" -ContentType "application/json" -Body $payBody
  "PAID_OK rid=$rid paid_amount=$apiTotal status=$($paid.status) amount_total=$($paid.amount_total)" | Write-Host
  "OFFER_AFTER_PAY= $(Db-GetOfferRow -OfferId $offerId)" | Write-Host

  # 3) preview/refund step1 (qty=1)
  $prevBody = @{ reservation_id = $rid; quantity_refund = 1 } | ConvertTo-Json
  $p1 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody
  "PREVIEW1_OK (qty=1) amount_total=$($p1.context.amount_total) goods=$($p1.context.amount_goods) ship=$($p1.context.amount_shipping)" | Write-Host

  $refund1Body = @{
    reservation_id  = $rid
    quantity_refund = 1
    reason          = "ops minimal step1"
    requested_by    = "BUYER"
  } | ConvertTo-Json
  $r1 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $refund1Body
  "REFUND1_OK status=$($r1.status) refunded_qty=$($r1.refunded_qty) refunded_amount_total=$($r1.refunded_amount_total)" | Write-Host
  "OFFER_AFTER_REFUND1= $(Db-GetOfferRow -OfferId $offerId)" | Write-Host

  # 4) preview/refund step2 (qty=1)
  $p2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody
  "PREVIEW2_OK (qty=1) amount_total=$($p2.context.amount_total) goods=$($p2.context.amount_goods) ship=$($p2.context.amount_shipping)" | Write-Host

  $refund2Body = @{
    reservation_id  = $rid
    quantity_refund = 1
    reason          = "ops minimal step2"
    requested_by    = "BUYER"
  } | ConvertTo-Json
  $r2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $refund2Body
  "REFUND2_OK status=$($r2.status) refunded_qty=$($r2.refunded_qty) refunded_amount_total=$($r2.refunded_amount_total)" | Write-Host
  "OFFER_AFTER_REFUND2= $(Db-GetOfferRow -OfferId $offerId)" | Write-Host

  # 5) DB verify
  Db-VerifySnapshot -ReservationId $rid
  "OK ($CaseKey) rid=$rid" | Write-Host
}

# ----------------------------
# main: 스킵 없이 3케이스 강제 실행
# ----------------------------
Run-Case -CaseKey "NO_SHIPPING"
Run-Case -CaseKey "PER_RESERVATION"
Run-Case -CaseKey "PER_QTY"