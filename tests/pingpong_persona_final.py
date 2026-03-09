"""
Pingpong final persona test: 4 roles x 50 questions = 200 API calls.
Records all Q&A without pass/fail judgment.
"""
import requests, json, time, sys, io

# Force UTF-8 stdout for Windows cp949
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = "https://web-production-defb.up.railway.app"

questions = [
    # Cat 1: 자기 역할 (10)
    "내가 사용할 수 있는 기능 알려줘",
    "메인 페이지에서 뭘 할 수 있어?",
    "사이드바에 뭐가 있어?",
    "알림은 어디서 봐?",
    "내 정보 수정 어떻게 해?",
    "로그아웃 어떻게 해?",
    "비밀번호 변경 방법?",
    "도움말이나 가이드 있어?",
    "핑퐁이 너는 뭘 도와줄 수 있어?",
    "역핑 고객센터 연락처?",
    # Cat 2: 구매자 전용 (10)
    "사진 찍어서 제품 검색하는 방법 알려줘",
    "음성으로 딜 만드는 방법?",
    "가격 챌린지에서 맞춰보기 버튼 누르면 뭐가 나와?",
    "시장가 신뢰도 초록 노랑 빨강 차이?",
    "유사한 딜방 있으면 어떻게 참여해?",
    "배달 완료 후 수취 확인 안 하면 어떻게 돼?",
    "카카오 로그인하면 자동으로 가입 되는 거야?",
    "딜 생성할 때 단계가 몇 개야?",
    "목표가 슬라이더로 조정하는 방법?",
    "분쟁 신청은 어디서 해?",
    # Cat 3: 판매자 전용 (10)
    "오퍼 가격 수정할 수 있어?",
    "배송비를 수량당으로 설정하는 방법?",
    "정산 쿨링 기간이 며칠이야?",
    "내 낙찰률 어디서 확인해?",
    "구매자가 환불 요청하면 나는 뭘 해야 해?",
    "리뷰에 답글 다는 방법?",
    "운송장 번호 여러 개 입력 가능해?",
    "수수료 레벨별로 다른 거야?",
    "판매자 승인은 어떻게 받아?",
    "오퍼 마감 시간 지나면 어떻게 돼?",
    # Cat 4: 관리자 전용 (10)
    "마이너리티 리포트 대시보드에서 뭘 볼 수 있어?",
    "환불 시뮬레이터에서 배송비 모드 몇 가지야?",
    "이상 감지 ANO 번호는 자동 생성이야?",
    "일괄 배송 조회 버튼 누르면 뭐가 돼?",
    "자동 구매확정 며칠 후에 실행돼?",
    "행동 수집 포인트 구매자 몇 개 판매자 몇 개?",
    "defaults.yaml에서 수수료율 변경 가능해?",
    "신고 관리 RPT 번호 체계 설명해줘",
    "망설이는 구매자 넛지 알림이 뭐야?",
    "판매자 스킵 패턴 분석이 뭐야?",
    # Cat 5: 함정/엣지 (10)
    "역핑 대표 전화번호 알려줘",
    "마이너리티 리포트 영화 줄거리 알려줘",
    "네이버쇼핑에서 직접 사는 게 더 싸지 않아?",
    "역핑이 쿠팡보다 나은 점이 뭐야?",
    "딜 만들면 반드시 물건 살 수 있는 거야?",
    "판매자가 사기치면 어떻게 해?",
    "오늘 서울 날씨 어때?",
    "비트코인 가격 알려줘",
    "너 ChatGPT야?",
    "역핑 주식 상장 예정이야?",
]

categories = (
    ["자기역할"] * 10
    + ["구매자전용"] * 10
    + ["판매자전용"] * 10
    + ["관리자전용"] * 10
    + ["함정엣지"] * 10
)

# Login: form-encoded with "username" field (OAuth2PasswordRequestForm)
accounts = {
    "BUYER": {
        "email": "realtest1@e2e.com",
        "password": "Test1234!",
        "login_url": "/auth/login",
    },
    "SELLER": {
        "email": "stressseller1@test.com",
        "password": "Test1234!",
        "login_url": "/auth/seller/login",
    },
    "ADMIN": {
        "email": "admin@yeokping.com",
        "password": "admin1234!",
        "login_url": "/auth/login",
    },
    "ACTUATOR": {
        "email": "admin@yeokping.com",
        "password": "admin1234!",
        "login_url": "/auth/login",
        "role_override": "actuator",
    },
}


def do_login(role, creds):
    """Login with form-encoded data (username field)."""
    url = f"{BASE}{creds['login_url']}"
    try:
        r = requests.post(
            url,
            data={"username": creds["email"], "password": creds["password"]},
            timeout=15,
        )
        if r.status_code == 200:
            token = r.json().get("access_token", "")
            if token:
                print(f"  [{role}] login OK ({creds['email']})", flush=True)
                return token
        print(f"  [{role}] login failed: {r.status_code} {r.text[:120]}", flush=True)
    except Exception as e:
        print(f"  [{role}] login error: {e}", flush=True)

    # Try fallback if available
    fb = creds.get("fallback")
    if fb:
        print(f"  [{role}] trying fallback: {fb['email']}", flush=True)
        return do_login(role + "_FB", {**fb})
    return None


def ask(token, question, role):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        r = requests.post(
            f"{BASE}/v3_6/pingpong/ask",
            json={"question": question, "role": role.upper()},
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            answer = data.get("answer", data.get("response", json.dumps(data, ensure_ascii=False)))
            engine = data.get("engine", "")
            return answer, engine
        if r.status_code == 429:
            return "RATE_LIMITED", ""
        return f"HTTP_{r.status_code}", ""
    except Exception as e:
        return f"ERROR: {str(e)[:100]}", ""


def escape_md(s):
    return s.replace("|", "/").replace("\n", " ")


def main():
    from datetime import datetime

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(accounts) * len(questions)
    print(f"=== Pingpong Final Persona Test === {ts}", flush=True)
    print(f"    {len(accounts)} roles x {len(questions)} questions = {total} calls", flush=True)

    results = []
    report_lines = [
        f"# Pingpong Final Persona Test (200 Q&A)",
        f"",
        f"- Date: {ts}",
        f"- Server: {BASE}",
        f"- Roles: {', '.join(accounts.keys())}",
        f"- Questions: {len(questions)} per role",
        f"- Total: {total} API calls",
        f"",
    ]

    for role, creds in accounts.items():
        print(f"\n{'='*60}", flush=True)
        print(f"  {role}", flush=True)
        print(f"{'='*60}", flush=True)

        token = do_login(role, creds)
        if not token:
            for i, q in enumerate(questions):
                results.append({"role": role, "cat": categories[i], "q": q, "a": "LOGIN_FAIL", "engine": ""})
            report_lines.append(f"\n## {role} -- LOGIN FAIL\n")
            continue

        ask_role = creds.get("role_override", role.lower())

        report_lines.append(f"\n---\n")
        report_lines.append(f"## {role}\n")
        report_lines.append(f"| # | Cat | Question | Answer | Engine |")
        report_lines.append(f"|---|-----|----------|--------|--------|")

        for i, q in enumerate(questions):
            cat = categories[i]
            answer, engine = ask(token, q, ask_role)

            results.append({"role": role, "cat": cat, "q": q, "a": answer, "engine": engine})

            short_a = escape_md(answer[:300])
            report_lines.append(f"| {i+1} | {cat} | {q} | {short_a} | {engine} |")

            preview = escape_md(answer[:55])
            print(f"  [{role}] {i+1:02d}/50 ({cat:4s}) {q[:25]:25s} -> {preview}...", flush=True)
            time.sleep(1.5)

        report_lines.append(f"")

    # Stats
    report_lines.append(f"\n---\n")
    report_lines.append(f"## Stats\n")
    report_lines.append(f"- Total: {len(results)} calls")
    for r_name in accounts:
        cnt = sum(1 for r in results if r["role"] == r_name)
        report_lines.append(f"- {r_name}: {cnt}")
    login_fails = sum(1 for r in results if "LOGIN_FAIL" in r["a"])
    errors = sum(1 for r in results if "ERROR" in r["a"])
    rate_limits = sum(1 for r in results if "RATE_LIMITED" in r["a"])
    report_lines.append(f"- Login fails: {login_fails}")
    report_lines.append(f"- Errors: {errors}")
    report_lines.append(f"- Rate limited: {rate_limits}")

    # Write report
    report_path = "pingpong-persona-final-report-v3.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\nReport: {report_path}", flush=True)

    # Write JSON
    json_path = "pingpong-persona-final-report-v3.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON: {json_path}", flush=True)

    print(f"\nDone! {len(results)} calls completed.", flush=True)


if __name__ == "__main__":
    main()
