# scripts/test_part2.ps1
# Yeokping Backend Integration Test Part 2 - Read / Admin / Settlement Flow
# Prerequisite: test_part1.ps1 must have run -> test_ids.json must exist
# Encoding: UTF-8 BOM

param(
    [string]$Base    = "http://127.0.0.1:9000",
    [string]$IdsFile = "$PSScriptRoot\test_ids.json"
)

$ErrorActionPreference = "Continue"
$PASS = 0; $FAIL = 0

# ---------------------------------------------------------------------------
# Load IDs
# ---------------------------------------------------------------------------
if (-not (Test-Path $IdsFile)) {
    Write-Host "[WARN] test_ids.json not found - using defaults" -ForegroundColor Yellow
    $ids = [PSCustomObject]@{}
} else {
    $ids = Get-Content $IdsFile -Encoding utf8 | ConvertFrom-Json
    Write-Host "[OK] test_ids.json loaded" -ForegroundColor DarkGray
}

function GetId { param([string]$k, [int]$def = 1)
    $v = $ids.$k
    if ($null -ne $v) { return [int]$v } else { return $def }
}

$buyerId1    = 1
$sellerId1   = 2          # existing approved seller
$dealId1     = 1          # existing deal
$offerId1    = 5          # existing offer (is_active=1)
$paidResId   = GetId "paid_reservation_id" 13
$dealIdNew   = GetId "deal_id_new"         1
$sellerIdNew = GetId "seller_id_new"       2
$proposalId  = GetId "proposal_id"         0
$reportId    = GetId "report_id"           0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function ok   { param([string]$m) Write-Host "  [PASS] $m" -ForegroundColor Green;  $script:PASS++ }
function fail { param([string]$m, [string]$e="") Write-Host "  [FAIL] $m  $e" -ForegroundColor Red; $script:FAIL++ }

function Api {
    param(
        [string]$Method = "GET",
        [string]$Path,
        [hashtable]$Body = $null
    )
    $url = "$Base$Path"
    try {
        if ($null -ne $Body -and $Method -ne "GET") {
            $json  = $Body | ConvertTo-Json -Depth 6 -Compress
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            return Invoke-RestMethod -Method $Method -Uri $url -Body $bytes `
                -ContentType "application/json; charset=utf-8" -ErrorAction Stop
        } else {
            return Invoke-RestMethod -Method $Method -Uri $url -ErrorAction Stop
        }
    } catch {
        $sc = $null
        try { $sc = [int]$_.Exception.Response.StatusCode } catch {}
        $detail = ""
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $detail = $reader.ReadToEnd()
        } catch {}
        if ([string]::IsNullOrEmpty($detail)) { $detail = $_.Exception.Message }
        return [PSCustomObject]@{ __err=$true; __sc=$sc; __msg=$detail.Substring(0,[Math]::Min(120,$detail.Length)) }
    }
}

# IsOk: correctly handles both single-object and array responses
# Arrays from JSON lists are NOT errors; only our __err wrapper objects are errors
function IsOk {
    param($r)
    if ($null -eq $r) { return $false }
    # Check if it's our error wrapper (PSCustomObject with __err=true)
    if ($r -is [System.Management.Automation.PSCustomObject]) {
        $errProp = $r.PSObject.Properties["__err"]
        if ($null -ne $errProp -and $errProp.Value -eq $true) { return $false }
    }
    return $true
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Yeokping Part 2: Read / Admin / Settlement" -ForegroundColor Cyan
Write-Host "  Base: $Base" -ForegroundColor DarkGray
Write-Host "=============================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# [1] Buyer / Seller read
# ---------------------------------------------------------------------------
Write-Host "`n[1] Buyer / Seller" -ForegroundColor Yellow

$r = Api "GET" "/buyers/$buyerId1"
if (IsOk $r) { ok "GET /buyers/$buyerId1 => name=$($r.name)" } else { fail "GET /buyers/$buyerId1" $r.__msg }

$r = Api "GET" "/buyers/"
if (IsOk $r) { ok "GET /buyers/ => OK" } else { fail "GET /buyers/" $r.__msg }

$r = Api "GET" "/sellers/$sellerId1"
if (IsOk $r) { ok "GET /sellers/$sellerId1 => biz=$($r.business_name)" } else { fail "GET /sellers/$sellerId1" $r.__msg }

$r = Api "GET" "/sellers/"
if (IsOk $r) { ok "GET /sellers/ => OK" } else { fail "GET /sellers/" $r.__msg }

$r = Api "GET" "/basic/buyers/$buyerId1"
if (IsOk $r) { ok "GET /basic/buyers/$buyerId1 => OK" } else { fail "GET /basic/buyers/$buyerId1" $r.__msg }

$r = Api "GET" "/basic/sellers/$sellerId1"
if (IsOk $r) { ok "GET /basic/sellers/$sellerId1 => OK" } else { fail "GET /basic/sellers/$sellerId1" $r.__msg }

# ---------------------------------------------------------------------------
# [2] Deal list / search
# ---------------------------------------------------------------------------
Write-Host "`n[2] Deal list / search" -ForegroundColor Yellow

$r = Api "GET" "/deals/?status=open&page=1&size=10"
if (IsOk $r) { ok "GET /deals/?status=open => total=$($r.total)" } else { fail "GET /deals/?status=open" $r.__msg }

$r = Api "GET" "/deals/?keyword=Smartphone&page=1&size=5"
if (IsOk $r) { ok "GET /deals/?keyword=Smartphone => OK" } else { fail "GET /deals/?keyword" $r.__msg }

$r = Api "GET" "/deals/$dealId1"
if (IsOk $r -and $r.id) { ok "GET /deals/$dealId1 => $($r.product_name)" } else { fail "GET /deals/$dealId1" $r.__msg }

$r = Api "GET" "/deals/$dealId1/participants"
if (IsOk $r) { ok "GET /deals/$dealId1/participants => OK" } else { fail "GET /deals/$dealId1/participants" $r.__msg }

# ---------------------------------------------------------------------------
# [3] Offer list
# ---------------------------------------------------------------------------
Write-Host "`n[3] Offer list" -ForegroundColor Yellow

$r = Api "GET" "/offers/"
if (IsOk $r) { ok "GET /offers/ => OK" } else { fail "GET /offers/" $r.__msg }

$r = Api "GET" ("/offers/deal/$dealId1/ranked")
if (IsOk $r) { ok "GET /offers/deal/$dealId1/ranked => OK" } else { fail "GET /offers/deal/$dealId1/ranked" $r.__msg }

$r = Api "GET" "/offers/detail/$offerId1"
if (IsOk $r) { ok "GET /offers/detail/$offerId1 => OK" } else { fail "GET /offers/detail/$offerId1" $r.__msg }

$r = Api "GET" "/offers/$offerId1/remaining"
if (IsOk $r) { ok "GET /offers/$offerId1/remaining => OK" } else { fail "GET /offers/$offerId1/remaining" $r.__msg }

$v36offersUrl = "/v3_6/offers?deal_id=$dealId1"
$r = Api "GET" $v36offersUrl
if (IsOk $r) { ok "GET /v3_6/offers?deal_id=$dealId1 => OK" } else { fail "GET /v3_6/offers?deal_id=$dealId1" $r.__msg }

# ---------------------------------------------------------------------------
# [4] Reservation list
# ---------------------------------------------------------------------------
Write-Host "`n[4] Reservation list" -ForegroundColor Yellow

$r = Api "GET" "/reservations/buyer/$buyerId1"
if (IsOk $r) { ok "GET /reservations/buyer/$buyerId1 => OK" } else { fail "GET /reservations/buyer/$buyerId1" $r.__msg }

$r = Api "GET" "/reservations/seller/$sellerId1"
if (IsOk $r) { ok "GET /reservations/seller/$sellerId1 => OK" } else { fail "GET /reservations/seller/$sellerId1" $r.__msg }

$r = Api "GET" "/v3_6/by-id/$paidResId"
if (IsOk $r) { ok "GET /v3_6/by-id/$paidResId => status=$($r.status)" } else { fail "GET /v3_6/by-id/$paidResId" $r.__msg }

$r = Api "GET" "/v3_6/refund/summary/$paidResId"
if (IsOk $r) { ok "GET /v3_6/refund/summary/$paidResId => OK" } else { fail "GET /v3_6/refund/summary/$paidResId" $r.__msg }

# ---------------------------------------------------------------------------
# [5] Spectator read
# ---------------------------------------------------------------------------
Write-Host "`n[5] Spectator read" -ForegroundColor Yellow

$r = Api "GET" "/spectator/viewers/$dealIdNew"
if (IsOk $r) { ok "GET /spectator/viewers/$dealIdNew => viewer_count=$($r.viewer_count)" } else { fail "GET /spectator/viewers/$dealIdNew" $r.__msg }

$r = Api "GET" "/spectator/predictions/$dealIdNew"
if (IsOk $r) { ok "GET /spectator/predictions/$dealIdNew => count=$($r.predictions_count)" } else { fail "GET /spectator/predictions/$dealIdNew" $r.__msg }

# URL construction: avoid string interpolation ambiguity with ?
$predUrl = "/spectator/predictions/" + $dealIdNew.ToString() + "?buyer_id=3"
$r = Api "GET" $predUrl
if (IsOk $r) { ok "GET /spectator/predictions/$dealIdNew`?buyer_id=3 => count=$($r.predictions_count)" } else { fail "GET /spectator/predictions/$dealIdNew`?buyer_id=3" $r.__msg }

$r = Api "GET" "/spectator/predictions/$dealIdNew/count"
if (IsOk $r) { ok "GET /spectator/predictions/$dealIdNew/count => OK" } else { fail "GET /spectator/predictions/$dealIdNew/count" $r.__msg }

$myPredUrl = "/spectator/my_predictions?buyer_id=3"
$r = Api "GET" $myPredUrl
if (IsOk $r) { ok "GET /spectator/my_predictions?buyer_id=3 => OK" } else { fail "GET /spectator/my_predictions?buyer_id=3" $r.__msg }

$r = Api "GET" "/spectator/rankings?year_month=2026-02"
if (IsOk $r) { ok "GET /spectator/rankings => OK" } else { fail "GET /spectator/rankings" $r.__msg }

# ---------------------------------------------------------------------------
# [6] Spectator settle
# ---------------------------------------------------------------------------
Write-Host "`n[6] Spectator settle" -ForegroundColor Yellow

$r = Api "POST" "/spectator/settle/$dealIdNew" -Body @{}
if (IsOk $r) { ok "POST /spectator/settle/$dealIdNew => settled=$($r.settled), processed=$($r.processed)" } else { fail "POST /spectator/settle/$dealIdNew" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [7] Payment / Settlement read
# ---------------------------------------------------------------------------
Write-Host "`n[7] Payment / Settlement read" -ForegroundColor Yellow

$r = Api "GET" "/payments/settlements"
if (IsOk $r) { ok "GET /payments/settlements => OK" } else { fail "GET /payments/settlements" $r.__msg }

$r = Api "GET" "/payments/settlements?status_filter=PAID"
if (IsOk $r) { ok "GET /payments/settlements?status_filter=PAID => OK" } else { fail "GET /payments/settlements?status_filter=PAID" $r.__msg }

$r = Api "GET" "/payments/settlements/$sellerId1"
if (IsOk $r) { ok "GET /payments/settlements/$sellerId1 => OK" } else { fail "GET /payments/settlements/$sellerId1" $r.__msg }

$r = Api "GET" "/settlements/seller/$sellerId1"
if (IsOk $r) { ok "GET /settlements/seller/$sellerId1 => OK" } else { fail "GET /settlements/seller/$sellerId1" $r.__msg }

# Use an existing paid reservation (13 has known settlements)
$r = Api "GET" "/settlements/reservation/13"
if (IsOk $r) { ok "GET /settlements/reservation/13 => OK" } else { fail "GET /settlements/reservation/13" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [8] Settlement batch: payout_due + execute
# ---------------------------------------------------------------------------
Write-Host "`n[8] Settlement batch" -ForegroundColor Yellow

$r = Api "POST" "/payments/settlements/payout_due"
if (IsOk $r) { ok "POST /payments/settlements/payout_due => paid_count=$($r.paid_count)" } else { fail "POST /payments/settlements/payout_due" "$($r.__sc) $($r.__msg)" }

$r = Api "POST" "/settlements/payout/execute" -Body @{}
if (IsOk $r) { ok "POST /settlements/payout/execute => success=$($r.success)" } else { fail "POST /settlements/payout/execute" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [9] Reviews read
# ---------------------------------------------------------------------------
Write-Host "`n[9] Reviews" -ForegroundColor Yellow

$r = Api "GET" "/reviews/seller/$sellerId1"
if (IsOk $r) { ok "GET /reviews/seller/$sellerId1 => OK" } else { fail "GET /reviews/seller/$sellerId1" $r.__msg }

$r = Api "GET" "/reviews/seller/$sellerId1/summary"
if (IsOk $r) { ok "GET /reviews/seller/$sellerId1/summary => OK" } else { fail "GET /reviews/seller/$sellerId1/summary" $r.__msg }

# ---------------------------------------------------------------------------
# [10] Notifications
# ---------------------------------------------------------------------------
Write-Host "`n[10] Notifications" -ForegroundColor Yellow

$r = Api "GET" "/notifications/buyer/$buyerId1"
if (IsOk $r) { ok "GET /notifications/buyer/$buyerId1 => OK" } else { fail "GET /notifications/buyer/$buyerId1" $r.__msg }

# ---------------------------------------------------------------------------
# [11] Reports read + admin resolve
# ---------------------------------------------------------------------------
Write-Host "`n[11] Reports" -ForegroundColor Yellow

$myRptUrl = "/reports/my?reporter_id=1&reporter_type=buyer"
$r = Api "GET" $myRptUrl
if (IsOk $r) { ok "GET /reports/my => OK" } else { fail "GET /reports/my" $r.__msg }

$r = Api "GET" "/admin/reports"
if (IsOk $r) { ok "GET /admin/reports => OK" } else { fail "GET /admin/reports" $r.__msg }

if ($reportId -gt 0) {
    # ResolveRequest requires: resolution (str)
    $r = Api "POST" "/admin/reports/$reportId/resolve" -Body @{
        resolution   = "warn_seller"
        action_taken = "TestResolve"
    }
    if (IsOk $r) { ok "POST /admin/reports/$reportId/resolve => OK" } else { fail "POST /admin/reports/$reportId/resolve" "$($r.__sc) $($r.__msg)" }
}

# ---------------------------------------------------------------------------
# [12] Delivery
# ---------------------------------------------------------------------------
Write-Host "`n[12] Delivery" -ForegroundColor Yellow

$r = Api "GET" "/delivery/carriers"
if (IsOk $r) { ok "GET /delivery/carriers => OK" } else { fail "GET /delivery/carriers" $r.__msg }

$r = Api "GET" "/delivery/track/$paidResId"
if (IsOk $r) { ok "GET /delivery/track/$paidResId => status=$($r.status)" } else { fail "GET /delivery/track/$paidResId" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [13] Anomaly detect
# ---------------------------------------------------------------------------
Write-Host "`n[13] Anomaly" -ForegroundColor Yellow

$r = Api "GET" "/admin/anomaly/detect?lookback_hours=24"
if (IsOk $r) { ok "GET /admin/anomaly/detect => OK" } else { fail "GET /admin/anomaly/detect" $r.__msg }

# ---------------------------------------------------------------------------
# [14] Policy proposals: list + approve
#     ReviewRequest: reviewed_by (string), review_note (optional string)
# ---------------------------------------------------------------------------
Write-Host "`n[14] Policy proposals" -ForegroundColor Yellow

$r = Api "GET" "/admin/policy/proposals"
if (IsOk $r) { ok "GET /admin/policy/proposals => OK" } else { fail "GET /admin/policy/proposals" $r.__msg }

if ($proposalId -gt 0) {
    $r = Api "GET" "/admin/policy/proposals/$proposalId"
    if (IsOk $r) { ok "GET /admin/policy/proposals/$proposalId => OK" } else { fail "GET /admin/policy/proposals/$proposalId" $r.__msg }

    # reviewed_by must be STRING
    $r = Api "POST" "/admin/policy/proposals/$proposalId/approve" -Body @{
        reviewed_by = "admin"
        review_note = "Approved in test"
    }
    if (IsOk $r) { ok "POST /admin/policy/proposals/$proposalId/approve => OK" } else { fail "POST /admin/policy/proposals/$proposalId/approve" "$($r.__sc) $($r.__msg)" }
}

# ---------------------------------------------------------------------------
# [15] Admin users
# ---------------------------------------------------------------------------
Write-Host "`n[15] Admin users" -ForegroundColor Yellow

$r = Api "GET" "/admin/users/banned"
if (IsOk $r) { ok "GET /admin/users/banned => count=$($r.Count)" } else { fail "GET /admin/users/banned" $r.__msg }

# ---------------------------------------------------------------------------
# [16] Dashboard / Insights
# ---------------------------------------------------------------------------
Write-Host "`n[16] Dashboard / Insights" -ForegroundColor Yellow

$r = Api "GET" "/dashboard/buyer/$buyerId1"
if (IsOk $r) { ok "GET /dashboard/buyer/$buyerId1 => OK" } else { fail "GET /dashboard/buyer/$buyerId1" $r.__msg }

$r = Api "GET" "/dashboard/seller/$sellerId1"
if (IsOk $r) { ok "GET /dashboard/seller/$sellerId1 => OK" } else { fail "GET /dashboard/seller/$sellerId1" $r.__msg }

$r = Api "GET" "/insights/buyer/$buyerId1/overview"
if (IsOk $r) { ok "GET /insights/buyer/$buyerId1/overview => OK" } else { fail "GET /insights/buyer/$buyerId1/overview" $r.__msg }

$r = Api "GET" "/insights/seller/$sellerId1/overview"
if (IsOk $r) { ok "GET /insights/seller/$sellerId1/overview => OK" } else { fail "GET /insights/seller/$sellerId1/overview" $r.__msg }

# ---------------------------------------------------------------------------
# [17] Preview pack (requires user_id query param)
# NOTE: use ${var} braces or string concat — bare $var?param=val confuses PS5
# ---------------------------------------------------------------------------
Write-Host "`n[17] Preview pack" -ForegroundColor Yellow

$prevDealUrl = "/preview/deal/" + $dealId1 + "?user_id=" + $buyerId1
$r = Api "GET" $prevDealUrl
if (IsOk $r) { ok "GET /preview/deal/$dealId1`?user_id=$buyerId1 => OK" } else { fail "GET /preview/deal/$dealId1" "$($r.__sc) $($r.__msg)" }

$prevBuyerUrl = "/preview/buyer/" + $buyerId1 + "?user_id=" + $buyerId1
$r = Api "GET" $prevBuyerUrl
if (IsOk $r) { ok "GET /preview/buyer/$buyerId1`?user_id=$buyerId1 => OK" } else { fail "GET /preview/buyer/$buyerId1" "$($r.__sc) $($r.__msg)" }

$prevSellerUrl = "/preview/seller/" + $sellerId1 + "?user_id=" + $buyerId1
$r = Api "GET" $prevSellerUrl
if (IsOk $r) { ok "GET /preview/seller/$sellerId1`?user_id=$buyerId1 => OK" } else { fail "GET /preview/seller/$sellerId1" "$($r.__sc) $($r.__msg)" }

$prevResUrl = "/preview/reservation/" + $paidResId + "?user_id=" + $buyerId1
$r = Api "GET" $prevResUrl
if (IsOk $r) { ok "GET /preview/reservation/$paidResId`?user_id=$buyerId1 => OK" } else { fail "GET /preview/reservation/$paidResId" "$($r.__sc) $($r.__msg)" }

$prevOfferUrl = "/preview/offer/" + $offerId1 + "?user_id=" + $buyerId1
$r = Api "GET" $prevOfferUrl
if (IsOk $r) { ok "GET /preview/offer/$offerId1`?user_id=$buyerId1 => OK" } else { fail "GET /preview/offer/$offerId1" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [18] Activity log
# ---------------------------------------------------------------------------
Write-Host "`n[18] Activity log" -ForegroundColor Yellow

$r = Api "GET" "/activity/by-buyer/$buyerId1"
if (IsOk $r) { ok "GET /activity/by-buyer/$buyerId1 => OK" } else { fail "GET /activity/by-buyer/$buyerId1" $r.__msg }

$r = Api "GET" "/activity/by-seller/$sellerId1"
if (IsOk $r) { ok "GET /activity/by-seller/$sellerId1 => OK" } else { fail "GET /activity/by-seller/$sellerId1" $r.__msg }

$r = Api "GET" "/activity/by-deal/$dealId1"
if (IsOk $r) { ok "GET /activity/by-deal/$dealId1 => OK" } else { fail "GET /activity/by-deal/$dealId1" $r.__msg }

# ---------------------------------------------------------------------------
# [19] Policy status
# ---------------------------------------------------------------------------
Write-Host "`n[19] Policy status" -ForegroundColor Yellow

$r = Api "GET" "/admin/policy/status"
if (IsOk $r) { ok "GET /admin/policy/status => OK" } else { fail "GET /admin/policy/status" $r.__msg }

# ---------------------------------------------------------------------------
# [20] Pingpong AI (schema: screen + question required)
# ---------------------------------------------------------------------------
Write-Host "`n[20] Pingpong AI" -ForegroundColor Yellow

$r = Api "POST" "/v3_6/pingpong/ask" -Body @{
    screen   = "home"
    question = "What is the refund policy?"
    user_id  = $buyerId1
    role     = "buyer"
}
if (IsOk $r) { ok "POST /v3_6/pingpong/ask => OK" } else { fail "POST /v3_6/pingpong/ask" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [21] Dispute open / close
# ---------------------------------------------------------------------------
Write-Host "`n[21] Dispute" -ForegroundColor Yellow

$r = Api "POST" "/v3_6/$paidResId/dispute/open" -Body @{
    reason   = "TestDispute"
    buyer_id = $buyerId1
}
if (IsOk $r) { ok "POST /v3_6/$paidResId/dispute/open => OK" } elseif ($r.__sc -eq 409) {
    ok "POST /v3_6/$paidResId/dispute/open => already in dispute (409)"
} else { fail "POST /v3_6/$paidResId/dispute/open" "$($r.__sc) $($r.__msg)" }

$r = Api "POST" "/v3_6/$paidResId/dispute/close" -Body @{
    resolution = "seller_fault"
    admin_id   = 1
}
if (IsOk $r) { ok "POST /v3_6/$paidResId/dispute/close => OK" } else { fail "POST /v3_6/$paidResId/dispute/close" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Part 2 Summary" -ForegroundColor Cyan
Write-Host "  PASS : $PASS" -ForegroundColor Green
$fc = if ($FAIL -gt 0) { "Red" } else { "Green" }
Write-Host "  FAIL : $FAIL" -ForegroundColor $fc
Write-Host "=============================================" -ForegroundColor Cyan

exit $(if ($FAIL -gt 0) { 1 } else { 0 })
