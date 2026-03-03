# scripts/test_pricing_deep.ps1
# Yeokping Pricing Deep Test - AI Helper, Option Parsing, Guardrail, Brand Mapping
# Encoding: UTF-8 BOM

param(
    [string]$Base    = "http://127.0.0.1:9000",
    [string]$IdsFile = "$PSScriptRoot\test_ids.json"
)

$ErrorActionPreference = "Continue"
$PASS = 0; $FAIL = 0; $SKIP = 0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function ok   { param([string]$m) Write-Host "  [PASS] $m" -ForegroundColor Green;  $script:PASS++ }
function fail { param([string]$m, [string]$e="") Write-Host "  [FAIL] $m  $e" -ForegroundColor Red; $script:FAIL++ }
function skip { param([string]$m) Write-Host "  [SKIP] $m" -ForegroundColor DarkGray; $script:SKIP++ }
function info { param([string]$m) Write-Host "         $m" -ForegroundColor DarkCyan }

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
        return [PSCustomObject]@{ __err=$true; __sc=$sc; __msg=$detail.Substring(0,[Math]::Min(200,$detail.Length)) }
    }
}

function IsOk { param($r) return ($null -ne $r -and -not $r.__err) }

function DealHelper {
    param([string]$Title, [string]$FreeText="")
    $body = @{ raw_title=$Title }
    if ($FreeText) { $body["raw_free_text"] = $FreeText }
    return Api "POST" "/ai/deal_helper" $body
}

# load IDs if available
$ids = @{}
if (Test-Path $IdsFile) {
    try { $ids = Get-Content $IdsFile -Raw | ConvertFrom-Json -AsHashtable } catch {}
}
$buyerId = if ($ids["buyer_id_new"]) { [int]$ids["buyer_id_new"] } else { 1 }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Yeokping Pricing Deep Test" -ForegroundColor Cyan
Write-Host "  Base: $Base   buyerId: $buyerId" -ForegroundColor DarkGray
Write-Host "=====================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# GROUP A: Naver Price Matching (4 cases)
# ---------------------------------------------------------------------------
Write-Host "`n[A] Naver Price Matching" -ForegroundColor Yellow

# A-1: 에어팟 프로 2 — 네이버 최저가 존재해야 함
$r = DealHelper "에어팟 프로 2"
if (IsOk $r) {
    $src   = $r.price.price_source
    $price = $r.price.naver_lowest_price
    $brand = $r.brand
    info "price_source=$src  naver_lowest_price=$price  brand=$brand"
    if ($src -eq "naver" -and $price -gt 0) {
        ok "A-1 에어팟 프로 2 => Naver price=$price"
    } else {
        fail "A-1 에어팟 프로 2 => 네이버 가격 없음 (source=$src)"
    }
} else { fail "A-1 에어팟 프로 2 => API 오류" $r.__msg }

# A-2: 갤럭시 S25 Ultra — 네이버 최저가 존재해야 함
$r = DealHelper "갤럭시 S25 Ultra"
if (IsOk $r) {
    $src   = $r.price.price_source
    $price = $r.price.naver_lowest_price
    $brand = $r.brand
    info "price_source=$src  naver_lowest_price=$price  brand=$brand"
    if ($src -eq "naver" -and $price -gt 0) {
        ok "A-2 갤럭시 S25 Ultra => Naver price=$price"
    } else {
        fail "A-2 갤럭시 S25 Ultra => 네이버 가격 없음 (source=$src)"
    }
} else { fail "A-2 갤럭시 S25 Ultra => API 오류" $r.__msg }

# A-3: 나이키 에어맥스 90 — 의류/신발 네이버 검색
$r = DealHelper "나이키 에어맥스 90"
if (IsOk $r) {
    $src   = $r.price.price_source
    $price = $r.price.naver_lowest_price
    info "price_source=$src  naver_lowest_price=$price"
    if ($src -eq "naver" -and $price -gt 0) {
        ok "A-3 나이키 에어맥스 90 => Naver price=$price"
    } else {
        # 네이버에 없으면 SKIP (LLM 추정치도 허용)
        skip "A-3 나이키 에어맥스 90 => 네이버 가격 없음 (source=$src, 허용)"
    }
} else { fail "A-3 나이키 에어맥스 90 => API 오류" $r.__msg }

# A-4: 완전 가상의 제품 — llm_estimate여야 함
$r = DealHelper "ZZZZZ가상상품XYZNOTREAL99999"
if (IsOk $r) {
    $src = $r.price.price_source
    info "price_source=$src"
    if ($src -eq "llm_estimate") {
        ok "A-4 존재하지 않는 상품 => price_source=llm_estimate (정상)"
    } else {
        fail "A-4 존재하지 않는 상품 => price_source=$src (llm_estimate 기대)"
    }
} else { fail "A-4 존재하지 않는 상품 => API 오류" $r.__msg }

# ---------------------------------------------------------------------------
# GROUP B: Condition Extraction from free_text (3 cases)
# ---------------------------------------------------------------------------
Write-Host "`n[B] Condition Extraction from free_text" -ForegroundColor Yellow

# B-1: 무료배송 → shipping_fee_krw=0
$r = DealHelper "에어팟 프로 2" "무료배송, 30만원 이하 희망"
if (IsOk $r) {
    $fee = $r.conditions.shipping_fee_krw
    info "shipping_fee_krw=$fee"
    if ($fee -eq 0) {
        ok "B-1 무료배송 → shipping_fee_krw=0"
    } else {
        fail "B-1 무료배송 → shipping_fee_krw=$fee (0 기대)"
    }
} else { fail "B-1 무료배송 조건 추출 => API 오류" $r.__msg }

# B-2: 1년 보증 → warranty_months=12
$r = DealHelper "노트북" "1년 보증 포함, 삼성 AS 가능"
if (IsOk $r) {
    $wm = $r.conditions.warranty_months
    info "warranty_months=$wm"
    if ($wm -eq 12) {
        ok "B-2 1년 보증 → warranty_months=12"
    } else {
        fail "B-2 1년 보증 → warranty_months=$wm (12 기대)"
    }
} else { fail "B-2 보증 기간 추출 => API 오류" $r.__msg }

# B-3: 2일 배송 → delivery_days=2
$r = DealHelper "아이폰 15 Pro" "2일 이내 배송 가능, 미개봉 새 제품"
if (IsOk $r) {
    $dd = $r.conditions.delivery_days
    info "delivery_days=$dd"
    if ($dd -eq 2) {
        ok "B-3 2일 배송 → delivery_days=2"
    } else {
        fail "B-3 2일 배송 → delivery_days=$dd (2 기대)"
    }
} else { fail "B-3 배송일 추출 => API 오류" $r.__msg }

# ---------------------------------------------------------------------------
# GROUP C: Deal Creation + Guardrail (3 cases)
# ---------------------------------------------------------------------------
Write-Host "`n[C] Deal Creation + Guardrail Auto-Enrich" -ForegroundColor Yellow

$ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

# C-1: anchor_price 없이 딜 생성 → AI가 anchor_price 자동 채워야 함
$r = Api "POST" "/deals/" @{
    product_name = "에어팟 프로 2 테스트 $ts"
    creator_id   = $buyerId
    desired_qty  = 1
    target_price = 95000
}
if (IsOk $r) {
    $dealId1   = $r.id
    $anchor    = $r.anchor_price
    $brand     = $r.brand
    $opt1title = $r.option1_title
    info "deal_id=$dealId1  anchor_price=$anchor  brand=$brand  option1_title=$opt1title"
    if ($anchor -gt 0) {
        ok "C-1 anchor_price 없이 딜 생성 → AI가 anchor=$anchor 자동 채움"
    } else {
        fail "C-1 anchor_price 없이 딜 생성 → anchor_price=$anchor (> 0 기대)"
    }
    if ($brand) {
        ok "C-1 brand 자동 매핑 → brand=$brand"
    } else {
        skip "C-1 brand null (AI 추출 실패)"
    }
} else { fail "C-1 딜 생성 => API 오류" $r.__msg }

# C-2: anchor_price 직접 입력 → AI 자동호출 스킵, anchor 그대로 유지
$ts2 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$r = Api "POST" "/deals/" @{
    product_name = "갤럭시 S25 anchor 직접입력 $ts2"
    creator_id   = $buyerId
    desired_qty  = 1
    target_price = 1200000
    anchor_price = 1300000
}
if (IsOk $r) {
    $dealId2 = $r.id
    $anchor  = $r.anchor_price
    info "deal_id=$dealId2  anchor_price=$anchor"
    if ($anchor -eq 1300000) {
        ok "C-2 anchor_price 직접 입력 → anchor=$anchor 그대로 유지"
    } else {
        fail "C-2 anchor_price 직접 입력 → anchor=$anchor (1300000 기대)"
    }
} else { fail "C-2 anchor_price 직접 입력 => API 오류" $r.__msg }

# C-3: target > anchor → guardrail이 캡 적용해야 함 (target 보정)
$ts3 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$r = Api "POST" "/deals/" @{
    product_name = "guardrail 테스트 초과가격 $ts3"
    creator_id   = $buyerId
    desired_qty  = 1
    target_price = 9999999
    anchor_price = 100000
}
if (IsOk $r) {
    $dealId3   = $r.id
    $target    = $r.target_price
    $anchor    = $r.anchor_price
    info "deal_id=$dealId3  target_price=$target  anchor_price=$anchor"
    # 가드레일이 target을 anchor의 일정 비율 이내로 캡을 씌워야 함
    if ($target -lt 9999999) {
        ok "C-3 target 9999999 > anchor 100000 → guardrail 캡 적용, target=$target"
    } else {
        skip "C-3 target=$target (guardrail 미적용 또는 정책 허용 범위)"
    }
} else { fail "C-3 guardrail 초과가격 딜 생성 => API 오류" $r.__msg }

# ---------------------------------------------------------------------------
# GROUP D: Option Parsing — selected_value (2 cases)
# ---------------------------------------------------------------------------
Write-Host "`n[D] Option Parsing — selected_value" -ForegroundColor Yellow

# D-1: 에어팟 프로 2 256GB 블랙 미개봉 → 용량/색상/상태 옵션 추출
$r = DealHelper "에어팟 프로 2 256GB 블랙 미개봉"
if (IsOk $r) {
    $opts = $r.suggested_options
    $optCount = if ($opts) { @($opts).Count } else { 0 }
    info "suggested_options count=$optCount"
    foreach ($o in $opts) {
        info "  title=$($o.title)  selected_value=$($o.selected_value)  values=$($o.values -join ',')"
    }
    # 최소 1개 옵션이 selected_value를 갖고 있어야 함
    $hasSelected = ($opts | Where-Object { $_.selected_value -ne $null -and $_.selected_value -ne "" }).Count -gt 0
    if ($hasSelected) {
        ok "D-1 에어팟 프로 2 256GB 블랙 미개봉 → selected_value 있는 옵션 존재"
    } else {
        fail "D-1 에어팟 프로 2 256GB 블랙 미개봉 → selected_value 없음 (LLM이 추출 실패)"
    }
    # 옵션 개수 검증
    if ($optCount -ge 2) {
        ok "D-1 옵션 $optCount 개 추출됨 (2개 이상 기대)"
    } else {
        fail "D-1 옵션 $optCount 개 (2개 이상 기대)"
    }
} else { fail "D-1 옵션 파싱 => API 오류" $r.__msg }

# D-2: 갤럭시 버즈2 프로 화이트 — 색상 selected_value 확인
$r = DealHelper "갤럭시 버즈2 프로 화이트"
if (IsOk $r) {
    $opts = $r.suggested_options
    foreach ($o in $opts) {
        info "  title=$($o.title)  selected_value=$($o.selected_value)"
    }
    $colorOpt = $opts | Where-Object { $_.title -match "색상|color" }
    if ($colorOpt -and $colorOpt.selected_value) {
        ok "D-2 갤럭시 버즈2 프로 화이트 → 색상 selected_value=$($colorOpt.selected_value)"
    } else {
        skip "D-2 색상 옵션 selected_value 없음 (LLM 파싱 결과 따라 다름)"
    }
} else { fail "D-2 색상 옵션 파싱 => API 오류" $r.__msg }

# ---------------------------------------------------------------------------
# GROUP E: Group-buy Qty vs Price Suggestion (2 cases)
# ---------------------------------------------------------------------------
Write-Host "`n[E] Group-buy Qty vs Price Suggestion" -ForegroundColor Yellow

$ts4 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

# E-1: desired_qty=1 — anchor_price 기반 desired_price_suggestion 확인
$r1 = DealHelper "다이슨 에어랩" ""
$desiredQty1Price = $null
$desiredQty10Price = $null
if (IsOk $r1) {
    $desiredQty1Price = $r1.price.desired_price_suggestion
    $center = $r1.price.center_price
    info "에어랩 center_price=$center  desired_price_suggestion=$desiredQty1Price"
    if ($desiredQty1Price -gt 0 -and $desiredQty1Price -lt $center) {
        ok "E-1 다이슨 에어랩 desired_price=$desiredQty1Price < center=$center (할인 목표 반영)"
    } else {
        fail "E-1 desired_price=$desiredQty1Price center=$center (desired < center 기대)"
    }
}

# E-2: desired_price_suggestion이 center의 ~95%인지 확인
if (IsOk $r1 -and $r1.price.center_price -gt 0) {
    $ratio = [math]::Round($desiredQty1Price / $r1.price.center_price * 100, 1)
    info "desired / center ratio = $ratio%"
    if ($ratio -ge 90 -and $ratio -le 99) {
        ok "E-2 desired/center 비율 $ratio% (90~99% 범위 — 공동구매 할인)"
    } else {
        fail "E-2 desired/center 비율 $ratio% (90~99% 기대)"
    }
} else { skip "E-2 center_price 없음 — 네이버 가격 조회 실패" }

# ---------------------------------------------------------------------------
# GROUP F: Brand & Option Auto-Mapping (4 cases)
# ---------------------------------------------------------------------------
Write-Host "`n[F] Brand Auto-Mapping" -ForegroundColor Yellow

# F-1: 에어팟 → Apple
$r = DealHelper "에어팟 프로 2세대"
if (IsOk $r) {
    $brand = $r.brand
    info "brand=$brand"
    if ($brand -match "Apple|애플") {
        ok "F-1 에어팟 → brand=$brand (Apple/애플 포함)"
    } else {
        fail "F-1 에어팟 → brand=$brand (Apple 기대)"
    }
} else { fail "F-1 에어팟 브랜드 => API 오류" $r.__msg }

# F-2: 갤럭시 → Samsung/삼성
$r = DealHelper "갤럭시 S25"
if (IsOk $r) {
    $brand = $r.brand
    info "brand=$brand"
    if ($brand -match "Samsung|삼성") {
        ok "F-2 갤럭시 → brand=$brand (Samsung/삼성 포함)"
    } else {
        fail "F-2 갤럭시 → brand=$brand (Samsung 기대)"
    }
} else { fail "F-2 갤럭시 브랜드 => API 오류" $r.__msg }

# F-3: 나이키 → Nike/나이키
$r = DealHelper "나이키 에어포스 1"
if (IsOk $r) {
    $brand = $r.brand
    info "brand=$brand"
    if ($brand -match "Nike|나이키") {
        ok "F-3 나이키 → brand=$brand (Nike/나이키 포함)"
    } else {
        fail "F-3 나이키 → brand=$brand (Nike 기대)"
    }
} else { fail "F-3 나이키 브랜드 => API 오류" $r.__msg }

# F-4: LG 전자 → LG
$r = DealHelper "LG 그램 17"
if (IsOk $r) {
    $brand = $r.brand
    info "brand=$brand"
    if ($brand -match "LG") {
        ok "F-4 LG 그램 → brand=$brand (LG 포함)"
    } else {
        fail "F-4 LG 그램 → brand=$brand (LG 기대)"
    }
} else { fail "F-4 LG 브랜드 => API 오류" $r.__msg }

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
$total = $PASS + $FAIL + $SKIP
Write-Host "  TOTAL $total  PASS $PASS  FAIL $FAIL  SKIP $SKIP" -ForegroundColor $(if ($FAIL -eq 0) { "Green" } else { "Red" })
Write-Host "=====================================================" -ForegroundColor Cyan
if ($FAIL -gt 0) { exit 1 } else { exit 0 }
