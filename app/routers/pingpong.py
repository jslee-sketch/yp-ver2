# app/routers/pingpong.py
from __future__ import annotations

import json
import os
import re
import time
import traceback
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import httpx

from app.database import get_db
from app import models, crud
from app.llm_client import get_client

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

router = APIRouter(
    prefix="/v3_6/pingpong",
    tags=["pingpong"],
)

# =========================================================
# Sidecar proxy config
# =========================================================
SIDECAR_URL = os.getenv("SIDECAR_URL", "http://localhost:9100")

# =========================================================
# Pydantic Schemas
# =========================================================

class PingpongContextIn(BaseModel):
    deal_id: Optional[int] = None
    reservation_id: Optional[int] = None
    offer_id: Optional[int] = None


class PingpongAskIn(BaseModel):
    user_id: Optional[int] = Field(None, description="질문하는 사용자 id (옵션)")
    role: Optional[str] = Field(None, description="buyer / seller / admin 등")
    screen: str = Field(..., description="현재 화면 타입 (DEAL_ROOM, REFUND_FLOW 등)")
    context: PingpongContextIn = Field(default_factory=PingpongContextIn)
    question: str = Field(..., description="사용자가 묻는 자연어 질문")
    locale: str = Field("ko", description="ko / en (기본 ko)")
    mode: str = Field("read_only", description="read_only | suggest_actions")
    max_chat_messages: int = Field(10, description="딜 채팅 최근 메시지 최대 개수(토큰 폭주 방지)")


class PolicyRefOut(BaseModel):
    policy_id: int
    policy_key: str
    title: str
    domain: str
    version: int


class PingpongActionOut(BaseModel):
    type: str
    label: str
    endpoint: Optional[str] = None
    payload_template: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = True


class PingpongAskOut(BaseModel):
    answer: str
    used_policies: List[PolicyRefOut] = []
    actions: List[PingpongActionOut] = []
    debug: Optional[Dict[str, Any]] = None


# =========================================================
# Utilities
# =========================================================

_PII_PATTERNS = [
    re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"),  # 휴대폰
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),  # 이메일
    re.compile(r"\b\d{12,19}\b"),  # 카드/계좌 등 길게 보이는 숫자
]


def _redact_pii(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _PII_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def _jsonable(obj: Any) -> Any:
    """datetime 등 JSON 직렬화 불가능 타입을 안전하게 변환(재귀)."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    return str(obj)


def _safe_json_loads(s: str) -> Dict[str, Any]:
    """
    LLM 출력이 JSON만 딱 주지 않고 앞/뒤에 텍스트를 붙이거나,
    혹은 줄바꿈/코드블록이 섞이는 경우를 대비해서
    가장 그럴듯한 { ... } JSON 오브젝트를 추출해서 파싱한다.
    """
    if not s:
        return {}

    s = s.strip()

    # 1) 바로 JSON 파싱 시도
    try:
        data = json.loads(s)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    # 2) 코드블록 제거(```json ... ``` 형태)
    if s.startswith("```"):
        s2 = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s2 = re.sub(r"\s*```$", "", s2)
        s2 = s2.strip()
        try:
            data = json.loads(s2)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

    # 3) 첫 '{'부터 마지막 '}'까지 잘라서 파싱
    i = s.find("{")
    j = s.rfind("}")
    if i != -1 and j != -1 and j > i:
        chunk = s[i : j + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    return {}


def _trim_context_snapshot(
    ctx: Dict[str, Any],
    *,
    max_chat_messages: int = 10,
    max_message_chars: int = 200,
) -> Dict[str, Any]:
    """채팅/대용량 컨텍스트 토큰 폭주 방지."""
    try:
        snapshots = ctx.get("snapshots") or {}
        chat = snapshots.get("deal_chat_recent")
        if isinstance(chat, list):
            chat = chat[-max(0, int(max_chat_messages)):]
            for m in chat:
                if isinstance(m, dict) and isinstance(m.get("message"), str):
                    msg = m["message"]
                    if len(msg) > max_message_chars:
                        m["message"] = msg[:max_message_chars] + "…"
            snapshots["deal_chat_recent"] = chat
            ctx["snapshots"] = snapshots
    except Exception:
        pass
    return ctx


# =========================================================
# Policy safe getters (모델 속성명 흔들림 대비)
# =========================================================

def _pkey(p: Any) -> Optional[str]:
    """
    PolicyDeclaration에서 policy_key를 안전하게 꺼낸다.
    - SQLAlchemy 모델/딕셔너리/기타 타입 모두 방어
    """
    if p is None:
        return None

    # dict 대응
    if isinstance(p, dict):
        v = p.get("policy_key") or p.get("key") or p.get("policyKey")
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return None

    # SQLAlchemy 모델 대응 (정석: policy_key)
    v = getattr(p, "policy_key", None)
    if isinstance(v, str):
        v = v.strip()
        if v:
            return v

    # 혹시 과거 코드/이름 흔들림 대응
    v = getattr(p, "key", None)
    if isinstance(v, str):
        v = v.strip()
        if v:
            return v

    return None


def _pdomain(p: Any) -> str:
    return (getattr(p, "domain", None) or "").strip()


def _ptitle(p: Any) -> str:
    return (getattr(p, "title", None) or "").strip()


def _pdesc(p: Any) -> str:
    # DB 스키마: description_md, 예전코드/다른모델: description
    return (getattr(p, "description_md", None) or getattr(p, "description", None) or "").strip()


def _pver(p: Any) -> int:
    v = getattr(p, "version", None)
    try:
        return int(v) if v is not None else 1
    except Exception:
        return 1


def _pid(p: Any) -> int:
    v = getattr(p, "id", None)
    try:
        return int(v) if v is not None else 0
    except Exception:
        return 0


# =========================================================
# Context Builder
# =========================================================

def _build_context_snapshot(db: Session, body: PingpongAskIn) -> Dict[str, Any]:
    """
    screen + context(deal_id/reservation_id/offer_id)를 기반으로
    LLM에게 넘길 '요약 컨텍스트'를 만든다.
    """
    ctx: Dict[str, Any] = {
        "screen": body.screen,
        "user": {"user_id": body.user_id, "role": body.role},
        "raw_context": body.context.model_dump(mode="json"),
        "snapshots": {},
    }

    # 1) 딜 정보
    if body.context.deal_id:
        deal = db.query(models.Deal).filter(models.Deal.id == body.context.deal_id).first()
        if deal:
            ctx["snapshots"]["deal"] = _jsonable({
                "id": getattr(deal, "id", None),
                "product_name": getattr(deal, "product_name", None),
                "desired_qty": getattr(deal, "desired_qty", None),
                "status": getattr(deal, "status", None),
                "deadline_at": getattr(deal, "deadline_at", None),
                "product_norm": getattr(deal, "product_norm", None),
                "options_norm": getattr(deal, "options_norm", None),
                "created_at": getattr(deal, "created_at", None),
            })

            # 딜 채팅 최근 30개(나중에 trim)
            try:
                messages = (
                    db.query(models.DealChatMessage)
                    .filter(models.DealChatMessage.deal_id == deal.id)
                    .order_by(models.DealChatMessage.created_at.desc())
                    .limit(30)
                    .all()
                )
                ctx["snapshots"]["deal_chat_recent"] = [
                    _jsonable({
                        "id": getattr(m, "id", None),
                        "sender_role": getattr(m, "sender_role", None),
                        "sender_id": getattr(m, "sender_id", None),
                        "message": getattr(m, "message", None),
                        "created_at": getattr(m, "created_at", None),
                    })
                    for m in reversed(messages)
                ]
            except Exception:
                pass

    # 2) 예약 정보
    if body.context.reservation_id:
        r = db.query(models.Reservation).filter(models.Reservation.id == body.context.reservation_id).first()
        if r:
            ctx["snapshots"]["reservation"] = _jsonable({
                "id": getattr(r, "id", None),
                "status": getattr(r, "status", None),
                "qty": getattr(r, "qty", None),
                "refunded_qty": getattr(r, "refunded_qty", None),
                "amount_total": getattr(r, "amount_total", None),
                "refunded_amount_total": getattr(r, "refunded_amount_total", None),
                "paid_at": getattr(r, "paid_at", None),
                "created_at": getattr(r, "created_at", None),
                "expires_at": getattr(r, "expires_at", None),
            })

    # 3) 오퍼 정보
    if body.context.offer_id:
        offer = db.query(models.Offer).filter(models.Offer.id == body.context.offer_id).first()
        if offer:
            ctx["snapshots"]["offer"] = _jsonable({
                "id": getattr(offer, "id", None),
                "deal_id": getattr(offer, "deal_id", None),
                "price": getattr(offer, "price", None),
                "sold_qty": getattr(offer, "sold_qty", None),
                "reserved_qty": getattr(offer, "reserved_qty", None),
                "shipping_mode": getattr(offer, "shipping_mode", None),
                "created_at": getattr(offer, "created_at", None),
            })

    return ctx


# =========================================================
# MD 파일 직접 로드 (DB가 완전히 비었을 때 fallback)
# =========================================================
_MD_POLICY_CACHE: List[Any] = []
_MD_POLICY_LOADED = False

def _load_policies_from_md_files(question: str, limit: int = 15) -> List[Any]:
    """policy_declarations DB가 비었을 때 .md 파일에서 직접 검색하여 가상 PolicyDeclaration 반환"""
    global _MD_POLICY_CACHE, _MD_POLICY_LOADED
    from pathlib import Path as _MdPath

    if not _MD_POLICY_LOADED:
        _app_dir = _MdPath(__file__).resolve().parent.parent  # app/routers -> app
        # 여러 경로 후보 시도 (로컬 + Docker + CWD)
        _candidate_bases = [
            _app_dir,                                              # __file__ 기준
            _MdPath("/app/app"),                                   # Docker /app/ 기준
            _MdPath(os.getcwd()) / "app",                          # CWD 기준
        ]
        doc_roots = []
        for base in _candidate_bases:
            for sub in ["policy/docs/public", "policy/docs/admin", "policy/docs/admin/ssot", "policy/docs"]:
                dr = base / sub
                if dr.exists() and dr not in doc_roots:
                    doc_roots.append(dr)
        if not doc_roots:
            print(f"[pingpong] WARNING: No policy/docs dirs found. Bases tried: {[str(b) for b in _candidate_bases]}", flush=True)
        for dr in doc_roots:
            if not dr.exists():
                continue
            for fp in sorted(dr.rglob("*.md")):
                if not fp.is_file():
                    continue
                try:
                    text = fp.read_text(encoding="utf-8", errors="replace").strip()
                except Exception:
                    continue
                if not text:
                    continue
                try:
                    rel = fp.relative_to(_app_dir / "policy" / "docs").as_posix().removesuffix(".md")
                except Exception:
                    rel = fp.stem
                kl = rel.lower()
                domain = (
                    "REFUND" if "refund" in kl else
                    "SHIPPING" if "shipping" in kl else
                    "SETTLEMENT" if "settlement" in kl else
                    "FEES" if "fee" in kl else
                    "TIERS" if "tier" in kl else
                    "PRICING" if "pricing" in kl or "price" in kl else
                    "GUARDRAILS" if "guardrail" in kl else
                    "TIME" if "time" in kl else
                    "PARTICIPANTS" if "participant" in kl else
                    "PINGPONG" if "pingpong" in kl else
                    "BUYER" if "buyer" in kl else
                    "SELLER" if "seller" in kl else
                    "GENERAL"
                )
                title = fp.stem
                for line in text.splitlines()[:10]:
                    ls = line.strip()
                    if ls.startswith("# ") and ls[2:].strip():
                        title = ls[2:].strip()
                        break

                # 가상 객체 (PolicyDeclaration ORM 없이 duck-typing)
                class _FakePolicy:
                    pass
                obj = _FakePolicy()
                obj.id = len(_MD_POLICY_CACHE) + 90000  # 가상 ID (DB와 충돌 안 되게)
                obj.domain = domain
                obj.policy_key = rel
                obj.title = title
                obj.description_md = text
                obj.version = 1
                obj.is_active = 1
                _MD_POLICY_CACHE.append(obj)
        _MD_POLICY_LOADED = True
        print(f"[pingpong] MD fallback loaded: {len(_MD_POLICY_CACHE)} docs", flush=True)

    if not _MD_POLICY_CACHE:
        return []

    # 질문 기반 스코어링 (sidecar retrieve_kb_snippets 간소화)
    ql = (question or "").lower()
    tokens = re.findall(r"[가-힣]{2,}|[a-z]{2,}", ql)
    if not tokens:
        return _MD_POLICY_CACHE[:limit]

    scored = []
    for p in _MD_POLICY_CACHE:
        s = 0.0
        text_l = (p.description_md or "").lower()
        path_l = (p.policy_key or "").lower()
        for t in tokens[:15]:
            if t in path_l:
                s += 8
            if t in text_l:
                s += min(20, text_l.count(t) * 2)
        scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]


def _build_policy_fallback_answer(question: str, policies: List[Any]) -> str:
    """LLM 없이 정책 텍스트에서 직접 관련 내용을 추출하여 답변 생성."""
    if not policies:
        return "역핑 관련 정보가 아직 준비되지 않았어요. 곧 업데이트될 예정이에요!"

    ql = (question or "").lower()
    tokens = re.findall(r"[가-힣]{2,}|[a-z]{2,}", ql)

    # 질문 토큰으로 정책 점수 매기기
    scored = []
    for p in policies:
        s = 0.0
        text_l = (getattr(p, "description_md", "") or "").lower()
        title_l = (getattr(p, "title", "") or "").lower()
        key_l = (getattr(p, "policy_key", "") or "").lower()
        for t in tokens[:10]:
            if t in title_l:
                s += 10
            if t in key_l:
                s += 5
            if t in text_l:
                s += min(15, text_l.count(t) * 2)
        scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)

    # 상위 3개 정책의 핵심 내용 추출
    top = [p for _, p in scored[:3]]
    parts = []
    for p in top:
        title = getattr(p, "title", "") or ""
        desc = (getattr(p, "description_md", "") or "").strip()
        # 핵심 내용만 추출 (첫 500자)
        if desc:
            lines = desc.split("\n")
            summary_lines = []
            char_count = 0
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("<!--"):
                    continue
                summary_lines.append(stripped)
                char_count += len(stripped)
                if char_count > 500:
                    break
            if summary_lines:
                parts.append(f"[{title}]\n" + "\n".join(summary_lines))

    if parts:
        return "관련 정책 정보를 찾았어요!\n\n" + "\n\n".join(parts[:2])

    # 일반적인 역핑 설명 (하드코딩 fallback)
    return (
        "역핑은 공동구매 중개 플랫폼이에요.\n\n"
        "1. 바이어가 딜을 만들어요 (원하는 상품 등록)\n"
        "2. 셀러가 오퍼를 보내요 (가격/조건 제안)\n"
        "3. 바이어가 마음에 드는 오퍼에 참여(예약)해요\n"
        "4. 목표 수량이 모이면 공동구매가 성사돼요\n"
        "5. 결제 → 배송 → 정산 순서로 진행돼요\n\n"
        "더 궁금한 점이 있으면 질문해 주세요!"
    )


def _choose_policy_domains(screen: str) -> List[str]:
    s = (screen or "").upper()
    if s in ("REFUND_FLOW", "RESERVATION_DETAIL"):
        return ["MONEY", "REFUND", "POINT"]
    if s in ("DEAL_ROOM", "DEAL_LIST", "DEAL_DETAIL"):
        return ["DEAL", "MONEY"]
    if s in ("OFFER_WRITE", "OFFER_EDIT"):
        return ["DEAL", "OFFER", "MONEY"]
    if s in ("SETTLEMENT_DASHBOARD", "SETTLEMENT_DETAIL"):
        return ["SETTLEMENT", "MONEY"]
    return ["MONEY", "GENERAL", "POINT"]


# =========================================================
# Policy fallback (LLM이 used_policy_keys를 비울 때)
# =========================================================

def _fallback_policy_keys(
    question: str,
    domains: List[str],
    policies: List[Any],
    max_keys: int = 3,
) -> List[str]:
    q = (question or "").lower()

    by_key = {_pkey(p): p for p in policies if _pkey(p)}

    def pick(k: str, out: List[str]) -> None:
        if k in by_key and k not in out:
            out.append(k)

    out: List[str] = []

    if "포인트" in q:
        pick("refund.partial_refund.points_rule", out)
        pick("point.revoke.when_refund.buyer_fault", out)
        pick("point.keep.when_refund.seller_fault", out)
        pick("point.on_refund_revoke", out)
        pick("point.on_paid_grant", out)

    if "부분" in q or "부분환불" in q:
        pick("refund.partial_refund.definition", out)
        pick("refund.partial_refund_allowed", out)
        pick("refund.partial_refund.points_rule", out)

    if "전액" in q or "전체" in q:
        pick("refund.full_refund.definition", out)

    if "수수료" in q or "pg" in q:
        pick("money.fee.pg_platform.burden", out)
        pick("refund.before_shipping.buyer_fault.fee_burden", out)
        pick("refund.before_shipping.seller_fault.fee_burden", out)

    if "배송" in q or "발송" in q:
        pick("money.shipping_fee.refund.rule", out)
        pick("refund.after_shipping.buyer_fault.limit", out)
        pick("refund.after_shipping.seller_fault.allowed", out)

    if "금액" in q or "환불액" in q:
        pick("money.refund_amount.calc", out)
        pick("money.amount_definition", out)

    # 그래도 비면: 도메인 우선순위로 대표 1개라도
    if not out:
        domain_priority = [d.upper() for d in (domains or [])] + ["REFUND", "POINT", "MONEY", "GENERAL"]
        for d in domain_priority:
            for p in policies:
                if (_pdomain(p) or "").upper() == d and _pkey(p):
                    out.append(_pkey(p))
                    break
            if out:
                break

    # 최소 1개 보장(정말 정책이 없으면 빈 배열)
    if out:
        return out[: max(1, int(max_keys or 1))]
    return []


# =========================================================
# Prompt builder
# =========================================================

def _build_system_prompt(
    locale: str,
    policies: List[models.PolicyDeclaration],
    mode: str,
    *,
    allowed_keys: Optional[List[str]] = None,
) -> str:
    locale = (locale or "ko").lower()
    mode = (mode or "read_only").lower()

    if locale.startswith("ko"):
        intro = (
            "너는 공동구매 플랫폼 '역핑'의 공식 AI 헬퍼 '핑퐁이'다.\n"
            "항상 정책선언집을 최우선 근거로 삼고, 사용자의 현재 화면과 컨텍스트를 바탕으로 답한다.\n"
            "정책선언집에 관련 내용이 있으면 그 내용을 기반으로 구체적으로 답변하라.\n"
            "정책선언집에 없는 내용이라면 일반적인 지식으로 최선을 다해 답변하라.\n"
            "'확인 중' 이나 '잠시 후 다시' 같은 대기 메시지를 절대 쓰지 마라. 항상 즉시 답변하라.\n"
        )
    else:
        intro = (
            "You are 'Pingpong', the official AI helper of Yeokping.\n"
            "Always follow the policy declarations first and answer based on the screen/context.\n"
            "If policy docs contain relevant info, answer specifically based on them.\n"
            "Never respond with placeholder messages like 'checking' or 'please wait'. Always answer immediately.\n"
        )

    # 정책 텍스트 (상위 5개는 길게, 나머지는 짧게)
    lines: List[str] = []
    for i, p in enumerate(policies):
        desc = (getattr(p, "description_md", "") or "").strip()
        max_len = 2000 if i < 5 else 600  # 상위 5개는 충분한 컨텍스트 제공
        if len(desc) > max_len:
            desc = desc[:max_len] + "…"
        lines.append(f"- [{p.domain}] {p.policy_key} (v{p.version}) :: {p.title} :: {desc}")
    policies_text = "\n".join(lines) if lines else "(등록된 정책이 부족합니다. 일반적인 지식으로 답변하라.)"

    # 허용 policy_key 목록(너무 길면 줄이기)
    allowed_keys = allowed_keys or []
    allowed_keys_sorted = sorted([k for k in allowed_keys if isinstance(k, str) and k.strip()])
    max_show = 120  # 너무 길면 토큰 낭비라 적당히 제한(현재는 20이라 넉넉)
    head = allowed_keys_sorted[:max_show]
    tail_n = max(0, len(allowed_keys_sorted) - len(head))

    if head:
        allowed_keys_text = "\n".join(head)
        if tail_n > 0:
            allowed_keys_text += f"\n… (총 {len(allowed_keys_sorted)}개 중 {tail_n}개 더 있음)"
    else:
        allowed_keys_text = "(없음)"

    # 모드 규칙
    mode_rule = (
        "현재 mode는 read_only 이다. 사용자를 대신해 어떤 API도 실행하지 않는다.\n"
        if mode == "read_only" else
        "현재 mode는 suggest_actions 이다. 실행은 하지 말고, '제안 액션'만 JSON actions에 넣어라.\n"
    )

    guide = f"""
{mode_rule}
답변 규칙:
- 정책선언집과 모순되는 말을 하면 안 된다.
- 사용자가 바로 행동할 수 있을 정도로만 구체적으로 말해라.
- 정책에 없는 내용이면 일반 지식으로 최대한 도움이 되는 답변을 해라.
- '확인 중', '잠시 후 다시', '추가 확인이 필요합니다' 같은 대기 메시지를 절대 쓰지 마라.
- used_policy_keys는 아래 '허용 policy_key 목록'에 있는 값만 넣어라.
- 관련 정책이 하나라도 있으면 used_policy_keys는 반드시 1개 이상 포함해라.
- read_only 모드에서는 actions를 반드시 빈 배열([])로 내려라.
- suggest_actions 모드에서만 actions를 내려라.

[허용 policy_key 목록]
{allowed_keys_text}

반드시 아래 JSON 형식으로만 응답해라:

{{
  "answer": "사용자에게 보여줄 최종 답변 (문자열)",
  "used_policy_keys": ["policy.key.1", "policy.key.2"],
  "actions": [
    {{
      "type": "suggest_api",
      "label": "사용자에게 보여줄 액션 설명",
      "endpoint": "POST /v3_6/...",
      "payload_template": {{}},
      "requires_confirmation": true
    }}
  ]
}}
""".strip()

    return f"{intro}\n\n[정책선언집]\n{policies_text}\n\n{guide}"


# =========================================================
# Intent Classification (sidecar 패턴 경량화)
# =========================================================

_INTENT_SYSTEM_PROMPT = """\
Your ENTIRE response must be exactly one JSON object. No markdown, no explanation.
FORMAT: {"intent": "INTENT_NAME", "query": null}

You classify messages for 역핑(Yeokping), a Korean group-buying platform.

INTENT VALUES (pick one):
  EXTERNAL_PRICE   - Price query with brand/model name (갤럭시, 아이폰, 맥북, 에어팟, 다이슨 등)
  EXTERNAL_NEWS    - News/headline request (뉴스, 헤드라인, 기사, 속보)
  YEOKPING_GENERAL - Platform question (refund, fees, shipping, deals, offers, reservations, points, policy)
  SMALLTALK        - Everything else (greetings, general knowledge, weather, jokes)

RULES:
- Yeokping-specific terms = YEOKPING_GENERAL: 역핑, 딜, 오퍼, 예약, 환불, 정산, 쿨링, 액츄에이터, 공동구매
- Price + product name = EXTERNAL_PRICE. "얼마야" alone = SMALLTALK
- "수수료 얼마?" = YEOKPING_GENERAL (platform fee)
- Entity with number (딜 10번, 오퍼 5번) = YEOKPING_GENERAL
- When in doubt = SMALLTALK

EXAMPLES:
{"intent": "EXTERNAL_PRICE", "query": "갤럭시 S25"}
{"intent": "YEOKPING_GENERAL", "query": null}
{"intent": "SMALLTALK", "query": null}
"""

_YEOKPING_KEYWORDS = re.compile(
    r"(역핑|공동구매|오퍼|offer|딜|deal|액츄에이터|예약|reservation|환불|수수료|정산|쿨링|배송비|"
    r"포인트|refund|settlement|shipping|cooling|판매자|구매자|방장|leader|PG|마감|참여|결제)",
    re.IGNORECASE,
)

_NEWS_PAT = re.compile(
    r"(뉴스|헤드라인|해드라인|headline|news|기사|시사|속보)",
    re.IGNORECASE,
)

_PRICE_PRODUCT_PAT = re.compile(
    r"(갤럭시|galaxy|아이폰|iphone|에어팟|airpod|맥북|macbook|LG\s*그램|그램|다이슨|dyson|"
    r"나이키|nike|아디다스|adidas|RTX|노트북|냉장고|세탁기|TV|모니터|카메라|PS5|플스|닌텐도|스위치|"
    r"아이패드|ipad|갤럭시탭|버즈|buds|워치|watch|에어맥스|조던|뉴발란스)",
    re.IGNORECASE,
)
_PRICE_TRIGGER_PAT = re.compile(
    r"(가격|얼마|최저가|시세|싼|비싼|시장가|쇼핑|비교|검색해|찾아|알려)",
    re.IGNORECASE,
)


def _classify_intent_simple(question: str) -> Dict[str, Any]:
    """경량 regex 기반 의도 분류 (LLM 호출 전 빠른 라우팅)."""
    q = (question or "").strip().lower()

    # 1) 역핑 키워드 → YEOKPING_GENERAL
    if _YEOKPING_KEYWORDS.search(q):
        return {"intent": "YEOKPING_GENERAL", "query": None}

    # 2) 제품명 + 가격 트리거 → EXTERNAL_PRICE
    if _PRICE_PRODUCT_PAT.search(q) and _PRICE_TRIGGER_PAT.search(q):
        # 제품 키워드 추출
        m = _PRICE_PRODUCT_PAT.search(q)
        product_query = m.group(0) if m else q
        return {"intent": "EXTERNAL_PRICE", "query": product_query}

    # 3) 제품명만 있어도 "얼마" 포함 → EXTERNAL_PRICE
    if _PRICE_PRODUCT_PAT.search(q) and re.search(r"(얼마|가격|최저가)", q):
        m = _PRICE_PRODUCT_PAT.search(q)
        return {"intent": "EXTERNAL_PRICE", "query": m.group(0) if m else q}

    # 4) 뉴스 키워드 → EXTERNAL_NEWS
    if _NEWS_PAT.search(q):
        return {"intent": "EXTERNAL_NEWS", "query": None}

    return {"intent": "UNKNOWN", "query": None}


def _classify_intent_llm(question: str) -> Dict[str, Any]:
    """LLM 기반 의도 분류 (regex 실패 시 fallback)."""
    try:
        client = get_client()
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            max_tokens=80,
            temperature=0,
            timeout=8,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        data = json.loads(raw)
        intent = str(data.get("intent", "SMALLTALK")).upper()
        if intent not in ("EXTERNAL_PRICE", "EXTERNAL_NEWS", "YEOKPING_GENERAL", "SMALLTALK"):
            intent = "SMALLTALK"
        return {"intent": intent, "query": data.get("query")}
    except Exception:
        return {"intent": "SMALLTALK", "query": None}


def _classify_intent(question: str) -> Dict[str, Any]:
    """regex 우선, 불확실하면 LLM fallback."""
    result = _classify_intent_simple(question)
    if result["intent"] != "UNKNOWN":
        return result
    return _classify_intent_llm(question)


# =========================================================
# External Price Handler (Naver Shopping API)
# =========================================================

def _handle_external_price(query: str) -> Optional[str]:
    """네이버 쇼핑 API로 가격 조회. 실패 시 None."""
    try:
        from app.utils.naver_shopping import search_naver_shopping
        result = search_naver_shopping(query)
        if result and result.lowest_price > 0:
            price_str = f"{result.lowest_price:,}원"
            if result.lowest_price >= 10000:
                price_str += f" (약 {result.lowest_price // 10000}만원대)"

            lines = [f"{result.product_name}"]
            lines.append(f"최저가: {price_str}")
            if result.mall_name:
                lines.append(f"판매처: {result.mall_name}")
            if result.highest_price and result.highest_price > result.lowest_price:
                lines.append(f"가격 범위: {result.lowest_price:,}원 ~ {result.highest_price:,}원")
            lines.append("(네이버쇼핑 기준, 실제 가격과 다를 수 있습니다)")

            from urllib.parse import quote_plus
            eq = quote_plus(query)
            lines.append("")
            lines.append("자세한 비교는 아래에서 확인해 보세요:")
            lines.append(f"- 네이버쇼핑: https://search.shopping.naver.com/search/all?query={eq}")
            lines.append(f"- 다나와: https://search.danawa.com/dsearch.php?k1={eq}")
            lines.append(f"- 쿠팡: https://www.coupang.com/np/search?q={eq}")

            return "\n".join(lines)
    except Exception as e:
        print(f"[pingpong] 네이버 가격 조회 실패: {e}")

    # 가격 조회 실패 → 링크만 제공
    try:
        from urllib.parse import quote_plus
        eq = quote_plus(query)
        return (
            f"'{query}' 가격 정보를 직접 조회하지 못했어요. 아래에서 확인해 보세요:\n"
            f"- 네이버쇼핑: https://search.shopping.naver.com/search/all?query={eq}\n"
            f"- 다나와: https://search.danawa.com/dsearch.php?k1={eq}\n"
            f"- 쿠팡: https://www.coupang.com/np/search?q={eq}"
        )
    except Exception:
        return None


# =========================================================
# News Handler (Google News RSS)
# =========================================================

def _handle_external_news() -> Optional[str]:
    """Google News RSS에서 최신 한국 뉴스 헤드라인을 가져온다."""
    import xml.etree.ElementTree as ET
    try:
        import requests as _req
        rss_url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
        resp = _req.get(rss_url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        if not items:
            return None
        headlines = []
        for item in items[:5]:
            title_el = item.find("title")
            if title_el is not None and title_el.text:
                headlines.append(title_el.text.strip())
        if not headlines:
            return None
        lines = ["오늘의 주요 뉴스 헤드라인이에요:"]
        for i, h in enumerate(headlines, 1):
            lines.append(f"{i}. {h}")
        lines.append("")
        lines.append("더 자세한 뉴스는 아래에서 확인하세요:")
        lines.append("- 구글뉴스: https://news.google.com/?hl=ko&gl=KR&ceid=KR:ko")
        lines.append("- 네이버뉴스: https://news.naver.com/")
        return "\n".join(lines)
    except Exception as e:
        print(f"[pingpong] 뉴스 RSS 실패: {e}")
        return None


# =========================================================
# Smalltalk Handler
# =========================================================

def _handle_smalltalk(question: str) -> str:
    """일반 대화 처리 (정책 KB 없이 LLM으로 자연스럽게)."""
    try:
        client = get_client()
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": (
                    "너는 공동구매 플랫폼 '역핑'의 AI 헬퍼 '핑퐁이'야. "
                    "친절하고 자연스럽게 대화해. "
                    "역핑/정책/서버/DB 같은 내부 용어는 쓰지 마. "
                    "1~4문장으로 짧게 답해. "
                    "확신 없으면 '정확하진 않지만...' 같은 완충 표현을 써."
                )},
                {"role": "user", "content": question},
            ],
            temperature=0.7,
            max_tokens=300,
            timeout=10,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return (
            "역핑은 공동구매 중개 플랫폼이에요! "
            "딜, 오퍼, 정책 관련 질문을 해주시면 도움을 드릴 수 있어요."
        )


# =========================================================
# Sidecar proxy endpoint (replaces direct brain call)
# =========================================================
@router.post("/ask", response_model=None)
async def pingpong_ask_proxy(request: Request):
    """
    Proxy to sidecar server for full AI agent capabilities.
    Falls back to brain endpoint if sidecar is unreachable.
    """
    try:
        body_json = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    if not (body_json.get("question") or "").strip():
        raise HTTPException(status_code=400, detail="question is required")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{SIDECAR_URL}/ask", json=body_json)
            return resp.json()
    except Exception:
        # Sidecar unreachable → fall back to brain
        pass

    # Fallback: call brain directly
    from app.database import get_db as _get_db
    db_gen = _get_db()
    db = next(db_gen)
    try:
        body = PingpongAskIn(**body_json)
        result = _pingpong_brain_logic(body, db)
        return jsonable_encoder(result)
    except Exception as brain_err:
        print(f"[pingpong /ask] Brain fallback error: {brain_err}", flush=True)
        traceback.print_exc()
        # 최후 fallback — 정책 MD 파일에서 직접 답변 생성
        question = body_json.get("question", "")
        md_policies = _load_policies_from_md_files(question)
        fallback_answer = _build_policy_fallback_answer(question, md_policies)
        return {
            "answer": fallback_answer,
            "used_policies": [],
            "actions": [],
            "debug": {"brain_error": str(brain_err), "fallback": "md_direct"},
        }
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# =========================================================
# Brain endpoint (policy-based LLM, called by sidecar internally)
# =========================================================
@router.post("/brain/ask", response_model=PingpongAskOut)
def pingpong_brain_ask(
    body: PingpongAskIn = Body(...),
    db: Session = Depends(get_db),
):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    return _pingpong_brain_logic(body, db)


def _pingpong_brain_logic(
    body: PingpongAskIn,
    db: Session,
) -> PingpongAskOut:
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    # 0) 의도 분류 — EXTERNAL_PRICE / SMALLTALK은 정책 KB 불필요
    body.question = _redact_pii(body.question.strip())
    intent = _classify_intent(body.question)

    # EXTERNAL_PRICE → 네이버 쇼핑 API 직접 응답
    if intent["intent"] == "EXTERNAL_PRICE":
        price_query = intent.get("query") or body.question
        price_answer = _handle_external_price(price_query)
        if price_answer:
            # 로그 저장
            try:
                crud.log_pingpong(
                    db, user_id=body.user_id, role=body.role,
                    locale=body.locale, screen=body.screen,
                    deal_id=body.context.deal_id, reservation_id=body.context.reservation_id,
                    offer_id=body.context.offer_id, mode=body.mode,
                    question=body.question, answer=price_answer,
                    used_policy_keys=[], used_policy_ids=[], actions=[],
                    context={"intent": "EXTERNAL_PRICE", "query": price_query},
                    request_payload={"intent": intent},
                    response_payload={"source": "naver_shopping"},
                    llm_model="naver_api", latency_ms=0,
                    prompt_tokens=None, completion_tokens=None,
                    error_code=None, error_message=None,
                )
            except Exception:
                pass
            return PingpongAskOut(
                answer=price_answer,
                used_policies=[],
                actions=[],
                debug={"intent": "EXTERNAL_PRICE", "query": price_query},
            )

    # EXTERNAL_NEWS → Google News RSS
    if intent["intent"] == "EXTERNAL_NEWS":
        news_answer = _handle_external_news()
        if news_answer:
            try:
                crud.log_pingpong(
                    db, user_id=body.user_id, role=body.role,
                    locale=body.locale, screen=body.screen,
                    deal_id=body.context.deal_id, reservation_id=body.context.reservation_id,
                    offer_id=body.context.offer_id, mode=body.mode,
                    question=body.question, answer=news_answer,
                    used_policy_keys=[], used_policy_ids=[], actions=[],
                    context={"intent": "EXTERNAL_NEWS"},
                    request_payload={"intent": intent},
                    response_payload={"source": "google_news_rss"},
                    llm_model="rss", latency_ms=0,
                    prompt_tokens=None, completion_tokens=None,
                    error_code=None, error_message=None,
                )
            except Exception:
                pass
            return PingpongAskOut(
                answer=news_answer,
                used_policies=[],
                actions=[],
                debug={"intent": "EXTERNAL_NEWS"},
            )
        # RSS 실패 시 링크만 제공
        fallback_news = (
            "뉴스 헤드라인을 바로 가져오지 못했어요. 아래에서 확인해 보세요:\n"
            "- 구글뉴스: https://news.google.com/?hl=ko&gl=KR&ceid=KR:ko\n"
            "- 네이버뉴스: https://news.naver.com/"
        )
        return PingpongAskOut(
            answer=fallback_news,
            used_policies=[],
            actions=[],
            debug={"intent": "EXTERNAL_NEWS", "rss_failed": True},
        )

    # SMALLTALK → 가벼운 LLM 대화 (정책 KB 스킵)
    if intent["intent"] == "SMALLTALK":
        smalltalk_answer = _handle_smalltalk(body.question)
        try:
            crud.log_pingpong(
                db, user_id=body.user_id, role=body.role,
                locale=body.locale, screen=body.screen,
                deal_id=body.context.deal_id, reservation_id=body.context.reservation_id,
                offer_id=body.context.offer_id, mode=body.mode,
                question=body.question, answer=smalltalk_answer,
                used_policy_keys=[], used_policy_ids=[], actions=[],
                context={"intent": "SMALLTALK"},
                request_payload={"intent": intent},
                response_payload={"source": "smalltalk_llm"},
                llm_model="gpt-4.1-mini", latency_ms=0,
                prompt_tokens=None, completion_tokens=None,
                error_code=None, error_message=None,
            )
        except Exception:
            pass
        return PingpongAskOut(
            answer=smalltalk_answer,
            used_policies=[],
            actions=[],
            debug={"intent": "SMALLTALK"},
        )

    # YEOKPING_GENERAL → 아래 정책 기반 LLM 로직 진행

    # 1) 컨텍스트
    ctx = _build_context_snapshot(db, body)

    max_chat_messages = int(getattr(body, "max_chat_messages", 10) or 10)
    ctx = _trim_context_snapshot(ctx, max_chat_messages=max_chat_messages, max_message_chars=200)

    # 2) 정책 로드
    domains = _choose_policy_domains(body.screen)
    policies = crud.get_active_policies(db, domains=domains, limit_total=40)

    # ✅ fallback: 도메인 매칭 실패 시 GENERAL(+핵심 공통)로 재시도
    if not policies:
        fallback_domains = ["GENERAL", "TIME", "REFUND", "FEES", "GUARDRAILS", "PARTICIPANTS", "PINGPONG", "POINT"]
        # (질문에 '정산/settlement'가 보이면 SETTLEMENT도 추가하는 식으로 더 똑똑하게 해도 됨)
        policies = crud.get_active_policies(db, domains=fallback_domains, limit_total=40)

    # ✅ 그래도 비면 최후: domains=None (전체에서 40개)
    if not policies:
        policies = crud.get_active_policies(db, domains=None, limit_total=40)

    # ✅ DB 완전히 비면 → .md 파일에서 직접 로드하여 가상 PolicyDeclaration 생성
    if not policies:
        policies = _load_policies_from_md_files(body.question)

    # ✅ allowed_keys 산정 (policy_key 확정)  ---- 가장 중요 ----
    allowed_keys_set = {p.policy_key for p in policies if getattr(p, "policy_key", None)}
    allowed_keys_set.discard(None)  # 방어
    if (not allowed_keys_set) and policies:
        # 혹시라도 이상하면 강제 보정(지금 네 증상 방지)
        allowed_keys_set = {
            str(getattr(p, "policy_key", "")).strip()
            for p in policies
            if getattr(p, "policy_key", None)
        }
        allowed_keys_set.discard("")

    allowed_keys_list = sorted(list(allowed_keys_set))
    allowed_keys_head = allowed_keys_list[:10]

    # 3) 프롬프트 구성 (allowed_keys 인자 유무 방어)
    try:
        system_prompt = _build_system_prompt(
            body.locale,
            policies,
            body.mode,
            allowed_keys=allowed_keys_list,
        )
    except TypeError:
        # 파일 내 _build_system_prompt 시그니처가 아직 allowed_keys를 안 받는 경우
        system_prompt = _build_system_prompt(body.locale, policies, body.mode)

    user_payload = {
        "screen": body.screen,
        "mode": body.mode,
        "question": body.question,
        "context": ctx,
    }

    started = time.time()
    llm_model = "gpt-4.1-mini"

    raw_data: Dict[str, Any] = {}
    answer = ""
    used_keys: List[str] = []
    actions: List[Dict[str, Any]] = []

    error_code: Optional[str] = None
    error_message: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    raw_content: str = ""
    policy_keys_source: str = "llm"  # ✅ 무조건 미리 정의(아래 debug에서 안전)

    llm_request_meta: Dict[str, Any] = {
        "model": llm_model,
        "domains": domains,
        "screen": body.screen,
        "mode": body.mode,
        "max_chat_messages": max_chat_messages,
        "policy_count": len(policies),
        "allowed_keys_count": len(allowed_keys_set),
    }

    try:
        client = get_client()

        # ✅ datetime 직렬화 문제 방지
        safe_user_payload = _jsonable(user_payload)

        resp = client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(safe_user_payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=30,
            max_tokens=1200,
        )

        raw_content = resp.choices[0].message.content or ""
        raw_data = _safe_json_loads(raw_content)

        # 토큰 메타(있으면 기록)
        try:
            usage = getattr(resp, "usage", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                completion_tokens = getattr(usage, "completion_tokens", None)
        except Exception:
            pass

        answer = (raw_data.get("answer") or "").strip()
        used_keys = raw_data.get("used_policy_keys") or []
        actions = raw_data.get("actions") or []

        if not isinstance(used_keys, list):
            used_keys = []
        if not isinstance(actions, list):
            actions = []

        if not answer:
            raise ValueError("LLM returned empty answer")

    except Exception as e:
        error_code = "LLM_ERROR"
        error_message = f"{type(e).__name__}: {str(e)}"

        print("[pingpong_ask] LLM_ERROR:", error_message)
        if raw_content:
            print("[pingpong_ask] RAW_CONTENT_HEAD:", raw_content[:500])
        traceback.print_exc()

        # ✅ LLM 실패 시 정책 텍스트를 직접 반환 (LLM 없이)
        answer = _build_policy_fallback_answer(body.question, policies)
        used_keys = [p.policy_key for p in policies[:3] if getattr(p, "policy_key", None)]
        actions = []
        raw_data = {"fallback": True, "error_message": error_message, "policy_direct": True}

    latency_ms = int((time.time() - started) * 1000)

    # ---------------------------------------------------------
    # ✅ used_policy_keys 보정 로직 (핵심)
    #  - (A) LLM이 비우면 fallback
    #  - (B) LLM이 줬지만 허용 목록에 없어서 필터 후 비면 fallback
    # ---------------------------------------------------------

    # (A) LLM이 아예 비워서 준 경우
    if (not used_keys) and policies:
        used_keys = _fallback_policy_keys(body.question, domains, policies, max_keys=3)
        policy_keys_source = "fallback_empty"

    # ✅ 1차 필터: 반드시 allowed_keys_set 기준으로만!
    used_keys = [k for k in used_keys if isinstance(k, str) and k in allowed_keys_set]

    # (B) 필터 후 비었으면(LLM이 이상한 키 줬거나 allowed_keys 이상) fallback 재시도
    if (not used_keys) and policies:
        used_keys = _fallback_policy_keys(body.question, domains, policies, max_keys=3)
        used_keys = [k for k in used_keys if isinstance(k, str) and k in allowed_keys_set]
        if used_keys:
            policy_keys_source = "fallback_after_filter"

    # ---------------------------------------------------------
    # used_policies 조립
    # ---------------------------------------------------------
    key_to_policy = {p.policy_key: p for p in policies if getattr(p, "policy_key", None)}
    used_refs: List[PolicyRefOut] = []
    used_policy_ids: List[int] = []

    for k in used_keys:
        p = key_to_policy.get(k)
        if not p:
            continue
        used_policy_ids.append(p.id)
        used_refs.append(
            PolicyRefOut(
                policy_id=p.id,
                policy_key=p.policy_key,
                title=p.title,
                domain=p.domain,
                version=int(p.version),
            )
        )

    # actions 정리: suggest_actions일 때만 허용
    actions_out: List[PingpongActionOut] = []
    if (body.mode or "read_only").lower() == "suggest_actions":
        for a in actions:
            if not isinstance(a, dict):
                continue
            actions_out.append(
                PingpongActionOut(
                    type=str(a.get("type") or "hint"),
                    label=str(a.get("label") or ""),
                    endpoint=a.get("endpoint"),
                    payload_template=a.get("payload_template") if isinstance(a.get("payload_template"), dict) else None,
                    requires_confirmation=True,  # ✅ 파이썬에서는 True
                )
            )
    else:
        actions_out = []

    # 5) 로그 저장 (항상)
    try:
        crud.log_pingpong(
            db,
            user_id=body.user_id,
            role=body.role,
            locale=body.locale,
            screen=body.screen,
            deal_id=body.context.deal_id,
            reservation_id=body.context.reservation_id,
            offer_id=body.context.offer_id,
            mode=body.mode,
            question=body.question,
            answer=answer,
            used_policy_keys=used_keys,
            used_policy_ids=used_policy_ids,
            actions=[a.model_dump(mode="json") for a in actions_out],
            context=_jsonable(ctx),
            request_payload=_jsonable({
                "system_prompt_hint": "omitted",
                "domains": domains,
                "user_payload": user_payload,
                "llm_request_meta": llm_request_meta,
            }),
            response_payload=_jsonable({
                "raw_data": raw_data,
                "raw_content_head": raw_content[:500] if raw_content else None,
                "policy_keys_source": policy_keys_source,
                "final_used_policy_keys": used_keys,
            }),
            llm_model=llm_model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            error_code=error_code,
            error_message=error_message,
        )
    except Exception:
        pass

    return PingpongAskOut(
        answer=answer,
        used_policies=used_refs,
        actions=actions_out,
        debug={
            "domains": domains,
            "latency_ms": latency_ms,
            "has_deal_chat": "deal_chat_recent" in (ctx.get("snapshots") or {}),
            "error": error_code,
            "error_message": error_message,

            # ✅ 핵심 디버그(원인 추적)
            "policy_count": len(policies),
            "allowed_keys_count": len(allowed_keys_set),
            "allowed_keys_head": allowed_keys_head,
            "used_policy_keys": used_keys,
            "raw_content_head": (raw_content[:300] if raw_content else None),
            "policy_keys_source": policy_keys_source,
        },
    )