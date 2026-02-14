# app/policy/target_vs_anchor_guardrail.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# Types
# -------------------------
Level = str  # "ALLOW" | "WARN_SOFT" | "WARN_HARD" | "BLOCK"


@dataclass(frozen=True)
class PriceAxisEvaluationInput:
    deal_id: int
    category: Optional[str]
    target_price: Optional[float]
    anchor_price: Optional[float]
    evidence_score: Optional[int] = None          # 0~100
    anchor_confidence: Optional[float] = None     # 0~1
    now_ts: Optional[datetime] = None


@dataclass(frozen=True)
class PriceAxisEvaluationResult:
    level: Level
    reason_codes: List[str]
    metrics: Dict[str, Any]
    ui: Dict[str, Any]
    ops: Dict[str, Any]


# -------------------------
# Helpers
# -------------------------
def _clamp_int(x: Optional[int], lo: int, hi: int, default: int) -> int:
    try:
        if x is None:
            return default
        return max(lo, min(hi, int(x)))
    except Exception:
        return default


def _clamp_float(x: Optional[float], lo: float, hi: float, default: float) -> float:
    try:
        if x is None:
            return default
        v = float(x)
        return max(lo, min(hi, v))
    except Exception:
        return default


def _level_rank(level: Level) -> int:
    order = {"ALLOW": 0, "WARN_SOFT": 1, "WARN_HARD": 2, "BLOCK": 3}
    return order.get(level, 0)


def _rank_to_level(rank: int) -> Level:
    inv = {0: "ALLOW", 1: "WARN_SOFT", 2: "WARN_HARD", 3: "BLOCK"}
    return inv.get(max(0, min(3, int(rank))), "ALLOW")


def _relax_one(level: Level, block_floor: Level = "WARN_HARD") -> Level:
    # 완화는 1단계만. BLOCK은 WARN_HARD까지만.
    if level == "BLOCK":
        return block_floor
    return _rank_to_level(_level_rank(level) - 1)


def _tighten_one(level: Level) -> Level:
    return _rank_to_level(_level_rank(level) + 1)


def _get_thresholds(params: Dict[str, Any], category: Optional[str]) -> Dict[str, float]:
    g = (((params.get("guardrails") or {}).get("target_vs_anchor") or {}))
    base = (g.get("thresholds") or {})
    overrides = (g.get("category_overrides") or {})
    cat = (category or "default").strip() or "default"
    ov = (overrides.get(cat) or overrides.get("default") or {})

    def pick(key: str, default: float) -> float:
        v = ov.get(key, base.get(key, default))
        try:
            return float(v)
        except Exception:
            return float(default)

    return {
        "soft_warn": pick("soft_warn", 0.15),
        "hard_warn": pick("hard_warn", 0.25),
        "block": pick("block", 0.40),
    }


def _get_adjust_params(params: Dict[str, Any]) -> Tuple[int, int, float]:
    g = (((params.get("guardrails") or {}).get("target_vs_anchor") or {}))
    ev = (g.get("evidence_adjust") or {})
    ac = (g.get("anchor_confidence_adjust") or {})

    relax_if = _clamp_int(ev.get("relax_if_e_score_ge"), 0, 100, 80)
    tighten_if = _clamp_int(ev.get("tighten_if_e_score_le"), 0, 100, 20)
    relax_conf_lt = _clamp_float(ac.get("relax_if_conf_lt"), 0.0, 1.0, 0.5)
    return relax_if, tighten_if, relax_conf_lt


def _ui_for(level: Level, *, anchor_missing: bool, reasons: list[str] | None = None) -> dict:
    reasons = reasons or []

    # ✅ 1) TARGET_INVALID는 anchor_missing보다 우선해서 보여준다 (SSOT UX)
    if "TARGET_INVALID" in reasons:
        return {
            "badge": "HARD" if level in ("WARN_HARD", "BLOCK") else "SOFT",
            "short_title": "목표가 확인",
            "short_body": "목표가가 0원 이하로 입력됐어요. 목표가를 수정해 주세요.",
            "cta": "ADJUST_TARGET",
        }

    # ✅ 2) Anchor missing일 때 기본 문구
    if anchor_missing:
        if level == "WARN_HARD":
            return {
                "badge": "HARD",
                "short_title": "근거 필요",
                "short_body": "외부 기준가가 아직 없어요. 근거를 추가하면 정확도가 올라갑니다.",
                "cta": "ADD_EVIDENCE",
            }
        return {"badge": "NONE", "short_title": "", "short_body": "", "cta": "NONE"}

    # ✅ 3) Anchor present일 때 레벨별 기본 문구
    if level == "BLOCK":
        return {
            "badge": "BLOCK",
            "short_title": "목표가 조정 필요",
            "short_body": "외부 기준가 대비 괴리가 너무 큽니다. 목표가 조정 또는 근거 보강이 필요해요.",
            "cta": "LOCKED",
        }
    if level == "WARN_HARD":
        return {
            "badge": "HARD",
            "short_title": "목표가 재확인 필요",
            "short_body": "외부 기준가 대비 차이가 큽니다. 근거 추가 또는 목표가 조정이 필요해요.",
            "cta": "ADD_EVIDENCE",
        }
    if level == "WARN_SOFT":
        return {
            "badge": "SOFT",
            "short_title": "목표가 확인",
            "short_body": "외부 기준가와 차이가 있을 수 있어요.",
            "cta": "NONE",
        }
    return {"badge": "NONE", "short_title": "", "short_body": "", "cta": "NONE"}


def evaluate_target_vs_anchor(params: Dict[str, Any], inp: PriceAxisEvaluationInput) -> PriceAxisEvaluationResult:
    """
    SSOT: docs/admin/ssot/target_vs_anchor_gap_ssot_v1.md
    - Anchor 없으면 기본 ALLOW(단 evidence/target 이상이면 WARN_HARD)
    - Anchor 있으면 gap로 base level 결정 후 evidence/confidence 보정
    - 출력은 level + reason_codes + metrics/ui/ops로 고정
    """
    now_ts = inp.now_ts or datetime.utcnow()
    evidence_score = _clamp_int(inp.evidence_score, 0, 100, 0)
    anchor_conf = _clamp_float(inp.anchor_confidence, 0.0, 1.0, 1.0)

    thresholds = _get_thresholds(params, inp.category)
    soft_warn = float(thresholds["soft_warn"])
    hard_warn = float(thresholds["hard_warn"])
    block = float(thresholds["block"])

    relax_if, tighten_if, relax_conf_lt = _get_adjust_params(params)

    reason: List[str] = []
    target = None if inp.target_price is None else float(inp.target_price)
    anchor = None if inp.anchor_price is None else float(inp.anchor_price)

    # -------------------------
    # Anchor missing
    # -------------------------
    if anchor is None:
        reason.append("ANCHOR_MISSING")
        if target is None:
            reason.append("TARGET_MISSING")
            level: Level = "ALLOW"
        else:
            if target <= 0:
                level = "WARN_HARD"
                reason.append("TARGET_INVALID")
            elif evidence_score <= 0:
                level = "WARN_HARD"
                reason.append("EVIDENCE_MISSING")
            elif evidence_score <= 20:
                level = "WARN_HARD"
                reason.append("EVIDENCE_LOW")
            else:
                level = "ALLOW"

        return PriceAxisEvaluationResult(
            level=level,
            reason_codes=reason,
            metrics={
                "target": target,
                "anchor": anchor,
                "gap": None,
                "abs_diff": None,
                "thresholds": thresholds,
                "evidence_score": evidence_score,
                "anchor_confidence": anchor_conf,
                "now_ts": now_ts.isoformat(),
            },
            ui=_ui_for(level, anchor_missing=True, reasons=reason), 
            ops={
                "deal_state_action": "NOOP" if level in ("ALLOW", "WARN_SOFT") else "MARK_NEEDS_RECONFIRM",
                "log_event": True,
            },
        )

    # -------------------------
    # Anchor present
    # -------------------------
    if anchor <= 0:
        # invalid anchor
        reason.extend(["ANCHOR_INVALID"])
        level = "WARN_HARD"
        return PriceAxisEvaluationResult(
            level=level,
            reason_codes=reason,
            metrics={
                "target": target,
                "anchor": anchor,
                "gap": None,
                "abs_diff": None,
                "thresholds": thresholds,
                "evidence_score": evidence_score,
                "anchor_confidence": anchor_conf,
                "now_ts": now_ts.isoformat(),
            },
            ui=_ui_for(level, anchor_missing=False, reasons=reason),
            ops={"deal_state_action": "MARK_NEEDS_RECONFIRM", "log_event": True},
        )

    # anchor만 있고 target이 없음: 판단은 유보(ALLOW) + 로그만
    if target is None:
        reason.extend(["TARGET_MISSING"])
        level = "ALLOW"
        return PriceAxisEvaluationResult(
            level=level,
            reason_codes=reason,
            metrics={
                "target": target,
                "anchor": anchor,
                "gap": None,
                "abs_diff": None,
                "thresholds": thresholds,
                "evidence_score": evidence_score,
                "anchor_confidence": anchor_conf,
                "now_ts": now_ts.isoformat(),
            },
            ui=_ui_for(level, anchor_missing=False, reasons=reason),
            ops={"deal_state_action": "NOOP", "log_event": True},
        )

    # ✅ target invalid (0 이하) — anchor 유무와 무관하게 최우선
    if target <= 0:
        reason.extend(["TARGET_INVALID"])
        level = "WARN_HARD"
        return PriceAxisEvaluationResult(
            level=level,
            reason_codes=reason,
            metrics={
                "target": target,
                "anchor": anchor,
                "gap": None,
                "abs_diff": None,
                "thresholds": thresholds,
                "evidence_score": evidence_score,
                "anchor_confidence": anchor_conf,
                "now_ts": now_ts.isoformat(),
            },
            ui=_ui_for(level, anchor_missing=False, reasons=reason),
            ops={"deal_state_action": "MARK_NEEDS_RECONFIRM", "log_event": True},
        )

    abs_diff = abs(target - anchor)
    gap = abs_diff / anchor

    # base level by gap
    if gap >= block:
        level = "BLOCK"
        reason.append("GAP_BLOCK")
    elif gap >= hard_warn:
        level = "WARN_HARD"
        reason.append("GAP_HARD_WARN")
    elif gap >= soft_warn:
        level = "WARN_SOFT"
        reason.append("GAP_SOFT_WARN")
    else:
        level = "ALLOW"
        reason.append("GAP_OK")


    # evidence adjust

    # ✅ BLOCK은 evidence로 완화하지 않음 (운영 안전)
    if level != "BLOCK" and evidence_score >= relax_if:
        new_level = _relax_one(level)
        if new_level != level:
            level = new_level
            reason.append("E_SCORE_RELAXED")

    elif evidence_score <= tighten_if:
        new_level = _tighten_one(level)
        if new_level != level:
            level = new_level
            reason.append("E_SCORE_TIGHTENED")

    # anchor confidence adjust (optional)
    if anchor_conf < relax_conf_lt:
        new_level = _relax_one(level)
        if new_level != level:
            level = new_level
            reason.append("ANCHOR_LOW_CONFIDENCE")

    # ops action
    if level == "BLOCK":
        action = "LOCK_TARGET"
    elif level == "WARN_HARD":
        action = "MARK_NEEDS_RECONFIRM"
    else:
        action = "NOOP"

    return PriceAxisEvaluationResult(
        level=level,
        reason_codes=reason,
        metrics={
            "target": target,
            "anchor": anchor,
            "gap": float(gap),
            "abs_diff": float(abs_diff),
            "thresholds": thresholds,
            "evidence_score": evidence_score,
            "anchor_confidence": anchor_conf,
            "now_ts": now_ts.isoformat(),
        },
        ui=_ui_for(level, anchor_missing=False, reasons=reason),
        ops={"deal_state_action": action, "log_event": True},
    )


def apply_guardrail_to_deal(db, deal, result, stage: str) -> None:
    """
    B) result.level/action에 따라 deal flags/status를 업데이트
    - needs_reconfirm
    - target_locked (또는 lock flag)
    - (S1이면 BLOCK_CREATE 처리 등)
    """
    ...

def build_guardrail_ui(result) -> dict:
    """
    C) UI badge/title/body/cta 생성 (짧게)
    """
    ...

def emit_guardrail_event(db, deal, inp, result, stage: str) -> None:
    """
    D) evidence_pack.pricing_guardrail_v1 로그/감사 이벤트 기록
    """
    ...

def run_target_vs_anchor_guardrail(db, deal, stage: str) -> None:
    """
    S1/S2/S3에서 공통으로 부르는 단일 엔트리포인트
    A -> B -> C -> D 순으로 실행
    """
    inp = ... # deal에서 target/anchor/evidence_score 구성
    result = evaluate_target_vs_anchor(inp)
    apply_guardrail_to_deal(db, deal, result, stage=stage)
    # ui는 deal에 저장할지/응답에만 쓸지 정책에 따라 선택
    emit_guardrail_event(db, deal, inp, result, stage=stage)