"""
핑퐁이 100문항 적응 테스트
- 환불 기본 (20), 교환 (10), 반품 (10), 분쟁 프로세스 (20),
  정산 (15), 시스템 (15), 레거시 트랩 (10)
- 판정: answer에 expect_keywords 중 하나 포함 → PASS
         answer에 fail_keywords 포함 → FAIL
- 95%+ PASS, 0 FAIL 목표
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Tuple

ENDPOINT = os.getenv("PINGPONG_ENDPOINT", "https://www.yeokping.com/v3_6/pingpong/ask")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "pingpong-100q-report.json"


def http_post(url: str, payload: dict, timeout: int = 30) -> Tuple[int, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        return e.code, raw.decode("utf-8", errors="replace")
    except Exception as ex:
        return 0, str(ex)


def ask(question: str, role: str = "buyer", screen: str = "GENERAL") -> Tuple[int, str]:
    payload = {
        "user_id": 1,
        "role": role,
        "screen": screen,
        "context": {"deal_id": None, "reservation_id": None, "offer_id": None},
        "question": question,
        "locale": "ko",
        "mode": "read_only",
        "max_chat_messages": 10,
    }
    status, text = http_post(ENDPOINT, payload, timeout=45)
    if status == 200:
        try:
            data = json.loads(text)
            return status, data.get("answer", "")
        except Exception:
            return status, text
    return status, text


# ─── 100 Questions ───────────────────────────────────────────
# Format: (id, question, expect_keywords, fail_keywords, role, screen)
#   expect_keywords: answer에 하나라도 포함되면 PASS
#   fail_keywords:   answer에 하나라도 포함되면 FAIL (override)

QUESTIONS: List[Tuple[str, str, List[str], List[str], str, str]] = [
    # ═══════════════════════════════════════════
    # 환불 기본 (R01–R20)
    # ═══════════════════════════════════════════
    ("R01", "환불 가능해?", ["환불", "refund", "가능"], ["불가능한 서비스"], "buyer", "REFUND_FLOW"),
    ("R02", "환불 절차가 어떻게 돼?", ["환불", "절차", "신청", "요청"], [], "buyer", "REFUND_FLOW"),
    ("R03", "환불 수수료는 얼마야?", ["수수료", "fee", "%", "부담"], [], "buyer", "REFUND_FLOW"),
    ("R04", "바이어 귀책 환불이면 배송비 누가 내?", ["바이어", "배송비", "부담", "왕복"], [], "buyer", "REFUND_FLOW"),
    ("R05", "셀러 귀책 환불이면 배송비는?", ["셀러", "배송비", "부담"], [], "buyer", "REFUND_FLOW"),
    ("R06", "부분환불 가능해?", ["부분", "환불", "가능", "partial"], [], "buyer", "REFUND_FLOW"),
    ("R07", "부분환불하면 포인트는 어떻게 돼?", ["포인트", "환불", "비례", "차감"], [], "buyer", "REFUND_FLOW"),
    ("R08", "환불 기한이 있어?", ["기한", "일", "영업일", "기간", "day", "쿨링", "환불"], [], "buyer", "REFUND_FLOW"),
    ("R09", "환불 요청 후 언제 돈 돌려받아?", ["환불", "기간", "일", "처리", "영업", "PG", "카드"], [], "buyer", "REFUND_FLOW"),
    ("R10", "결제 전 취소 가능?", ["취소", "결제", "가능", "무료"], [], "buyer", "REFUND_FLOW"),
    ("R11", "발송 전 환불이면 수수료 있어?", ["발송", "환불", "수수료"], [], "buyer", "REFUND_FLOW"),
    ("R12", "발송 후 환불이면 뭐가 달라?", ["발송", "환불", "배송비", "수수료"], [], "buyer", "REFUND_FLOW"),
    ("R13", "전액환불 조건이 뭐야?", ["전액", "환불", "full", "조건"], [], "buyer", "REFUND_FLOW"),
    ("R14", "환불 시뮬레이터가 뭐야?", ["시뮬레이터", "환불", "계산", "미리"], [], "buyer", "REFUND_FLOW"),
    ("R15", "PG 환불은 어떻게 진행돼?", ["PG", "환불", "결제", "카드"], [], "buyer", "REFUND_FLOW"),
    ("R16", "환불하면 정산은 어떻게 돼?", ["정산", "환불", "차감", "hold"], [], "buyer", "REFUND_FLOW"),
    ("R17", "쿨링 기간이 뭐야?", ["쿨링", "cooling", "기간", "영업일"], [], "buyer", "REFUND_FLOW"),
    ("R18", "환불 거절당하면 어떻게 해?", ["분쟁", "거절", "이의", "dispute", "신청"], [], "buyer", "REFUND_FLOW"),
    ("R19", "환불 시 세금계산서는?", ["세금", "계산서", "tax", "조정"], [], "buyer", "REFUND_FLOW"),
    ("R20", "변심 환불도 가능해?", ["변심", "환불", "가능", "바이어"], [], "buyer", "REFUND_FLOW"),

    # ═══════════════════════════════════════════
    # 교환 (X01–X10)
    # ═══════════════════════════════════════════
    ("X01", "교환 어떻게 해?", ["교환", "exchange", "요청", "신청"], [], "buyer", "REFUND_FLOW"),
    ("X02", "교환 배송비 누가 내?", ["교환", "배송비", "부담", "귀책", "셀러", "바이어"], [], "buyer", "REFUND_FLOW"),
    ("X03", "교환하면 정산 금액은 바뀌어?", ["교환", "정산", "유지", "금액"], [], "buyer", "REFUND_FLOW"),
    ("X04", "교환 검수는 어떻게 해?", ["교환", "검수", "확인", "inspect"], [], "buyer", "REFUND_FLOW"),
    ("X05", "교환 상품 불량이면?", ["교환", "불량", "환불", "재교환"], [], "buyer", "REFUND_FLOW"),
    ("X06", "교환 기한이 있어?", ["교환", "기한", "일", "기간"], [], "buyer", "REFUND_FLOW"),
    ("X07", "교환 안 되는 상품이 있어?", ["교환", "불가", "제한", "조건"], [], "buyer", "REFUND_FLOW"),
    ("X08", "교환 대신 환불 가능해?", ["교환", "환불", "변경", "가능"], [], "buyer", "REFUND_FLOW"),
    ("X09", "교환 중 취소 가능?", ["교환", "취소", "가능"], [], "buyer", "REFUND_FLOW"),
    ("X10", "오배송이면 교환? 환불?", ["오배송", "교환", "환불", "셀러"], [], "buyer", "REFUND_FLOW"),

    # ═══════════════════════════════════════════
    # 반품 (T01–T10)
    # ═══════════════════════════════════════════
    ("T01", "반품 어떻게 해?", ["반품", "return", "요청", "신청"], [], "buyer", "REFUND_FLOW"),
    ("T02", "반품 배송비 누가 내?", ["반품", "배송비", "부담"], [], "buyer", "REFUND_FLOW"),
    ("T03", "반품 운송장 어떻게 입력해?", ["운송장", "반품", "입력", "tracking"], [], "buyer", "REFUND_FLOW"),
    ("T04", "반품 후 환불 언제 돼?", ["반품", "환불", "기간", "확인", "검수", "영업일"], [], "buyer", "REFUND_FLOW"),
    ("T05", "반품 검수 불합격이면?", ["반품", "검수", "불합격", "감가", "FAIL"], [], "buyer", "REFUND_FLOW"),
    ("T06", "반품 기한이 있어?", ["반품", "기한", "일", "기간"], [], "buyer", "REFUND_FLOW"),
    ("T07", "반품 안 되는 경우?", ["반품", "불가", "제한", "사용"], [], "buyer", "REFUND_FLOW"),
    ("T08", "반품 감가가 뭐야?", ["감가", "차감", "deduction", "반품"], [], "buyer", "REFUND_FLOW"),
    ("T09", "미배송이면 반품 필요해?", ["미배송", "반품", "불필요", "없"], [], "buyer", "REFUND_FLOW"),
    ("T10", "반품 안 보내면 어떻게 돼?", ["반품", "미발송", "타임아웃", "자동", "종결"], [], "buyer", "REFUND_FLOW"),

    # ═══════════════════════════════════════════
    # 분쟁 프로세스 (D01–D20)
    # ═══════════════════════════════════════════
    ("D01", "분쟁 신청 어떻게 해?", ["분쟁", "dispute", "신청", "요청"], [], "buyer", "GENERAL"),
    ("D02", "분쟁 카테고리가 뭐가 있어?", ["분쟁", "카테고리", "품질", "오배송", "불량"], [], "buyer", "GENERAL"),
    ("D03", "분쟁하면 어떤 절차야?", ["분쟁", "Round", "반론", "중재", "절차"], [], "buyer", "GENERAL"),
    ("D04", "AI 중재가 뭐야?", ["AI", "중재", "분석", "추천", "mediation"], [], "buyer", "GENERAL"),
    ("D05", "분쟁 Round 1이 뭐야?", ["Round 1", "반론", "제안", "1차"], [], "buyer", "GENERAL"),
    ("D06", "분쟁 Round 2가 뭐야?", ["Round 2", "재반론", "2차"], [], "buyer", "GENERAL"),
    ("D07", "분쟁 승인하면 어떻게 돼?", ["승인", "accept", "합의", "환불", "처리"], [], "buyer", "GENERAL"),
    ("D08", "분쟁 거절하면 어떻게 돼?", ["거절", "reject", "미합의", "법적"], [], "buyer", "GENERAL"),
    ("D09", "분쟁 기한은 며칠이야?", ["분쟁", "기한", "일", "영업일", "deadline"], [], "buyer", "GENERAL"),
    ("D10", "분쟁 타임아웃이 뭐야?", ["타임아웃", "timeout", "자동", "종결", "기한"], [], "buyer", "GENERAL"),
    ("D11", "분쟁에서 정액 제안이 뭐야?", ["정액", "fixed", "금액", "제안"], [], "buyer", "GENERAL"),
    ("D12", "분쟁에서 정률 제안이 뭐야?", ["정률", "rate", "%", "비율", "제안"], [], "buyer", "GENERAL"),
    ("D13", "분쟁에서 배송비 부담은 어떻게 정해?", ["배송비", "부담", "셀러", "바이어", "분쟁"], [], "buyer", "GENERAL"),
    ("D14", "분쟁 미합의시 법적 안내가 뭐야?", ["법적", "소액", "소비자원", "안내", "legal"], [], "buyer", "GENERAL"),
    ("D15", "분쟁 증거 첨부 어떻게 해?", ["증거", "evidence", "첨부", "사진"], [], "buyer", "GENERAL"),
    ("D16", "구매자가 분쟁 신청 가능?", ["구매자", "바이어", "buyer", "분쟁", "신청"], [], "buyer", "GENERAL"),
    ("D17", "판매자가 분쟁에 반론 어떻게 해?", ["판매자", "셀러", "반론", "response", "제안"], [], "seller", "GENERAL"),
    ("D18", "AI가 법적 근거도 알려줘?", ["법적", "전자상거래", "근거", "legal", "AI"], [], "buyer", "GENERAL"),
    ("D19", "분쟁 넛지 메시지가 뭐야?", ["넛지", "nudge", "메시지", "알림", "독촉"], [], "buyer", "GENERAL"),
    ("D20", "분쟁 자동 종결 조건은?", ["자동", "종결", "타임아웃", "기한", "AUTO"], [], "buyer", "GENERAL"),

    # ═══════════════════════════════════════════
    # 정산 (S01–S15)
    # ═══════════════════════════════════════════
    ("S01", "정산이 뭐야?", ["정산", "settlement", "셀러", "지급"], [], "seller", "GENERAL"),
    ("S02", "정산 절차가 어떻게 돼?", ["정산", "HOLD", "READY", "APPROVED", "PAID"], [], "seller", "GENERAL"),
    ("S03", "정산 쿨링 기간은?", ["쿨링", "cooling", "기간", "영업일"], [], "seller", "GENERAL"),
    ("S04", "정산 수수료는 얼마야?", ["수수료", "fee", "%", "플랫폼"], [], "seller", "GENERAL"),
    ("S05", "정산금 계산 방식은?", ["정산", "계산", "수수료", "차감", "금액"], [], "seller", "GENERAL"),
    ("S06", "정산 HOLD 상태가 뭐야?", ["HOLD", "정산", "보류", "대기", "쿨링", "결제"], [], "seller", "GENERAL"),
    ("S07", "정산 READY가 뭐야?", ["READY", "정산", "준비", "쿨링"], [], "seller", "GENERAL"),
    ("S08", "정산 APPROVED가 뭐야?", ["APPROVED", "정산", "승인", "지급"], [], "seller", "GENERAL"),
    ("S09", "정산금 받으려면 뭐 해야 돼?", ["정산", "계좌", "셀러", "지급"], [], "seller", "GENERAL"),
    ("S10", "환불 후 정산 어떻게 바뀌어?", ["환불", "정산", "차감", "재계산"], [], "seller", "GENERAL"),
    ("S11", "Clawback이 뭐야?", ["Clawback", "환수", "차감", "정산"], [], "seller", "GENERAL"),
    ("S12", "이미 PAID 정산 후 환불이면?", ["PAID", "환불", "Clawback", "환수", "차감"], [], "seller", "GENERAL"),
    ("S13", "정산 배치는 언제 돌아?", ["배치", "batch", "정산", "자동"], [], "seller", "GENERAL"),
    ("S14", "정산 영향도 확인 어떻게 해?", ["정산", "영향", "impact", "시뮬레이터"], [], "seller", "GENERAL"),
    ("S15", "정산 세금계산서는?", ["세금", "계산서", "tax", "정산"], [], "seller", "GENERAL"),

    # ═══════════════════════════════════════════
    # 시스템/일반 (G01–G15)
    # ═══════════════════════════════════════════
    ("G01", "역핑이 뭐야?", ["역핑", "공동구매", "플랫폼", "역경매"], [], "buyer", "GENERAL"),
    ("G02", "딜이 뭐야?", ["딜", "deal", "공동구매", "상품"], [], "buyer", "GENERAL"),
    ("G03", "오퍼가 뭐야?", ["오퍼", "offer", "셀러", "제안"], [], "buyer", "GENERAL"),
    ("G04", "예약이 뭐야?", ["예약", "reservation", "결제"], [], "buyer", "GENERAL"),
    ("G05", "결제 방법은?", ["결제", "payment", "PG", "카드"], [], "buyer", "GENERAL"),
    ("G06", "결제 제한 시간 있어?", ["결제", "시간", "제한", "timeout", "분"], [], "buyer", "GENERAL"),
    ("G07", "포인트 어떻게 쓸 수 있어?", ["포인트", "point", "사용", "적립"], [], "buyer", "GENERAL"),
    ("G08", "신뢰도 등급이 뭐야?", ["신뢰도", "등급", "trust", "tier"], [], "buyer", "GENERAL"),
    ("G09", "액추에이터가 뭐야?", ["액추에이터", "actuator", "중개"], [], "buyer", "GENERAL"),
    ("G10", "리뷰 어떻게 써?", ["리뷰", "review", "평가", "별점"], [], "buyer", "GENERAL"),
    ("G11", "딜 라운드가 뭐야?", ["라운드", "round", "딜", "기간"], [], "buyer", "GENERAL"),
    ("G12", "가격 여정 맵이 뭐야?", ["가격", "여정", "journey", "맵"], [], "buyer", "GENERAL"),
    ("G13", "알림은 어떻게 와?", ["알림", "notification", "push", "메시지"], [], "buyer", "GENERAL"),
    ("G14", "고객센터 연락처?", ["고객센터", "문의", "연락", "support", "안내", "어렵", "핑퐁"], [], "buyer", "GENERAL"),
    ("G15", "개인정보 어떻게 보호돼?", ["개인정보", "보호", "privacy", "보안"], [], "buyer", "GENERAL"),

    # ═══════════════════════════════════════════
    # 레거시 트랩 (L01–L10): 잘못된 용어/구형 질문 → 올바른 안내
    # ═══════════════════════════════════════════
    ("L01", "v2 API 쓸 수 있어?", ["v3", "최신", "버전", "현재", "사용"], ["v2를 사용"], "buyer", "GENERAL"),
    ("L02", "days_since_delivery가 뭐야?", ["배송", "기간", "일수", "환불", "delivery"], [], "buyer", "GENERAL"),
    ("L03", "수동 정산은 어떻게 해?", ["정산", "자동", "배치", "batch", "수동", "안내", "어렵"], [], "seller", "GENERAL"),
    ("L04", "환불 시 cancel 상태가 뭐야?", ["환불", "cancel", "상태", "status"], [], "buyer", "REFUND_FLOW"),
    ("L05", "포인트 현금화 가능해?", ["포인트", "현금", "불가", "사용"], ["현금화 가능"], "buyer", "GENERAL"),
    ("L06", "셀러 직접 결제 받을 수 있어?", ["정산", "플랫폼", "결제", "직접", "안내", "어렵"], ["직접 결제 가능"], "seller", "GENERAL"),
    ("L07", "수수료 면제 가능해?", ["수수료", "면제", "fee", "조건"], [], "seller", "GENERAL"),
    ("L08", "환불 90일 지나면?", ["90일", "기한", "불가", "제한", "환불", "분쟁", "소비자"], [], "buyer", "REFUND_FLOW"),
    ("L09", "분쟁 3라운드 있어?", ["2라운드", "최대", "Round", "없", "분쟁"], [], "buyer", "GENERAL"),
    ("L10", "결제 없이 예약 가능?", ["결제", "예약", "필수", "필요", "payment"], [], "buyer", "GENERAL"),
]


def judge(answer: str, expect_kw: List[str], fail_kw: List[str]) -> str:
    """PASS / FAIL / SKIP"""
    if not answer or answer.strip() == "":
        return "SKIP"
    low = answer.lower()
    # fail_keywords check first
    for fk in fail_kw:
        if fk.lower() in low:
            return "FAIL"
    # expect_keywords
    for ek in expect_kw:
        if ek.lower() in low:
            return "PASS"
    return "SKIP"


def main():
    print(f"Endpoint: {ENDPOINT}")
    print(f"Total questions: {len(QUESTIONS)}")
    print("=" * 60)

    results = []
    pass_count = 0
    fail_count = 0
    skip_count = 0
    error_count = 0

    for i, (qid, question, expect_kw, fail_kw, role, screen) in enumerate(QUESTIONS):
        status, answer = ask(question, role=role, screen=screen)

        if status != 200:
            verdict = "ERROR"
            error_count += 1
            answer_preview = f"HTTP {status}"
        else:
            verdict = judge(answer, expect_kw, fail_kw)
            if verdict == "PASS":
                pass_count += 1
            elif verdict == "FAIL":
                fail_count += 1
            else:
                skip_count += 1
            answer_preview = answer[:120].replace("\n", " ")

        tag = {"PASS": "OK", "FAIL": "XX", "SKIP": "??", "ERROR": "!!"}[verdict]
        print(f"  [{tag}] {qid}: {question[:40]:<42} -> {verdict}")
        if verdict in ("FAIL", "ERROR"):
            print(f"       answer: {answer_preview}")

        results.append({
            "id": qid,
            "question": question,
            "role": role,
            "screen": screen,
            "status": status,
            "verdict": verdict,
            "answer_preview": answer_preview if verdict != "PASS" else answer[:200],
        })

        # 0.3s delay to avoid rate limiting
        time.sleep(0.3)

    print("\n" + "=" * 60)
    total = len(QUESTIONS)
    print(f"PASS: {pass_count}/{total}  FAIL: {fail_count}  SKIP: {skip_count}  ERROR: {error_count}")
    pct = pass_count / total * 100 if total else 0
    print(f"Pass rate: {pct:.1f}%  (target: 95%+)")
    print(f"FAIL count: {fail_count}  (target: 0)")

    report = {
        "endpoint": ENDPOINT,
        "total": total,
        "pass": pass_count,
        "fail": fail_count,
        "skip": skip_count,
        "error": error_count,
        "pass_rate_pct": round(pct, 1),
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport saved: {REPORT_PATH}")

    # exit code: 0 if pass_rate >= 95% and fail == 0
    if fail_count == 0 and pct >= 95:
        print("RESULT: TARGET MET")
        return 0
    else:
        print("RESULT: TARGET NOT MET")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
