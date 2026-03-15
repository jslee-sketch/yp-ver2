"""
환불 비용 계산 엔진 — 12가지 시나리오 완전 커버

비용 부담 매트릭스:
┌──────────────┬───────┬──────────┬──────────┬──────┬────────────┐
│ 사유         │ 귀책  │ 왕배송비 │ 반품배송 │ 감가 │ 수수료환급 │
├──────────────┼───────┼──────────┼──────────┼──────┼────────────┤
│ 변심         │ buyer │ 구매자※  │ 구매자   │검수  │ 환급(특혜) │
│ 불량/오배송  │seller │ 0        │ 판매자   │ 0   │ 환급       │
│ 파손(배송중) │seller │ 0        │ 판매자   │ 0   │ 환급       │
│ 미배송       │seller │ 해당없음 │ 해당없음 │ 0   │ 환급       │
│ 설명과다름   │seller │ 0        │ 판매자   │ 0   │ 환급       │
│ 분쟁합의     │ 합의  │ 합의     │ 합의     │합의 │ 비례환급   │
└──────────────┴───────┴──────────┴──────────┴──────┴────────────┘
※ 무료배송: 왕복(원복+반품), 유료배송: 편도(반품만), 조건부: 왕복
"""
import os
from pathlib import Path
import yaml

BUYER_FAULT_REASONS = ["buyer_change_mind"]
SELLER_FAULT_REASONS = ["defective", "wrong_item", "damaged", "not_delivered", "description_mismatch"]


def _load_raw_policy() -> dict:
    """defaults.yaml을 raw dict으로 로드 (PolicyBundle에 없는 섹션 접근용)"""
    path = os.environ.get("POLICY_YAML_PATH")
    if not path:
        path = str(Path(__file__).resolve().parent.parent / "policy" / "params" / "defaults.yaml")
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def determine_fault(reason: str) -> str:
    if reason in BUYER_FAULT_REASONS:
        return "buyer"
    elif reason in SELLER_FAULT_REASONS:
        return "seller"
    return "buyer"


def calculate_refund(
    original_amount: int,
    shipping_fee: int = 0,
    shipping_mode: str = "free",
    reason: str = "buyer_change_mind",
    delivery_status: str = "delivered",
    days_since_delivery: int = 0,
    inspection_deduction_rate: float = 0.0,
    dispute_agreed_amount: int = None,
    resolution_type: str = None,
    role: str = "buyer",
) -> dict:
    """모든 경우의 수 환불 계산"""
    raw = _load_raw_policy()
    rp = raw.get("refund", {})
    sp = raw.get("settlement", {})
    mp = raw.get("money", {})

    cooling_days = rp.get("cooling_period_days", 7)
    seller_fault_cooling = rp.get("seller_fault_cooling_days", 90)
    default_return_ship = rp.get("default_return_shipping_cost", 3000)
    max_deduction = rp.get("max_inspection_deduction_rate", 0.5)
    minor_threshold = rp.get("minor_compensation_threshold_rate", 0.1)
    fee_rate = mp.get("platform_fee_rate", 0.035)

    total_paid = original_amount + shipping_fee
    fault = determine_fault(reason)

    # ── 환불 가능 여부 ──
    can_refund = True
    blocked_reason = None

    if delivery_status == "delivered":
        if fault == "buyer" and days_since_delivery > cooling_days:
            can_refund = False
            blocked_reason = f"수령 후 {cooling_days}일 초과 (단순 변심)"
        elif fault == "seller" and days_since_delivery > seller_fault_cooling:
            can_refund = False
            blocked_reason = f"수령 후 {seller_fault_cooling}일 초과 (판매자 귀책도 {seller_fault_cooling}일 한도)"

    # ── 반품 필요 여부 ──
    return_required = False
    if delivery_status in ("in_transit", "delivered") and reason != "not_delivered":
        if resolution_type != "COMPENSATION":
            return_required = True
    if resolution_type == "EXCHANGE":
        return_required = True

    # ── 소액 보상 판정: 결제금액의 10% 이하 → 반품 면제 ──
    if dispute_agreed_amount is not None and total_paid > 0:
        if dispute_agreed_amount <= int(total_paid * minor_threshold):
            if resolution_type in ("PARTIAL_REFUND", "COMPENSATION", None):
                return_required = False

    # ── 시나리오별 비용 계산 ──
    deductions = []
    return_shipping_cost = 0
    original_shipping_deduction = 0
    usage_deduction_val = 0
    shipping_payer = "none"
    buyer_refund = 0

    # ━━━ 시나리오 1: 배송 전 취소 ━━━
    if delivery_status == "before_shipping":
        buyer_refund = total_paid
        return_required = False

    # ━━━ 시나리오 6: 미배송 ━━━
    elif reason == "not_delivered":
        buyer_refund = total_paid
        return_required = False

    # ━━━ 시나리오 5,7: 판매자 귀책 ━━━
    elif fault == "seller" and dispute_agreed_amount is None and resolution_type not in ("PARTIAL_REFUND", "EXCHANGE", "COMPENSATION"):
        buyer_refund = total_paid
        shipping_payer = "seller"
        if return_required:
            deductions.append({
                "type": "반품 배송비",
                "amount": 0,
                "note": "판매자 귀책 — 반품 배송비 판매자 부담"
            })

    # ━━━ 시나리오 8: 분쟁 합의 전액환불 ━━━
    elif dispute_agreed_amount is not None and resolution_type == "FULL_REFUND":
        if fault == "seller":
            buyer_refund = total_paid
            shipping_payer = "seller"
        else:
            if shipping_mode == "free":
                original_shipping_deduction = default_return_ship
                return_shipping_cost = default_return_ship
                shipping_payer = "buyer"
                buyer_refund = total_paid - original_shipping_deduction - return_shipping_cost
            elif shipping_mode == "buyer_paid":
                return_shipping_cost = default_return_ship
                shipping_payer = "buyer"
                buyer_refund = original_amount - return_shipping_cost
            else:
                original_shipping_deduction = default_return_ship
                return_shipping_cost = default_return_ship
                shipping_payer = "buyer"
                buyer_refund = total_paid - original_shipping_deduction - return_shipping_cost

    # ━━━ 시나리오 9: 분쟁 합의 부분환불 ━━━
    elif dispute_agreed_amount is not None and resolution_type == "PARTIAL_REFUND":
        buyer_refund = dispute_agreed_amount
        return_required = False

    # ━━━ 시나리오 10: 분쟁 합의 교환 ━━━
    elif resolution_type == "EXCHANGE":
        buyer_refund = 0
        if fault == "seller":
            shipping_payer = "seller"
        else:
            return_shipping_cost = default_return_ship
            shipping_payer = "buyer"

    # ━━━ 시나리오 11: 분쟁 합의 보상금 ━━━
    elif resolution_type == "COMPENSATION":
        buyer_refund = dispute_agreed_amount or 0
        return_required = False

    # ━━━ 시나리오 2: 변심 + 무료배송 + 배송후 ━━━
    elif fault == "buyer" and shipping_mode == "free":
        original_shipping_deduction = default_return_ship
        return_shipping_cost = default_return_ship
        shipping_payer = "buyer"
        deductions.append({
            "type": "왕복 배송비 (무료배송 원복 + 반품)",
            "amount": original_shipping_deduction + return_shipping_cost,
            "note": f"무료배송 원복 {default_return_ship:,}원 + 반품 {default_return_ship:,}원"
        })
        base = total_paid - original_shipping_deduction - return_shipping_cost

        rate = min(inspection_deduction_rate, max_deduction)
        if rate > 0:
            usage_deduction_val = int(original_amount * rate)
            deductions.append({
                "type": f"사용 감가 ({rate*100:.0f}%)",
                "amount": usage_deduction_val,
                "note": "판매자 검수 결과"
            })
        buyer_refund = max(0, base - usage_deduction_val)

    # ━━━ 시나리오 3: 변심 + 유료배송 + 배송후 ━━━
    elif fault == "buyer" and shipping_mode == "buyer_paid":
        return_shipping_cost = default_return_ship
        shipping_payer = "buyer"
        deductions.append({
            "type": "반품 배송비 (편도)",
            "amount": return_shipping_cost,
            "note": "유료배송 상품 — 반품 배송비만 부담"
        })
        if shipping_fee > 0:
            deductions.append({
                "type": "원래 배송비 환불 불가",
                "amount": shipping_fee,
                "note": "유료배송 상품의 원래 배송비는 환불 불가"
            })
        base = original_amount - return_shipping_cost

        rate = min(inspection_deduction_rate, max_deduction)
        if rate > 0:
            usage_deduction_val = int(original_amount * rate)
            deductions.append({
                "type": f"사용 감가 ({rate*100:.0f}%)",
                "amount": usage_deduction_val,
            })
        buyer_refund = max(0, base - usage_deduction_val)

    # ━━━ 시나리오 4: 변심 + 조건부무료배송 ━━━
    elif fault == "buyer" and shipping_mode == "conditional_free":
        original_shipping_deduction = default_return_ship
        return_shipping_cost = default_return_ship
        shipping_payer = "buyer"
        deductions.append({
            "type": "왕복 배송비 (조건부 무료배송 원복 + 반품)",
            "amount": original_shipping_deduction + return_shipping_cost,
        })
        base = total_paid - original_shipping_deduction - return_shipping_cost
        rate = min(inspection_deduction_rate, max_deduction)
        if rate > 0:
            usage_deduction_val = int(original_amount * rate)
            deductions.append({"type": f"사용 감가 ({rate*100:.0f}%)", "amount": usage_deduction_val})
        buyer_refund = max(0, base - usage_deduction_val)

    # ━━━ 기타 (fallback) ━━━
    else:
        buyer_refund = total_paid

    buyer_refund = max(0, buyer_refund) if can_refund else 0
    total_deduction = return_shipping_cost + original_shipping_deduction + usage_deduction_val

    # ── 판매자 정산 영향 ──
    seller_original = int(original_amount * (1 - fee_rate))
    if buyer_refund >= total_paid:
        seller_new = 0
    elif buyer_refund > 0:
        remaining_product = original_amount - buyer_refund + (shipping_fee if shipping_mode == "buyer_paid" and fault == "buyer" else 0)
        remaining_product = max(0, min(remaining_product, original_amount))
        seller_new = int(remaining_product * (1 - fee_rate))
    else:
        seller_new = seller_original

    seller_deduction = seller_original - seller_new
    seller_return_burden = default_return_ship if (fault == "seller" and return_required) else 0
    fee_refund = int(buyer_refund * fee_rate) if buyer_refund > 0 else 0

    result = {
        "can_refund": can_refund,
        "blocked_reason": blocked_reason,
        "fault": fault,
        "return_required": return_required,

        "original_amount": original_amount,
        "shipping_fee": shipping_fee,
        "total_paid": total_paid,
        "shipping_mode": shipping_mode,
        "delivery_status": delivery_status,
        "reason": reason,
        "resolution_type": resolution_type,

        "deductions": deductions,
        "total_deduction": total_deduction,
        "buyer_refund_amount": buyer_refund,
        "shipping_payer": shipping_payer,
        "usage_deduction": usage_deduction_val,
        "usage_deduction_rate": inspection_deduction_rate,

        "cooling_period_days": cooling_days,
        "days_since_delivery": days_since_delivery,
    }

    if role in ("seller", "admin"):
        result["settlement_impact"] = {
            "before": seller_original,
            "after": seller_new if can_refund else seller_original,
            "loss": seller_deduction if can_refund else 0,
            "return_shipping_burden": seller_return_burden,
            "platform_fee_refund": fee_refund,
            "fee_rate": fee_rate,
            "note": "역핑 특혜: 환불 시 플랫폼 수수료도 판매자에게 환급"
        }

    if role == "admin":
        result["pg_note"] = "카드 취소: PG 수수료 자동 환급. 가상계좌/계좌이체: 플랫폼 흡수."

    return result
