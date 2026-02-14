# tools/pingpong_sidecar_openai v1.2.py
# tools/pingpong_sidecar_openai.py
from __future__ import annotations

import os
import re
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI

# ============================================================
# Config
# ============================================================
OPENAI_MODEL = (os.environ.get("YP_OPENAI_MODEL") or "gpt-5-mini").strip()
YP_SERVER_URL = (os.environ.get("YP_SERVER_URL") or "http://127.0.0.1:9000").rstrip("/")
HTTP_TIMEOUT = float(os.environ.get("YP_HTTP_TIMEOUT") or "8.0")
EXTERNAL_TIMEOUT = float(os.environ.get("YP_EXTERNAL_TIMEOUT") or "2.5")

DEBUG = (os.environ.get("PINGPONG_SIDECAR_DEBUG") or "false").lower() == "true"
USER_NAME = (os.environ.get("YP_USER_NAME") or "").strip() or None

KEEP_TURNS = 8
DEFAULTS_YAML_PATH = ("app", "policy", "params", "defaults.yaml")
KST = ZoneInfo("Asia/Seoul")

HTTP = requests.Session()
HTTP.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PingpongSidecar/1.2",
        "Accept": "*/*",
    }
)

def _dbg(*args: Any) -> None:
    if DEBUG:
        ts = time.strftime("%H:%M:%S")
        print("[DBG]", ts, *args)

# ============================================================
# Exported KB loader (for autotest_v2 imports)
# ============================================================
@dataclass
class KBItem:
    path: str
    text: str
    text_l: str
    weight: float = 1.0

KB: List[KBItem] = []
_KB_LOADED = False

def repo_root() -> Path:
    cur = Path(__file__).resolve()
    for p in [cur.parent, cur.parent.parent, Path.cwd()]:
        if (p / "app").exists():
            return p
    return Path.cwd()

def load_kb() -> None:
    global KB, _KB_LOADED
    if _KB_LOADED:
        return
    root = repo_root()
    allow_suffix = {".md", ".txt", ".yaml", ".yml", ".json"}
    kb: List[KBItem] = []

    def _w(path_l: str) -> float:
        w = 1.0
        if "/policy/" in path_l:
            w *= 1.2
        if path_l.endswith("defaults.yaml") or path_l.endswith("defaults.yml"):
            w *= 1.6
        return w

    scan_dirs = [root / "docs", root / "app" / "policy", root / "app" / "docs"]
    for d in scan_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in allow_suffix:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                continue
            if not text:
                continue
            rel = str(f.relative_to(root)).replace("\\", "/")
            kb.append(KBItem(path=rel, text=text, text_l=text.lower(), weight=_w(rel.lower())))

    KB = kb
    _KB_LOADED = True
    print(f"✅ KB 로드 완료: {len(KB)}개 파일/문서 인덱싱됨")

def retrieve_kb_snippets(query: str) -> str:
    ql = (query or "").lower().strip()
    if not ql:
        return ""
    toks = re.findall(r"[가-힣]{2,}|[a-z]{2,}|[0-9]{1,}", ql)
    if not toks:
        return ""
    scored: List[Tuple[float, KBItem]] = []
    for it in KB:
        s = 0.0
        path_l = it.path.lower()
        for t in toks[:20]:
            if t in path_l:
                s += 8
            if t in it.text_l:
                s += min(20, it.text_l.count(t) * 2)
        s *= it.weight
        if s > 0:
            scored.append((s, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[str] = []
    total = 0
    for s, it in scored[:6]:
        chunk = it.text[:6000]
        block = f"### [자료: {it.path}] (score={int(s)}) ###\n{chunk}"
        if total + len(block) > 16000:
            break
        out.append(block)
        total += len(block)
    return "\n\n".join(out)

# ============================================================
# Exported time SSOT loader (for autotest_v2 imports)
# ============================================================
SSOT_TIME: Dict[str, float] = {}
_TIME_LOADED = False

def load_time_values_from_defaults() -> None:
    global SSOT_TIME, _TIME_LOADED
    if _TIME_LOADED:
        return
    root = repo_root()
    path = root.joinpath(*DEFAULTS_YAML_PATH)
    if not path.exists():
        SSOT_TIME = {}
        _TIME_LOADED = True
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        SSOT_TIME = {}
        _TIME_LOADED = True
        return

    out: Dict[str, float] = {}
    in_time = False
    base_indent: Optional[int] = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s*time\s*:\s*$", line):
            in_time = True
            base_indent = len(line) - len(line.lstrip())
            continue
        if not in_time:
            continue
        indent = len(line) - len(line.lstrip())
        if base_indent is not None and indent <= base_indent:
            break
        m = re.match(r"^\s*([a-zA-Z0-9_]+)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$", line)
        if not m:
            continue
        out[m.group(1).strip()] = float(m.group(2))
    SSOT_TIME = out
    _TIME_LOADED = True

def fmt_time_value(key: str, v: float) -> str:
    if key.endswith("_minutes") or key.endswith("_priority_minutes") or key.endswith("_timeout_minutes"):
        return f"{int(round(v))}분"
    if key.endswith("_days"):
        return f"{int(round(v))}일"
    if key.endswith("_hours"):
        if v < 1:
            return f"{int(round(v * 60))}분"
        if float(v).is_integer():
            return f"{int(v)}시간"
        hh = int(v)
        mm = int(round((v - hh) * 60))
        return f"{hh}시간 {mm}분" if mm > 0 else f"{hh}시간"
    return str(int(v)) if float(v).is_integer() else str(v)

# ============================================================
# Patterns / IDs
# ============================================================
_YEOKPING_HINT_PAT = re.compile(
    r"(역핑|딜방|딜\b|deal\b|오퍼|offer\b|예약|reservation\b|환불|취소|refund|cancel|"
    r"배송|shipping|수수료|fee|포인트|point|정산|settlement|등급|티어|tier|레벨|level|"
    r"마감|deadline|결제|payment|쿨링|cooling)",
    re.IGNORECASE,
)

PRICE_PAT = re.compile(r"(최저가|가격|얼마|price)", re.IGNORECASE)
WEATHER_PAT = re.compile(r"(날씨|weather|forecast)", re.IGNORECASE)
NEWS_PAT = re.compile(r"(뉴스|헤드라인|해드라인|headline|news)", re.IGNORECASE)

EXTERNAL_ASK_PAT = re.compile(
    r"(검색|찾아|조회|요약|알려|뉴스|헤드라인|해드라인|날씨|기온|강수|미세먼지|price|가격|최저가|얼마|시세)",
    re.IGNORECASE,
)


TIME_Q_PAT = re.compile(
    r"(몇\s*(시간|분|일)|기간|지속|유효|마감|남은\s*시간|deadline|until|"
    r"쿨링|cooling|환불\s*가능|취소\s*가능|무상\s*환불|결제창|payment\s*window|우선\s*시간|priority|타임아웃|timeout|윈도우|window)",
    re.IGNORECASE,
)
HOWTO_PAT = re.compile(r"(어떻게|방법|절차|순서|가이드|설명|정의|뭐야|무엇|만들|생성|등록|가입)", re.IGNORECASE)
INSTANCE_TIME_PAT = re.compile(r"(딜|오퍼|예약)\s*#?\s*\d+.*(언제|남은\s*시간|마감\s*시각|정확한|까지)", re.IGNORECASE)

_ID_ONLY_PAT = re.compile(r"^\s*#?\s*(\d{1,9})\s*(번|호)?\s*(?:이야|입니다|예요|요)?\s*[.!?]?\s*$")
_LINK_REQ_PAT = re.compile(r"(출처|링크|url|네이버|구글|다나와|쿠팡)", re.IGNORECASE)

def is_yeokping_related(q: str) -> bool:
    return bool(_YEOKPING_HINT_PAT.search(q or ""))

def extract_ids_from_text(q: str) -> Dict[str, Optional[int]]:
    q = q or ""
    out: Dict[str, Optional[int]] = {"deal_id": None, "offer_id": None, "reservation_id": None}

    def _looks_like_duration(text: str) -> bool:
        return bool(re.search(r"\d+\s*(시간|분|일|주|개월|년)\b", text))

    def _pick(pat: str) -> Optional[int]:
        m = re.search(pat, q, re.IGNORECASE)
        if not m:
            return None
        try:
            v = int(m.group(1))
            return v if v > 0 else None
        except Exception:
            return None

    if not _looks_like_duration(q):
        out["reservation_id"] = _pick(r"(?:예약|reservation)\s*(?:번호|id)?\s*#?\s*(\d{1,9})")
        out["offer_id"] = _pick(r"(?:오퍼|offer)\s*(?:번호|id)?\s*#?\s*(\d{1,9})")
        out["deal_id"] = _pick(r"(?:딜방|딜|deal)\s*(?:번호|id)?\s*#?\s*(\d{1,9})")
    return out

def parse_id_only(raw: str) -> Optional[int]:
    m = _ID_ONLY_PAT.match((raw or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

# ============================================================
# Deterministic time policy answer (policy questions only)
# ============================================================
def maybe_answer_time_policy_only(q: str) -> Optional[str]:
    q = (q or "").strip()
    if not q:
        return None
    if HOWTO_PAT.search(q):
        return None
    if not TIME_Q_PAT.search(q):
        return None
    if INSTANCE_TIME_PAT.search(q):
        return None

    rows: List[str] = []

    def add(label: str, key: str) -> None:
        v = SSOT_TIME.get(key)
        if v is None:
            return
        rows.append(f"{label}은 {fmt_time_value(key, v)}입니다.")

    # deal
    if re.search(r"(딜방|딜|deal).*(모집|마감|유효|지속|기간)", q, re.IGNORECASE):
        add("딜방 모집/마감 기본", "deal_deadline_hours")

    # offer
    if re.search(r"(오퍼|offer).*(수정|editable|edit)", q, re.IGNORECASE):
        add("오퍼 수정 가능 구간", "offer_editable_window_hours")
    if re.search(r"(오퍼|offer).*(마감|유효|지속|기간)", q, re.IGNORECASE):
        add("오퍼 마감 기본", "offer_deadline_hours")

    # payment
    if re.search(r"(결제창|payment\s*window|오퍼\s*마감\s*후\s*결제)", q, re.IGNORECASE):
        add("오퍼 마감 후 결제창", "buyer_payment_window_hours")
    if re.search(r"(예약|reservation).*(결제|타임아웃|제한|timeout)|결제\s*제한\s*시간", q, re.IGNORECASE):
        add("예약 후 결제 제한시간", "payment_timeout_minutes")

    # refund/cooling
    if re.search(r"(쿨링|cooling|환불\s*가능|취소\s*가능|무상\s*환불)", q, re.IGNORECASE):
        add("쿨링(환불 가능 기간) 기본", "cooling_days")

    # leader priority
    if re.search(r"(방장|리더|leader).*(우선|priority)", q, re.IGNORECASE):
        add("방장 우선 시간", "buyer_leader_priority_minutes")

    # seller decision
    if re.search(r"(판매자|seller).*(결정|decision).*(제한|timeout|시간|기간)", q, re.IGNORECASE):
        add("판매자 결정 제한시간", "seller_decision_timeout_hours")
    if re.search(r"(판매자|seller).*(결정).*(윈도우|window)", q, re.IGNORECASE):
        v = SSOT_TIME.get("seller_decision_window_hours")
        if v is not None:
            if abs(v - 0.5) < 1e-9:
                rows.append("판매자 결정 윈도우는 30분입니다.")
            else:
                rows.append(f"판매자 결정 윈도우는 {fmt_time_value('seller_decision_window_hours', v)}입니다.")

    if not rows:
        add("쿨링(환불 가능 기간) 기본", "cooling_days")

    if not rows:
        return None

    return " ".join(rows) + " (defaults.yaml SSOT 기준)"

# ============================================================
# External fetch (budgeted)
#  - ALWAYS returns links (list, can be empty)
#  - price: invalidate absurd low for expensive items
# ============================================================
_PRICE_RE = re.compile(r"(\d{1,3}(?:,\d{3})+)\s*원")
STOPWORDS_PRICE_QUERY = {
    "가격","최저가","얼마","좀","검색","검색해","검색해줘","알려줘","알려","가능","가능해","수","있어","있나요",
    "찾아","찾아줘","정보","부탁","해줄","해줘","모두","다","전부","전체",
}
EXPENSIVE_HINT = re.compile(
    r"(노트북|laptop|그램|gram|갤럭시북|galaxy\s*book|macbook|아이폰|iphone|갤럭시\s*s|rtx|oled|tv|"
    r"냉장고|세탁기|카메라|gpu|i7|i9|m3|m4|nt\d+|[A-Z]{2,}\d{3,})",
    re.IGNORECASE,
)

def _to_int_krw(s: str) -> Optional[int]:
    try:
        return int(s.replace(",", ""))
    except Exception:
        return None

def normalize_price_query(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"[?？!！]+$", "", s)
    toks = re.findall(r"[가-힣A-Za-z0-9]+", s)
    kept = [t for t in toks if t.lower() not in STOPWORDS_PRICE_QUERY]
    out = " ".join(kept).strip()
    return out if len(out) >= 2 else s

def _percentile(xs: List[int], p: float) -> Optional[int]:
    if not xs:
        return None
    xs2 = sorted(xs)
    k = int(round((len(xs2) - 1) * p))
    k = max(0, min(k, len(xs2) - 1))
    return xs2[k]

def fetch_price_external(q: str) -> Dict[str, Any]:
    query = normalize_price_query(q)
    links = [
        {"title": f"네이버쇼핑 '{query}'", "url": f"https://search.shopping.naver.com/search/all?query={quote_plus(query)}"},
        {"title": f"다나와 '{query}'", "url": f"https://search.danawa.com/dsearch.php?k1={quote_plus(query)}"},
        {"title": f"쿠팡 '{query}'", "url": f"https://www.coupang.com/np/search?q={quote_plus(query)}"},
    ]

    nums: List[int] = []
    try:
        r = HTTP.get(links[1]["url"], timeout=EXTERNAL_TIMEOUT)
        html = r.text or ""
        for m in _PRICE_RE.finditer(html):
            v = _to_int_krw(m.group(1))
            if v:
                nums.append(v)
    except Exception:
        nums = []

    nums = sorted(nums)[:300]
    low = min(nums) if nums else None
    p10 = _percentile(nums, 0.10) if nums else None
    p50 = _percentile(nums, 0.50) if nums else None
    p90 = _percentile(nums, 0.90) if nums else None

    if EXPENSIVE_HINT.search(query) and low is not None and low < 50000:
        return {"kind": "price", "ok": False, "links_only": True, "query": query, "links": links}

    ok = bool(nums and low is not None and p90 is not None)
    return {"kind": "price", "ok": ok, "links_only": (not ok), "query": query, "low_estimate": low, "range": {"p10": p10, "p50": p50, "p90": p90}, "links": links}

def fetch_news_external(q: str) -> Dict[str, Any]:
    query = normalize_external_query(q)
    rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
    links = [
        {"title": f"구글뉴스 '{query}'", "url": f"https://news.google.com/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"},
        {"title": f"네이버뉴스 '{query}'", "url": f"https://search.naver.com/search.naver?where=news&query={quote_plus(query)}"},
    ]
    try:
        r = HTTP.get(rss_url, timeout=EXTERNAL_TIMEOUT)
        if r.status_code != 200:
            return {"kind": "news", "ok": False, "links": links}
        root = ET.fromstring(r.text)
    
        items = []
        for it in root.findall(".//item")[:5]:
            t = (it.findtext("title") or "").strip()
            u = (it.findtext("link") or "").strip()
            if t and u:
                items.append({"title": t, "url": u})

        headlines = [x["title"] for x in items][:3]
        return {"kind": "news", "ok": bool(items), "items": items, "headlines": headlines, "links": links}

    except Exception:
        return {"kind": "news", "ok": False, "links": links}

CITY_COORDS = {
    "서울": (37.5665, 126.9780),
    "부산": (35.1796, 129.0756),
    "인천": (37.4563, 126.7052),
    "대구": (35.8714, 128.6014),
    "대전": (36.3504, 127.3845),
    "광주": (35.1595, 126.8526),
    "울산": (35.5384, 129.3114),
    "수원": (37.2636, 127.0286),
    "제주": (33.4996, 126.5312),
}

def fetch_weather_external(q: str) -> Dict[str, Any]:
    city = "서울"
    for c in CITY_COORDS.keys():
        if c in q:
            city = c
            break
    lat, lon = CITY_COORDS[city]
    links = [
        {"title": f"네이버 '{city} 날씨'", "url": f"https://search.naver.com/search.naver?query={quote_plus(city+' 날씨')}"},
        {"title": f"구글 '{city} weather'", "url": f"https://www.google.com/search?q={quote_plus(city+' weather')}"},
    ]
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max", "timezone": "Asia/Seoul"}
        r = HTTP.get(url, params=params, timeout=EXTERNAL_TIMEOUT)
        if r.status_code != 200:
            return {"kind": "weather", "ok": False, "city": city, "links": links}
        data = r.json()
        daily = data.get("daily") or {}
        dates = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        pmax = daily.get("precipitation_probability_max") or []
        items = []
        for i in range(min(3, len(dates))):
            items.append({"date": dates[i], "tmax": tmax[i], "tmin": tmin[i], "precip": pmax[i]})
        return {"kind": "weather", "ok": bool(items), "city": city, "daily_3d": items, "links": links}
    except Exception:
        return {"kind": "weather", "ok": False, "city": city, "links": links}

def external_fetch(q: str) -> Dict[str, Any]:
    if WEATHER_PAT.search(q):
        return fetch_weather_external(q)
    if NEWS_PAT.search(q):
        return fetch_news_external(q)
    if PRICE_PAT.search(q):
        return fetch_price_external(q)
    return {"kind": "none", "ok": False, "links": []}

# ============================================================
# Server calls: preview + refund_preview
# ============================================================
def _http_get_json(url: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        r = HTTP.get(url, params=params, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if isinstance(data, dict):
            data["_http_status"] = r.status_code
        return data if isinstance(data, dict) else {"detail": str(data), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": None}

def call_preview(entity: str, _id: int, user_id: int, role: str) -> Dict[str, Any]:
    return _http_get_json(f"{YP_SERVER_URL}/preview/{entity}/{_id}", {"user_id": user_id, "role": role}, timeout=HTTP_TIMEOUT)

def call_preview_me(user_id: int, role: str) -> Dict[str, Any]:
    return _http_get_json(f"{YP_SERVER_URL}/preview/me", {"user_id": user_id, "role": role}, timeout=HTTP_TIMEOUT)

def call_refund_preview(reservation_id: int, role: str) -> Dict[str, Any]:
    fault_party = "BUYER"
    trigger = "BUYER_CANCEL"
    if (role or "").upper() == "SELLER":
        fault_party = "SELLER"
        trigger = "SELLER_CANCEL"
    return _http_get_json(
        f"{YP_SERVER_URL}/admin/refund/preview",
        {"reservation_id": reservation_id, "fault_party": fault_party, "trigger": trigger},
        timeout=HTTP_TIMEOUT,
    )

def answer_from_refund_preview(pre: Dict[str, Any]) -> str:
    if not isinstance(pre, dict):
        return "지금은 환불 프리뷰 응답을 해석할 수 없어요."
    st = int(pre.get("_http_status") or 0)
    if st >= 500 or pre.get("error") == "OFFLINE":
        return "예약 환불 프리뷰 조회가 지금 실패했어요. 잠시 후 다시 시도해 주세요."
    if st >= 300:
        detail = pre.get("detail") or pre.get("msg") or pre.get("error") or "요청이 처리되지 않았습니다."
        return f"예약 환불 프리뷰 조회가 지금 실패했어요: {detail}"

    ctx = pre.get("ctx") if isinstance(pre.get("ctx"), dict) else {}
    meta = pre.get("meta") if isinstance(pre.get("meta"), dict) else {}
    decision = pre.get("decision") if isinstance(pre.get("decision"), dict) else {}

    total = meta.get("amount_total_refund") or ctx.get("amount_total")
    goods = meta.get("amount_goods_refund") or ctx.get("amount_goods")
    ship = meta.get("amount_shipping_refund") or ctx.get("amount_shipping")
    note = meta.get("decision_note") or decision.get("note")

    if total is None:
        return "환불 프리뷰는 조회됐지만, 금액 계산 결과가 비어 있어요."

    msg = f"예약 환불 프리뷰 기준으로 총 {int(total):,}원"
    if goods is not None or ship is not None:
        msg += f" (상품 {int(goods or 0):,}원 / 배송 {int(ship or 0):,}원)"
    msg += " 입니다."
    if note:
        msg += f" {str(note)}"
    return msg

# ============================================================
# Conversation state
# ============================================================
@dataclass
class ConversationState:
    role: str = "BUYER"
    user_id: int = 1
    user_name: Optional[str] = None

    pending_kind: Optional[str] = None   # reservation/offer/deal
    pending_template: Optional[str] = None

    last_ids: Dict[str, Optional[int]] = field(default_factory=lambda: {"deal_id": None, "offer_id": None, "reservation_id": None})
    last_mode: str = "chitchat"
    last_links: List[Dict[str, str]] = field(default_factory=list)

    # ✅ last external context (for follow-up link requests)
    last_external_kind: str = ""  # "news" / "weather" / "price"
    last_external_query: str = ""  # normalized external query (for "출처" display)
    last_news_items: List[Dict[str, str]] = field(default_factory=list)

    history: List[Dict[str, str]] = field(default_factory=list)

S = ConversationState()

def observe_user_query_intent(state: ConversationState, q: str) -> None:
    ql = (q or "").lower()
    if re.search(r"(환불|취소|refund|cancel)", ql):
        state.pending_kind = "reservation"
        state.pending_template = "예약#{id} 환불 가능 여부와 환불 금액 알려줘"
        return
    if re.search(r"(오퍼|offer)", ql):
        state.pending_kind = "offer"
        state.pending_template = "오퍼#{id} 상태/마감/조건 알려줘"
        return
    if re.search(r"(딜방|딜|deal)", ql):
        state.pending_kind = "deal"
        state.pending_template = "딜#{id} 상태/마감 알려줘"
        return

def normalize_user_input(state: ConversationState, raw: str) -> str:
    n = parse_id_only(raw)
    if n is None:
        return raw
    if state.pending_kind and state.pending_template:
        return state.pending_template.format(id=n)
    return raw

def update_last_ids_from_text(state: ConversationState, q: str) -> None:
    ids = extract_ids_from_text(q)
    for k in ("deal_id", "offer_id", "reservation_id"):
        if ids.get(k) is not None:
            state.last_ids[k] = ids[k]

def likely_followup_is_yeokping(prev_mode: str, raw: str) -> bool:
    if prev_mode != "yeokping":
        return False
    if parse_id_only(raw) is not None:
        return True
    return bool(re.search(r"(그럼|그거|왜|맞지|아니|다시|확인)", raw))

def _merge_links(a: List[Dict[str, str]], b: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for src in (a or []) + (b or []):
        if not isinstance(src, dict):
            continue
        url = (src.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"title": (src.get("title") or url).strip(), "url": url})
    return out

# ============================================================
# OpenAI only for smalltalk/explain (no internal facts)
# ============================================================
def instructions_for(category: str, user_name: Optional[str]) -> str:
    name = f"{user_name}님" if user_name else "고객님"
    if category == "smalltalk":
        return f"""
너는 친절하고 자연스러운 대화 상대(핑퐁이)야.
- 역핑/SSOT/서버/preview 같은 단어를 절대 꺼내지 마.
- 1~4문장.
- 호칭은 "{name}".
""".strip()
    if category == "explain":
        return f"""
너는 역핑을 설명하는 역할이야.
- 딜/딜방/오퍼/예약 흐름으로 설명해.
- 숫자/정책시간은 '이미 주어진 SSOT'가 있을 때만 인용해.
- 2~8문장.
- 호칭은 "{name}".
""".strip()
    return f"한국어로 2~6문장. 호칭은 {name}."

def openai_generate(client: OpenAI, category: str, question: str, docs: str, history: List[Dict[str, str]], user_name: Optional[str]) -> str:
    hist = history[-KEEP_TURNS:]
    hist_txt = ""
    if hist:
        lines = []
        for t in hist:
            u = (t.get("user") or "").strip()
            a = (t.get("bot") or "").strip()
            if u:
                lines.append(f"사용자: {u}")
            if a:
                lines.append(f"핑퐁이: {a}")
        hist_txt = "\n".join(lines)

    prompt = f"""
[최근 대화]
{hist_txt if hist_txt else "(없음)"}

[질문]
{question}

[DOCS]
{docs if docs else "(없음)"}
""".strip()

    resp = client.responses.create(
        model=OPENAI_MODEL,
        instructions=instructions_for(category, user_name),
        input=prompt,
        text={"verbosity": "medium"},
        reasoning={"effort": "minimal"},
        max_output_tokens=450,
        store=False,
    )
    return (resp.output_text or "").strip()

def _fmt_kst_min(dt: datetime) -> str:
    # YYYY-MM-DD HH:MM (KST)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")

def _parse_dt_any(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, (int, float)):
        # epoch seconds
        try:
            return datetime.fromtimestamp(float(v), tz=KST)
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # tolerate "Z"
        s = s.replace("Z", "+00:00")
        # tolerate space
        s = s.replace(" ", "T") if "T" not in s and ":" in s else s
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None

def _find_created_at(obj: Any) -> Optional[datetime]:
    """Try to find created_at in nested dicts."""
    if isinstance(obj, dict):
        for k in ("created_at", "createdAt", "created_time", "createdTime", "created"):
            if k in obj:
                dt = _parse_dt_any(obj.get(k))
                if dt:
                    return dt
        # search shallowly in common nests
        for k in ("pack", "ctx", "meta", "reservation", "deal", "offer", "data"):
            dt = _find_created_at(obj.get(k))
            if dt:
                return dt
    elif isinstance(obj, list):
        for it in obj[:5]:
            dt = _find_created_at(it)
            if dt:
                return dt
    return None

def deeplink_for(kind: str, _id: int, sub: str = "") -> str:
    # 앱 전용 딥링크 (웹 없음)
    if kind == "reservation":
        base = f"yeokping://preview/reservation/{_id}"
        return base + (f"/{sub}" if sub else "")
    if kind == "offer":
        return f"yeokping://preview/offer/{_id}"
    if kind == "dealroom":
        return f"yeokping://preview/dealroom/{_id}"
    if kind == "me":
        return f"yeokping://preview/me/{_id}"
    return f"yeokping://preview/me/{S.user_id}"

def header_with_created(kind_kr: str, _id: int, created_at: Optional[datetime]) -> str:
    if created_at:
        return f"{kind_kr} #{_id} · 생성 {_fmt_kst_min(created_at)} (KST)"
    return f"{kind_kr} #{_id} · 생성시각 확인 필요"

def render_button(label: str, link: str) -> str:
    # CLI에서는 버튼을 텍스트로 표현 (앱 UI에서는 실제 버튼으로 매핑)
    return f"[{label}]({link})"


def finalize(answer: str, evidence: str) -> str:
    a = (answer or "").strip()
    a = re.sub(r"(?:\n*\[근거:[^\]]*\]\s*)+$", "", a, flags=re.IGNORECASE).strip()
    return a + f"\n[근거: {evidence}]"


def _dig(obj: Any, keys: List[str]) -> Any:
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur

def _first_str(*vals: Any) -> Optional[str]:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None

def _first_int(*vals: Any) -> Optional[int]:
    for v in vals:
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    return None

def _topic_for_reservation(q: str) -> str:
    # refund / payment / shipping / general
    if re.search(r"(환불|취소|refund|cancel|쿨링|cooling|반품|교환)", q, re.IGNORECASE):
        return "refund"
    if re.search(r"(결제|영수증|결제창|payment|타임아웃|timeout|실패|승인|카드)", q, re.IGNORECASE):
        return "payment"
    if re.search(r"(배송|송장|택배|tracking|shipment|shipping|도착|출고|지연)", q, re.IGNORECASE):
        return "shipping"
    return "reservation"

def _summarize_reservation_payment(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보(가능하면): 상태, 금액, 제한시간/메모
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    # 흔한 키 후보들
    status = _first_str(
        _dig(pack, ["reservation", "status"]),
        _dig(pack, ["status"]),
        _dig(pre, ["ctx", "status"]),
    )
    amount = _first_int(
        _dig(pack, ["reservation", "amount_total"]),
        _dig(pack, ["amount_total"]),
        _dig(pre, ["ctx", "amount_total"]),
    )
    timeout_min = _first_int(
        _dig(pack, ["reservation", "payment_timeout_minutes"]),
        _dig(pre, ["ctx", "payment_timeout_minutes"]),
    )
    lines: List[str] = []
    if status:
        lines.append(f"• 결제/예약 상태: {status}")
    if amount is not None:
        lines.append(f"• 결제 금액: {amount:,}원")
    if timeout_min is not None:
        lines.append(f"• 결제 제한시간: {timeout_min}분")
    return lines[:3]

def _summarize_reservation_shipping(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보: 배송상태, 택배사/송장, 최근 업데이트
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    ship_status = _first_str(
        _dig(pack, ["reservation", "shipping_status"]),
        _dig(pack, ["shipping", "status"]),
        _dig(pre, ["ctx", "shipping_status"]),
    )
    carrier = _first_str(
        _dig(pack, ["shipping", "carrier"]),
        _dig(pack, ["reservation", "shipping_carrier"]),
    )
    tracking = _first_str(
        _dig(pack, ["shipping", "tracking_no"]),
        _dig(pack, ["reservation", "tracking_no"]),
    )
    updated = _first_str(
        _dig(pack, ["shipping", "updated_at"]),
        _dig(pack, ["reservation", "shipping_updated_at"]),
    )
    lines: List[str] = []
    if ship_status:
        lines.append(f"• 배송 상태: {ship_status}")
    if carrier or tracking:
        lines.append(f"• 송장: {carrier or '택배'} {tracking or ''}".strip())
    if updated:
        lines.append(f"• 최근 업데이트: {updated}")
    return lines[:3]

def _summarize_offer(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보: 가격/조건/마감
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    price = _first_int(_dig(pack, ["offer", "price"]), _dig(pack, ["price"]))
    ship = _first_str(_dig(pack, ["offer", "shipping"]), _dig(pack, ["shipping"]))
    deadline = _first_str(_dig(pack, ["offer", "deadline_at"]), _dig(pack, ["deadline_at"]))
    lines: List[str] = []
    if price is not None:
        lines.append(f"• 제안가: {price:,}원")
    if ship:
        lines.append(f"• 배송: {ship}")
    if deadline:
        lines.append(f"• 마감: {deadline}")
    return lines[:3]

def _summarize_dealroom(pre: Dict[str, Any]) -> List[str]:
    # 최대 3개 정보: 모집현황/마감/타겟 등(가능한 것만)
    pack = _dig(pre, ["pack"]) if isinstance(pre, dict) else None
    cur = _first_int(_dig(pack, ["deal", "buyer_count"]), _dig(pack, ["buyer_count"]))
    target = _first_int(_dig(pack, ["deal", "target_buyer_count"]), _dig(pack, ["target_buyer_count"]))
    deadline = _first_str(_dig(pack, ["deal", "deadline_at"]), _dig(pack, ["deadline_at"]))
    lines: List[str] = []
    if cur is not None and target is not None:
        lines.append(f"• 참여 현황: {cur}/{target}")
    elif cur is not None:
        lines.append(f"• 참여자 수: {cur}")
    if deadline:
        lines.append(f"• 마감: {deadline}")
    return lines[:3]



# ============================================================
# External query normalization (for links/search)
#   - Remove chatty filler ("아... 오케이", "알려줘" ...)
#   - Keep short, keyword-like query
# ============================================================
STOPWORDS_EXTERNAL_QUERY = {
    # filler / interjection
    "아", "아아", "음", "어", "오케이", "ok", "ㅇㅋ", "ㅎㅎ", "ㅋㅋ",
    # request verbs
    "알려줘", "알려", "말해줘", "말해", "찾아줘", "찾아", "보여줘", "보여",
    "검색", "검색해", "검색해줘", "부탁", "해줘", "해줄",
    # time/quantity fluff
    "오늘", "지금", "방금", "하나만", "한개만",
    # common wrappers
    "관련", "관련한", "헤드라인",
    # common intent words that should not become query
    "뉴스", "기사", "헤드라인", "해드라인", "url", "링크",
    "뽑아줘", "뽑아", "줘", "줄래", "줄래요", "줘요",
    "하나", "하나만", "한", "개", "한개", "한개만",
    "관련", "관련한",
}

def normalize_external_query(text: str, *, max_len: int = 80) -> str:
    s = (text or "").strip()
    # trailing punctuation
    s = re.sub(r"[?？!！.。]+$", "", s)
    s = re.sub(r"\s+", " ", s)

    toks = re.findall(r"[가-힣A-Za-z0-9]+", s)
    kept = []
    for t in toks:
        tl = t.lower()
        if tl in STOPWORDS_EXTERNAL_QUERY:
            continue
        kept.append(t)

    out = " ".join(kept).strip()
    if len(out) < 2:
        out = s

    if len(out) > max_len:
        out = out[:max_len].rstrip()
    return out


def handle_external(raw: str, q: str) -> Optional[str]:
    """
    External handler SSOT:
    - External is triggered ONLY when:
        (EXTERNAL_ASK_PAT matches AND topic matches) OR topic matches strongly
    - Prevent smalltalk from leaking into external.
    - Always refresh S.last_links for this request (or clear).
    - Support follow-up: "URL/링크" after news headlines.
    """
    # 0) follow-up: previously fetched news -> user asks url/link
    if re.search(r"(url|링크|주소)", raw, re.IGNORECASE) and S.last_external_kind == "news" and S.last_news_items:
        it = S.last_news_items[0]
        msg = f"가장 위 제목 링크예요: {it.get('url')}"
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "external")

    # 1) detect topics by raw(q)
    wants_weather = bool(WEATHER_PAT.search(q))
    wants_news = bool(NEWS_PAT.search(q))
    wants_price = bool(PRICE_PAT.search(q))

    has_topic = bool(wants_weather or wants_news or wants_price)
    has_intent = bool(EXTERNAL_ASK_PAT.search(q))

    # 2) strict gate: to avoid "너는 안 추워?" leaking into external
    #    - must have topic AND intent
    if not (has_topic and has_intent):
        return None

    # 3) choose kind by topic
    if wants_weather:
        kind = "weather"
    elif wants_news:
        kind = "news"
    else:
        kind = "price"

    # 4) normalize query for search/links
    eq = normalize_external_query(q)

    # 5) save SSOT for "출처"
    S.last_external_kind = kind
    S.last_external_query = eq

    # 6) fetch by kind
    if kind == "weather":
        ext = fetch_weather_external(eq)
    elif kind == "news":
        ext = fetch_news_external(eq)
    else:
        ext = fetch_price_external(eq)

    # 7) build links (prefer ext.links, fallback by kind)
    links = ext.get("links") if isinstance(ext, dict) else []
    if isinstance(links, list) and links:
        S.last_links = _merge_links([], links)
    else:
        if kind == "news":
            S.last_links = _merge_links([], [
                {"title": f"구글뉴스 '{eq}'", "url": f"https://news.google.com/search?q={quote_plus(eq)}&hl=ko&gl=KR&ceid=KR:ko"},
                {"title": f"네이버뉴스 '{eq}'", "url": f"https://search.naver.com/search.naver?where=news&query={quote_plus(eq)}"},
            ])
        elif kind == "weather":
            S.last_links = _merge_links([], [
                {"title": f"네이버 '{eq} 날씨'", "url": f"https://search.naver.com/search.naver?query={quote_plus(eq+' 날씨')}"},
                {"title": f"구글 '{eq} weather'", "url": f"https://www.google.com/search?q={quote_plus(eq+' weather')}"},
            ])
        else:
            S.last_links = _merge_links([], [
                {"title": f"네이버쇼핑 '{eq}'", "url": f"https://search.shopping.naver.com/search/all?query={quote_plus(eq)}"},
                {"title": f"다나와 '{eq}'", "url": f"https://search.danawa.com/dsearch.php?k1={quote_plus(eq)}"},
                {"title": f"쿠팡 '{eq}'", "url": f"https://www.coupang.com/np/search?q={quote_plus(eq)}"},
            ])

    # 8) if fetch failed, still provide links
    if not isinstance(ext, dict) or not ext.get("ok"):
        msg = "지금은 실시간 조회가 불안정합니다."
        if S.last_links:
            msg += "\n" + "\n".join([f"- {x['title']}: {x['url']}" for x in S.last_links[:2] if x.get("url")])
        else:
            msg += " 필요하시면 '출처'라고 입력해 주세요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "external")

    # 9) success rendering
    if kind == "weather":
        city = ext.get("city") or "서울"
        items = ext.get("daily_3d") or []
        if items:
            d0 = items[0]
            msg = f"{city} 기준 {d0.get('date')} 예상 최고 {d0.get('tmax')}° / 최저 {d0.get('tmin')}°, 강수확률 {d0.get('precip')}% 입니다."
        else:
            msg = "날씨 정보를 가져오지 못했어요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "external")

    if kind == "news":
        # store items for follow-up URL requests
        S.last_news_items = ext.get("items") or []
        heads = ext.get("headlines") or []
        if heads:
            msg = "오늘 뉴스로는 이런 제목들이 보여요: " + " / ".join(heads[:3])
        else:
            msg = "뉴스 제목을 가져오지 못했어요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "external")

    # price
    if ext.get("links_only") or not ext.get("ok"):
        msg = "지금은 신뢰할 수 있는 가격 숫자를 못 가져왔어요."
        if S.last_links:
            msg += "\n" + "\n".join([f"- {x['title']}: {x['url']}" for x in S.last_links[:2] if x.get("url")])
        else:
            msg += " 필요하시면 '출처'라고 입력해 주세요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "external")

    low = ext.get("low_estimate")
    rg = ext.get("range") or {}
    p10, p50, p90 = rg.get("p10"), rg.get("p50"), rg.get("p90")
    msg = f"최저가 추정 {int(low):,}원 / 대략 {int(p10):,}~{int(p90):,}원 범위 (중앙값 {int(p50):,}원) 정도로 보여요. (실시간 변동 가능)"
    S.last_mode = "external"
    S.history.append({"user": q, "bot": msg})
    S.history[:] = S.history[-KEEP_TURNS:]
    return finalize(msg, "external")


# ============================================================
# Core step (exported for autotest_v2)
# ============================================================
def step_once(raw: str, client: OpenAI) -> str:
    global S
    raw = (raw or "").strip()
    if not raw:
        return ""

    load_kb()
    load_time_values_from_defaults()

    # "출처" command
    if raw in ("출처", "링크", "source"):
        if not S.last_links:
            return finalize("(지금 보여드릴 출처가 없어요.)", "없음")
        lines = ["요청하신 출처 링크입니다."]
        if S.last_external_query:
            lines.append(f"(검색어: {S.last_external_query})")
        for it in S.last_links[:10]:
            lines.append(f"- {it.get('title')} : {it.get('url')}")
        return finalize("\n".join(lines), "external")

    prev_mode = S.last_mode
    observe_user_query_intent(S, raw)

    q = normalize_user_input(S, raw)
    update_last_ids_from_text(S, q)

    # ✅ 회귀 방지: 일반 대화로 넘어가면 pending을 해제(환불 고착 방지)
    if not is_yeokping_related(q) and not EXTERNAL_ASK_PAT.search(q):
        if parse_id_only(raw) is None:
            S.pending_kind = None
            S.pending_template = None


    # ============================================================
    # ID-first SSOT (instance) — if ID is present, go to server + button UX
    #   - reservation: refund/payment/shipping/general
    #   - offer: offer preview
    #   - deal: dealroom preview
    # ============================================================
    ids_now = extract_ids_from_text(q)
    _dbg("gate_idfirst", {"raw": raw, "q": q, "ids_now": ids_now, "pending": S.pending_kind, "last_ids": S.last_ids})

    rid_now = ids_now.get("reservation_id")
    oid_now = ids_now.get("offer_id")
    did_now = ids_now.get("deal_id")

    # --- reservation id path ---
    if rid_now:
        rid_int = int(rid_now)
        topic = _topic_for_reservation(q)

        # created_at (best effort)
        created_at = None
        pre_res: Optional[Dict[str, Any]] = None
        try:
            pre_res = call_preview("reservation", rid_int, S.user_id, S.role)
            created_at = _find_created_at(pre_res)
        except Exception:
            pre_res = None
            created_at = None

        head = header_with_created("예약", rid_int, created_at)

        # (1) refund -> refund_preview endpoint
        if topic == "refund":
            pre = call_refund_preview(rid_int, S.role)

            link = deeplink_for("reservation", rid_int, "refund")
            btn = render_button("환불 프리뷰 열기", link)

            st = int(pre.get("_http_status") or 0) if isinstance(pre, dict) else 0
            offline = isinstance(pre, dict) and pre.get("error") == "OFFLINE"
            if offline or st >= 300 or not isinstance(pre, dict):
                msg = (
                    f"{head}\n\n"
                    "지금 대화에서는 환불 정보를 조회하지 못했어요.\n"
                    "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                    f"{btn}"
                )
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            # 성공: 최대 3개 정보
            ctx = pre.get("ctx") if isinstance(pre.get("ctx"), dict) else {}
            meta = pre.get("meta") if isinstance(pre.get("meta"), dict) else {}
            decision = pre.get("decision") if isinstance(pre.get("decision"), dict) else {}

            total = meta.get("amount_total_refund") or ctx.get("amount_total")
            goods = meta.get("amount_goods_refund") or ctx.get("amount_goods")
            ship = meta.get("amount_shipping_refund") or ctx.get("amount_shipping")
            note = meta.get("decision_note") or decision.get("note")

            lines: List[str] = []
            if total is not None:
                lines.append(f"• 환불 프리뷰 기준 총 {int(total):,}원")
            if goods is not None or ship is not None:
                lines.append(f"• 상품 {int(goods or 0):,}원 / 배송 {int(ship or 0):,}원")
            if note:
                lines.append(f"• {str(note)}")
            lines = lines[:3] if lines else ["• 환불 프리뷰 요약을 만들지 못했어요."]

            msg = f"{head}\n\n" + "\n".join(lines) + f"\n\n{btn}"
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        # (2) payment -> reservation preview + payment screen
        if topic == "payment":
            link = deeplink_for("reservation", rid_int, "payment")
            btn = render_button("결제 프리뷰 열기", link)

            # 서버 조회 실패해도 버튼은 제공
            if not isinstance(pre_res, dict) or (pre_res.get("_http_status") or 0) >= 300:
                msg = (
                    f"{head}\n\n"
                    "지금 대화에서는 결제 정보를 조회하지 못했어요.\n"
                    "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                    f"{btn}"
                )
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            lines = _summarize_reservation_payment(pre_res)
            if not lines:
                lines = ["• 결제 요약 정보를 만들지 못했어요."]

            msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        # (3) shipping -> reservation preview + shipping screen
        if topic == "shipping":
            link = deeplink_for("reservation", rid_int, "shipping")
            btn = render_button("배송 프리뷰 열기", link)

            if not isinstance(pre_res, dict) or (pre_res.get("_http_status") or 0) >= 300:
                msg = (
                    f"{head}\n\n"
                    "지금 대화에서는 배송 정보를 조회하지 못했어요.\n"
                    "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                    f"{btn}"
                )
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            lines = _summarize_reservation_shipping(pre_res)
            if not lines:
                lines = ["• 배송 요약 정보를 만들지 못했어요."]

            msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        # (4) general reservation preview screen
        link = deeplink_for("reservation", rid_int, "")
        btn = render_button("예약 프리뷰 열기", link)

        if not isinstance(pre_res, dict) or (pre_res.get("_http_status") or 0) >= 300:
            msg = (
                f"{head}\n\n"
                "지금 대화에서는 예약 정보를 조회하지 못했어요.\n"
                "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                f"{btn}"
            )
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        # 최대 3개: 상태/금액/기타(있으면)
        pack = pre_res.get("pack") if isinstance(pre_res.get("pack"), dict) else {}
        status = _first_str(_dig(pack, ["reservation", "status"]), _dig(pack, ["status"]), _dig(pre_res, ["ctx", "status"]))
        amount = _first_int(_dig(pack, ["reservation", "amount_total"]), _dig(pack, ["amount_total"]), _dig(pre_res, ["ctx", "amount_total"]))
        lines: List[str] = []
        if status:
            lines.append(f"• 예약 상태: {status}")
        if amount is not None:
            lines.append(f"• 금액: {amount:,}원")
        lines = lines[:3] if lines else ["• 예약 요약 정보를 만들지 못했어요."]

        msg = f"{head}\n\n" + "\n".join(lines) + f"\n\n{btn}"
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # --- offer id path ---
    if oid_now:
        oid_int = int(oid_now)
        pre = call_preview("offer", oid_int, S.user_id, S.role)
        created_at = _find_created_at(pre)
        head = header_with_created("오퍼", oid_int, created_at)
        link = deeplink_for("offer", oid_int, "")
        btn = render_button("오퍼 프리뷰 열기", link)

        st = int(pre.get("_http_status") or 0) if isinstance(pre, dict) else 0
        if st >= 300 or not isinstance(pre, dict):
            msg = (
                f"{head}\n\n"
                "지금 대화에서는 오퍼 정보를 조회하지 못했어요.\n"
                "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                f"{btn}"
            )
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        lines = _summarize_offer(pre)
        if not lines:
            lines = ["• 오퍼 요약 정보를 만들지 못했어요."]
        msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # --- deal id path (dealroom) ---
    if did_now:
        did_int = int(did_now)
        pre = call_preview("deal", did_int, S.user_id, S.role)
        created_at = _find_created_at(pre)
        head = header_with_created("딜방", did_int, created_at)
        link = deeplink_for("dealroom", did_int, "")
        btn = render_button("딜방 프리뷰 열기", link)

        st = int(pre.get("_http_status") or 0) if isinstance(pre, dict) else 0
        if st >= 300 or not isinstance(pre, dict):
            msg = (
                f"{head}\n\n"
                "지금 대화에서는 딜방 정보를 조회하지 못했어요.\n"
                "정확한 내용은 아래 화면에서 확인해 주세요.\n\n"
                f"{btn}"
            )
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        lines = _summarize_dealroom(pre)
        if not lines:
            lines = ["• 딜방 요약 정보를 만들지 못했어요."]
        msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")



    # --- time policy only ---
    time_ans = maybe_answer_time_policy_only(q)
    if time_ans:
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": time_ans})
        S.history = S.history[-KEEP_TURNS:]
        return finalize(time_ans, "docs")

    # --- external (SSOT) ---
    ext_ans = handle_external(raw, q)
    if ext_ans:
        return ext_ans

    # --- internal/yeokping ---
    want_yeokping = bool(is_yeokping_related(q) or likely_followup_is_yeokping(prev_mode, raw))

    ids = extract_ids_from_text(q)
    rid = ids.get("reservation_id")

    # refund deterministic
    if False and want_yeokping and re.search(r"(환불|취소|refund|cancel)", q, re.IGNORECASE) and rid:
        pre = call_refund_preview(int(rid), S.role)
        msg = answer_from_refund_preview(pre)
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # points deterministic
    if want_yeokping and re.search(r"(포인트|point|잔액|적립|차감)", q, re.IGNORECASE):
        me = call_preview_me(S.user_id, S.role)
        if isinstance(me, dict) and me.get("ok") and isinstance(me.get("pack"), dict):
            pack = me.get("pack") or {}
            points = pack.get("points") if isinstance(pack.get("points"), dict) else None
            bal = points.get("balance") if isinstance(points, dict) else None
            if bal is not None:
                msg = f"현재 포인트 잔액은 {int(bal):,}점으로 보입니다."
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")
        msg = "지금은 포인트 잔액을 가져오지 못했어요. (preview/me 확인 실패)"
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # explain vs smalltalk
    if want_yeokping:
        docs = retrieve_kb_snippets(q)
        ans = openai_generate(client, "explain", q, docs, S.history, S.user_name)
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": ans})
        S.history = S.history[-KEEP_TURNS:]
        return finalize(ans, "docs" if docs else "없음")

    ans = openai_generate(client, "smalltalk", q, "", S.history, S.user_name)
    S.last_mode = "chitchat"
    S.history.append({"user": q, "bot": ans})
    S.history = S.history[-KEEP_TURNS:]
    return finalize(ans, "없음")


# ============================================================
# Interactive main
# ============================================================
def main() -> None:
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        print("❌ OPENAI_API_KEY가 없습니다.\n   (PowerShell) $env:OPENAI_API_KEY='...'\n")
        return

    client = OpenAI()
    load_kb()
    load_time_values_from_defaults()

    print("\n" + "=" * 60)
    print("🤖 Pingpong Sidecar (OpenAI) v1.2 — preview_pack + refund_preview + external(budgeted)")
    print(f"   server={YP_SERVER_URL}")
    print(f"   model={OPENAI_MODEL}")
    print(f"   server_timeout={HTTP_TIMEOUT:.1f}s / external_timeout={EXTERNAL_TIMEOUT:.1f}s")
    print("=" * 60)

    role_map = {"1": "ADMIN", "2": "SELLER", "3": "BUYER"}
    c = input("권한 선택 (1:Admin, 2:Seller, 3:Buyer): ").strip()
    S.role = role_map.get(c, "BUYER")

    uid_in = input("user_id (기본 1): ").strip()
    S.user_id = int(uid_in) if uid_in.isdigit() else 1
    S.user_name = USER_NAME

    print(f"\n✅ [{S.role}] 시작 (종료: exit/quit). '출처'라고 치면 마지막 링크를 보여줌.\n")

    while True:
        raw = input("나: ").strip()
        if raw.lower() in ("exit", "quit"):
            break
        ans = step_once(raw, client)
        if ans:
            print(f"\n핑퐁이: {ans}\n")

if __name__ == "__main__":
    main()