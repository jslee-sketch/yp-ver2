# tools/qa_sidecar_autotest_v2.py
from __future__ import annotations

import argparse
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

import tools.pingpong_sidecar_openai as sidecar


# ----------------------------
# Utilities
# ----------------------------
_EVID_RE = re.compile(r"\[근거:\s*([^\]]+)\]\s*$", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_DEEPLINK_RE = re.compile(r"yeokping://preview/\S+", re.IGNORECASE)


def parse_evidence(answer: str) -> str:
    m = _EVID_RE.search(answer or "")
    return (m.group(1).strip() if m else "")


def strip_evidence(answer: str) -> str:
    return _EVID_RE.sub("", (answer or "")).strip()


def ensure_parent(path: str) -> None:
    if not path:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: str, rec: Dict[str, Any]) -> None:
    if not path:
        return
    ensure_parent(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def reset_state(role: str = "BUYER", user_id: int = 1) -> None:
    sidecar.S = sidecar.ConversationState()
    sidecar.S.role = role
    sidecar.S.user_id = user_id


def has_deeplink(a: str) -> bool:
    return bool(_DEEPLINK_RE.search(a or ""))


# ----------------------------
# Case generation
# ----------------------------
def gen_internal(rng: random.Random) -> str:
    # 내부 SSOT/preview 관련(시간/환불/포인트 + ID-first 확장 케이스 포함)
    qs = [
        # time SSOT
        "딜방 모집/마감 기본 시간은 몇 시간이야?",
        "오퍼 마감시간은 몇 시간이야?",
        "오퍼 수정 가능 구간은 몇 시간이야?",
        "오퍼 마감 후 결제창은 몇 시간이야?",
        "예약 후 결제 제한시간은 몇 분이야?",
        "쿨링(환불 가능 기간) 기본은 며칠이야?",
        # refund instance (ID-first)
        "예약#403 환불가능 여부와 환불금액 알려줘",
        "예약#402 환불가능 여부 알려줘",
        # points deterministic
        "내 포인트 잔액은 몇 점이야?",
        # pending setup
        "환불 가능해?",
        # ✅ ID-first 확장(결제/배송/오퍼/딜방)
        "예약#403 결제 상태 알려줘",
        "예약#403 결제 프리뷰 보여줘",
        "예약#403 배송 상태 알려줘",
        "예약#403 송장/배송 정보 알려줘",
        "오퍼#101 상태/조건 알려줘",
        "오퍼#101 가격/배송 조건 요약해줘",
        "딜방#77 상태/마감 알려줘",
        "딜#77 상태/마감 알려줘",
    ]
    return rng.choice(qs)


def gen_external(rng: random.Random) -> str:
    qs = [
        "오늘 서울 날씨 어때?",
        "내일 부산 날씨(최고/최저/강수확률) 알려줘",
        "오늘 일본 관련 헤드라인 뉴스 3개 요약해줘",
        "오늘 미국 관련 해드라인 뉴스 3개만 뽑아줘",
        # 오타/변형
        "오늘 미국 관련 해드라운 뉴스 3개만 뽑아줘",
        "갤럭시북4 프로 16 최저가 알려줘",
        "LG OLED TV 55인치 C3 최저가와 범위 알려줘",
        "오뚜기 진라면 40개입 가격대 알려줘",
    ]
    return rng.choice(qs)


def gen_explain(rng: random.Random) -> str:
    qs = [
        "역핑은 어떤 플랫폼이야?",
        "딜방(Deal Room)이 뭐야?",
        "오퍼(Offer)는 뭐고 흐름은 어떻게 돼?",
        "구매자는 회원가입할 때 어떤 정보가 필요해?",
        "판매자 등급/티어는 어떻게 운영되는 구조야?",
        "환불은 어떤 기준으로 판단돼?",
    ]
    return rng.choice(qs)


def gen_smalltalk(rng: random.Random) -> str:
    qs = [
        "안녕",
        "오늘 기분이 좋아.",
        "요즘 좀 외롭다…",
        "개그 하나만 해줘",
        "핑퐁이로 3행시 해줘",
        "너는 안 추워?",
        "뭐하고 있어?",
        "배고픈데 뭐 먹을까?",
    ]
    return rng.choice(qs)


# ----------------------------
# Scoring
# ----------------------------
@dataclass
class Score:
    ok: bool
    reason: str


def score_internal(q: str, a: str) -> Score:
    evid = parse_evidence(a)
    body = strip_evidence(a)

    # refund instance: must be server and include deeplink to refund
    if "예약#" in q and ("환불" in q or "취소" in q):
        if evid != "server":
            return Score(False, f"refund instance expected evidence=server, got={evid}")
        if not has_deeplink(a):
            return Score(False, "refund instance missing deeplink")
        if "환불 프리뷰" not in body and "환불" not in body:
            return Score(False, "refund instance missing refund-like keywords")
        return Score(True, "OK")

    # points deterministic: server + '점'
    if ("포인트" in q) or ("잔액" in q):
        if evid != "server":
            return Score(False, f"points expected evidence=server, got={evid}")
        if "점" not in body:
            return Score(False, "points missing '점'")
        return Score(True, "OK")

    # payment/shipping/offer/dealroom: if ID present, must be server + deeplink
    if ("예약#" in q and any(k in q for k in ("결제", "영수증", "payment", "타임아웃"))) or ("예약#" in q and any(k in q for k in ("배송", "송장", "택배", "tracking"))):
        if evid != "server":
            return Score(False, f"reservation payment/shipping expected evidence=server, got={evid}")
        if not has_deeplink(a):
            return Score(False, "reservation payment/shipping missing deeplink")
        return Score(True, "OK")

    if "오퍼#" in q or ("오퍼" in q and "#101" in q):
        if evid != "server":
            return Score(False, f"offer instance expected evidence=server, got={evid}")
        if not has_deeplink(a):
            return Score(False, "offer instance missing deeplink")
        return Score(True, "OK")

    if "딜방#" in q or "딜#77" in q or "딜방" in q and "#77" in q:
        if evid != "server":
            return Score(False, f"dealroom instance expected evidence=server, got={evid}")
        if not has_deeplink(a):
            return Score(False, "dealroom instance missing deeplink")
        return Score(True, "OK")

    # time policy: should include duration (docs)
    if any(k in q for k in ("딜방", "오퍼", "결제창", "쿨링", "마감", "몇 시간", "몇 분", "며칠")):
        # allow docs or 없음 depending on your finalize
        if evid not in ("docs", "없음"):
            return Score(False, f"time policy expected evidence=docs(or 없음), got={evid}")
        if not re.search(r"\d+\s*(시간|분|일)", body):
            return Score(False, "time policy missing number+unit (시간/분/일)")
        return Score(True, "OK")

    # fallback
    return Score(True, "OK")


def score_external(q: str, a: str) -> Score:
    evid = parse_evidence(a)
    body = strip_evidence(a)

    if evid != "external":
        return Score(False, f"external expected evidence=external, got={evid}")

    is_unstable = ("불안정" in body) or ("못 가져왔" in body)

    wants_weather = bool(sidecar.WEATHER_PAT.search(q))
    wants_news = bool(sidecar.NEWS_PAT.search(q))
    wants_price = bool(sidecar.PRICE_PAT.search(q))

    if wants_weather:
        if is_unstable:
            if not (_URL_RE.search(body) or ("출처" in body)):
                return Score(False, "weather unstable but no links and no '출처'")
            return Score(True, "OK")
        if not re.search(r"-?\d+(\.\d+)?°", body):
            return Score(False, "weather success but missing temperature (°)")
        return Score(True, "OK")

    if wants_price:
        if is_unstable:
            if not (_URL_RE.search(body) or ("출처" in body)):
                return Score(False, "price unstable but no links and no '출처'")
            return Score(True, "OK")
        if not re.search(r"\d{1,3}(?:,\d{3})+\s*원|\d+\s*원", body):
            return Score(False, "price success but missing KRW amount")
        return Score(True, "OK")

    if wants_news:
        if is_unstable:
            if not (_URL_RE.search(body) or ("출처" in body)):
                return Score(False, "news unstable but no links and no '출처'")
            return Score(True, "OK")
        if not ("오늘 뉴스" in body or "/" in body):
            return Score(False, "news success but format doesn't look like headlines list")
        if "서울 기준" in body and "°" in body:
            return Score(False, "news response looks like weather output")
        return Score(True, "OK")

    if is_unstable and (_URL_RE.search(body) or ("출처" in body)):
        return Score(True, "OK")

    return Score(False, "external route triggered but topic not recognized")


def score_explain(q: str, a: str) -> Score:
    evid = parse_evidence(a)
    body = strip_evidence(a)
    if evid in ("external", "server"):
        return Score(False, f"explain got unexpected evidence={evid}")
    if len(body) < 10:
        return Score(False, "explain too short/empty")
    if any(k in q for k in ("역핑", "딜방", "오퍼", "환불")):
        if not any(k in body for k in ("딜", "딜방", "오퍼", "예약", "환불", "정책")):
            return Score(False, "explain missing core terms")
    return Score(True, "OK")


def score_smalltalk(q: str, a: str) -> Score:
    evid = parse_evidence(a)
    body = strip_evidence(a)

    if evid != "없음":
        return Score(False, f"smalltalk expected evidence=없음, got={evid}")
    if _URL_RE.search(body) or _DEEPLINK_RE.search(body):
        return Score(False, "smalltalk unexpectedly contains URL/deeplink")
    if "서울 기준" in body and "°" in body:
        return Score(False, "smalltalk looks like weather output")
    if "오늘 뉴스" in body and "/" in body:
        return Score(False, "smalltalk looks like news output")
    if re.search(r"\d+\s*원", body):
        return Score(False, "smalltalk looks like price output")
    return Score(True, "OK")


# ----------------------------
# Stress scenarios (multi-turn)
# ----------------------------
@dataclass
class ScenarioTurn:
    text: str
    kind: str  # smalltalk|weather|news|price|internal_points|internal_refund|internal_time|url_followup|id_payment|id_shipping|id_offer|id_dealroom|dontcare


def scenario_templates() -> List[List[ScenarioTurn]]:
    return [
        # Router regression: smalltalk -> weather -> smalltalk
        [
            ScenarioTurn("오늘 너무 추웠다.", "smalltalk"),
            ScenarioTurn("오늘 서울 날씨 어때?", "weather"),
            ScenarioTurn("너는 안 추워?", "smalltalk"),
        ],
        # News + URL follow-up
        [
            ScenarioTurn("오늘 미국 관련 해드라인 뉴스 3개만 뽑아줘.", "news"),
            ScenarioTurn("아, URL로 줄 수 있어?", "url_followup"),
            ScenarioTurn("고마워", "smalltalk"),
        ],
        # Weather then news (avoid stale links)
        [
            ScenarioTurn("오늘 서울 날씨 어때?", "weather"),
            ScenarioTurn("오늘 일본 관련 헤드라인 뉴스 3개 요약해줘", "news"),
            ScenarioTurn("출처", "dontcare"),
        ],
        # Price then source, then smalltalk
        [
            ScenarioTurn("갤럭시북4 프로 16 최저가 알려줘", "price"),
            ScenarioTurn("출처", "dontcare"),
            ScenarioTurn("너는 안 추워?", "smalltalk"),
        ],
        # Pending refund flow: set pending -> id-only triggers instance refund (server + deeplink)
        [
            ScenarioTurn("환불 가능해?", "dontcare"),
            ScenarioTurn("402", "internal_refund"),
        ],
        # Internal points should be server
        [
            ScenarioTurn("내 포인트 잔액은 몇 점이야?", "internal_points"),
            ScenarioTurn("고마워", "smalltalk"),
        ],
        # ✅ ID-first 확장: payment/shipping
        [
            ScenarioTurn("예약#403 결제 상태 알려줘", "id_payment"),
            ScenarioTurn("예약#403 배송 상태 알려줘", "id_shipping"),
            ScenarioTurn("고마워", "smalltalk"),
        ],
        # ✅ ID-first 확장: offer/dealroom
        [
            ScenarioTurn("오퍼#101 조건 요약해줘", "id_offer"),
            ScenarioTurn("딜방#77 상태/마감 알려줘", "id_dealroom"),
            ScenarioTurn("고마워", "smalltalk"),
        ],
    ]


def score_turn(turn: ScenarioTurn, answer: str) -> Score:
    q = turn.text

    if turn.kind == "smalltalk":
        return score_smalltalk(q, answer)
    if turn.kind in ("weather", "news", "price"):
        return score_external(q, answer)
    if turn.kind == "internal_points":
        return score_internal(q, answer)
    if turn.kind == "internal_refund":
        # expecting server + deeplink
        evid = parse_evidence(answer)
        if evid != "server":
            return Score(False, f"expected evidence=server, got={evid}")
        if not has_deeplink(answer):
            return Score(False, "refund follow-up missing deeplink")
        return Score(True, "OK")
    if turn.kind == "url_followup":
        evid = parse_evidence(answer)
        body = strip_evidence(answer)
        if evid != "external":
            return Score(False, f"url_followup expected evidence=external, got={evid}")
        if not _URL_RE.search(body):
            return Score(False, "url_followup missing URL")
        return Score(True, "OK")
    if turn.kind in ("id_payment", "id_shipping", "id_offer", "id_dealroom"):
        evid = parse_evidence(answer)
        if evid != "server":
            return Score(False, f"{turn.kind} expected evidence=server, got={evid}")
        if not has_deeplink(answer):
            return Score(False, f"{turn.kind} missing deeplink")
        return Score(True, "OK")

    # dontcare
    return Score(True, "OK")


# ----------------------------
# Runner
# ----------------------------
def run_single_category(
    name: str,
    n: int,
    rng: random.Random,
    client: OpenAI,
    *,
    dump_path: str,
    print_fail: bool,
    verbose: bool,
    show: int,
) -> Tuple[int, int, float, int]:
    ok_cnt = 0
    total_ms = 0.0
    fail_cnt = 0
    shown = 0

    for i in range(n):
        reset_state()

        if name == "internal":
            q = gen_internal(rng)
        elif name == "external":
            q = gen_external(rng)
        elif name == "explain":
            q = gen_explain(rng)
        else:
            q = gen_smalltalk(rng)

        t0 = time.time()
        a = sidecar.step_once(q, client)
        ms = (time.time() - t0) * 1000.0
        total_ms += ms

        if name == "internal":
            sc = score_internal(q, a)
        elif name == "external":
            sc = score_external(q, a)
        elif name == "explain":
            sc = score_explain(q, a)
        else:
            sc = score_smalltalk(q, a)

        ok = sc.ok
        if ok:
            ok_cnt += 1
        else:
            fail_cnt += 1

        rec = {
            "type": "single",
            "category": name,
            "i": i,
            "q": q,
            "a": a,
            "evidence": parse_evidence(a),
            "ok": ok,
            "reason": sc.reason,
            "latency_ms": int(ms),
        }
        append_jsonl(dump_path, rec)

        if verbose or (print_fail and not ok) or (show > 0 and shown < show):
            print("\n" + "=" * 80)
            print(f"[single] cat={name} i={i} ok={ok} ms={int(ms)} reason={sc.reason}")
            print(f"Q: {q}")
            print(f"A: {a}")
            shown += 1

    avg_ms = (total_ms / max(1, n))
    return ok_cnt, n, avg_ms, fail_cnt


def run_scenarios(
    scenario_n: int,
    rng: random.Random,
    client: OpenAI,
    *,
    dump_path: str,
    print_fail: bool,
    verbose: bool,
    show: int,
) -> Tuple[int, int, float, int]:
    templ = scenario_templates()
    ok_s = 0
    total_ms = 0.0
    fail_s = 0
    shown = 0

    for sid in range(scenario_n):
        reset_state()
        scenario = rng.choice(templ)

        scen_ok = True
        scen_reason = "OK"
        t0s = time.time()

        for tidx, turn in enumerate(scenario):
            q = turn.text
            a = sidecar.step_once(q, client)
            sc = score_turn(turn, a)

            rec = {
                "type": "scenario",
                "scenario_id": sid,
                "turn_idx": tidx,
                "turn_kind": turn.kind,
                "q": q,
                "a": a,
                "evidence": parse_evidence(a),
                "ok": sc.ok,
                "reason": sc.reason,
            }
            append_jsonl(dump_path, rec)

            if not sc.ok:
                scen_ok = False
                scen_reason = f"turn#{tidx} kind={turn.kind}: {sc.reason}"
                if verbose or print_fail:
                    print("\n" + "=" * 80)
                    print(f"[scenario FAIL] sid={sid} turn={tidx} kind={turn.kind} reason={sc.reason}")
                    print(f"Q: {q}")
                    print(f"A: {a}")
                break

            if show > 0 and shown < show and not verbose and not print_fail:
                print("\n" + "=" * 80)
                print(f"[scenario sample] sid={sid} turn={tidx} kind={turn.kind}")
                print(f"Q: {q}")
                print(f"A: {a}")
                shown += 1

        ms_s = (time.time() - t0s) * 1000.0
        total_ms += ms_s

        if scen_ok:
            ok_s += 1
        else:
            fail_s += 1

        append_jsonl(
            dump_path,
            {
                "type": "scenario_summary",
                "scenario_id": sid,
                "ok": scen_ok,
                "reason": scen_reason,
                "latency_ms": int(ms_s),
            },
        )

    avg_ms = (total_ms / max(1, scenario_n))
    return ok_s, scenario_n, avg_ms, fail_s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="single-turn 테스트를 카테고리별로 n개 실행")
    ap.add_argument("--scenario_n", type=int, default=100, help="멀티턴 스트레스 시나리오 개수")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--show", type=int, default=0, help="PASS 샘플을 일부 출력(카테고리/시나리오 합산)")
    ap.add_argument("--dump", type=str, default="", help="전체 케이스를 jsonl로 저장 (예: logs/autotest.jsonl)")
    ap.add_argument("--print_fail", action="store_true", help="FAIL 케이스 Q/A를 콘솔에 출력")
    ap.add_argument("--verbose", action="store_true", help="모든 케이스 Q/A를 콘솔에 출력(출력 매우 많음)")
    args = ap.parse_args()

    sidecar.load_kb()
    sidecar.load_time_values_from_defaults()

    client = OpenAI()
    rng = random.Random(args.seed)

    if args.dump:
        ensure_parent(args.dump)
        Path(args.dump).write_text("", encoding="utf-8")

    cats = ["internal", "external", "explain", "smalltalk"]

    print("\n--- single-turn tests ---")
    for c in cats:
        ok, n, avg, fail = run_single_category(
            c,
            args.n,
            rng,
            client,
            dump_path=args.dump,
            print_fail=args.print_fail,
            verbose=args.verbose,
            show=args.show,
        )
        pct = int(round((ok / max(1, n)) * 100))
        print(f"- {c}: {pct}% ({ok}/{n}) fail={fail} avg_ms={int(avg)}")

    print("\n--- scenario (multi-turn stress) ---")
    ok_s, n_s, avg_s, fail_s = run_scenarios(
        args.scenario_n,
        rng,
        client,
        dump_path=args.dump,
        print_fail=args.print_fail,
        verbose=args.verbose,
        show=args.show,
    )
    pct_s = int(round((ok_s / max(1, n_s)) * 100))
    print(f"- scenarios: {pct_s}% ({ok_s}/{n_s}) fail={fail_s} avg_ms={int(avg_s)}")

    if args.dump:
        print(f"\n📝 dumped: {args.dump}")


if __name__ == "__main__":
    main()