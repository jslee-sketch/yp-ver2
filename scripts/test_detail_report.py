#!/usr/bin/env python3
# scripts/test_detail_report.py
"""
역핑 DB 상태 상세 리포트 스크립트
콘솔에 요약 출력 + scripts/test_detail_report.json 전체 상세 저장

실행: python scripts/test_detail_report.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows 콘솔 cp949 → UTF-8 강제 (이모지/한글 출력)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]          # C:\dev\yp-ver2
DB_PATH = ROOT / "app" / "ypver2.db"
OUT_PATH = Path(__file__).resolve().parent / "test_detail_report.json"


# ── helpers ─────────────────────────────────────────────────────────────────

def _fmt_krw(v) -> str:
    if v is None:
        return "N/A"
    return f"{int(v):,}원"


def _fmt_dt(v) -> str:
    if v is None:
        return ""
    return str(v)[:16]


def _q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list:
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


def _q1(conn: sqlite3.Connection, sql: str, params: tuple = ()):
    rows = _q(conn, sql, params)
    return rows[0][0] if rows else None


def _safe_int(v, default=0) -> int:
    try:
        return int(v or default)
    except (TypeError, ValueError):
        return default


# ── 섹션 1: 테이블 & 레코드 수 ───────────────────────────────────────────────

def table_counts(conn: sqlite3.Connection) -> dict:
    tables = [r[0] for r in _q(conn, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    counts: dict[str, int] = {}
    total = 0
    for t in tables:
        cnt = _safe_int(_q1(conn, f"SELECT COUNT(*) FROM [{t}]"))
        counts[t] = cnt
        total += cnt
    return {"tables": tables, "counts": counts, "total_records": total}


# ── 섹션 2: E2E 흐름 (최근 PAID 예약 기준) ──────────────────────────────────

def e2e_flow(conn: sqlite3.Connection) -> dict:
    row = _q(conn, """
        SELECT r.id, r.deal_id, r.offer_id, r.buyer_id,
               r.shipped_at, r.arrival_confirmed_at,
               o.price, d.target_price, d.product_name
        FROM reservations r
        JOIN offers o ON o.id = r.offer_id
        JOIN deals  d ON d.id = r.deal_id
        WHERE r.status = 'PAID'
        ORDER BY r.id DESC
        LIMIT 1
    """)
    if not row:
        return {"error": "PAID 예약 없음"}

    rid, did, oid, bid, shipped_at, arrival_at, price, target_price, pname = row[0]

    srow = _q(conn,
              "SELECT status FROM reservation_settlements WHERE reservation_id=? ORDER BY id DESC LIMIT 1",
              (rid,))
    settle_status = srow[0][0] if srow else "없음"

    return {
        "reservation_id": rid,
        "deal_id": did,
        "offer_id": oid,
        "product_name": pname,
        "offer_price": _safe_int(price),
        "target_price": _safe_int(target_price) if target_price else None,
        "offer_created": True,
        "payment_completed": True,
        "shipped": shipped_at is not None,
        "arrival_confirmed": arrival_at is not None,
        "settlement_status": settle_status,
    }


# ── 섹션 3: 가격 분석 ────────────────────────────────────────────────────────

def price_analysis(conn: sqlite3.Connection) -> dict:
    row = _q(conn, """
        SELECT d.id, d.product_name, d.target_price, d.anchor_price,
               MIN(o.price) AS lowest_offer,
               MAX(o.price) AS highest_offer,
               COUNT(o.id)  AS offer_count
        FROM deals d
        JOIN offers o ON o.deal_id = d.id AND o.is_active = 1
        GROUP BY d.id
        ORDER BY offer_count DESC, d.id DESC
        LIMIT 1
    """)
    if not row:
        return {"error": "활성 오퍼 있는 딜 없음"}

    did, pname, target, anchor, low, high, cnt = row[0]

    diff_label = ""
    diff = None
    if target is not None and low is not None:
        diff = int(target) - int(low)
        if diff > 0:
            diff_label = f"+{diff:,}원 (희망가 > 최저오퍼)"
        elif diff < 0:
            diff_label = f"{diff:,}원 (최저오퍼가 더 저렴)"
        else:
            diff_label = "±0원 (희망가 = 최저오퍼)"

    return {
        "deal_id": did,
        "product_name": pname,
        "desired_price": _safe_int(target) if target else None,
        "anchor_price": _safe_int(anchor) if anchor else None,
        "lowest_offer": _safe_int(low) if low else None,
        "highest_offer": _safe_int(high) if high else None,
        "offer_count": _safe_int(cnt),
        "desired_vs_lowest": diff,
        "desired_vs_lowest_label": diff_label,
    }


# ── 섹션 4: 핑퐁이 통계 ─────────────────────────────────────────────────────

def pingpong_stats(conn: sqlite3.Connection) -> dict:
    total_logs  = _safe_int(_q1(conn, "SELECT COUNT(*) FROM pingpong_logs"))
    total_cases = _safe_int(_q1(conn, "SELECT COUNT(*) FROM pingpong_cases"))

    # intent 분포 (pingpong_cases)
    intent_rows = _q(conn, """
        SELECT intent, COUNT(*) AS cnt
        FROM pingpong_cases
        WHERE intent IS NOT NULL
        GROUP BY intent
        ORDER BY cnt DESC
        LIMIT 10
    """)
    intent_dist = {r[0]: r[1] for r in intent_rows}

    # screen 분포 (pingpong_logs)
    screen_rows = _q(conn, """
        SELECT screen, COUNT(*) AS cnt
        FROM pingpong_logs
        GROUP BY screen
        ORDER BY cnt DESC
        LIMIT 5
    """)
    screen_dist = {r[0]: r[1] for r in screen_rows}

    # 최근 대화 샘플
    recent_rows = _q(conn, """
        SELECT question, answer, created_at
        FROM pingpong_logs
        ORDER BY id DESC
        LIMIT 3
    """)
    recent = [
        {
            "q": (r[0] or "")[:80],
            "a": (r[1] or "")[:80],
            "at": _fmt_dt(r[2]),
        }
        for r in recent_rows
    ]

    # 오류율
    err_cnt = _safe_int(_q1(conn, "SELECT COUNT(*) FROM pingpong_logs WHERE error_code IS NOT NULL"))

    return {
        "total_logs": total_logs,
        "total_cases": total_cases,
        "error_count": err_cnt,
        "intent_distribution": intent_dist,
        "screen_distribution": screen_dist,
        "recent_logs": recent,
    }


# ── 섹션 5: 정책 제안서 ──────────────────────────────────────────────────────

def policy_proposals(conn: sqlite3.Connection) -> dict:
    rows = _q(conn, """
        SELECT id, title, status, proposal_type, proposed_at, reviewed_by, review_note
        FROM policy_proposals
        ORDER BY id DESC
        LIMIT 10
    """)
    items = [
        {
            "id": r[0],
            "title": r[1],
            "status": r[2],
            "type": r[3],
            "proposed_at": _fmt_dt(r[4]),
            "reviewed_by": r[5],
            "review_note": (r[6] or "")[:60] if r[6] else None,
        }
        for r in rows
    ]

    status_rows = _q(conn, """
        SELECT status, COUNT(*) FROM policy_proposals GROUP BY status ORDER BY COUNT(*) DESC
    """)
    status_dist = {r[0]: r[1] for r in status_rows}

    total = _safe_int(_q1(conn, "SELECT COUNT(*) FROM policy_proposals"))
    return {"items": items, "status_distribution": status_dist, "total": total}


# ── 섹션 6: 정산 ────────────────────────────────────────────────────────────

def settlement_stats(conn: sqlite3.Connection) -> dict:
    rows = _q(conn, """
        SELECT status,
               COUNT(*)                  AS cnt,
               SUM(seller_payout_amount) AS payout_sum,
               SUM(buyer_paid_amount)    AS paid_sum
        FROM reservation_settlements
        GROUP BY status
        ORDER BY CASE status
            WHEN 'HOLD'     THEN 1
            WHEN 'PENDING'  THEN 2
            WHEN 'READY'    THEN 3
            WHEN 'APPROVED' THEN 4
            WHEN 'PAID'     THEN 5
            ELSE 6
        END
    """)

    by_status: dict = {}
    grand_cnt = 0
    grand_payout = 0

    for status, cnt, payout, paid in rows:
        by_status[status] = {
            "count": _safe_int(cnt),
            "seller_payout_total": _safe_int(payout),
            "buyer_paid_total": _safe_int(paid),
        }
        grand_cnt += _safe_int(cnt)
        grand_payout += _safe_int(payout)

    # 최근 지급 완료 건
    paid_rows = _q(conn, """
        SELECT rs.id, rs.seller_id, rs.seller_payout_amount, rs.paid_at
        FROM reservation_settlements rs
        WHERE rs.status = 'PAID'
        ORDER BY rs.id DESC
        LIMIT 3
    """)
    recent_paid = [
        {"id": r[0], "seller_id": r[1], "amount": _safe_int(r[2]), "paid_at": _fmt_dt(r[3])}
        for r in paid_rows
    ]

    return {
        "by_status": by_status,
        "grand_total_count": grand_cnt,
        "grand_total_payout": grand_payout,
        "recent_paid": recent_paid,
    }


# ── 섹션 7: 관전자 (Spectator) ───────────────────────────────────────────────

def spectator_info(conn: sqlite3.Connection) -> dict:
    # tier 라벨 맵 (YAML 우선, 없으면 기본값)
    TIER_LABELS: dict[str, str] = {
        "exact": "정확 적중",
        "close": "근접",
        "good": "우수",
        "participate": "참여",
        "miss": "미스",
    }
    try:
        import yaml  # type: ignore
        yaml_path = ROOT / "app" / "policy" / "params" / "spectator.yaml"
        if yaml_path.exists():
            cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            for t in cfg.get("spectator", {}).get("scoring", {}).get("tiers", []):
                TIER_LABELS[t["name"]] = t.get("label", t["name"])
    except Exception:
        pass

    # 판정 완료 예측 최신 5건
    settled_rows = _q(conn, """
        SELECT sp.id, sp.deal_id, sp.buyer_id,
               sp.predicted_price, sp.settled_price,
               sp.error_pct, sp.tier_name, sp.points_earned, sp.settled_at,
               d.product_name
        FROM spectator_predictions sp
        JOIN deals d ON d.id = sp.deal_id
        WHERE sp.settled_at IS NOT NULL
        ORDER BY sp.settled_at DESC
        LIMIT 5
    """)
    recent_settled = [
        {
            "id": r[0],
            "deal_id": r[1],
            "product_name": r[9],
            "buyer_id": r[2],
            "predicted_price": _safe_int(r[3]),
            "settled_price": _safe_int(r[4]) if r[4] else None,
            "error_pct": round(float(r[5]), 2) if r[5] is not None else None,
            "tier_name": r[6],
            "tier_label": TIER_LABELS.get(r[6] or "", r[6] or ""),
            "points_earned": _safe_int(r[7]),
            "settled_at": _fmt_dt(r[8]),
        }
        for r in settled_rows
    ]

    total_pred   = _safe_int(_q1(conn, "SELECT COUNT(*) FROM spectator_predictions"))
    pending_pred = _safe_int(_q1(conn, "SELECT COUNT(*) FROM spectator_predictions WHERE settled_at IS NULL"))
    total_viewers = _safe_int(_q1(conn, "SELECT COUNT(*) FROM deal_viewers"))

    # 월별 랭킹 통계
    monthly_rows = _q(conn, """
        SELECT year_month,
               COUNT(*)          AS buyers,
               SUM(total_points) AS pts,
               MAX(total_points) AS top_pts
        FROM spectator_monthly_stats
        GROUP BY year_month
        ORDER BY year_month DESC
        LIMIT 3
    """)
    monthly = [
        {"year_month": r[0], "active_buyers": r[1], "total_points": _safe_int(r[2]), "top_points": _safe_int(r[3])}
        for r in monthly_rows
    ]

    # 배지 현황
    badge_rows = _q(conn, """
        SELECT badge_type, COUNT(*) AS cnt
        FROM spectator_badges
        GROUP BY badge_type
        ORDER BY cnt DESC
    """)
    badges = {r[0]: r[1] for r in badge_rows}

    return {
        "total_predictions": total_pred,
        "settled_predictions": total_pred - pending_pred,
        "pending_predictions": pending_pred,
        "total_viewers": total_viewers,
        "recent_settled": recent_settled,
        "monthly_stats": monthly,
        "badges": badges,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not DB_PATH.exists():
        print(f"❌ DB 파일 없음: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    report: dict = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "db_path": str(DB_PATH),
    }

    tc  = table_counts(conn);    report["tables"]           = tc
    e2e = e2e_flow(conn);        report["e2e_flow"]         = e2e
    pa  = price_analysis(conn);  report["price_analysis"]   = pa
    pp  = pingpong_stats(conn);  report["pingpong"]         = pp
    prp = policy_proposals(conn);report["policy_proposals"] = prp
    st  = settlement_stats(conn);report["settlements"]      = st
    sp  = spectator_info(conn);  report["spectator"]        = sp

    conn.close()

    # ── 콘솔 출력 ─────────────────────────────────────────────────────────

    SEP = "=" * 57

    print(f"\n{SEP}")
    print(f"  역핑 DB 리포트  |  {report['generated_at']}")
    print(SEP)

    # ① 테이블 & 레코드
    print(f"\n📊 테이블 {len(tc['tables'])}개, 레코드 총 {tc['total_records']:,}건")
    top = sorted(tc["counts"].items(), key=lambda x: -x[1])
    for name, cnt in top[:8]:
        if cnt > 0:
            bar = "█" * min(cnt // max(top[0][1] // 20, 1), 20)
            print(f"   {name:<36} {cnt:>5,}건  {bar}")

    # ② E2E 흐름
    rid_label = f" (예약 #{e2e.get('reservation_id','?')})" if "reservation_id" in e2e else ""
    print(f"\n🔄 E2E 흐름{rid_label}:")
    if "error" in e2e:
        print(f"   ⚠️  {e2e['error']}")
    else:
        tick = lambda v: "✅" if v else "❌"
        print(f"   offer_created:       {tick(e2e['offer_created'])}")
        print(f"   payment_completed:   {tick(e2e['payment_completed'])}")
        print(f"   shipped:             {tick(e2e['shipped'])}")
        print(f"   arrival_confirmed:   {tick(e2e['arrival_confirmed'])}")
        print(f"   settlement_status:   {e2e['settlement_status']}")

    # ③ 가격 분석
    pname_label = f" ({pa.get('product_name','')})" if "product_name" in pa else ""
    print(f"\n💰 가격 분석{pname_label}:")
    if "error" in pa:
        print(f"   ⚠️  {pa['error']}")
    else:
        if pa.get("desired_price"):
            print(f"   desired_price:       {_fmt_krw(pa['desired_price'])}")
        if pa.get("anchor_price"):
            print(f"   anchor_price:        {_fmt_krw(pa['anchor_price'])}")
        if pa.get("lowest_offer"):
            print(f"   lowest_offer:        {_fmt_krw(pa['lowest_offer'])}")
        if pa.get("desired_vs_lowest_label"):
            print(f"   desired_vs_lowest:   {pa['desired_vs_lowest_label']}")

    # ④ 핑퐁이
    print(f"\n🤖 핑퐁이:")
    print(f"   총 대화: {pp['total_logs']:,}건  |  케이스: {pp['total_cases']:,}건  |  오류: {pp['error_count']}건")
    if pp["intent_distribution"]:
        print(f"   의도 분포:")
        for intent, cnt in list(pp["intent_distribution"].items())[:5]:
            print(f"     {intent:<28}: {cnt}건")
    if pp["screen_distribution"]:
        print(f"   화면별:")
        for scr, cnt in list(pp["screen_distribution"].items())[:3]:
            print(f"     {scr:<28}: {cnt}건")

    # ⑤ 정책 제안서
    print(f"\n📜 정책 제안서 (총 {prp['total']}건):")
    if prp["items"]:
        for item in prp["items"][:5]:
            rb = f"  ← {item['reviewed_by']}" if item.get("reviewed_by") else ""
            print(f"   #{item['id']:>3}: {item['title'][:38]:<38} [{item['status']}]{rb}")
    else:
        print("   (없음)")

    # ⑥ 정산
    print(f"\n⚖️  정산:")
    for status, info in st["by_status"].items():
        print(f"   {status:<10}: {info['count']:>3}건  (합계 {_fmt_krw(info['seller_payout_total'])})")
    print(f"   {'─'*40}")
    print(f"   전체: {st['grand_total_count']}건  /  {_fmt_krw(st['grand_total_payout'])}")

    # ⑦ 관전자
    print(f"\n🎯 관전자:")
    print(f"   예측 총 {sp['total_predictions']}건  (판정완료: {sp['settled_predictions']}건, 대기: {sp['pending_predictions']}건)")
    print(f"   딜 뷰어: {sp['total_viewers']}건")
    if sp["recent_settled"]:
        print(f"   최근 판정 결과:")
        for s in sp["recent_settled"][:3]:
            err_s  = f"{s['error_pct']:.2f}%" if s["error_pct"] is not None else "?"
            label  = s["tier_label"] or s["tier_name"] or ""
            pts    = s["points_earned"]
            print(f"     예측#{s['id']}: 예측가 {_fmt_krw(s['predicted_price'])} / 성사가 {_fmt_krw(s['settled_price'])} → 오차 {err_s} ({label}, +{pts}pt)")
    if sp["badges"]:
        badge_str = "  ".join(f"{b}:{c}" for b, c in list(sp["badges"].items())[:4])
        print(f"   배지: {badge_str}")
    if sp["monthly_stats"]:
        print(f"   월별 통계:")
        for m in sp["monthly_stats"]:
            print(f"     {m['year_month']}: {m['active_buyers']}명 참여, 총 {m['total_points']:,}pt (최고 {m['top_points']:,}pt)")

    print(f"\n{SEP}")
    print(f"📁 전체 상세: {OUT_PATH}")

    # ── JSON 저장 ─────────────────────────────────────────────────────────
    OUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"✅ 저장 완료\n")


if __name__ == "__main__":
    main()
