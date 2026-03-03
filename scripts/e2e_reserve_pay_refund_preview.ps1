param(
  [string]$BaseUrl = "http://127.0.0.1:9000",
  [string]$DbPath  = "C:\dev\yp-ver2\app\ypver2.db",
  [int]$BuyerId    = 1,
  [int]$Qty        = 1,

  # ✅ 스위치 기본값 true 금지 규칙 회피: int로 처리 (1=reset, 0=no reset)
  [int]$ForceResetWhenSoldOut = 1,

  # ✅ 스위치 기본값 true 금지 규칙 회피: int로 처리 (1=debug, 0=no debug)
  [int]$PrintDebug = 1
)

$ErrorActionPreference = "Stop"

function Invoke-Py {
  param(
    [Parameter(Mandatory=$true)][string]$Code,
    [string[]]$PyArgs = @()
  )
  $tmp = Join-Path $env:TEMP ("yp_tmp_" + [Guid]::NewGuid().ToString("N") + ".py")
  Set-Content -Path $tmp -Value $Code -Encoding UTF8
  try {
    $out = & python $tmp @PyArgs 2>&1
    return ($out | Out-String).Trim()
  } finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
}

function Get-OfferState {
  param([int]$OfferId)
  $code = @"
import sqlite3,sys
db=sys.argv[1]
oid=int(sys.argv[2])
con=sqlite3.connect(db); cur=con.cursor()
cur.execute('select id, deal_id, total_available_qty, sold_qty, reserved_qty, price from offers where id=?',(oid,))
print(cur.fetchone())
con.close()
"@
  Invoke-Py -Code $code -PyArgs @($DbPath, "$OfferId")
}

function Get-OfferSelection {
  # returns "offer_id,deal_id,price,total,sold,reserved" or throws
  $pickCode = @"
import sqlite3,sys
db=sys.argv[1]
con=sqlite3.connect(db); cur=con.cursor()
cur.execute("""
select id, deal_id, price, total_available_qty, ifnull(sold_qty,0), ifnull(reserved_qty,0)
from offers
where (total_available_qty > (ifnull(sold_qty,0) + ifnull(reserved_qty,0)))
  and ifnull(price,0) > 0
order by id desc
limit 1
""")
r=cur.fetchone()
if r:
    print(f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]}")
con.close()
"@
  $s = Invoke-Py -Code $pickCode -PyArgs @($DbPath)
  if ($s) { return $s }

  if ($ForceResetWhenSoldOut -ne 1) {
    throw "No available offer found (all sold out: total <= sold+reserved for all offers)"
  }

  $resetCode = @"
import sqlite3,sys
db=sys.argv[1]
con=sqlite3.connect(db); cur=con.cursor()

cur.execute("""
select id, deal_id, price, total_available_qty, ifnull(sold_qty,0), ifnull(reserved_qty,0)
from offers
where ifnull(price,0) > 0 and ifnull(total_available_qty,0) > 0
order by total_available_qty desc, id desc
limit 1
""")
r=cur.fetchone()
if not r:
    print("")
    con.close()
    raise SystemExit(0)

oid=r[0]
cur.execute("update offers set sold_qty=0, reserved_qty=0 where id=?", (oid,))
con.commit()

cur.execute("""
select id, deal_id, price, total_available_qty, ifnull(sold_qty,0), ifnull(reserved_qty,0)
from offers where id=?
""",(oid,))
r2=cur.fetchone()
print(f"{r2[0]},{r2[1]},{r2[2]},{r2[3]},{r2[4]},{r2[5]}")
con.close()
"@
  $s2 = Invoke-Py -Code $resetCode -PyArgs @($DbPath)
  if (-not $s2) {
    throw "No offers found in DB to reset. Create offers first."
  }
  return $s2
}

function Get-RefundPreviewEndpoint {
  try {
    $oa = Invoke-RestMethod "$BaseUrl/openapi.json"
  } catch {
    return $null
  }

  $paths = @()
  foreach ($p in $oa.paths.PSObject.Properties.Name) {
    if ($p -match "refund" -and $p -match "preview") {
      $paths += $p
    }
  }
  if ($paths.Count -eq 0) { return $null }

  $preferred = @(
    "/admin/refund/preview",
    "/v3_6/reservations/refund/preview",
    "/v3_6/refund/preview/{reservation_id}"
  )

  foreach ($pp in $preferred) {
    if ($paths -contains $pp) { return $pp }
  }
  return $paths[0]
}

# ------------------------------------------------------------
# 0) Offer 선택(없으면 reset)
# ------------------------------------------------------------
$pick = Get-OfferSelection
$parts = $pick.Split(",")
$offerId = [int]$parts[0]
$dealId  = [int]$parts[1]
$price   = [double]$parts[2]
$totalQ  = [int]$parts[3]
$soldQ   = [int]$parts[4]
$resvQ   = [int]$parts[5]

if ($PrintDebug -eq 1) {
  "Using deal_id=$dealId offer_id=$offerId price=$price offer(total=$totalQ sold=$soldQ reserved=$resvQ)" | Write-Host
  "OFFER_BEFORE= $(Get-OfferState -OfferId $offerId)" | Write-Host
}

if ($price -le 0) {
  throw "Invalid offer.price for offer_id=$offerId => $price"
}

# ------------------------------------------------------------
# 1) 예약 생성
# ------------------------------------------------------------
$body = @{
  deal_id = $dealId
  offer_id = $offerId
  buyer_id = $BuyerId
  qty = $Qty
} | ConvertTo-Json

$res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations" -ContentType "application/json" -Body $body
$rid = [int]$res.id
"RID=$rid" | Write-Host

if ($PrintDebug -eq 1) {
  "OFFER_AFTER_RESERVE= $(Get-OfferState -OfferId $offerId)" | Write-Host
}

# ------------------------------------------------------------
# 2) 결제 (paid_amount는 offer.price*qty)
# ------------------------------------------------------------
$paidAmount = [int]([math]::Round($price * $Qty))
$pay = @{
  reservation_id = $rid
  buyer_id = $BuyerId
  paid_amount = $paidAmount
} | ConvertTo-Json

$paid = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations/pay" -ContentType "application/json" -Body $pay
"PAID_OK rid=$rid paid_amount=$paidAmount status=$($paid.status) amount_total=$($paid.amount_total)" | Write-Host

if ($PrintDebug -eq 1) {
  "OFFER_AFTER_PAY= $(Get-OfferState -OfferId $offerId)" | Write-Host
}

# ------------------------------------------------------------
# 3) refund preview endpoint 탐색 후 호출 (있으면)
# ------------------------------------------------------------
$previewPath = Get-RefundPreviewEndpoint
if (-not $previewPath) {
  "PREVIEW: no refund preview endpoint found in openapi.json (skipping)" | Write-Host
} else {
  try {
    if ($previewPath -eq "/v3_6/refund/preview/{reservation_id}") {
      # ✅ path param GET
      $u = "$BaseUrl/v3_6/refund/preview/$rid"
      $preview = Invoke-RestMethod -Method Get -Uri $u
    }
    elseif ($previewPath -eq "/admin/refund/preview") {
      # ✅ OpenAPI 기준: GET + querystring
      $faultParty = "BUYER"
      $trigger    = "BUYER_CANCEL"
      $u = "$BaseUrl/admin/refund/preview?reservation_id=$rid&fault_party=$faultParty&trigger=$trigger"
      $preview = Invoke-RestMethod -Method Get -Uri $u
    }
    else {
      # ✅ 나머지는 "일단 GET + querystring reservation_id"로 시도 (POST 금지)
      $u = "$BaseUrl$previewPath?reservation_id=$rid"
      $preview = Invoke-RestMethod -Method Get -Uri $u
    }

    "PREVIEW_OK path=$previewPath uri=$u" | Write-Host
    $preview | ConvertTo-Json -Depth 30 | Write-Host
  } catch {
    "PREVIEW_CALL_FAILED path=$previewPath uri=$u err=$($_.Exception.Message)" | Write-Host
  }
}

# ------------------------------------------------------------
# 4) DB row sanity (payments/settlements)
# ------------------------------------------------------------
$checkCode = @"
import sqlite3,sys
db=sys.argv[1]
rid=int(sys.argv[2])
con=sqlite3.connect(db); cur=con.cursor()

cur.execute("select id,status,qty,amount_goods,amount_shipping,amount_total,paid_at,cancelled_at,expired_at from reservations where id=?", (rid,))
print("RESV_ROW=", cur.fetchone())

cur.execute("select id,reservation_id,paid_amount,pg_fee_amount,currency,paid_at from reservation_payments where reservation_id=? order by id desc limit 5",(rid,))
print("PAYMENTS_FOR_RID=", cur.fetchall())

cur.execute("select id,reservation_id,deal_id,offer_id,seller_id,buyer_id,buyer_paid_amount,pg_fee_amount,platform_commission_amount,seller_payout_amount,status from reservation_settlements where reservation_id=? order by id desc limit 5",(rid,))
print("SETTLEMENTS_FOR_RID=", cur.fetchall())

con.close()
"@
Invoke-Py -Code $checkCode -PyArgs @($DbPath, "$rid") | Write-Host