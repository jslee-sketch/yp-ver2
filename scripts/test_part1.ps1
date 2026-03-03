# scripts/test_part1.ps1
# Yeokping Backend Integration Test Part 1 - Write / Create Flow
# After completion, IDs are saved to test_ids.json for Part 2.
# Encoding: UTF-8 BOM

param(
    [string]$Base    = "http://127.0.0.1:9000",
    [string]$IdsFile = "$PSScriptRoot\test_ids.json"
)

$ErrorActionPreference = "Continue"
$PASS = 0; $FAIL = 0
$ids  = @{}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function ok   { param([string]$m) Write-Host "  [PASS] $m" -ForegroundColor Green;  $script:PASS++ }
function fail { param([string]$m, [string]$e="") Write-Host "  [FAIL] $m  $e" -ForegroundColor Red; $script:FAIL++ }

function Api {
    param(
        [string]$Method = "GET",
        [string]$Path,
        [hashtable]$Body = $null,
        [switch]$Form
    )
    $url = "$Base$Path"
    try {
        if ($null -ne $Body -and $Method -ne "GET" -and $Method -ne "DELETE") {
            if ($Form) {
                $enc = ($Body.GetEnumerator() | ForEach-Object {
                    "$([uri]::EscapeDataString($_.Key))=$([uri]::EscapeDataString($_.Value))"
                }) -join "&"
                return Invoke-RestMethod -Method $Method -Uri $url -Body $enc `
                    -ContentType "application/x-www-form-urlencoded" -ErrorAction Stop
            } else {
                $json  = $Body | ConvertTo-Json -Depth 6 -Compress
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
                return Invoke-RestMethod -Method $Method -Uri $url -Body $bytes `
                    -ContentType "application/json; charset=utf-8" -ErrorAction Stop
            }
        } elseif ($null -ne $Body -and $Method -eq "DELETE") {
            $json  = $Body | ConvertTo-Json -Depth 6 -Compress
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            return Invoke-RestMethod -Method DELETE -Uri $url -Body $bytes `
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
        return [PSCustomObject]@{ __err=$true; __sc=$sc; __msg=$detail.Substring(0,[Math]::Min(150,$detail.Length)) }
    }
}

function IsOk { param($r) return ($null -ne $r -and -not $r.__err) }

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Yeokping Part 1: Write / Create Flow" -ForegroundColor Cyan
Write-Host "  Base: $Base" -ForegroundColor DarkGray
Write-Host "=============================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# [1] Health
# ---------------------------------------------------------------------------
Write-Host "`n[1] Health" -ForegroundColor Yellow

$r = Api "GET" "/"
if (IsOk $r) { ok "GET / => running" } else { fail "GET /" $r.__msg }

$r = Api "GET" "/health"
if (IsOk $r -and $r.ok) { ok "GET /health => ok" } else { fail "GET /health" $r.__msg }

$r = Api "GET" "/health/deep"
if (IsOk $r -and $r.status) { ok "GET /health/deep => $($r.status)" } else { fail "GET /health/deep" $r.__msg }

$r = Api "GET" "/version"
if (IsOk $r -and $r.version) { ok "GET /version => $($r.version)" } else { fail "GET /version" $r.__msg }

# ---------------------------------------------------------------------------
# [2] Buyer create
# Note: pydantic validates email - must use real TLD (e.g. @gmail.com, not @yp.test)
# ---------------------------------------------------------------------------
Write-Host "`n[2] Buyer create" -ForegroundColor Yellow

$ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$buyerEmail = "t.buyer.${ts}@gmail.com"
$r = Api "POST" "/buyers/" -Body @{
    email    = $buyerEmail
    name     = "TestBuyer$ts"
    password = "test1234"
}
if (IsOk $r -and $r.id) {
    $ids.buyer_id_new = $r.id
    ok "POST /buyers/ => id=$($r.id)"
} else { fail "POST /buyers/" $r.__msg }

# ---------------------------------------------------------------------------
# [3] Auth login
# ---------------------------------------------------------------------------
Write-Host "`n[3] Auth login" -ForegroundColor Yellow

$r = Api "POST" "/auth/login" -Body @{
    username = "buyer0_auto@test.com"
    password = "test1234"
} -Form
if (IsOk $r -and $r.access_token) {
    $ids.token_buyer1 = $r.access_token
    ok "POST /auth/login => token OK"
} else { fail "POST /auth/login" $r.__msg }

# ---------------------------------------------------------------------------
# [4] Seller create (note: newly created seller will be PENDING, not APPROVED)
#     For offers we use existing sellers 1-4 (verified_at already set)
# ---------------------------------------------------------------------------
Write-Host "`n[4] Seller create" -ForegroundColor Yellow

$sellerEmail = "t.seller.${ts}@gmail.com"
# business_number must be unique — use timestamp suffix
$bizNum = "$($ts.ToString().Substring($ts.ToString().Length - 9, 3))-$($ts.ToString().Substring($ts.ToString().Length - 6, 2))-$($ts.ToString().Substring($ts.ToString().Length - 4))"
$r = Api "POST" "/sellers/" -Body @{
    email            = $sellerEmail
    business_name    = "TestSeller$ts"
    business_number  = $bizNum
    phone            = "010-9999-8888"
    address          = "Seoul Test Addr 1"
    zip_code         = "06000"
    established_date = "2020-01-01"
    password         = "test1234"
}
if (IsOk $r -and $r.id) {
    $ids.seller_id_new = $r.id
    ok "POST /sellers/ => id=$($r.id)"
} else { fail "POST /sellers/" $r.__msg }

# ---------------------------------------------------------------------------
# [5] Deal create
# ---------------------------------------------------------------------------
Write-Host "`n[5] Deal create" -ForegroundColor Yellow

$r = Api "POST" "/deals/" -Body @{
    product_name = "TestProduct_$ts"
    creator_id   = 1
    desired_qty  = 3
    target_price = 50000
    anchor_price = 62000
}
if (IsOk $r -and $r.id) {
    $ids.deal_id_new = $r.id
    ok "POST /deals/ => id=$($r.id)"
} else { fail "POST /deals/" $r.__msg }

# ---------------------------------------------------------------------------
# [6] Deal participant add (requires qty field per DealParticipantCreate schema)
# ---------------------------------------------------------------------------
Write-Host "`n[6] Deal participant add" -ForegroundColor Yellow

$dealId = if ($ids.deal_id_new) { $ids.deal_id_new } else { 1 }
$r = Api "POST" "/deals/$dealId/participants" -Body @{
    deal_id  = $dealId
    buyer_id = 2
    qty      = 1
}
if (IsOk $r -and $r.id) {
    $ids.participant_id = $r.id
    ok "POST /deals/$dealId/participants => id=$($r.id)"
} else { fail "POST /deals/$dealId/participants" $r.__msg }

# ---------------------------------------------------------------------------
# [7] Offer create (use existing approved seller, seller_id=2)
# ---------------------------------------------------------------------------
Write-Host "`n[7] Offer create" -ForegroundColor Yellow

$approvedSellerId = 2   # seller 1-4 all have verified_at set
$r = Api "POST" "/offers" -Body @{
    price                        = 48000
    total_available_qty          = 10
    deal_id                      = $dealId
    seller_id                    = $approvedSellerId
    delivery_days                = 3
    cooling_days                 = 7
    shipping_mode                = "NONE"
    shipping_fee_per_reservation = 0
    shipping_fee_per_qty         = 0
    comment                      = "TestOffer"
}
if (IsOk $r -and $r.id) {
    $ids.offer_id_new = $r.id
    ok "POST /offers => id=$($r.id)"
} else { fail "POST /offers" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [8] Reservation create (v3.6)
# ---------------------------------------------------------------------------
Write-Host "`n[8] Reservation create (v3.6)" -ForegroundColor Yellow

$offerId = if ($ids.offer_id_new) { $ids.offer_id_new } else { 6 }
$r = Api "POST" "/v3_6/reservations" -Body @{
    deal_id  = $dealId
    offer_id = $offerId
    buyer_id = 1
    qty      = 1
}
if (IsOk $r -and $r.id) {
    $ids.reservation_id_new = $r.id
    ok "POST /v3_6/reservations => id=$($r.id), status=$($r.status)"
} else { fail "POST /v3_6/reservations" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [9] Pay (v3.6)
# ---------------------------------------------------------------------------
Write-Host "`n[9] Pay (v3.6)" -ForegroundColor Yellow

$resId = if ($ids.reservation_id_new) { $ids.reservation_id_new } else { 115 }
$r = Api "POST" "/v3_6/pay" -Body @{
    reservation_id      = $resId
    buyer_id            = 1
    paid_amount         = 48000
    buyer_point_per_qty = 0
}
if (IsOk $r) {
    $ids.paid_reservation_id = $resId
    ok "POST /v3_6/pay => status=$($r.status)"
} elseif ($r.__sc -eq 400) {
    ok "POST /v3_6/pay => already paid (400 idempotent)"
    $ids.paid_reservation_id = $resId
} else { fail "POST /v3_6/pay" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [10] Refund preview (after paying = PAID state is previewable)
# ---------------------------------------------------------------------------
Write-Host "`n[10] Refund preview (PAID)" -ForegroundColor Yellow

$paidResId = if ($ids.paid_reservation_id) { $ids.paid_reservation_id } else { 116 }
$r = Api "GET" "/v3_6/refund/preview/$paidResId"
if (IsOk $r) { ok "GET /v3_6/refund/preview/$paidResId => OK" } else { fail "GET /v3_6/refund/preview/$paidResId" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [11] Ship (v3.6) — fields: shipping_carrier, tracking_number
# ---------------------------------------------------------------------------
Write-Host "`n[11] Ship (v3.6)" -ForegroundColor Yellow
$r = Api "POST" "/v3_6/reservations/$paidResId/ship" -Body @{
    shipping_carrier = "CJ"
    tracking_number  = "T-$ts"
}
if (IsOk $r) { ok "POST /v3_6/reservations/$paidResId/ship => OK" } else { fail "POST /v3_6/reservations/$paidResId/ship" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [12] Arrival confirm (v3.6)
# ---------------------------------------------------------------------------
Write-Host "`n[12] Arrival confirm" -ForegroundColor Yellow

$r = Api "POST" "/v3_6/reservations/$paidResId/arrival-confirm" -Body @{
    buyer_id = 1
}
if (IsOk $r) { ok "POST /v3_6/reservations/$paidResId/arrival-confirm => OK" } elseif ($r.__sc -eq 409) {
    ok "POST /v3_6/reservations/$paidResId/arrival-confirm => already confirmed (409)"
} else { fail "POST /v3_6/reservations/$paidResId/arrival-confirm" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [13] Review create (existing PAID reservation)
# ---------------------------------------------------------------------------
Write-Host "`n[13] Review create" -ForegroundColor Yellow

$r = Api "POST" "/reviews" -Body @{
    reservation_id = $paidResId
    seller_id      = $approvedSellerId
    buyer_id       = 1
    price_fairness = 4
    quality        = 5
    shipping       = 4
    communication  = 5
    accuracy       = 4
    comment        = "TestReview"
    media_count    = 0
}
if (IsOk $r -and $r.id) {
    $ids.review_id = $r.id
    ok "POST /reviews => id=$($r.id)"
} elseif ($r.__sc -eq 400 -or $r.__sc -eq 409) {
    ok "POST /reviews => already reviewed ($($r.__sc))"
} else { fail "POST /reviews" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [14] Spectator view record (buyer_id as QUERY PARAM)
# ---------------------------------------------------------------------------
Write-Host "`n[14] Spectator view record" -ForegroundColor Yellow

$spectatorViewUrl = "/spectator/view/$dealId" + "?buyer_id=3"
$r = Api "POST" $spectatorViewUrl
if (IsOk $r) { ok "POST /spectator/view/$dealId`?buyer_id=3 => viewer_count=$($r.viewer_count)" } else { fail "POST /spectator/view/$dealId`?buyer_id=3" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [15] Spectator predict
# ---------------------------------------------------------------------------
Write-Host "`n[15] Spectator predict" -ForegroundColor Yellow

$r = Api "POST" "/spectator/predict" -Body @{
    deal_id         = $dealId
    buyer_id        = 3
    predicted_price = 47500
    comment         = "TestPrediction"
}
if (IsOk $r -and $r.id) {
    $ids.prediction_id = $r.id
    ok "POST /spectator/predict => id=$($r.id)"
} elseif ($r.__sc -eq 400) {
    ok "POST /spectator/predict => already submitted or ineligible (400)"
} else { fail "POST /spectator/predict" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [16] Report create
# ---------------------------------------------------------------------------
Write-Host "`n[16] Report create" -ForegroundColor Yellow

$r = Api "POST" "/reports" -Body @{
    reporter_id   = 1
    reporter_type = "buyer"
    target_type   = "seller"
    target_id     = 1
    category      = "fraud"
    description   = "TestReport"
}
if (IsOk $r -and $r.id) {
    $ids.report_id = $r.id
    ok "POST /reports => id=$($r.id)"
} else { fail "POST /reports" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [17] Notification seed
# ---------------------------------------------------------------------------
Write-Host "`n[17] Notification seed" -ForegroundColor Yellow

$r = Api "POST" "/notifications/dev/seed"
if (IsOk $r) { ok "POST /notifications/dev/seed => OK" } else { fail "POST /notifications/dev/seed" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [18] Policy proposal create
#     Schema: ProposalCreate requires title, description, proposal_type
# ---------------------------------------------------------------------------
Write-Host "`n[18] Policy proposal create" -ForegroundColor Yellow

$r = Api "POST" "/admin/policy/proposals" -Body @{
    title             = "Fee Adjustment Proposal $ts"
    description       = "Reduce platform fee to attract more sellers"
    proposal_type     = "parameter_change"
    target_param      = "platform_fee_rate"
    proposed_value    = "0.03"
    evidence_summary  = "Market analysis shows lower fee increases supply"
}
if (IsOk $r -and $r.id) {
    $ids.proposal_id = $r.id
    ok "POST /admin/policy/proposals => id=$($r.id)"
} else { fail "POST /admin/policy/proposals" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [19] Admin: BAN / UNBAN
# ---------------------------------------------------------------------------
Write-Host "`n[19] Admin BAN / UNBAN" -ForegroundColor Yellow

$newBuyerId = if ($ids.buyer_id_new) { $ids.buyer_id_new } else { 5 }
$r = Api "POST" "/admin/users/ban" -Body @{
    user_id   = $newBuyerId
    user_type = "buyer"
    ban_type  = "permanent"
    reason    = "TestBan"
}
if (IsOk $r) { ok "POST /admin/users/ban => OK" } else { fail "POST /admin/users/ban" "$($r.__sc) $($r.__msg)" }

$r = Api "POST" "/admin/users/unban" -Body @{
    user_id   = $newBuyerId
    user_type = "buyer"
}
if (IsOk $r) { ok "POST /admin/users/unban => OK" } else { fail "POST /admin/users/unban" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [20] Password change
# ---------------------------------------------------------------------------
Write-Host "`n[20] Password change" -ForegroundColor Yellow

$r = Api "POST" "/auth/change-password" -Body @{
    user_id          = 1
    user_type        = "buyer"
    current_password = "test1234"
    new_password     = "test1234"
}
if (IsOk $r) { ok "POST /auth/change-password => OK" } else { fail "POST /auth/change-password" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [21] Settlements: refresh_due batch
# ---------------------------------------------------------------------------
Write-Host "`n[21] Settlements refresh_due" -ForegroundColor Yellow

$r = Api "POST" "/payments/settlements/refresh_due"
if (IsOk $r) { ok "POST /payments/settlements/refresh_due => updated=$($r.updated)" } else { fail "POST /payments/settlements/refresh_due" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [22] Settlements: batch-auto-approve
# ---------------------------------------------------------------------------
Write-Host "`n[22] Settlements batch-auto-approve" -ForegroundColor Yellow

$r = Api "POST" "/settlements/batch-auto-approve"
if (IsOk $r) { ok "POST /settlements/batch-auto-approve => OK" } else { fail "POST /settlements/batch-auto-approve" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [23] Offers: dev expire batch
# ---------------------------------------------------------------------------
Write-Host "`n[23] Offers dev/expire" -ForegroundColor Yellow

$r = Api "POST" "/offers/dev/expire"
if (IsOk $r) { ok "POST /offers/dev/expire => OK" } else { fail "POST /offers/dev/expire" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# [24] Deals: dev close_expired batch
# ---------------------------------------------------------------------------
Write-Host "`n[24] Deals dev/close_expired" -ForegroundColor Yellow

$r = Api "POST" "/deals/dev/close_expired"
if (IsOk $r) { ok "POST /deals/dev/close_expired => count=$($r.count)" } else { fail "POST /deals/dev/close_expired" "$($r.__sc) $($r.__msg)" }

# ---------------------------------------------------------------------------
# Save IDs
# ---------------------------------------------------------------------------
$ids | ConvertTo-Json -Depth 3 | Out-File -FilePath $IdsFile -Encoding utf8
Write-Host "`n[Saved] test_ids.json => $IdsFile" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Part 1 Summary" -ForegroundColor Cyan
Write-Host "  PASS : $PASS" -ForegroundColor Green
$fc = if ($FAIL -gt 0) { "Red" } else { "Green" }
Write-Host "  FAIL : $FAIL" -ForegroundColor $fc
Write-Host "=============================================" -ForegroundColor Cyan

exit $(if ($FAIL -gt 0) { 1 } else { 0 })
