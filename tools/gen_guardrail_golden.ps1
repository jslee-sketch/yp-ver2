# tools/gen_guardrail_golden.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# UTF-8 안정화 (한글 깨짐 최소화)
try {
  $OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {}

. "$PSScriptRoot/_guardrail_snapshot.ps1"

$BASE = "http://127.0.0.1:9000"

# 0) DB reset + fullflow
curl.exe -s -X POST "$BASE/admin/simulate/fullflow?reset_db=true" | Out-Null

# 1) S2 target update
$null = Invoke-RestMethod -Method Patch `
  -Uri "$BASE/deals/1/target" `
  -ContentType "application/json" `
  -Body '{"target_price": 777}'

# 2) S3 anchor inject
$null = Invoke-RestMethod -Method Post `
  -Uri "$BASE/admin/anchor/deal/1" `
  -ContentType "application/json" `
  -Body '{"anchor_price": 1000, "evidence_score": 80, "anchor_confidence": 1.0}'

# 3) Fetch previews (raw)
$dealJsonRaw  = curl.exe -s "$BASE/preview/deal/1?user_id=1&role=BUYER"
$offerJsonRaw = curl.exe -s "$BASE/preview/offer/2?user_id=1&role=BUYER"

if (-not $dealJsonRaw -or $dealJsonRaw.Trim().Length -lt 2) { throw "Empty deal preview response" }
if (-not $offerJsonRaw -or $offerJsonRaw.Trim().Length -lt 2) { throw "Empty offer preview response" }

# 4) Parse JSON (PS5.1 compatible: no -Depth)
$dealObj  = $dealJsonRaw  | ConvertFrom-Json
$offerObj = $offerJsonRaw | ConvertFrom-Json

# 5) Stable snapshots
$dealStable  = ConvertTo-StableDealSnapshot  -DealPreview $dealObj
$offerStable = ConvertTo-StableOfferSnapshot -OfferPreview $offerObj

# 6) Write golden
$goldDir = Join-Path $PSScriptRoot "golden"
New-Item -ItemType Directory -Force -Path $goldDir | Out-Null

$dealOut  = Join-Path $goldDir "deal_guardrail.golden.json"
$offerOut = Join-Path $goldDir "offer_guardrail.golden.json"

# ConvertTo-Json -Depth는 PS5에도 존재하므로 여기서는 OK
($dealStable  | ConvertTo-Json -Depth 50) | Out-File -Encoding utf8 $dealOut
($offerStable | ConvertTo-Json -Depth 50) | Out-File -Encoding utf8 $offerOut

Write-Host "OK: wrote golden snapshots"
Write-Host " - $dealOut"
Write-Host " - $offerOut"