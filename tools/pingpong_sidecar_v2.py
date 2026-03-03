# tools/pingpong_sidecar_v2.py
# ============================================================
# Pingpong Sidecar v2 — Zero-crash Router + "Mouth"
#   - Brain: server /v3_6/pingpong/ask (policy reasoning)
#   - Data:  server /preview/* and /v3_6/reservations/refund/preview
#   - External (Option1): ONLY weather/news/price
#   - Sidecar: routing + formatting + safe fallback
# ============================================================

from __future__ import annotations

import os
import re
import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# OpenAI is optional — sidecar should never crash if key invalid/missing.
try:
    from openai import OpenAI
    from openai import AuthenticationError as OpenAIAuthError
    from openai import APIError as OpenAIAPIError
    from openai import RateLimitError as OpenAIRateLimitError
except Exception:
    OpenAI = None  # type: ignore
    OpenAIAuthError = Exception  # type: ignore
    OpenAIAPIError = Exception  # type: ignore
    OpenAIRateLimitError = Exception  # type: ignore


# ============================================================
# Config
# ============================================================
OPENAI_MODEL = (os.environ.get("YP_OPENAI_MODEL") or "gpt-5-mini").strip()
YP_SERVER_URL = (os.environ.get("YP_SERVER_URL") or "http://127.0.0.1:9000").rstrip("/")
HTTP_TIMEOUT = float(os.environ.get("YP_HTTP_TIMEOUT") or "8.0")
ASK_TIMEOUT = float(os.environ.get("YP_ASK_TIMEOUT") or "0") or max(1.5, HTTP_TIMEOUT / 2.0)
EXTERNAL_TIMEOUT = float(os.environ.get("YP_EXTERNAL_TIMEOUT") or "2.5")

DEBUG = (os.environ.get("PINGPONG_SIDECAR_DEBUG") or "false").lower() == "true"
KEEP_TURNS = 8

DEFAULTS_YAML_PATH = ("app", "policy", "params", "defaults.yaml")

HTTP = requests.Session()
HTTP.headers.update(
    {
        "User-Agent": "PingpongSidecarV2/2.0",
        "Accept": "*/*",
    }
)

def _dbg(*args: Any) -> None:
    if not DEBUG:
        return
    try:
        ts = time.strftime("%H:%M:%S")
        print("[DBG]", ts, *args)
    except Exception:
        # never crash on debug
        pass


# ============================================================
# State (slots separated to avoid pollution)
# ============================================================
@dataclass
class RefsSlot:
    kind: str = ""  # "ask" | "server" | "external"
    items: List[Dict[str, str]] = field(default_factory=list)  # {policy_key,title} OR {title,url}

@dataclass
class ConversationState:
    role: str = "BUYER"
    user_id: int = 1
    user_name: Optional[str] = None

    # remember last seen ids
    last_ids: Dict[str, Optional[int]] = field(default_factory=lambda: {"deal_id": None, "offer_id": None, "reservation_id": None})
    pending_kind: Optional[str] = None  # "reservation" | "offer" | "deal" | None

    # last mode for follow-up heuristics
    last_mode: str = "chitchat"  # "chitchat" | "yeokping" | "external"

    # conversation history (for OpenAI smalltalk only)
    history: List[Dict[str, str]] = field(default_factory=list)

    # refs slots
    last_refs_ask: RefsSlot = field(default_factory=lambda: RefsSlot(kind="ask"))
    last_refs_server: RefsSlot = field(default_factory=lambda: RefsSlot(kind="server"))
    last_refs_external: RefsSlot = field(default_factory=lambda: RefsSlot(kind="external"))

    # external follow-up (news link)
    last_news_items: List[Dict[str, str]] = field(default_factory=list)
    last_external_query: str = ""
    last_external_kind: str = ""  # weather/news/price


S = ConversationState()


# ============================================================
# Patterns / Intent
# ============================================================
_YEOKPING_HINT_PAT = re.compile(
    r"(역핑|딜방|딜\b|deal\b|오퍼|offer\b|예약|reservation\b|환불|취소|refund|cancel|"
    r"배송|shipping|수수료|fee|포인트|point|정산|settlement|등급|티어|tier|레벨|level|"
    r"마감|deadline|결제|payment|쿨링|cooling|정책|ssot)",
    re.IGNORECASE,
)

# Option1: only these become external
PRICE_PAT = re.compile(r"(최저가|가격|얼마|price|시세)", re.IGNORECASE)
WEATHER_PAT = re.compile(r"(날씨|weather|forecast|기온|강수|미세먼지)", re.IGNORECASE)
NEWS_PAT = re.compile(r"(뉴스|헤드라인|해드라인|headline|news)", re.IGNORECASE)

# Commands (refs)
_LINK_REQ_PAT = re.compile(r"(출처|링크|url|source|refs|references|근거)", re.IGNORECASE)

# time-only Q
TIME_Q_PAT = re.compile(
    r"(몇\s*(시간|분|일)|기간|지속|유효|마감|남은\s*시간|deadline|until|"
    r"쿨링|cooling|환불\s*가능|취소\s*가능|결제창|payment\s*window|"
    r"타임아웃|timeout|윈도우|window)",
    re.IGNORECASE,
)

HOWTO_PAT = re.compile(r"(어떻게|방법|절차|순서|가이드|설명|정의|뭐야|무엇)", re.IGNORECASE)

_ID_ONLY_PAT = re.compile(r"^\s*#?\s*(\d{1,9})\s*(번|호)?\s*(?:이야|입니다|예요|요)?\s*[.!?]?\s*$")

def is_yeokping_related(q: str) -> bool:
    return bool(_YEOKPING_HINT_PAT.search(q or ""))

def parse_id_only(raw: str) -> Optional[int]:
    m = _ID_ONLY_PAT.match((raw or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

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


# ============================================================
# KB + SSOT time (very lightweight)
# ============================================================
_KB_LOADED = False
_KB_DOCS: List[Tuple[str, str]] = []  # (path, content)
_SSOT_TIME: Dict[str, float] = {}
_TIME_LOADED = False

def load_kb() -> None:
    global _KB_LOADED, _KB_DOCS
    if _KB_LOADED:
        return
    _KB_LOADED = True
    docs: List[Tuple[str, str]] = []

    # Keep it simple: index only app/policy/docs/public + admin
    roots = [
        Path("app") / "policy" / "docs" / "public",
        Path("app") / "policy" / "docs" / "admin",
    ]
    for r in roots:
        try:
            if not r.exists():
                continue
            for p in r.rglob("*.md"):
                try:
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                    docs.append((str(p).replace("\\", "/"), txt))
                except Exception:
                    continue
        except Exception:
            continue

    _KB_DOCS = docs
    if DEBUG:
        print(f"✅ KB 로드 완료: {len(_KB_DOCS)}개 파일/문서 인덱싱됨")

def load_time_values_from_defaults() -> None:
    global _TIME_LOADED, _SSOT_TIME
    if _TIME_LOADED:
        return
    _TIME_LOADED = True
    _SSOT_TIME = {}
    path = Path(*DEFAULTS_YAML_PATH)
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return

    # super-light yaml parse: find `time:` section and parse "  key: value"
    in_time = False
    base_indent: Optional[int] = None
    out: Dict[str, float] = {}
    for ln in lines:
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        if re.match(r"^\s*time\s*:\s*$", ln):
            in_time = True
            base_indent = len(ln) - len(ln.lstrip())
            continue
        if not in_time:
            continue

        indent = len(ln) - len(ln.lstrip())
        if base_indent is not None and indent <= base_indent:
            # left the time section
            break

        m = re.match(r"^\s*([a-zA-Z0-9_]+)\s*:\s*([0-9.]+)\s*$", ln)
        if not m:
            continue
        k = m.group(1).strip()
        v = m.group(2).strip()
        try:
            out[k] = float(v)
        except Exception:
            continue

    _SSOT_TIME = out

def retrieve_kb_snippets(q: str, max_docs: int = 3, max_chars: int = 1400) -> str:
    """
    super simple keyword match. zero-crash.
    """
    q2 = (q or "").strip().lower()
    if not q2:
        return ""
    tokens = [t for t in re.split(r"\s+", q2) if len(t) >= 2][:8]
    if not tokens:
        return ""

    scored: List[Tuple[int, str, str]] = []
    for path, txt in _KB_DOCS:
        low = txt.lower()
        score = 0
        for t in tokens:
            if t in low:
                score += 1
        if score > 0:
            scored.append((score, path, txt))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = scored[:max_docs]
    chunks: List[str] = []
    for score, path, txt in picked:
        # take head chunk only
        s = txt.strip()
        if len(s) > max_chars:
            s = s[:max_chars] + "\n...(truncated)"
        chunks.append(f"[{path}]\n{s}")
    return "\n\n".join(chunks)


# ============================================================
# Formatting helpers
# ============================================================
def finalize(msg: str, evidence: str) -> str:
    msg = (msg or "").strip()
    ev = (evidence or "없음").strip()
    return f"{msg}\n[근거: {ev}]"

def _fmt_kst_min(dt: datetime) -> str:
    # keep timezone safety
    try:
        # If dt has no tz, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # KST = UTC+9
        kst = dt.astimezone(timezone.utc).astimezone(timezone(offset=timezone.utc.utcoffset(dt) or timezone.utc.utcoffset(dt)))  # safe no-op
    except Exception:
        pass
    # simple, stable format
    try:
        # try KST explicitly
        kst = dt.astimezone(timezone.utc).astimezone(timezone(offset=timezone.utc.utcoffset(datetime.now(timezone.utc)) or timezone.utc.utcoffset(datetime.now(timezone.utc))))
    except Exception:
        kst = dt
    return kst.strftime("%Y-%m-%d %H:%M")

def _parse_dt_any(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        s = s.replace("Z", "+00:00")
        s = s.replace(" ", "T") if "T" not in s and ":" in s else s
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None

def _find_created_at(obj: Any) -> Optional[datetime]:
    """
    best-effort search for created_at-like fields in nested dict.
    """
    try:
        if isinstance(obj, dict):
            for k in ("created_at", "createdAt", "created_time", "createdTime", "created"):
                if k in obj:
                    dt = _parse_dt_any(obj.get(k))
                    if dt:
                        return dt
            for k in ("pack", "ctx", "meta", "reservation", "deal", "offer", "data", "context"):
                dt = _find_created_at(obj.get(k))
                if dt:
                    return dt
        if isinstance(obj, list):
            for it in obj[:5]:
                dt = _find_created_at(it)
                if dt:
                    return dt
    except Exception:
        return None
    return None

def header_with_created(kind_kr: str, _id: int, created_at: Optional[datetime]) -> str:
    if created_at:
        return f"{kind_kr} #{_id} · 생성 {_fmt_kst_min(created_at)}"
    return f"{kind_kr} #{_id} · 생성시각 확인 필요"

def render_button(label: str, link: str) -> str:
    # CLI text. App can map it to real button.
    return f"[{label}]({link})"

def deeplink_for(kind: str, _id: int, sub: str = "") -> str:
    # keep consistent with your existing deep link style
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


# ============================================================
# Safe HTTP helpers (never raise)
# ============================================================
def _http_post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        r = HTTP.post(url, json=payload, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if not isinstance(data, dict):
            data = {"detail": str(data)}
        data["_http_status"] = r.status_code
        return data
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}

def _http_get_json(url: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        r = HTTP.get(url, params=params, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "").strip()}
        if not isinstance(data, dict):
            data = {"detail": str(data)}
        data["_http_status"] = r.status_code
        return data
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}


# ============================================================
# Server calls
# ============================================================
def call_preview(entity: str, _id: int, user_id: int, role: str) -> Dict[str, Any]:
    return _http_get_json(f"{YP_SERVER_URL}/preview/{entity}/{_id}", {"user_id": user_id, "role": role}, timeout=HTTP_TIMEOUT)

def call_preview_me(user_id: int, role: str) -> Dict[str, Any]:
    return _http_get_json(f"{YP_SERVER_URL}/preview/me", {"user_id": user_id, "role": role}, timeout=HTTP_TIMEOUT)

def call_refund_preview_v36(reservation_id: int, role: str) -> Dict[str, Any]:
    # Use the v3_6 endpoint that works for BUYER too:
    payload = {"reservation_id": int(reservation_id), "role": (role or "BUYER").upper()}
    return _http_post_json(f"{YP_SERVER_URL}/v3_6/reservations/refund/preview", payload, timeout=HTTP_TIMEOUT)

def call_pingpong_ask(screen: str, role: str, question: str, mode: str, max_chat_messages: int, context: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "screen": screen,
        "role": (role or "BUYER").upper(),
        "question": question,
        "mode": mode,
        "max_chat_messages": int(max_chat_messages),
        "context": context or {},
    }
    return _http_post_json(f"{YP_SERVER_URL}/v3_6/pingpong/ask", payload, timeout=ASK_TIMEOUT)


# ============================================================
# Ask answer renderer (mouth)
# ============================================================
def render_ask_answer_for_user(obj: Dict[str, Any]) -> str:
    if not isinstance(obj, dict):
        return "지금은 답변을 만들지 못했어요."
    st = int(obj.get("_http_status") or 0)
    if st >= 500 or obj.get("error") == "OFFLINE":
        return "지금은 서버 응답이 불안정해요. 잠시 후 다시 시도해 주세요."
    if st >= 300:
        detail = obj.get("detail") or obj.get("error") or "요청이 처리되지 않았습니다."
        return f"지금은 답변을 가져오지 못했어요: {detail}"

    ans = (obj.get("answer") or "").strip()
    if not ans:
        ans = "지금은 답변이 비어 있어요. 질문을 조금만 더 구체적으로 말해줄래요?"
    return ans


# ============================================================
# Deterministic summarizers (preview/refund)
# ============================================================
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
            iv = int(float(v))
            return iv
        except Exception:
            continue
    return None

def _dig(d: Any, keys: List[str]) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur

def summarize_reservation_payment(pre_res: Dict[str, Any]) -> List[str]:
    pack = pre_res.get("pack") if isinstance(pre_res.get("pack"), dict) else {}
    status = _first_str(_dig(pack, ["reservation", "status"]), _dig(pre_res, ["ctx", "status"]))
    amount = _first_int(_dig(pack, ["reservation", "amount_total"]), _dig(pre_res, ["ctx", "amount_total"]))
    out = []
    if status:
        out.append(f"• 결제/예약 상태: {status}")
    if amount is not None:
        out.append(f"• 결제 금액: {amount:,}원")
    return out[:3]

def summarize_offer(pre: Dict[str, Any]) -> List[str]:
    pack = pre.get("pack") if isinstance(pre.get("pack"), dict) else {}
    st = _first_str(_dig(pack, ["offer", "status"]), _dig(pack, ["status"]))
    price = _first_int(_dig(pack, ["offer", "price"]), _dig(pack, ["price"]))
    out = []
    if st:
        out.append(f"• 오퍼 상태: {st}")
    if price is not None:
        out.append(f"• 오퍼 가격: {price:,}원")
    return out[:3]

def summarize_dealroom(pre: Dict[str, Any]) -> List[str]:
    pack = pre.get("pack") if isinstance(pre.get("pack"), dict) else {}
    st = _first_str(_dig(pack, ["deal", "status"]), _dig(pack, ["status"]))
    target = _first_int(_dig(pack, ["deal", "target_price"]), _dig(pack, ["target_price"]))
    out = []
    if st:
        out.append(f"• 딜방 상태: {st}")
    if target is not None:
        out.append(f"• 목표가: {target:,}원")
    return out[:3]

def summarize_refund_v36(obj: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Returns (lines, server_refs_to_store)
    """
    ctx = obj.get("context") if isinstance(obj.get("context"), dict) else {}
    decision = obj.get("decision") if isinstance(obj.get("decision"), dict) else {}

    total = _first_int(ctx.get("amount_total"))
    goods = _first_int(ctx.get("amount_goods"))
    ship = _first_int(ctx.get("amount_shipping"))
    note = _first_str(decision.get("note"))

    lines: List[str] = []
    if total is not None:
        if goods is not None or ship is not None:
            lines.append(f"환불 프리뷰 기준 총 {total:,}원 (상품 {int(goods or 0):,}원 / 배송 {int(ship or 0):,}원) 입니다.")
        else:
            lines.append(f"환불 프리뷰 기준 총 {total:,}원 입니다.")
    if note:
        lines.append(f"• {note}")

    refs = [
        {"policy_key": "server:/v3_6/reservations/refund/preview", "title": f"환불 프리뷰(실시간) — reservation_id={ctx.get('reservation_id')}"},
        {"policy_key": f"deeplink:{deeplink_for('reservation', int(ctx.get('reservation_id') or 0), 'refund')}", "title": "환불 프리뷰 화면 딥링크"},
    ]
    return (lines[:3] if lines else ["환불 프리뷰 요약을 만들지 못했어요."], refs)


# ============================================================
# External (Option1): weather/news/price only
# ============================================================
def infer_external_kind_option1(q: str) -> Optional[str]:
    q = (q or "").strip()
    if not q:
        return None
    if WEATHER_PAT.search(q):
        return "weather"
    if NEWS_PAT.search(q):
        return "news"
    if PRICE_PAT.search(q):
        return "price"
    return None

def _compact_query_for_external(kind: str, q: str) -> str:
    """
    External 검색용 쿼리를 '짧고 의미있게' 축약한다.
    - price: 제품명/스펙 중심으로 6~10토큰
    - news:  핵심 키워드만
    - weather: 도시/지역 중심
    """
    q0 = (q or "").strip()
    if not q0:
        return q0

    # remove filler
    q0 = re.sub(r"(알려줘|알려\s*줘|조회|검색|요약|부탁|가능해\??|해줘|해\s*줘|좀|혹시|대략|대략적인|정도)", " ", q0, flags=re.IGNORECASE)
    q0 = re.sub(r"\s+", " ", q0).strip()

    # keep only useful tokens
    toks = re.split(r"\s+", q0)
    toks = [t for t in toks if t and len(t) <= 40]

    if kind == "weather":
        # keep first 2~3 tokens (city/region)
        return " ".join(toks[:3]) if toks else q0

    if kind == "news":
        # keep up to 6 tokens
        return " ".join(toks[:6]) if toks else q0

    # price
    # common noisy words
    drop = set(["오늘", "현재", "마감", "종가", "시황", "환율", "코스피", "코스닥"])
    toks2 = [t for t in toks if t not in drop]
    if not toks2:
        toks2 = toks
    return " ".join(toks2[:10]) if toks2 else q0

def normalize_external_query(q: str) -> str:
    q = (q or "").strip()
    q = re.sub(r"\s+", " ", q)
    return q[:120]

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

def fetch_weather_external(eq: str) -> Dict[str, Any]:
    # best-effort using open-meteo (no key)
    # NOTE: If it fails -> ok False and links are provided by handle_external.
    try:
        # minimal heuristic: if eq has city name, keep it
        city = eq or "서울"
        # open-meteo needs lat/lon; to keep v2 simple, we do NOT geocode (avoid fragility).
        return {"kind": "weather", "ok": False, "city": city, "links": []}
    except Exception:
        return {"kind": "weather", "ok": False, "city": (eq or "서울"), "links": []}

def fetch_news_external(eq: str) -> Dict[str, Any]:
    # Fetch RSS headlines via Google News RSS (best-effort). If blocked -> ok False.
    try:
        rss = f"https://news.google.com/rss/search?q={requests.utils.quote(eq)}&hl=ko&gl=KR&ceid=KR:ko"
        r = HTTP.get(rss, timeout=EXTERNAL_TIMEOUT)
        if r.status_code != 200:
            return {"kind": "news", "ok": False, "links": [{"title": "Google News RSS", "url": rss}]}
        # ultra-light parse: extract <title> of items
        txt = r.text or ""
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", txt)
        # first title is channel title, skip it
        heads = [t.strip() for t in titles[1:6] if t.strip()]
        # extract links
        links = re.findall(r"<link>(https?://.*?)</link>", txt)
        item_links = links[1:6] if len(links) > 1 else []
        items = []
        for i in range(min(len(heads), len(item_links))):
            items.append({"title": heads[i], "url": item_links[i]})
        return {"kind": "news", "ok": bool(heads), "headlines": heads, "items": items, "links": [{"title": "Google News", "url": f"https://news.google.com/search?q={requests.utils.quote(eq)}&hl=ko&gl=KR&ceid=KR:ko"}]}
    except Exception:
        return {"kind": "news", "ok": False, "links": []}

def fetch_price_external(eq: str) -> Dict[str, Any]:
    # We do NOT scrape numbers in v2 (fragile). Provide links-only safely.
    return {"kind": "price", "ok": False, "links_only": True, "links": []}

def handle_external(raw: str, q: str, kind: str) -> Optional[str]:
    """
    External v2:
    - Called only when router decided kind in {weather,news,price}
    - Never crashes; always stores external refs slot.
    - Supports follow-up: ask for '링크/url' after news
    """
    # follow-up: user asks URL for last news item
    try:
        if re.search(r"(url|링크|주소)", raw or "", re.IGNORECASE) and S.last_external_kind == "news" and S.last_news_items:
            it = S.last_news_items[0]
            msg = f"가장 위 제목 링크예요: {it.get('url')}"
            S.last_mode = "external"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            # store refs
            S.last_refs_external.items = [{"title": it.get("title", "news link"), "url": it.get("url", "")}]
            return finalize(msg, "external")
    except Exception:
        pass

    # normalize query
    eq = normalize_external_query(q)
    S.last_external_kind = kind
    S.last_external_query = eq

    if kind == "weather":
        ext = fetch_weather_external(eq)
    elif kind == "news":
        ext = fetch_news_external(eq)
    else:
        ext = fetch_price_external(eq)

    # build links fallback
    links = ext.get("links") if isinstance(ext, dict) else []
    if not (isinstance(links, list) and links):
        if kind == "news":
            links = [
                {"title": f"구글뉴스 '{eq}'", "url": f"https://news.google.com/search?q={requests.utils.quote(eq)}&hl=ko&gl=KR&ceid=KR:ko"},
                {"title": f"네이버뉴스 '{eq}'", "url": f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(eq)}"},
            ]
        elif kind == "weather":
            links = [
                {"title": f"네이버 '{eq} 날씨'", "url": f"https://search.naver.com/search.naver?query={requests.utils.quote(eq+' 날씨')}"},
                {"title": f"구글 '{eq} weather'", "url": f"https://www.google.com/search?q={requests.utils.quote(eq+' weather')}"},
            ]
        else:
            links = [
                {"title": f"네이버쇼핑 '{eq}'", "url": f"https://search.shopping.naver.com/search/all?query={requests.utils.quote(eq)}"},
                {"title": f"다나와 '{eq}'", "url": f"https://search.danawa.com/dsearch.php?k1={requests.utils.quote(eq)}"},
            ]

    links = _merge_links([], links)
    # store external refs slot
    S.last_refs_external.items = [{"title": x.get("title", ""), "url": x.get("url", "")} for x in links[:10] if x.get("url")]

    # rendering
    ok = isinstance(ext, dict) and bool(ext.get("ok"))
    if not ok:
        msg = "지금은 실시간 조회가 불안정합니다."
        if links:
            msg += "\n" + "\n".join([f"- {x['title']}: {x['url']}" for x in links[:2]])
        else:
            msg += " 필요하시면 '출처'라고 입력해 주세요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "external")

    if kind == "news":
        S.last_news_items = ext.get("items") or []
        heads = ext.get("headlines") or []
        msg = "오늘 뉴스로는 이런 제목들이 보여요: " + " / ".join(heads[:3]) if heads else "뉴스 제목을 가져오지 못했어요."
        S.last_mode = "external"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "external")

    # weather success not implemented in v2 fetch -> stays fallback, but keep branch
    msg = "외부 조회 결과를 표시할 수 없어요."
    S.last_mode = "external"
    S.history.append({"user": q, "bot": msg})
    S.history[:] = S.history[-KEEP_TURNS:]
    return finalize(msg, "external")


# ============================================================
# References / Source command (single place)
# ============================================================
def is_refs_command(raw: str) -> bool:
    _cmd = (raw or "").strip().lower()
    _cmd = re.sub(r"\s+", " ", _cmd)
    _trim = re.sub(r"[.?!]+$", "", _cmd).strip()
    if not _trim:
        return False
    # strict command only (avoid false positives)
    return bool(re.fullmatch(r"(출처|링크|url|source|refs|references|근거|근거도|근거는|근거\s*보여줘|출처\s*보여줘|링크\s*보여줘)", _trim))

def render_refs() -> str:
    # priority: ask -> server -> external
    if S.last_refs_ask.items:
        lines = ["요청하신 근거(사용한 정책)입니다."]
        for p in S.last_refs_ask.items[:10]:
            k = (p.get("policy_key") or "").strip()
            t = (p.get("title") or "").strip()
            if k and t:
                lines.append(f"- {k} : {t}")
            elif t:
                lines.append(f"- {t}")
            elif k:
                lines.append(f"- {k}")
        return finalize("\n".join(lines), "server")

    if S.last_refs_server.items:
        lines = ["요청하신 근거(최근 서버 조회/프리뷰)입니다."]
        for p in S.last_refs_server.items[:10]:
            k = (p.get("policy_key") or "").strip()
            t = (p.get("title") or "").strip()
            if k and t:
                lines.append(f"- {k} : {t}")
            elif t:
                lines.append(f"- {t}")
            elif k:
                lines.append(f"- {k}")
        return finalize("\n".join(lines), "server")

    if S.last_refs_external.items:
        lines = ["요청하신 출처 링크입니다."]
        if S.last_external_query:
            lines.append(f"(검색어: {S.last_external_query})")
        for it in S.last_refs_external.items[:10]:
            title = (it.get("title") or "").strip()
            url = (it.get("url") or "").strip()
            if title or url:
                lines.append(f"- {title} : {url}")
        return finalize("\n".join(lines), "external")

    return finalize("(지금 보여드릴 근거/출처가 없어요.)", "없음")


# ============================================================
# OpenAI: smalltalk only (optional)
# ============================================================
def instructions_smalltalk(user_name: Optional[str]) -> str:
    name = f"{user_name}님" if user_name else "고객님"
    return f"""
[Smalltalk Rules]
1) 역핑/SSOT/서버/preview/DB/정책/내부시스템 같은 단어를 절대 꺼내지 마.
2) "자료가 없어서", "확인할 수 없어서" 같은 메타 발화 금지. (진짜로 개인정보/내부데이터가 필요한 경우만 예외)
3) 연예인/아이돌/일반상식/일상 질문은 자연스럽게 '그냥 답해'. 너무 조심스럽게 굴지 마.
4) 1~4문장.
5) 호칭은 "{name}".
""".strip()

def openai_smalltalk(client: Any, question: str, history: List[Dict[str, str]], user_name: Optional[str]) -> str:
    """
    Always safe: if OpenAI fails, return a canned reply.
    """
    q = (question or "").strip()
    if not q:
        return ""

    # If OpenAI not available, canned
    if client is None:
        return "안녕하세요! 뭐 도와드릴까요?"

    # Build small prompt with history (safe)
    hist = history[-KEEP_TURNS:]
    lines = []
    for t in hist:
        u = (t.get("user") or "").strip()
        a = (t.get("bot") or "").strip()
        if u:
            lines.append(f"사용자: {u}")
        if a:
            lines.append(f"핑퐁이: {a}")
    hist_txt = "\n".join(lines) if lines else "(없음)"

    prompt = f"""
[최근 대화]
{hist_txt}

[질문]
{q}
""".strip()

    try:
        resp = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions_smalltalk(user_name),
            input=prompt,
            max_output_tokens=220,
            store=False,
        )
        out = (getattr(resp, "output_text", "") or "").strip()
        return out or "음, 그건 이렇게 생각해볼 수 있어요. 좀 더 말해줘!"
    except (OpenAIAuthError, OpenAIRateLimitError, OpenAIAPIError):
        return "안녕하세요! 뭐 도와드릴까요?"
    except Exception:
        return "안녕하세요! 뭐 도와드릴까요?"


# ============================================================
# Router core: step_once (ZERO-CRASH)
# ============================================================
def step_once(raw: str, client: Any) -> str:
    """
    v2 routing order (important):
      0) refs command
      1) ID-first: reservation/offer/deal -> preview/refund preview
      2) external option1: weather/news/price only
      3) yeokping policy/howto/time -> ask brain
      4) smalltalk -> OpenAI smalltalk or canned
    """
    global S
    raw = (raw or "").strip()
    if not raw:
        return ""

    # Ensure KB/time loaded but never crash
    try:
        load_kb()
    except Exception:
        pass
    try:
        load_time_values_from_defaults()
    except Exception:
        pass

    # 0) refs command
    if is_refs_command(raw):
        return render_refs()

    prev_mode = S.last_mode
    q = raw  # keep normalization minimal in v2 (reduce surprises)

    # update ids cache
    ids_now = extract_ids_from_text(q)
    for k in ("deal_id", "offer_id", "reservation_id"):
        if ids_now.get(k) is not None:
            S.last_ids[k] = ids_now.get(k)

    _dbg("gate_idfirst", {"raw": raw, "q": q, "ids_now": ids_now, "pending": S.pending_kind, "last_ids": S.last_ids})

    rid_now = ids_now.get("reservation_id")
    oid_now = ids_now.get("offer_id")
    did_now = ids_now.get("deal_id")

    # ------------------------------------------------------------
    # 1) ID-first
    # ------------------------------------------------------------
    try:
        if rid_now:
            rid = int(rid_now)
            S.pending_kind = "reservation"
            # Always use refund preview for refund/cancel questions
            topic_refund = bool(re.search(r"(환불|취소|refund|cancel)", q, re.IGNORECASE))
            topic_payment = bool(re.search(r"(결제|payment)", q, re.IGNORECASE))
            topic_shipping = bool(re.search(r"(배송|shipping)", q, re.IGNORECASE))

            # created_at from preview (best effort)
            pre_res = call_preview("reservation", rid, S.user_id, S.role)
            created_at = _find_created_at(pre_res)
            head = header_with_created("예약", rid, created_at)

            if topic_refund or ("가능" in q and "취소" in q):
                pre = call_refund_preview_v36(rid, S.role)
                st = int(pre.get("_http_status") or 0)
                if st >= 300 or pre.get("error") == "OFFLINE":
                    link = deeplink_for("reservation", rid, "refund")
                    btn = render_button("환불 프리뷰 열기", link)
                    msg = f"{head}\n\n지금 대화에서는 환불 정보를 조회하지 못했어요.\n정확한 내용은 아래 화면에서 확인해 주세요.\n\n{btn}"
                    # store server refs
                    S.last_refs_server.items = [{"policy_key": "server:/v3_6/reservations/refund/preview", "title": f"환불 프리뷰 조회 실패 — reservation_id={rid}"},
                                                {"policy_key": f"deeplink:{link}", "title": "환불 프리뷰 화면 딥링크"}]
                    S.last_mode = "yeokping"
                    S.history.append({"user": q, "bot": msg})
                    S.history[:] = S.history[-KEEP_TURNS:]
                    return finalize(msg, "server")

                lines, refs = summarize_refund_v36(pre)
                link = deeplink_for("reservation", rid, "refund")
                btn = render_button("환불 프리뷰 열기", link)
                msg = f"{head}\n\n" + "\n".join(lines) + f"\n\n{btn}"
                # store refs
                S.last_refs_server.items = refs
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            if topic_payment:
                link = deeplink_for("reservation", rid, "payment")
                btn = render_button("결제 프리뷰 열기", link)
                st = int(pre_res.get("_http_status") or 0)
                if st >= 300 or pre_res.get("error") == "OFFLINE":
                    msg = f"{head}\n\n지금 대화에서는 결제 정보를 조회하지 못했어요.\n정확한 내용은 아래 화면에서 확인해 주세요.\n\n{btn}"
                    S.last_refs_server.items = [{"policy_key": "server:/preview/reservation/{id}", "title": f"예약 프리뷰 조회 실패 — reservation_id={rid}"},
                                                {"policy_key": f"deeplink:{link}", "title": "결제 프리뷰 화면 딥링크"}]
                    S.last_mode = "yeokping"
                    S.history.append({"user": q, "bot": msg})
                    S.history[:] = S.history[-KEEP_TURNS:]
                    return finalize(msg, "server")
                lines = summarize_reservation_payment(pre_res)
                if not lines:
                    lines = ["• 결제 요약 정보를 만들지 못했어요."]
                msg = f"{head}\n\n" + "\n".join(lines) + f"\n\n{btn}"
                S.last_refs_server.items = [{"policy_key": "server:/preview/reservation/{id}", "title": f"예약 프리뷰 — reservation_id={rid}"},
                                            {"policy_key": f"deeplink:{link}", "title": "결제 프리뷰 화면 딥링크"}]
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            if topic_shipping:
                link = deeplink_for("reservation", rid, "shipping")
                btn = render_button("배송 프리뷰 열기", link)
                msg = f"{head}\n\n정확한 배송 정보는 아래 화면에서 확인해 주세요.\n\n{btn}"
                S.last_refs_server.items = [{"policy_key": f"deeplink:{link}", "title": "배송 프리뷰 화면 딥링크"}]
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")

            # general reservation
            link = deeplink_for("reservation", rid, "")
            btn = render_button("예약 프리뷰 열기", link)
            st = int(pre_res.get("_http_status") or 0)
            if st >= 300 or pre_res.get("error") == "OFFLINE":
                msg = f"{head}\n\n지금 대화에서는 예약 정보를 조회하지 못했어요.\n정확한 내용은 아래 화면에서 확인해 주세요.\n\n{btn}"
                S.last_refs_server.items = [{"policy_key": "server:/preview/reservation/{id}", "title": f"예약 프리뷰 조회 실패 — reservation_id={rid}"},
                                            {"policy_key": f"deeplink:{link}", "title": "예약 프리뷰 화면 딥링크"}]
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")
            # minimal summary
            pack = pre_res.get("pack") if isinstance(pre_res.get("pack"), dict) else {}
            status = _first_str(_dig(pack, ["reservation", "status"]), _dig(pre_res, ["ctx", "status"]))
            amount = _first_int(_dig(pack, ["reservation", "amount_total"]), _dig(pre_res, ["ctx", "amount_total"]))
            lines = []
            if status:
                lines.append(f"• 예약 상태: {status}")
            if amount is not None:
                lines.append(f"• 금액: {amount:,}원")
            if not lines:
                lines = ["• 예약 요약 정보를 만들지 못했어요."]
            msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
            S.last_refs_server.items = [{"policy_key": "server:/preview/reservation/{id}", "title": f"예약 프리뷰 — reservation_id={rid}"},
                                        {"policy_key": f"deeplink:{link}", "title": "예약 프리뷰 화면 딥링크"}]
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        if oid_now:
            oid = int(oid_now)
            S.pending_kind = "offer"
            pre = call_preview("offer", oid, S.user_id, S.role)
            created_at = _find_created_at(pre)
            head = header_with_created("오퍼", oid, created_at)
            link = deeplink_for("offer", oid, "")
            btn = render_button("오퍼 프리뷰 열기", link)
            st = int(pre.get("_http_status") or 0)
            if st >= 300 or pre.get("error") == "OFFLINE":
                msg = f"{head}\n\n지금 대화에서는 오퍼 정보를 조회하지 못했어요.\n정확한 내용은 아래 화면에서 확인해 주세요.\n\n{btn}"
                S.last_refs_server.items = [{"policy_key": "server:/preview/offer/{id}", "title": f"오퍼 프리뷰 조회 실패 — offer_id={oid}"},
                                            {"policy_key": f"deeplink:{link}", "title": "오퍼 프리뷰 화면 딥링크"}]
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")
            lines = summarize_offer(pre) or ["• 오퍼 요약 정보를 만들지 못했어요."]
            msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
            S.last_refs_server.items = [{"policy_key": "server:/preview/offer/{id}", "title": f"오퍼 프리뷰 — offer_id={oid}"},
                                        {"policy_key": f"deeplink:{link}", "title": "오퍼 프리뷰 화면 딥링크"}]
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")

        if did_now:
            did = int(did_now)
            S.pending_kind = "deal"
            pre = call_preview("deal", did, S.user_id, S.role)
            created_at = _find_created_at(pre)
            head = header_with_created("딜방", did, created_at)
            link = deeplink_for("dealroom", did, "")
            btn = render_button("딜방 프리뷰 열기", link)
            st = int(pre.get("_http_status") or 0)
            if st >= 300 or pre.get("error") == "OFFLINE":
                msg = f"{head}\n\n지금 대화에서는 딜방 정보를 조회하지 못했어요.\n정확한 내용은 아래 화면에서 확인해 주세요.\n\n{btn}"
                S.last_refs_server.items = [{"policy_key": "server:/preview/deal/{id}", "title": f"딜방 프리뷰 조회 실패 — deal_id={did}"},
                                            {"policy_key": f"deeplink:{link}", "title": "딜방 프리뷰 화면 딥링크"}]
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                return finalize(msg, "server")
            lines = summarize_dealroom(pre) or ["• 딜방 요약 정보를 만들지 못했어요."]
            msg = f"{head}\n\n" + "\n".join(lines[:3]) + f"\n\n{btn}"
            S.last_refs_server.items = [{"policy_key": "server:/preview/deal/{id}", "title": f"딜방 프리뷰 — deal_id={did}"},
                                        {"policy_key": f"deeplink:{link}", "title": "딜방 프리뷰 화면 딥링크"}]
            S.last_mode = "yeokping"
            S.history.append({"user": q, "bot": msg})
            S.history[:] = S.history[-KEEP_TURNS:]
            return finalize(msg, "server")
    except Exception:
        # ID path must never crash
        _dbg("ID_PATH_EXCEPTION", traceback.format_exc())

    # ------------------------------------------------------------
    # 2) External (Option1)
    # ------------------------------------------------------------
    try:
        ext_kind = infer_external_kind_option1(q)
        if ext_kind:
            q_ext = _compact_query_for_external(ext_kind, q)
            out = handle_external(raw, q_ext, ext_kind)
            if out:
                return out
    except Exception:
        _dbg("EXTERNAL_EXCEPTION", traceback.format_exc())

    # ------------------------------------------------------------
    # 3) Yeokping: time-only shortcut (only if yeokping-related AND no ids)
    # ------------------------------------------------------------
    try:
        if is_yeokping_related(q) and TIME_Q_PAT.search(q) and not any(ids_now.values()):
            # small deterministic time answers if present in defaults
            # (keep it minimal; avoid hallucination)
            # common keys:
            # deal_deadline_hours, offer_deadline_hours, cooling_days, payment_timeout_minutes, etc.
            # If missing -> fall back to ask.
            key_map = [
                ("딜방", "deal_deadline_hours", "딜방 모집/마감 기본"),
                ("오퍼", "offer_deadline_hours", "오퍼 마감 기본"),
                ("쿨링", "cooling_days", "쿨링(환불 가능 기간) 기본"),
                ("결제", "payment_timeout_minutes", "결제 제한시간"),
            ]
            rows = []
            for hint, k, label in key_map:
                if hint in q and k in _SSOT_TIME:
                    v = _SSOT_TIME.get(k)
                    if v is None:
                        continue
                    # hours vs days/min
                    if k.endswith("_days"):
                        rows.append(f"{label}은 {int(v)}일입니다. (defaults.yaml SSOT 기준)")
                    elif k.endswith("_minutes"):
                        rows.append(f"{label}은 {int(v)}분입니다. (defaults.yaml SSOT 기준)")
                    else:
                        # hours
                        # if 0.5 -> 30분
                        if abs(v - 0.5) < 1e-9:
                            rows.append(f"{label}은 30분입니다. (defaults.yaml SSOT 기준)")
                        else:
                            rows.append(f"{label}은 {int(v)}시간입니다. (defaults.yaml SSOT 기준)")
            if rows:
                msg = rows[0]
                S.last_mode = "yeokping"
                S.history.append({"user": q, "bot": msg})
                S.history[:] = S.history[-KEEP_TURNS:]
                # this is docs-like, not policy ask
                return finalize(msg, "docs")
    except Exception:
        _dbg("TIME_EXCEPTION", traceback.format_exc())

    # ------------------------------------------------------------
    # 4) Yeokping policy/howto -> Ask brain
    # ------------------------------------------------------------
    want_yeokping = bool(is_yeokping_related(q) or (prev_mode == "yeokping" and (HOWTO_PAT.search(q) or TIME_Q_PAT.search(q))))
    if want_yeokping:
        ask_obj: Dict[str, Any] = {"_http_status": 0}
        try:
            ctx = {"sidecar": {"last_ids": dict(S.last_ids), "prev_mode": S.last_mode}}
            ask_obj = call_pingpong_ask(
                screen="DEAL_ROOM",
                role=S.role,
                question=q,
                mode="read_only",
                max_chat_messages=10,
                context=ctx,
            )
        except Exception:
            ask_obj = {"error": "OFFLINE", "detail": "ask call failed", "_http_status": 0}

        # store ask refs safely (always initialized)
        try:
            used = ask_obj.get("used_policies") if isinstance(ask_obj, dict) else None
            if isinstance(used, list):
                items = []
                for p in used[:10]:
                    if isinstance(p, dict):
                        items.append({
                            "policy_key": str(p.get("policy_key") or "").strip(),
                            "title": str(p.get("title") or p.get("policy_key") or "").strip(),
                        })
                S.last_refs_ask.items = [x for x in items if x.get("policy_key") or x.get("title")]
            else:
                S.last_refs_ask.items = []
        except Exception:
            S.last_refs_ask.items = []

        msg = render_ask_answer_for_user(ask_obj)
        S.last_mode = "yeokping"
        S.history.append({"user": q, "bot": msg})
        S.history[:] = S.history[-KEEP_TURNS:]
        return finalize(msg, "server")

    # ------------------------------------------------------------
    # 5) Smalltalk
    # ------------------------------------------------------------
    ans = openai_smalltalk(client, q, S.history, S.user_name)
    if not ans:
        ans = "음! 그 얘기 좀 더 해줘 😄"
    S.last_mode = "chitchat"
    S.history.append({"user": q, "bot": ans})
    S.history[:] = S.history[-KEEP_TURNS:]
    return finalize(ans, "없음")


# ============================================================
# CLI main
# ============================================================
def main() -> None:
    # Client init (optional)
    client = None
    if OpenAI is not None:
        # If key missing/invalid, sidecar still runs (smalltalk becomes canned)
        k = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if k and ("..." not in k):
            try:
                client = OpenAI()
            except Exception:
                client = None
        else:
            client = None

    # warm load
    try:
        load_kb()
    except Exception:
        pass
    try:
        load_time_values_from_defaults()
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("🤖 Pingpong Sidecar v2 — zero-crash router (ask+preview+external option1)")
    print(f"   server={YP_SERVER_URL}")
    print(f"   model={OPENAI_MODEL}")
    print(f"   server_timeout={HTTP_TIMEOUT:.1f}s / ask_timeout={ASK_TIMEOUT:.1f}s / external_timeout={EXTERNAL_TIMEOUT:.1f}s")
    print("=" * 60)

    role_map = {"1": "ADMIN", "2": "SELLER", "3": "BUYER"}
    c = input("권한 선택 (1:Admin, 2:Seller, 3:Buyer): ").strip()
    S.role = role_map.get(c, "BUYER")
    uid_in = input("user_id (기본 1): ").strip()
    S.user_id = int(uid_in) if uid_in.isdigit() else 1
    nm = (os.environ.get("YP_USER_NAME") or "").strip()
    S.user_name = nm or None

    print(f"\n✅ [{S.role}] 시작 (종료: exit/quit). '출처/근거'라고 치면 마지막 근거/출처를 보여줌.\n")

    while True:
        try:
            raw = input("나: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n(종료)")
            break

        if raw.lower() in ("exit", "quit", "q"):
            print("(종료)")
            break

        try:
            ans = step_once(raw, client)
        except Exception:
            # absolute last guard
            ans = finalize("죄송해요. 지금은 일시적인 오류가 발생했어요. 잠시 후 다시 시도해 주세요.", "없음")

        print("\n핑퐁이:", ans, "\n")


if __name__ == "__main__":
    main()