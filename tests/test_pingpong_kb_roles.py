"""
핑퐁이 KB 역할별 검색 테스트 (100문장 × 3역할 + 30 액추에이터)
OpenAI API 호출 없이 retrieve_kb_snippets 레이어만 테스트.
"""
import sys, os, json
from pathlib import Path
from datetime import datetime

# project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import tools.pingpong_sidecar_openai as sidecar

sidecar.load_kb()
retrieve_kb_snippets = sidecar.retrieve_kb_snippets
KB = sidecar.KB
print(f"\n=== KB loaded: {len(KB)} files ===\n")

# ──────────────────────────────────────────────
# 질문 목록 정의
# ──────────────────────────────────────────────

BUYER_QUESTIONS = [
    # 기본 플랫폼 이해 (10)
    ("역핑이 뭐야?", True),
    ("역경매가 뭐야?", True),
    ("공동구매 어떻게 해?", True),
    ("기존 쇼핑이랑 뭐가 달라?", True),
    ("역핑 어떻게 시작해?", True),
    ("회원가입 어떻게 해?", True),
    ("소셜 로그인 방법?", True),
    ("카카오 로그인 어떻게 해?", True),
    ("네이버 로그인?", True),
    ("구글 로그인?", True),
    # 딜 생성 (15)
    ("딜 만드는 법?", True),
    ("딜 생성 무료야?", True),
    ("사진으로 딜 만들 수 있어?", True),
    ("음성으로 제품 검색?", True),
    ("AI 분석 어떻게 해?", True),
    ("제품 정보 확인 어떻게?", True),
    ("유사 딜방이 뭐야?", True),
    ("가격 챌린지가 뭐야?", True),
    ("시장가 어떻게 조사해?", True),
    ("신뢰도 등급이 뭐야?", True),
    ("가격 소스 비교 패널?", True),
    ("할인율 슬라이더?", True),
    ("목표가 설정 방법?", True),
    ("딜 마감 시간?", True),
    ("딜 삭제 가능?", True),
    # 오퍼/예약/결제 (10)
    ("오퍼 비교 어떻게 해?", True),
    ("가격 여정 맵이 뭐야?", True),
    ("오퍼 선택 후 어떻게 돼?", True),
    ("예약 방법?", True),
    ("결제 시간 제한?", True),
    ("결제 후 흐름?", True),
    ("총 결제액 계산?", True),
    ("배송 방식 종류?", True),
    ("오퍼 확인 포인트?", True),
    ("결제 후 취소 가능?", True),
    # 주문/배송 (10)
    ("내 주문 어디서 봐?", True),
    ("배송 조회 방법?", True),
    ("배송 추적 가능?", True),
    ("배달 완료 후?", True),
    ("자동 구매확정?", True),
    ("수취 확인 방법?", True),
    ("배송이 안 와요", True),
    ("택배사 종류?", True),
    ("배송 상태 종류?", True),
    ("운송장 번호 확인?", True),
    # 환불/분쟁 (10)
    ("환불 어떻게 해?", True),
    ("환불 정책이 뭐야?", True),
    ("구매자 사유 환불?", True),
    ("판매자 사유 환불?", True),
    ("배송 전 환불?", True),
    ("배송 후 환불?", True),
    ("분쟁 신청 방법?", True),
    ("분쟁 제기 기간?", True),
    ("반품 방법?", True),
    ("교환 방법?", True),
    # 포인트/등급 (8)
    ("포인트 어떻게 쌓아?", True),
    ("포인트 소멸 기간?", True),
    ("등급 종류?", True),
    ("브론즈 실버 골드?", True),
    ("추천인 보상?", True),
    ("내 포인트 얼마야?", True),
    ("등급 업그레이드 조건?", True),
    ("포인트 유효기간?", True),
    # 관전 모드 (5)
    ("관전 모드가 뭐야?", True),
    ("예측하면 뭐가 좋아?", True),
    ("지난딜 가격조회?", True),
    ("완료된 딜 보기?", True),
    ("관전자 예측 어떻게?", True),
    # 핑퐁이 (3)
    ("핑퐁이가 뭐야?", True),
    ("핑퐁이 어떻게 써?", True),
    ("빠른 질문 버튼?", True),
    # 가격 합의 엔진 (7)
    ("3중 소스 검증?", True),
    ("네이버쇼핑 가격?", True),
    ("쿠팡 가격?", True),
    ("GPT 가격 추정?", True),
    ("액세서리 자동 필터?", True),
    ("브랜드 필터링?", True),
    ("명품 경고?", True),
    # 마이페이지/알림 (5)
    ("마이페이지 어디야?", True),
    ("프로필 수정?", True),
    ("알림 확인 방법?", True),
    ("소셜 연동 상태?", True),
    ("알림 설정?", True),
    # 모델 매칭 (5)
    ("갤럭시 S25 검색하면?", True),
    ("세트 상품 필터?", True),
    ("중고 제외?", True),
    ("온라인 미판매 제품?", True),
    ("모델 정확 매칭?", True),
    # 관리자 전용 (구매자는 답 없어야) (12)
    ("마이너리티 리포트가 뭐야?", False),
    ("환불 시뮬레이터?", False),
    ("이상 감지 관리?", False),
    ("신고 관리?", False),
    ("정책 파라미터 수정?", False),
    ("판매자 승인 처리?", False),
    ("관리자 대시보드?", False),
    ("정산 HOLD READY?", False),
    ("정책 문서 관리?", False),
    ("핑퐁이 정책제안?", False),
    ("관리자 딜 관리?", False),
    ("관리자 배송 관리?", False),
]

SELLER_QUESTIONS = [
    # 기본 (8)
    ("역핑이 뭐야?", True),
    ("판매자 등록 방법?", True),
    ("판매자 회원가입?", True),
    ("사업자 정보 입력?", True),
    ("서류 업로드?", True),
    ("관리자 승인 대기?", True),
    ("소셜 로그인?", True),
    ("판매자 역할 선택?", True),
    # 대시보드 (5)
    ("판매자 대시보드?", True),
    ("낙찰률 확인?", True),
    ("매출 확인?", True),
    ("정산 현황?", True),
    ("오퍼 채택률?", True),
    # 딜 탐색/오퍼 (12)
    ("딜 탐색 방법?", True),
    ("오퍼 제출 방법?", True),
    ("오퍼 마감 시간?", True),
    ("오퍼 작성 항목?", True),
    ("단가 입력?", True),
    ("배송비 설정?", True),
    ("환불 조건 설정?", True),
    ("오퍼 전략 팁?", True),
    ("공동구매 가격 인하?", True),
    ("오퍼 수정 가능?", True),
    ("오퍼 철회?", True),
    ("오퍼 관리 페이지?", True),
    # 배송 (12)
    ("배송 처리 방법?", True),
    ("운송장 번호 입력?", True),
    ("택배사 선택?", True),
    ("스마트택배 추적?", True),
    ("배송 처리 주의사항?", True),
    ("48시간 이내 배송?", True),
    ("배송 상태 종류?", True),
    ("운송장 오입력 수정?", True),
    ("배송 정책 설정?", True),
    ("무료배송 설정?", True),
    ("건당 배송비?", True),
    ("수량당 배송비?", True),
    # 정산 (12)
    ("정산 언제 돼?", True),
    ("정산 흐름?", True),
    ("HOLD READY APPROVED PAID?", True),
    ("쿨링 기간?", True),
    ("정산 금액 계산?", True),
    ("PG 수수료?", True),
    ("플랫폼 수수료?", True),
    ("레벨별 수수료?", True),
    ("수수료 인하 방법?", True),
    ("정산 지급일?", True),
    ("분쟁 정산 보류?", True),
    ("정산 관리 페이지?", True),
    # 환불/반품 (8)
    ("환불 요청 처리?", True),
    ("반품 요청?", True),
    ("교환 요청?", True),
    ("구매자 사유 환불?", True),
    ("판매자 사유 환불?", True),
    ("환불 시뮬레이터?", True),  # seller guide mentions it
    ("환불 금액 미리보기?", True),
    ("환불 관리 페이지?", True),
    # 분쟁 (6)
    ("분쟁 대응 방법?", True),
    ("증빙 자료 제출?", True),
    ("분쟁 환불 판정?", True),
    ("분쟁 레벨 하락?", True),
    ("분쟁 종료 후 정산?", True),
    ("분쟁 정산 재개?", True),
    # 리뷰/문의 (6)
    ("리뷰 관리?", True),
    ("리뷰 답글?", True),
    ("좋은 평점 팁?", True),
    ("고객 문의 관리?", True),
    ("문의 답변?", True),
    ("평점 레벨 반영?", True),
    # 수수료/레벨 (6)
    ("기본 수수료율?", True),
    ("레벨 1 수수료?", True),
    ("레벨 6 수수료?", True),
    ("레벨업 방법?", True),
    ("카테고리별 수수료?", True),
    ("수수료 안내 페이지?", True),
    # 브랜드/통계 (5)
    ("브랜드 필터링?", True),
    ("삼성 브랜드 매핑?", True),
    ("통계 페이지?", True),
    ("매출 추이?", True),
    ("오퍼 성공률?", True),
    # 액추에이터 (4)
    ("액추에이터가 뭐야?", True),
    ("액추에이터 커미션?", True),
    ("액추에이터 레벨별?", True),
    ("추천코드?", True),
    # 핑퐁이/공지 (4)
    ("핑퐁이 질문?", True),
    ("공지사항 확인?", True),
    ("빠른 질문 버튼?", True),
    ("판매자 빠른 질문?", True),
    # 관리자 전용 (판매자는 답 없어야) (12)
    ("마이너리티 리포트?", False),
    ("이상 감지 관리?", False),
    ("신고 관리?", False),
    ("정책 파라미터 수정?", False),
    ("관리자 대시보드?", False),
    ("판매자 승인 처리?", False),
    ("정책 문서 관리?", False),
    ("핑퐁이 정책제안?", False),
    ("관리자 딜 관리?", False),
    ("관리자 배송 관리?", False),
    ("알림 브로드캐스트?", False),
    ("공지 삭제?", False),
]

ADMIN_QUESTIONS = [
    # 대시보드 (5)
    ("관리자 대시보드?", True),
    ("KPI 카운트?", True),
    ("GMV 확인?", True),
    ("AOV 확인?", True),
    ("최근 활동 로그?", True),
    # 구매자 관리 (5)
    ("구매자 관리?", True),
    ("구매자 목록?", True),
    ("계정 정지?", True),
    ("구매자 등급?", True),
    ("구매자 포인트?", True),
    # 판매자 관리 (7)
    ("판매자 관리?", True),
    ("판매자 승인?", True),
    ("판매자 반려?", True),
    ("판매자 레벨?", True),
    ("판매자 수수료율?", True),
    ("판매자 정지?", True),
    ("판매자 연결 액추에이터?", True),
    # 액추에이터 관리 (4)
    ("액추에이터 관리?", True),
    ("액추에이터 목록?", True),
    ("추천코드 발급?", True),
    ("커미션 내역?", True),
    # 딜/오퍼 관리 (6)
    ("딜 관리?", True),
    ("딜 목록?", True),
    ("딜 시장가 컬럼?", True),
    ("오퍼 관리?", True),
    ("오퍼 번호 클릭?", True),
    ("딜 마감 기한?", True),
    # 예약/주문 관리 (5)
    ("예약 관리?", True),
    ("주문 상태 드롭다운?", True),
    ("PENDING PAID SHIPPED?", True),
    ("CONFIRMED CANCELLED?", True),
    ("REFUNDED DISPUTED?", True),
    # 배송 관리 (6)
    ("배송 관리?", True),
    ("일괄 배송 조회?", True),
    ("자동 구매확정 실행?", True),
    ("배송 상태 요약 카드?", True),
    ("스마트택배 API?", True),
    ("배송 추적 간격?", True),
    # 정산 관리 (6)
    ("정산 관리?", True),
    ("HOLD READY APPROVED PAID?", True),
    ("쿨링 기간 7일?", True),
    ("정산 지급 지연?", True),
    ("분쟁 정산 보류?", True),
    ("정산 APPROVED 처리?", True),
    # 환불 관리 (4)
    ("환불 관리?", True),
    ("환불 승인 거부?", True),
    ("환불 요청 목록?", True),
    ("환불 상태별 필터?", True),
    # 환불 시뮬레이터 (5)
    ("환불 시뮬레이터?", True),
    ("수동 모드?", True),
    ("예약 조회 모드?", True),
    ("배송비 3가지 모드?", True),
    ("환불 사유 통합?", True),
    # 분쟁 관리 (5)
    ("분쟁 관리?", True),
    ("분쟁 제기 기간?", True),
    ("관리자 처리 기한?", True),
    ("분쟁 정산 자동 보류?", True),
    ("분쟁 종료 후 정산 재개?", True),
    # 이상 감지/신고 (5)
    ("이상 감지?", True),
    ("이상 감지 ANO?", True),
    ("신고 관리?", True),
    ("신고 RPT?", True),
    ("Open Processing Closed?", True),
    # 마이너리티 리포트 (8)
    ("마이너리티 리포트?", True),
    ("사용자 행동 분석?", True),
    ("구매자 행동 수집?", True),
    ("판매자 행동 수집?", True),
    ("AI 프로파일링?", True),
    ("망설이는 구매자 감지?", True),
    ("넛지 알림?", True),
    ("인기 검색 키워드?", True),
    # 정책 관리 (6)
    ("정책 파라미터 관리?", True),
    ("defaults.yaml 수정?", True),
    ("payment_timeout_minutes?", True),
    ("platform_fee_rate?", True),
    ("정책 문서 관리?", True),
    ("MD 파일 편집?", True),
    # 핑퐁이 정책제안 (3)
    ("핑퐁이 정책제안?", True),
    ("제안 승인 거부?", True),
    ("정책 롤백?", True),
    # 가격 합의 엔진 (5)
    ("가격 합의 엔진?", True),
    ("3중 소스 교차 검증?", True),
    ("신뢰도 등급?", True),
    ("자동 필터링?", True),
    ("명품 가품 경고?", True),
    # 통계/로그/알림/공지/설정 (7)
    ("통계 KPI?", True),
    ("활동 로그?", True),
    ("알림 관리?", True),
    ("브로드캐스트 알림?", True),
    ("공지 관리?", True),
    ("공지 작성 삭제?", True),
    ("시스템 설정?", True),
    # 구매자/판매자 가이드도 볼 수 있어야 (5)
    ("구매자 가이드 내용?", True),
    ("판매자 가이드 내용?", True),
    ("딜 생성 단계?", True),
    ("오퍼 제출 항목?", True),
    ("배송 정책?", True),
]

ACTUATOR_QUESTIONS = [
    # 기본 (5)
    ("액추에이터가 뭐야?", True),
    ("액추에이터 역할?", True),
    ("판매자 모집?", True),
    ("커미션 구조?", True),
    ("추천코드?", True),
    # 판매자 가이드 접근 가능 (10)
    ("판매자 등록?", True),
    ("오퍼 제출?", True),
    ("정산 흐름?", True),
    ("배송 처리?", True),
    ("수수료율?", True),
    ("레벨별 수수료?", True),
    ("브랜드 필터링?", True),
    ("스마트택배?", True),
    ("환불 관리?", True),
    ("리뷰 관리?", True),
    # 관리자 전용 (차단) (10)
    ("마이너리티 리포트?", False),
    ("이상 감지?", False),
    ("신고 관리?", False),
    ("정책 파라미터 수정?", False),
    ("관리자 대시보드?", False),
    ("판매자 승인 처리?", False),
    ("정책 문서 관리?", False),
    ("핑퐁이 정책제안?", False),
    ("관리자 배송 관리?", False),
    ("알림 브로드캐스트?", False),
    # 구매자 가이드 (차단) (5)
    ("딜 생성 방법?", False),
    ("가격 챌린지?", False),
    ("관전 모드?", False),
    ("포인트 적립?", False),
    ("구매자 등급?", False),
]


def run_test(role: str, questions: list) -> dict:
    """Run KB retrieval test for a role."""
    results = {
        "role": role,
        "total": len(questions),
        "pass": 0,
        "fail": 0,
        "details": [],
    }

    for question, expect_docs in questions:
        docs = retrieve_kb_snippets(question, role=role)
        has_docs = bool(docs.strip())

        # Extract matched files
        files_used = []
        for line in docs.split("\n"):
            if "자료:" in line:
                try:
                    fname = line.split("자료: ")[1].split("]")[0]
                    score = line.split("score=")[1].split(")")[0] if "score=" in line else "?"
                    files_used.append(f"{fname}({score})")
                except:
                    pass

        # Check admin doc leakage
        admin_leaked = False
        if role.upper() != "ADMIN":
            admin_leaked = any("/admin/" in f for f in files_used)

        # Determine pass/fail
        if expect_docs:
            passed = has_docs  # Expected docs, got docs
        else:
            passed = not has_docs  # Expected no docs, got no docs

        if admin_leaked:
            passed = False  # Admin docs leaked to non-admin

        results["pass" if passed else "fail"] += 1
        results["details"].append({
            "question": question,
            "expect_docs": expect_docs,
            "has_docs": has_docs,
            "passed": passed,
            "admin_leaked": admin_leaked,
            "files": files_used[:3],  # Top 3
        })

    return results


def print_report(results: dict):
    role = results["role"]
    total = results["total"]
    passed = results["pass"]
    failed = results["fail"]
    rate = (passed / total * 100) if total else 0

    print(f"\n{'='*70}")
    print(f"  {role.upper()} -{passed}/{total} PASS ({rate:.1f}%)")
    print(f"{'='*70}")

    # Print failures
    failures = [d for d in results["details"] if not d["passed"]]
    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for d in failures:
            expect = "DOCS" if d["expect_docs"] else "NO DOCS"
            got = "GOT DOCS" if d["has_docs"] else "NO DOCS"
            leak = " [ADMIN LEAK!]" if d["admin_leaked"] else ""
            files = ", ".join(d["files"][:2]) if d["files"] else "-"
            print(f"    FAIL: \"{d['question']}\" -expect {expect}, {got}{leak}")
            if d["files"]:
                print(f"          files: {files}")

    # Print summary by category
    print(f"\n  PASS examples:")
    pass_examples = [d for d in results["details"] if d["passed"]][:5]
    for d in pass_examples:
        files = d["files"][0] if d["files"] else "-"
        print(f"    OK: \"{d['question']}\" → {files}")


def main():
    print(f"{'#'*70}")
    print(f"#  핑퐁이 KB 역할별 검색 테스트")
    print(f"#  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"#  KB: {len(KB)} files loaded")
    print(f"{'#'*70}")

    all_results = []

    for role, questions in [
        ("BUYER", BUYER_QUESTIONS),
        ("SELLER", SELLER_QUESTIONS),
        ("ADMIN", ADMIN_QUESTIONS),
        ("ACTUATOR", ACTUATOR_QUESTIONS),
    ]:
        r = run_test(role, questions)
        all_results.append(r)
        print_report(r)

    # Grand summary
    print(f"\n{'='*70}")
    print(f"  GRAND SUMMARY")
    print(f"{'='*70}")
    grand_total = sum(r["total"] for r in all_results)
    grand_pass = sum(r["pass"] for r in all_results)
    grand_fail = sum(r["fail"] for r in all_results)

    for r in all_results:
        rate = (r["pass"] / r["total"] * 100) if r["total"] else 0
        bar = "#" * int(rate / 5) + "." * (20 - int(rate / 5))
        print(f"  {r['role']:12s} {bar} {r['pass']:3d}/{r['total']:3d} ({rate:5.1f}%)")

    grand_rate = (grand_pass / grand_total * 100) if grand_total else 0
    print(f"  {'TOTAL':12s} {'─'*20} {grand_pass:3d}/{grand_total:3d} ({grand_rate:5.1f}%)")

    # Admin leak check
    total_leaks = 0
    for r in all_results:
        if r["role"].upper() != "ADMIN":
            leaks = [d for d in r["details"] if d["admin_leaked"]]
            total_leaks += len(leaks)
    print(f"\n  Admin doc leaks to non-admin: {total_leaks}")

    # Write JSON report
    report_path = ROOT / "pingpong-kb-test-report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Full report: {report_path}")


if __name__ == "__main__":
    main()
