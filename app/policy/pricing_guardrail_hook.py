"""
pricing_guardrail_hook.py

Target vs Anchor Guardrail을
S1(딜 생성) / S2(Target 변경) / S3(Anchor 도착)에서
공통으로 호출하기 위한 Hook 유틸.

원칙:
- Deal 모델에 컬럼이 있으면 적용
- 없으면 조용히 스킵
- 로직 중복 금지
"""

from __future__ import annotations

from typing import Optional, Any, Dict, List
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session

# SSOT 로직
from app.policy.target_vs_anchor_guardrail import (
    PriceAxisEvaluationInput,
    evaluate_target_vs_anchor,
)

# pricing.yaml 로더(이미 쓰고 있는 엔진 로더 재사용)
from app.policy.pricing_engine import load_pricing_params

# evidence logging
try:
    from app.routers.activity_log import log_evidence_pack
except Exception:
    log_evidence_pack = None


# ------------------------------------------------------------
# params loader (pricing.yaml) — repo/app/policy/params/pricing.yaml
# ------------------------------------------------------------
_GUARDRAIL_PARAMS = None

def _get_guardrail_params() -> Optional[Dict[str, Any]]:
    """
    evaluate_target_vs_anchor(params, inp) 의 params로 쓸 dict 로드.
    - pricing.yaml 에 guardrail/phrasing 등이 같이 들어있다는 전제
    - 경로 후보 2개(신규/레거시) 모두 시도
    """
    global _GUARDRAIL_PARAMS
    if _GUARDRAIL_PARAMS is not None:
        return _GUARDRAIL_PARAMS

    try:
        repo_root = Path(__file__).resolve().parents[2]  # .../<repo>
        candidates: List[Path] = [
            repo_root / "app" / "policy" / "params" / "pricing.yaml",  # ✅ 추천
            repo_root / "policy" / "params" / "pricing.yaml",          # ✅ 레거시 대비
        ]

        yaml_path = None
        for p in candidates:
            if p.exists():
                yaml_path = p
                break

        if yaml_path is None:
            _GUARDRAIL_PARAMS = None
            return None

        _GUARDRAIL_PARAMS = load_pricing_params(str(yaml_path))
        return _GUARDRAIL_PARAMS

    except Exception:
        _GUARDRAIL_PARAMS = None
        return None


# ------------------------------------------------------------
# A) 평가 함수
# ------------------------------------------------------------
def run_pricing_guardrail(
    *,
    deal_id: int,
    category: str | None,
    target_price: float | None,
    anchor_price: float | None,
    evidence_score: int | None = 0,
    anchor_confidence: float | None = 1.0,
    stage: str | None = None,   # ✅ 추가
):
    params = _get_guardrail_params() or {}

    inp = PriceAxisEvaluationInput(
        deal_id=int(deal_id),
        category=category,
        target_price=float(target_price) if target_price is not None else None,
        anchor_price=float(anchor_price) if anchor_price is not None else None,
        evidence_score=int(evidence_score or 0),
        anchor_confidence=float(anchor_confidence or 1.0),
        now_ts=datetime.now(timezone.utc),
    )

    result = evaluate_target_vs_anchor(params, inp)

    # ✅ stage는 result에 얹어서 downstream(log/preview)에서 사용 가능하게
    try:
        setattr(result, "_stage", stage or "UNKNOWN")
    except Exception:
        pass

    return result


# ------------------------------------------------------------
# B) Deal 상태 반영 (있으면 적용 / 없으면 스킵)
# ------------------------------------------------------------
def apply_guardrail_to_deal(
    db: Session,
    deal: Any,
    result: Any,
):
    """
    Deal 모델에 다음 필드가 있으면 반영:
    - needs_reconfirm
    - target_locked
    """
    level = getattr(result, "level", None)
    if not level:
        return

    # needs_reconfirm
    if hasattr(deal, "needs_reconfirm"):
        setattr(deal, "needs_reconfirm", level in ("WARN_HARD", "BLOCK"))

    # target_locked
    if hasattr(deal, "target_locked"):
        if level == "BLOCK":
            setattr(deal, "target_locked", True)

    try:
        db.add(deal)
        db.commit()
        db.refresh(deal)
    except Exception:
        db.rollback()


# ------------------------------------------------------------
# C) Evidence Pack 로그 기록
# ------------------------------------------------------------
def log_guardrail_evidence(
    db: Session,
    *,
    deal_id: int,
    result: Any,
    anchor_version: Optional[str] = None,
    stage: Optional[str] = None,   # ✅ 추가
):
    if log_evidence_pack is None:
        return

    try:
        payload: Dict[str, Any] = {
            "deal_id": deal_id,
            "stage": stage or getattr(result, "_stage", None) or "UNKNOWN",  # ✅ 추가
            "level": getattr(result, "level", None),
            "reason_codes": getattr(result, "reason_codes", []),
            "metrics": getattr(result, "metrics", {}),
        }

        st = payload["stage"]
        idempotency_key = (
            f"evidence:pricing_guardrail_v1:"
            f"deal:{deal_id}:stage:{st}:anchor:{anchor_version or 'none'}"
        )

        log_evidence_pack(
            db=db,
            event_type="pricing_guardrail_v1",
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except Exception:
        pass

# ------------------------------------------------------------
# D) Preview Pack에 Guardrail 요약 주입
# ------------------------------------------------------------
def attach_guardrail_to_pack(
    pack: Dict[str, Any],
    result: Any,
):
    """
    preview_pack에서 pack 완성 후 호출

    ✅ 기존: pack["pricing"]["guardrail"]에만 주입
    ✅ 개선: pricing이 없으면 pack["guardrail"]에 주입 (deal preview에서도 보이게)
    """
    if not pack or not result:
        return pack

    ui = getattr(result, "ui", None)
    if not ui:
        return pack

    level = getattr(result, "level", None)
    if level == "ALLOW":
        # ✅ ALLOW면 UI 노출 자체를 안 함 (payload 지저분해지는 것 방지)
        return pack

    guardrail_payload = {
        "level": getattr(result, "level", None),
        "reason_codes": getattr(result, "reason_codes", []),  # ✅ 추가
        "badge": ui.get("badge"),
        "short_title": ui.get("short_title"),
        "short_body": ui.get("short_body"),
    }
    
    pricing = pack.get("pricing")
    if isinstance(pricing, dict):
        pricing["guardrail"] = guardrail_payload
    else:
        # ✅ deal preview 같이 pricing 없는 pack에서도 노출 가능
        pack["guardrail"] = guardrail_payload

    return pack