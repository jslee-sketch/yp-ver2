# scripts/e2e_ops_one_shot.ps1
# 목적: 운영베이스 검증(스킵 없이)
# - CASE NO_SHIPPING / PER_RESERVATION / PER_QTY
# - create(v3.5 /reservations) -> pay(/reservations/pay) -> ship(v3_6) -> arrival-confirm(v3_6)
# - refund preview(v3_6) -> refund step1 -> refund step2 -> DB 검증

param(
  [string]$BaseUrl = "http://127.0.0.1:9000",
  [string]$DbPath  = "C:\dev\yp-ver2\app\ypver2.db",
  [int]$BuyerId    = 1,
  [int]$SellerId   = 2,
  [int]$QtyTwoStep = 2,     # 2-step 환불용 qty
  [string]$ShipCarrier = "CJ",
  [string]$Tracking1   = "T-123",
  [string]$Tracking2   = "T-999-NEW"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-True {
  param([bool]$Cond, [string]$Msg)
  if (-not $Cond) { throw "ASSERT_FAIL: $Msg" }
}

function Invoke-Py {
  param(
    [Parameter(Mandatory=$true)][string]$Code,
    [string[]]$PyArgs = @()
  )
  $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("yp_tmp_" + [guid]::NewGuid().ToString("N") + ".py")
  Set-Content -Path $tmp -Value $Code -Encoding UTF8
  try {
    $out = & python $tmp @PyArgs 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($out | Out-String) }
    return ($out | Out-String).Trim()
  } finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
  }
}

function Get-OfferByCase {
  param([string]$CaseName)

  $py = @"
import sqlite3,sys
db=sys.argv[1]
case=sys.argv[2]
con=sqlite3.connect(db)
cur=con.cursor()

def pick(sql):
  cur.execute(sql)
  return cur.fetchone()

base_where = "total_available_qty > (coalesce(sold_qty,0) + coalesce(reserved_qty,0))"

sql = None
if case=="NO_SHIPPING":
  sql = f"""
    select id,deal_id,seller_id,price,shipping_mode,
           coalesce(shipping_fee_per_reservation,0),coalesce(shipping_fee_per_qty,0),
           total_available_qty,coalesce(sold_qty,0),coalesce(reserved_qty,0)
    from offers
    where {base_where}
      and coalesce(shipping_fee_per_reservation,0)=0
      and coalesce(shipping_fee_per_qty,0)=0
    order by id desc
    limit 1
  """
elif case=="PER_RESERVATION":
  sql = f"""
    select id,deal_id,seller_id,price,shipping_mode,
           coalesce(shipping_fee_per_reservation,0),coalesce(shipping_fee_per_qty,0),
           total_available_qty,coalesce(sold_qty,0),coalesce(reserved_qty,0)
    from offers
    where {base_where}
      and coalesce(shipping_fee_per_reservation,0)>0
    order by id desc
    limit 1
  """
elif case=="PER_QTY":
  sql = f"""
    select id,deal_id,seller_id,price,shipping_mode,
           coalesce(shipping_fee_per_reservation,0),coalesce(shipping_fee_per_qty,0),
           total_available_qty,coalesce(sold_qty,0),coalesce(reserved_qty,0)
    from offers
    where {base_where}
      and shipping_mode='PER_QTY'
      and coalesce(shipping_fee_per_qty,0)>0
    order by id desc
    limit 1
  """

r = pick(sql) if sql else None
con.close()
print("" if not r else ",".join(map(str,r)))
"@

  $s = Invoke-Py -Code $py -PyArgs @($DbPath, $CaseName)
  if (-not $s) { return $null }

  $p = $s.Split(",")
  return @{
    offer_id = [int]$p[0]
    deal_id  = [int]$p[1]
    seller_id = [int]$p[2]
    price = [double]$p[3]
    shipping_mode = $p[4]
    fpr = [int]$p[5]
    fpq = [int]$p[6]
    total = [int]$p[7]
    sold  = [int]$p[8]
    resvd = [int]$p[9]
  }
}

function Initialize-PerQtyOffer {
  # PER_QTY 오퍼가 없으면 하나 생성 (deal_id=2 seller_id=$SellerId price=200 total=10 fpq=500)
  $py = @"
import sqlite3,sys,datetime
db=sys.argv[1]
seller_id=int(sys.argv[2])

con=sqlite3.connect(db)
cur=con.cursor()

cur.execute("""
select id,deal_id from offers
where shipping_mode='PER_QTY' and coalesce(shipping_fee_per_qty,0)>0
order by id desc
limit 1
""")
r=cur.fetchone()
if r:
  print(r[0])
  con.close()
  raise SystemExit(0)

deal_id=2
price=200.0
total=10
mode='PER_QTY'
fpr=0
fpq=500
now=datetime.datetime.utcnow().isoformat(sep=' ')

cur.execute("""
insert into offers (deal_id,seller_id,price,total_available_qty,sold_qty,reserved_qty,shipping_mode,shipping_fee_per_reservation,shipping_fee_per_qty,is_active,created_at)
values (?,?,?,?,?,?,?,?,?,?,?)
""",(deal_id,seller_id,price,total,0,0,mode,fpr,fpq,1,now))

oid=cur.lastrowid
con.commit()
con.close()
print(oid)
"@
  $oid = Invoke-Py -Code $py -PyArgs @($DbPath, "$SellerId")
  return [int]$oid
}

function Show-DbSnapshot {
  param([int]$Rid, [int]$OfferId)

  $py = @"
import sqlite3,sys
db=sys.argv[1]; rid=int(sys.argv[2]); oid=int(sys.argv[3])
con=sqlite3.connect(db)
cur=con.cursor()

cur.execute("""
select id,status,qty,refunded_qty,refunded_amount_total,
       amount_goods,amount_shipping,amount_total,
       paid_at,shipped_at,delivered_at,arrival_confirmed_at,
       cancelled_at,expired_at,shipping_carrier,tracking_number
from reservations where id=?
""",(rid,))
print("RESV=", cur.fetchone())

cur.execute("""
select id,total_available_qty,coalesce(sold_qty,0),coalesce(reserved_qty,0),
       shipping_mode,coalesce(shipping_fee_per_reservation,0),coalesce(shipping_fee_per_qty,0)
from offers where id=?
""",(oid,))
print("OFFER=", cur.fetchone())

try:
  cur.execute("""
  select id,reservation_id,buyer_paid_amount,pg_fee_amount,platform_commission_amount,seller_payout_amount,status
  from reservation_settlements
  where reservation_id=?
  order by id desc
  limit 1
  """,(rid,))
  print("SETTLEMENT=", cur.fetchone())
except Exception as e:
  print("SETTLEMENT= <table missing or query failed>", str(e))

con.close()
"@
  Invoke-Py -Code $py -PyArgs @($DbPath, "$Rid", "$OfferId") | Write-Host
}

function Invoke-Case {
  param([string]$CaseName, [hashtable]$Offer)

  Write-Host "==============================="
  Write-Host "CASE: $CaseName deal_id=$($Offer.deal_id) offer_id=$($Offer.offer_id) mode=$($Offer.shipping_mode) fpr=$($Offer.fpr) fpq=$($Offer.fpq)"
  Write-Host "OFFER_BEFORE: total=$($Offer.total) sold=$($Offer.sold) reserved=$($Offer.resvd) price=$($Offer.price)"
  Write-Host "==============================="

  # 1) create (v3.5)
  $createBody = @{
    deal_id  = $Offer.deal_id
    offer_id = $Offer.offer_id
    buyer_id = $BuyerId
    qty      = $QtyTwoStep
  } | ConvertTo-Json

  $res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations" -ContentType "application/json" -Body $createBody
  $rid = [int]$res.id
  Assert-True ($rid -gt 0) "create failed: rid not positive"
  Write-Host "RID=$rid created amount_total=$($res.amount_total) status=$($res.status)"

  # 2) pay (SSOT: response amount_total)
  $apiTotal = 0
  try { $apiTotal = [int]($res.amount_total) } catch { $apiTotal = 0 }
  Assert-True ($apiTotal -gt 0) "API amount_total is 0 (ops-base bug). rid=$rid"

  $payBody = @{
    reservation_id = $rid
    buyer_id       = $BuyerId
    paid_amount    = $apiTotal
  } | ConvertTo-Json

  $paid = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations/pay" -ContentType "application/json" -Body $payBody
  Assert-True ($paid.status -eq "PAID") "pay failed: status=$($paid.status)"
  Write-Host "PAID_OK rid=$rid paid_amount=$apiTotal"

  # 3) ship (v3.6)
  $shipBody = @{
    seller_id = $SellerId
    shipping_carrier = $ShipCarrier
    tracking_number  = $Tracking1
  } | ConvertTo-Json

  $ship = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/$rid/ship" -ContentType "application/json" -Body $shipBody
  Write-Host "SHIP_OK rid=$rid shipped_at=$($ship.shipped_at) carrier=$($ship.shipping_carrier) track=$($ship.tracking_number)"

  # 3-1) ship 재호출(업데이트 허용 여부 확인)
  $shipBody2 = @{
    seller_id = $SellerId
    shipping_carrier = $ShipCarrier
    tracking_number  = $Tracking2
  } | ConvertTo-Json

  $ship2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/$rid/ship" -ContentType "application/json" -Body $shipBody2
  Write-Host "SHIP2_OK rid=$rid shipped_at=$($ship2.shipped_at) carrier=$($ship2.shipping_carrier) track=$($ship2.tracking_number)"

  # 4) arrival-confirm (v3.6)
  $arrBody = @{ buyer_id = $BuyerId } | ConvertTo-Json
  $arr = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/$rid/arrival-confirm" -ContentType "application/json" -Body $arrBody
  Write-Host "ARRIVAL_OK rid=$rid delivered_at=$($arr.delivered_at) arrival_confirmed_at=$($arr.arrival_confirmed_at)"

  # 4-1) arrival-confirm idempotent
  $arr2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/$rid/arrival-confirm" -ContentType "application/json" -Body $arrBody
  Write-Host "ARRIVAL2_OK rid=$rid delivered_at=$($arr2.delivered_at) arrival_confirmed_at=$($arr2.arrival_confirmed_at)"

  # 5) refund preview (qty=1)
  $prevBody = @{
    reservation_id = $rid
    actor = "buyer_cancel"
    quantity_refund = 1
  } | ConvertTo-Json

  $prev = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody
  Write-Host "PREVIEW_OK rid=$rid (qty=1) context.amount_total=$($prev.context.amount_total) goods=$($prev.context.amount_goods) ship=$($prev.context.amount_shipping)"

  # 6) refund step1 (qty=1)
  $ref1Body = @{
    reservation_id = $rid
    requested_by = "BUYER"
    quantity_refund = 1
    reason = "e2e one-shot refund step1"
  } | ConvertTo-Json

  $r1 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $ref1Body
  Write-Host "REFUND1_OK rid=$rid status=$($r1.status) refunded_qty=$($r1.refunded_qty) refunded_amount_total=$($r1.refunded_amount_total)"
  Assert-True ($r1.refunded_qty -eq 1) "refund1 should set refunded_qty=1"

  # 7) refund step2 (qty=1) - 다시 preview 찍고 실행
  $prev2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody
  Write-Host "PREVIEW2_OK rid=$rid (qty=1) context.amount_total=$($prev2.context.amount_total) goods=$($prev2.context.amount_goods) ship=$($prev2.context.amount_shipping)"

  $ref2Body = @{
    reservation_id = $rid
    requested_by = "BUYER"
    quantity_refund = 1
    reason = "e2e one-shot refund step2"
  } | ConvertTo-Json

  $r2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $ref2Body
  Write-Host "REFUND2_OK rid=$rid status=$($r2.status) refunded_qty=$($r2.refunded_qty) refunded_amount_total=$($r2.refunded_amount_total)"
  Assert-True ($r2.status -eq "CANCELLED") "refund2 should CANCELLED"
  Assert-True ($r2.refunded_qty -eq $QtyTwoStep) "refund2 should refunded_qty==$QtyTwoStep"

  # 8) DB dump
  Show-DbSnapshot -Rid $rid -OfferId $Offer.offer_id

  Write-Host "OK ($CaseName) rid=$rid"
  Write-Host ""
}

# ------------------------
# MAIN
# ------------------------
$null = Initialize-PerQtyOffer

$cases = @("NO_SHIPPING","PER_RESERVATION","PER_QTY")

foreach ($c in $cases) {
  $offer = Get-OfferByCase -CaseName $c
  Assert-True ($null -ne $offer) "No available offer found for case=$c (capacity or config missing)"

  # 케이스별 seller_id를 offer에서 가져와 ship 검증을 맞춘다
  if ($offer.seller_id -gt 0) { $SellerId = $offer.seller_id }

  Invoke-Case -CaseName $c -Offer $offer
}

Write-Host "ALL CASES DONE"