# scripts/e2e_partial_refund_twostep_shipping.ps1
# 목적: (배송비 포함) 예약 -> 결제 -> 부분환불(1) -> 부분환불(2, 전체취소) E2E
# 핵심: shipping 설정은 "결제(backfill 포함)"까지 유지하고, 마지막에 원복한다.

param(
  [string]$BaseUrl = "http://127.0.0.1:9000",
  [string]$DbPath  = "C:\dev\yp-ver2\app\ypver2.db",
  [int]$BuyerId    = 1,
  [int]$Qty        = 2,
  [int]$ShipFeePerReservation = 500
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# Python runner (✅ traceback 절대 안 잘리게)
# ------------------------------------------------------------
function Invoke-PyTmp {
  param(
    [Parameter(Mandatory=$true)][string]$Code,
    [string[]]$PyArgs = @()
  )

  $tmpDir = [System.IO.Path]::GetTempPath()
  if (-not (Test-Path $tmpDir)) {
    New-Item -ItemType Directory -Path $tmpDir | Out-Null
  }

  $tmp = Join-Path -Path $tmpDir -ChildPath ("yp_tmp_" + [guid]::NewGuid().ToString("N") + ".py")
  Set-Content -Path $tmp -Value $Code -Encoding UTF8

  try {
    # ✅ stdout+stderr 모두 문자열로 합친다 (여기서 안 잘림)
    $outText = (& python $tmp @PyArgs 2>&1 | Out-String)
    $ec = $LASTEXITCODE
    if ($ec -ne 0) {
      throw [System.Exception]::new($outText)
    }
    return $outText
  }
  finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
  }
}

function Get-AvailableOffer {
  param([string]$DbPath)
  $py = @"
import sqlite3,sys
db=sys.argv[1]
con=sqlite3.connect(db)
cur=con.cursor()
cur.execute("""
  select id, deal_id
  from offers
  where total_available_qty > (coalesce(sold_qty,0) + coalesce(reserved_qty,0))
  order by id desc
  limit 1
""")
r=cur.fetchone()
con.close()
if not r:
  print("")
else:
  print(f"{r[0]},{r[1]}")
"@
  return (Invoke-PyTmp -Code $py -PyArgs @($DbPath)).Trim()
}

function Get-OfferRow {
  param([string]$DbPath, [int]$OfferId)
  $py = @"
import sqlite3,sys
db=sys.argv[1]; oid=int(sys.argv[2])
con=sqlite3.connect(db)
cur=con.cursor()
cur.execute("select id, deal_id, total_available_qty, coalesce(sold_qty,0), coalesce(reserved_qty,0), coalesce(price,0) from offers where id=?", (oid,))
r=cur.fetchall()
con.close()
print(r)
"@
  return (Invoke-PyTmp -Code $py -PyArgs @($DbPath, "$OfferId")).Trim()
}

function Get-ReservationAmountsFromDb {
  param([string]$DbPath, [int]$ReservationId)
  $py = @"
import sqlite3,sys
db=sys.argv[1]; rid=int(sys.argv[2])
con=sqlite3.connect(db)
cur=con.cursor()
cur.execute("select coalesce(amount_goods,0), coalesce(amount_shipping,0), coalesce(amount_total,0) from reservations where id=?", (rid,))
r=cur.fetchone()
con.close()
print(f"{r[0]},{r[1]},{r[2]}")
"@
  return (Invoke-PyTmp -Code $py -PyArgs @($DbPath, "$ReservationId")).Trim()
}

function Get-SettlementRow {
  param([string]$DbPath, [int]$ReservationId)
  $py = @"
import sqlite3,sys
db=sys.argv[1]; rid=int(sys.argv[2])
con=sqlite3.connect(db)
cur=con.cursor()
cur.execute("select id,reservation_id,buyer_paid_amount,pg_fee_amount,platform_commission_amount,seller_payout_amount,status from reservation_settlements where reservation_id=? order by id desc limit 1",(rid,))
r=cur.fetchone()
con.close()
print(r if r else "")
"@
  return (Invoke-PyTmp -Code $py -PyArgs @($DbPath, "$ReservationId")).Trim()
}

# ------------------------------------------------------------
# shipping temp set + restore (✅ restore는 파일로만 한다)
# ------------------------------------------------------------
function Set-OfferShippingTemp {
  param(
    [Parameter(Mandatory=$true)][string]$DbPath,
    [Parameter(Mandatory=$true)][int]$OfferId,
    [Parameter(Mandatory=$true)][int]$FeePerReservation
  )

  $py = @"
import sqlite3, sys, json
db=sys.argv[1]; oid=int(sys.argv[2]); fee=int(sys.argv[3])

con=sqlite3.connect(db)
cur=con.cursor()
cur.execute("select shipping_mode, shipping_fee_per_reservation, shipping_fee_per_qty from offers where id=?", (oid,))
r=cur.fetchone()
if not r:
    raise SystemExit("offer not found")

backup={"mode": r[0], "fee_per_reservation": r[1], "fee_per_qty": r[2]}

cur.execute(
  "update offers set shipping_mode=?, shipping_fee_per_reservation=?, shipping_fee_per_qty=? where id=?",
  ("PER_RESERVATION", fee, 0, oid)
)
con.commit()
con.close()
print(json.dumps(backup, ensure_ascii=False))
"@
  return (Invoke-PyTmp -Code $py -PyArgs @($DbPath, "$OfferId", "$FeePerReservation")).Trim()
}

function Restore-OfferShippingFromFile {
  param(
    [Parameter(Mandatory=$true)][string]$DbPath,
    [Parameter(Mandatory=$true)][int]$OfferId,
    [Parameter(Mandatory=$true)][string]$BackupFile
  )

  $py = @"
import sqlite3, sys, json, traceback, os
db=sys.argv[1]; oid=int(sys.argv[2]); path=sys.argv[3]

try:
    if not os.path.exists(path):
        raise RuntimeError(f"backup file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        bk=json.load(f)

    mode=bk.get("mode", None)
    fpr=int(bk.get("fee_per_reservation", 0) or 0)
    fpq=int(bk.get("fee_per_qty", 0) or 0)

    con=sqlite3.connect(db)
    cur=con.cursor()
    cur.execute(
      "update offers set shipping_mode=?, shipping_fee_per_reservation=?, shipping_fee_per_qty=? where id=?",
      (mode, fpr, fpq, oid)
    )
    con.commit()
    con.close()
    print("OK")
except Exception:
    print("RESTORE_FAILED_TRACEBACK:")
    print(traceback.format_exc())
    raise
"@

  [void](Invoke-PyTmp -Code $py -PyArgs @($DbPath, "$OfferId", "$BackupFile"))
}

# ------------------------------------------------------------
# 0) offer pick
# ------------------------------------------------------------
$pick = Get-AvailableOffer -DbPath $DbPath
if (-not $pick) { throw "No available offer found (all sold out: total <= sold+reserved for all offers)" }

$parts = $pick.Split(",")
$offerId = [int]$parts[0]
$dealId  = [int]$parts[1]

"Using deal_id=$dealId offer_id=$offerId" | Write-Host
("OFFER_BEFORE= " + (Get-OfferRow -DbPath $DbPath -OfferId $offerId)) | Write-Host

# ------------------------------------------------------------
# 1) shipping temp set (⚠ 결제까지 유지!)
# ------------------------------------------------------------
$backupJson = Set-OfferShippingTemp -DbPath $DbPath -OfferId $offerId -FeePerReservation $ShipFeePerReservation
$bkObj = $backupJson | ConvertFrom-Json

$backupFile = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath ("yp_ship_backup_" + $offerId + "_" + [guid]::NewGuid().ToString("N") + ".json")
Set-Content -Path $backupFile -Value $backupJson -Encoding UTF8

"SHIPPING_SET offer_id=$offerId => mode=PER_RESERVATION fee_per_reservation=$ShipFeePerReservation fee_per_qty=0 (will restore at end)" | Write-Host

try {
  # ------------------------------------------------------------
  # 2) reserve
  # ------------------------------------------------------------
  $resBody = @{
    deal_id  = $dealId
    offer_id = $offerId
    buyer_id = $BuyerId
    qty      = $Qty
  } | ConvertTo-Json

  $res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations" -ContentType "application/json" -Body $resBody
  $rid = [int]$res.id
  "RID=$rid" | Write-Host
  ("OFFER_AFTER_RESERVE= " + (Get-OfferRow -DbPath $DbPath -OfferId $offerId)) | Write-Host

  # ------------------------------------------------------------
  # 3) pay (paid_amount SSOT: API amount_total, if 0 => DB, if 0 => compute)
  # ------------------------------------------------------------
  $apiTotal = 0
  try { $apiTotal = [int]($res.amount_total) } catch { $apiTotal = 0 }

  $paidAmount = $apiTotal
  if ($paidAmount -le 0) {
    $dbAmts = Get-ReservationAmountsFromDb -DbPath $DbPath -ReservationId $rid
    $a = $dbAmts.Split(",")
    $dbTotal = [int]$a[2]
    if ($dbTotal -gt 0) {
      $paidAmount = $dbTotal
    } else {
      # 마지막 보루: offer.price*qty + shipping(per_reservation)
      $offerRow = (Get-OfferRow -DbPath $DbPath -OfferId $offerId)
      $m = [regex]::Match($offerRow, "\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*([0-9\.]+)\)")
      if (-not $m.Success) { throw "Cannot parse offer row for price: $offerRow" }
      $unitPrice = [int][double]$m.Groups[6].Value
      $paidAmount = ($unitPrice * $Qty) + $ShipFeePerReservation
    }
  }

  if ($paidAmount -le 0) {
    $dbAmts2 = Get-ReservationAmountsFromDb -DbPath $DbPath -ReservationId $rid
    $p2 = $dbAmts2.Split(",")
    throw "Invalid reservation.amount_total (API/DB both <=0). DB snapshot: amount_goods=$($p2[0]) amount_shipping=$($p2[1]) amount_total=$($p2[2])"
  }

  $payBody = @{
    reservation_id = $rid
    buyer_id       = $BuyerId
    paid_amount    = $paidAmount
  } | ConvertTo-Json

  $paid = Invoke-RestMethod -Method Post -Uri "$BaseUrl/reservations/pay" -ContentType "application/json" -Body $payBody
  "PAID_OK rid=$rid paid_amount=$paidAmount status=$($paid.status) amount_total=$($paid.amount_total)" | Write-Host
  ("OFFER_AFTER_PAY= " + (Get-OfferRow -DbPath $DbPath -OfferId $offerId)) | Write-Host

  # ------------------------------------------------------------
  # 4) preview (qty=1) + refund1
  # ------------------------------------------------------------
  $prevBody = @{ reservation_id = $rid; quantity_refund = 1 } | ConvertTo-Json
  $prev1 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody
  "PREVIEW_OK uri=$BaseUrl/v3_6/reservations/refund/preview (qty=1)" | Write-Host
  ($prev1 | ConvertTo-Json -Depth 30) | Write-Host

  $refund1Body = @{
    reservation_id  = $rid
    quantity_refund = 1
    reason          = "e2e shipping partial refund step1"
    requested_by    = "BUYER"
  } | ConvertTo-Json
  $r1 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $refund1Body
  "REFUND1_OK rid=$rid status=$($r1.status) refunded_qty=$($r1.refunded_qty) refunded_amount_total=$($r1.refunded_amount_total) phase=$($r1.phase)" | Write-Host
  ("OFFER_AFTER_REFUND1= " + (Get-OfferRow -DbPath $DbPath -OfferId $offerId)) | Write-Host
  ("SETTLEMENT_AFTER_REFUND1= " + (Get-SettlementRow -DbPath $DbPath -ReservationId $rid)) | Write-Host

  # ------------------------------------------------------------
  # 5) preview2 (qty=1) + refund2
  # ------------------------------------------------------------
  [void](Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund/preview" -ContentType "application/json" -Body $prevBody)
  "PREVIEW2_OK (qty=1)" | Write-Host

  $refund2Body = @{
    reservation_id  = $rid
    quantity_refund = 1
    reason          = "e2e shipping partial refund step2"
    requested_by    = "BUYER"
  } | ConvertTo-Json
  $r2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v3_6/reservations/refund" -ContentType "application/json" -Body $refund2Body
  "REFUND2_OK rid=$rid status=$($r2.status) refunded_qty=$($r2.refunded_qty) refunded_amount_total=$($r2.refunded_amount_total) phase=$($r2.phase)" | Write-Host
  ("OFFER_AFTER_REFUND2= " + (Get-OfferRow -DbPath $DbPath -OfferId $offerId)) | Write-Host

  # ------------------------------------------------------------
  # 6) DB dump
  # ------------------------------------------------------------
  $pyDump = @"
import sqlite3,sys
db=sys.argv[1]; rid=int(sys.argv[2])
con=sqlite3.connect(db)
cur=con.cursor()
cur.execute("select id,status,qty,refunded_qty,refunded_amount_total,amount_goods,amount_shipping,amount_total,paid_at,cancelled_at from reservations where id=?",(rid,))
print("RESV_ROW=", cur.fetchall())
cur.execute("select id,reservation_id,paid_amount,pg_fee_amount,currency,paid_at from reservation_payments where reservation_id=? order by id desc limit 3",(rid,))
print("PAYMENTS_FOR_RID=", cur.fetchall())
cur.execute("select id,reservation_id,deal_id,offer_id,seller_id,buyer_id,buyer_paid_amount,pg_fee_amount,platform_commission_amount,seller_payout_amount,status from reservation_settlements where reservation_id=? order by id desc limit 3",(rid,))
print("SETTLEMENTS_FOR_RID=", cur.fetchall())
con.close()
"@
  Invoke-PyTmp -Code $pyDump -PyArgs @($DbPath, "$rid") | Write-Host
}
finally {
  try {
    Restore-OfferShippingFromFile -DbPath $DbPath -OfferId $offerId -BackupFile $backupFile
    "SHIPPING_RESTORED ..." | Write-Host
  } catch {
    "SHIPPING_RESTORE_FAILED (ignored) offer_id=$offerId" | Write-Host
  } finally {
    Remove-Item $backupFile -ErrorAction SilentlyContinue
  }
}