# scripts/test_all.ps1
# 역핑 백엔드 통합 테스트 — Part1 + Part2 순서 실행 + 합산 결과 출력
# 실행: .\test_all.ps1
# 인코딩: UTF-8 BOM

param(
    [string]$Base = "http://127.0.0.1:9000"
)

$ErrorActionPreference = "Continue"
$startTime = Get-Date

Write-Host ""
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  역핑 통합 테스트 ALL (Part1 + Part2)" -ForegroundColor Yellow
Write-Host "  시작: $startTime" -ForegroundColor DarkGray
Write-Host "  서버: $Base" -ForegroundColor DarkGray
Write-Host "=================================================" -ForegroundColor Yellow

# ─── 서버 기동 확인 ───────────────────────────────────────────────────────────
try {
    $health = Invoke-RestMethod -Uri "$Base/health" -ErrorAction Stop
    if (-not $health.ok) { throw "ok != true" }
    Write-Host "`n[OK] 서버 연결 확인" -ForegroundColor Green
} catch {
    Write-Host "`n[ERROR] 서버 응답 없음 — $Base/health 실패" -ForegroundColor Red
    Write-Host "  힌트: uvicorn app.main:app --host 0.0.0.0 --port 9000" -ForegroundColor DarkGray
    exit 1
}

$scriptDir = $PSScriptRoot

# ─── Part 1 실행 ──────────────────────────────────────────────────────────────
Write-Host "`n----- Part 1 시작 -----" -ForegroundColor Cyan
$p1 = & powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File "$scriptDir\test_part1.ps1" -Base $Base `
    -IdsFile "$scriptDir\test_ids.json" 2>&1

$p1 | Write-Host

# Part 1 PASS/FAIL 파싱
$p1Pass = ($p1 | Select-String "\[PASS\]").Count
$p1Fail = ($p1 | Select-String "\[FAIL\]").Count

Write-Host ""
Write-Host "  [Part 1] PASS=$p1Pass  FAIL=$p1Fail" -ForegroundColor $(if ($p1Fail -gt 0) {"Red"} else {"Green"})

# ─── Part 2 실행 ──────────────────────────────────────────────────────────────
Write-Host "`n----- Part 2 시작 -----" -ForegroundColor Cyan
$p2 = & powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File "$scriptDir\test_part2.ps1" -Base $Base `
    -IdsFile "$scriptDir\test_ids.json" 2>&1

$p2 | Write-Host

$p2Pass = ($p2 | Select-String "\[PASS\]").Count
$p2Fail = ($p2 | Select-String "\[FAIL\]").Count

Write-Host ""
Write-Host "  [Part 2] PASS=$p2Pass  FAIL=$p2Fail" -ForegroundColor $(if ($p2Fail -gt 0) {"Red"} else {"Green"})

# ─── 최종 요약 ────────────────────────────────────────────────────────────────
$totalPass = $p1Pass + $p2Pass
$totalFail = $p1Fail + $p2Fail
$elapsed   = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)

Write-Host ""
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  최종 결과 요약" -ForegroundColor Yellow
Write-Host "  Part 1  : PASS=$p1Pass  FAIL=$p1Fail" -ForegroundColor $(if ($p1Fail -gt 0) {"Red"} else {"Green"})
Write-Host "  Part 2  : PASS=$p2Pass  FAIL=$p2Fail" -ForegroundColor $(if ($p2Fail -gt 0) {"Red"} else {"Green"})
Write-Host "  ─────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  합계    : PASS=$totalPass  FAIL=$totalFail" -ForegroundColor $(if ($totalFail -gt 0) {"Red"} else {"Green"})
Write-Host "  소요 시간: ${elapsed}s" -ForegroundColor DarkGray
Write-Host "=================================================" -ForegroundColor Yellow

if ($totalFail -gt 0) {
    Write-Host "`n[!] 실패 항목이 있습니다 — 위 [FAIL] 로그를 확인하세요." -ForegroundColor Red
    exit 1
} else {
    Write-Host "`n[OK] 모든 테스트 통과!" -ForegroundColor Green
    exit 0
}
