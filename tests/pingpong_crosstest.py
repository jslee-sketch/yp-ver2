"""
Pingpong cross-role KB test: 4 roles x 40 questions = 160 API calls.
Records all Q&A without pass/fail judgment.
"""
import requests, json, time, sys, io, os
from datetime import datetime

# Force UTF-8 stdout for Windows cp949
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = "https://web-production-defb.up.railway.app"

QUESTIONS = {
    "BUYER": [
        "B1 사진으로 딜 만들 수 있어?",
        "B2 음성으로 제품 검색하는 방법?",
        "B3 가격 챌린지가 뭐야?",
        "B4 시장가 신뢰도 차이가 뭐야?",
        "B5 배송 추적 어떻게 해?",
        "B6 자동 구매확정이 뭐야?",
        "B7 카카오로 로그인하는 방법?",
        "B8 유사한 딜방이 있으면 어떻게 돼?",
        "B9 환불하면 배송비는 누가 내?",
        "B10 목표가를 어떻게 설정해?",
    ],
    "SELLER": [
        "S1 오퍼 어떻게 제출해?",
        "S2 배송비 유형이 뭐가 있어?",
        "S3 정산 언제 돼?",
        "S4 수수료 얼마야?",
        "S5 리뷰 답글 어떻게 써?",
        "S6 환불 요청 들어오면 어떻게 해?",
        "S7 브랜드 필터링이 뭐야?",
        "S8 오퍼 마감 시간이 얼마야?",
        "S9 배송 처리 어떻게 해?",
        "S10 내 오퍼 낙찰률 확인?",
    ],
    "ADMIN": [
        "A1 마이너리티 리포트가 뭐야?",
        "A2 환불 시뮬레이터 사용법?",
        "A3 이상 감지 ANO 번호가 뭐야?",
        "A4 일괄 배송 조회 어떻게 해?",
        "A5 자동 구매확정 실행 방법?",
        "A6 행동 수집 포인트가 몇 개야?",
        "A7 판매자 승인 어떻게 해?",
        "A8 defaults.yaml 수정 방법?",
        "A9 가격 합의 엔진이 뭐야?",
        "A10 신고 관리 RPT 번호?",
    ],
    "ACTUATOR": [
        "T1 액츄에이터 역할이 뭐야?",
        "T2 판매자와 어떻게 연결돼?",
        "T3 커미션 구조가 어떻게 돼?",
        "T4 오퍼 제출 도와줄 수 있어?",
        "T5 정산은 어떻게 받아?",
        "T6 배송 관리도 해야 해?",
        "T7 딜 탐색 어떻게 해?",
        "T8 여러 판매자 관리 가능해?",
        "T9 리뷰 관리도 해?",
        "T10 수수료 구조?",
    ],
}

ALL_QUESTIONS = []
for qlist in QUESTIONS.values():
    ALL_QUESTIONS.extend(qlist)

ACCOUNTS = {
    "BUYER":    {"email": "realtest1@e2e.com",         "password": "Test1234!",    "login_url": "/auth/login"},
    "SELLER":   {"email": "stressseller1@test.com",    "password": "Test1234!",    "login_url": "/auth/seller/login"},
    "ADMIN":    {"email": "admin@yeokping.com",        "password": "admin1234!",   "login_url": "/auth/login"},
    "ACTUATOR": {"email": "admin@yeokping.com",        "password": "admin1234!",   "login_url": "/auth/login", "role_override": "ACTUATOR"},
}

def login(role, creds):
    try:
        login_url = creds.get("login_url", "/auth/login")
        r = requests.post(f"{BASE}{login_url}", data={
            "username": creds["email"],
            "password": creds["password"],
        }, timeout=15)
        if r.status_code == 200:
            return r.json().get("access_token", "")
        print(f"  [{role}] login failed: {r.status_code} {r.text[:120]}", flush=True)
    except Exception as e:
        print(f"  [{role}] login error: {e}", flush=True)
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
        data = r.json()
        answer = data.get("answer", data.get("response", json.dumps(data, ensure_ascii=False)))
        engine = data.get("engine", "")
        return answer, engine
    except Exception as e:
        return f"ERROR: {e}", ""

def escape_md(s):
    return s.replace("|", "\\|").replace("\n", "<br>")

def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== Pingpong Cross-Role Test === {ts}", flush=True)
    print(f"    {len(ACCOUNTS)} roles x {len(ALL_QUESTIONS)} questions = {len(ACCOUNTS)*len(ALL_QUESTIONS)} calls", flush=True)

    all_results = {}  # role -> list of {question, answer, engine}

    for role, creds in ACCOUNTS.items():
        print(f"\n--- {role} ---", flush=True)
        token = login(role, creds)
        if not token:
            all_results[role] = [{"question": q, "answer": "LOGIN_FAIL", "engine": ""} for q in ALL_QUESTIONS]
            continue

        ask_role = creds.get("role_override", role)
        results = []
        for i, q in enumerate(ALL_QUESTIONS):
            answer, engine = ask(token, q, ask_role)
            results.append({"question": q, "answer": answer, "engine": engine})
            short_a = answer[:60].replace("\n", " ")
            print(f"  [{i+1:3d}/40] {q[:30]:30s} -> {short_a}... [{engine}]", flush=True)
            time.sleep(1.0)

        all_results[role] = results

    # Write markdown report
    report_lines = [
        f"# Pingpong Cross-Role KB Test",
        f"",
        f"- Date: {ts}",
        f"- Server: {BASE}",
        f"- Roles: {', '.join(ACCOUNTS.keys())}",
        f"- Questions per role: {len(ALL_QUESTIONS)}",
        f"- Total API calls: {len(ACCOUNTS) * len(ALL_QUESTIONS)}",
        f"",
    ]

    for role in ACCOUNTS:
        report_lines.append(f"---")
        report_lines.append(f"")
        report_lines.append(f"## {role}")
        report_lines.append(f"")
        report_lines.append(f"| # | Question | Answer | Engine |")
        report_lines.append(f"|---|----------|--------|--------|")

        for entry in all_results[role]:
            q = escape_md(entry["question"])
            a = escape_md(entry["answer"][:500])
            e = entry["engine"]
            report_lines.append(f"| | {q} | {a} | {e} |")

        report_lines.append(f"")

    report_path = "pingpong-crosstest-report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\nReport saved: {report_path}", flush=True)

    # Also save JSON
    json_path = "pingpong-crosstest-report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"JSON saved: {json_path}", flush=True)

if __name__ == "__main__":
    main()
