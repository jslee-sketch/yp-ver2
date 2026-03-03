$ErrorActionPreference = "Stop"

function Assert($condition, $message) {
    if (-not $condition) {
        Write-Host "FAIL: $message" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "PASS: $message" -ForegroundColor Green
    }
}

function Reset-DB {
    curl.exe -s -X POST "http://127.0.0.1:9000/admin/simulate/fullflow?reset_db=true" | Out-Null
}

function Set-Target([double]$p) {
    Invoke-RestMethod -Method Patch `
      -Uri "http://127.0.0.1:9000/deals/1/target" `
      -ContentType "application/json" `
      -Body ("{`"target_price`": $p}") | Out-Null
}

function Set-Anchor([double]$anchor, [int]$evidence=80, [double]$conf=1.0) {
    Invoke-RestMethod -Method Post `
      -Uri "http://127.0.0.1:9000/admin/anchor/deal/1" `
      -ContentType "application/json" `
      -Body ("{`"anchor_price`": $anchor, `"evidence_score`": $evidence, `"anchor_confidence`": $conf}") | Out-Null
}

function Get-Deal-Guardrail {
    $deal = curl.exe -s "http://127.0.0.1:9000/preview/deal/1?user_id=1&role=BUYER" | ConvertFrom-Json
    return $deal.pack.pricing.guardrail
}

Write-Host "`n=== Guardrail Matrix Smoke ==="

$cases = @(
    @{
        name="A) Anchor missing + target valid => WARN_HARD(EVIDENCE_MISSING or ANCHOR_MISSING)"; 
        target=777; anchor=$null; 
        expectLevel="WARN_HARD"; expectReasons=@("ANCHOR_MISSING")
    },
    @{
        name="B) Target invalid (0) even with anchor => WARN_HARD(TARGET_INVALID)"; 
        target=0; anchor=1000; 
        expectLevel="WARN_HARD"; expectReasons=@("TARGET_INVALID")
    },
    @{
        name="C) Huge gap target<<anchor low evidence => BLOCK or WARN_HARD(GAP_BLOCK)"; 
        target=1; anchor=1000; evidence=0;
        expectLevel="BLOCK"; expectReasons=@("GAP_BLOCK")
    },
    @{
        name="D) Moderate gap + high evidence => relax to ALLOW (E_SCORE_RELAXED)"; 
        target=777; anchor=1000; evidence=80;
        expectLevel="ALLOW"; expectReasons=@("E_SCORE_RELAXED")
    }
)

foreach ($c in $cases) {
    Write-Host "`n--- $($c.name) ---"
    Reset-DB

    Set-Target $c.target

    if ($null -ne $c.anchor) {
        $ev = 80
        if ($c.ContainsKey("evidence")) { $ev = [int]$c.evidence }
        Set-Anchor $c.anchor $ev 1.0
    }

    $g = Get-Deal-Guardrail

    Assert ($g.level -eq $c.expectLevel) "Level == $($c.expectLevel) (got $($g.level))"

    foreach ($r in $c.expectReasons) {
        Assert ($g.reason_codes -contains $r) "reason_codes contains $r"
    }
}

Write-Host "`nALL MATRIX TESTS PASSED"