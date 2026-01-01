# app/routers/pingpong.py
from __future__ import annotations

import json
import re
import time
import traceback
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


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
    return ["MONEY", "GENERAL"]


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
            "확실하지 않으면 추측하지 말고 '추가 확인이 필요'하다고 말한다.\n"
        )
    else:
        intro = (
            "You are 'Pingpong', the official AI helper of Yeokping.\n"
            "Always follow the policy declarations first and answer based on the screen/context.\n"
            "If uncertain, do not guess; say that additional confirmation is needed.\n"
        )

    # 정책 텍스트(너무 길면 안 됨)
    lines: List[str] = []
    for p in policies:
        desc = (getattr(p, "description_md", "") or "").strip()
        if len(desc) > 400:
            desc = desc[:400] + "…"
        lines.append(f"- [{p.domain}] {p.policy_key} (v{p.version}) :: {p.title} :: {desc}")
    policies_text = "\n".join(lines) if lines else "(등록된 정책이 부족합니다.)"

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
- 모르는 부분은 추측하지 말고 '추가 확인이 필요합니다'라고 말해라.
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
# Endpoint
# =========================================================
@router.post("/ask", response_model=PingpongAskOut)
def pingpong_ask(
    body: PingpongAskIn = Body(...),
    db: Session = Depends(get_db),
):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    # 1) 컨텍스트
    body.question = _redact_pii(body.question.strip())
    ctx = _build_context_snapshot(db, body)

    max_chat_messages = int(getattr(body, "max_chat_messages", 10) or 10)
    ctx = _trim_context_snapshot(ctx, max_chat_messages=max_chat_messages, max_message_chars=200)

    # 2) 정책 로드
    domains = _choose_policy_domains(body.screen)
    policies = crud.get_active_policies(db, domains=domains, limit_total=40)

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
            max_tokens=600,
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

        answer = (
            "죄송해요. 지금은 답변 생성 중 오류가 발생했어요. "
            "잠시 후 다시 시도해 주세요. (정책/로그 기준으로는 추가 확인이 필요합니다.)"
        )
        used_keys = []
        actions = []
        raw_data = {"fallback": True, "error_message": error_message}

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