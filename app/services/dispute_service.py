"""분쟁 프로세스 v4 — 구조화 제안 + AI 법적 중재 + 넛지 + 자동 연결"""
import json
import os
import traceback
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Dispute, Reservation, User
from app.services.working_days import add_working_days, working_days_left
from app.services.proposal_calculator import calculate_proposal_amount


def _safe_notify(user_id, event_type, variables, db):
    try:
        if user_id is None:
            return
        from app.services.notification_service import send_notification
        send_notification(db, user_id=user_id, event_type=event_type, variables=variables)
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 1: 분쟁 신청 (구조화 제안)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def file_dispute(data: dict, db: Session) -> dict:
    reservation = db.query(Reservation).filter(Reservation.id == data["reservation_id"]).first()
    if not reservation:
        return {"error": "예약을 찾을 수 없습니다"}

    initiator_id = data["initiator_id"]
    if initiator_id == getattr(reservation, "buyer_id", None):
        respondent_id = getattr(reservation, "seller_id", None) or 0
        initiator_role = "buyer"
    else:
        respondent_id = getattr(reservation, "buyer_id", None) or 0
        initiator_role = "seller"

    now = datetime.utcnow()
    total = getattr(reservation, "total_amount", 0) or getattr(reservation, "amount_total", 0) or 0

    # 구조화 제안 금액 계산
    amt_type = data.get("amount_type", "fixed")
    amt_value = data.get("amount_value", data.get("requested_amount", 0))
    if amt_value is None:
        amt_value = 0
    calculated = calculate_proposal_amount(amt_type, float(amt_value), total)

    dispute = Dispute(
        reservation_id=reservation.id,
        initiator_id=initiator_id,
        respondent_id=respondent_id,
        initiator_role=initiator_role,
        category=data.get("category", "기타"),
        title=data.get("title", ""),
        description=data.get("description", ""),
        evidence_urls=json.dumps(data.get("evidence", []), ensure_ascii=False),
        requested_resolution=data.get("requested_resolution", "full_refund"),
        requested_amount=calculated,
        status="ROUND1_RESPONSE",
        current_round=1,
        r1_respondent_deadline=add_working_days(now, 3),
        # 구조화 제안
        initiator_amount_type=amt_type,
        initiator_amount_value=float(amt_value),
        initiator_amount_calculated=calculated,
        initiator_shipping_burden=data.get("shipping_burden", "seller"),
        initiator_return_required=data.get("return_required", True),
    )
    db.add(dispute)

    # 정산 보류
    if hasattr(reservation, "settlement_status"):
        reservation.settlement_status = "DISPUTE_HOLD"

    db.commit()
    db.refresh(dispute)

    return {
        "dispute_id": dispute.id,
        "status": dispute.status,
        "respondent_deadline": str(dispute.r1_respondent_deadline),
        "calculated_amount": calculated,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 2: Round 1 — 반론 + 구조화 제안
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def submit_round1_response(dispute_id: int, data: dict, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute or dispute.status != "ROUND1_RESPONSE":
        return {"error": "현재 Round 1 반론 단계가 아닙니다"}
    if datetime.utcnow() > dispute.r1_respondent_deadline:
        return {"error": "반론 기한이 만료되었습니다"}

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    total = getattr(reservation, "total_amount", 0) or getattr(reservation, "amount_total", 0) or 0

    # 구조화 제안 금액 계산
    amt_type = data.get("amount_type", "fixed")
    amt_value = data.get("amount_value", data.get("proposal_amount", 0))
    if amt_value is None:
        amt_value = 0
    calculated = calculate_proposal_amount(amt_type, float(amt_value), total)

    now = datetime.utcnow()
    dispute.r1_respondent_reply = data.get("reply", "")
    dispute.r1_respondent_evidence_urls = json.dumps(data.get("evidence", []), ensure_ascii=False)
    dispute.r1_respondent_proposal_type = data.get("proposal_type", "partial_refund")
    dispute.r1_respondent_proposal_amount = calculated
    dispute.r1_respondent_proposal_text = data.get("reasoning", data.get("proposal_text", ""))
    dispute.r1_respondent_at = now

    # 구조화 추가
    dispute.r1_respondent_amount_type = amt_type
    dispute.r1_respondent_amount_value = float(amt_value)
    dispute.r1_respondent_amount_calculated = calculated
    dispute.r1_respondent_shipping_burden = data.get("shipping_burden", "buyer")
    dispute.r1_respondent_return_required = data.get("return_required", False)

    dispute.status = "ROUND1_AI"
    db.commit()

    return run_ai_mediation(dispute_id, round_num=1, db=db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 3: AI 중재 (법적 기준 + 넛지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_ai_mediation(dispute_id: int, round_num: int, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        return {"error": "분쟁을 찾을 수 없습니다"}

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    total = getattr(reservation, "total_amount", 0) or getattr(reservation, "amount_total", 0) or 0
    shipping_fee = getattr(reservation, "shipping_fee", 0) or getattr(reservation, "amount_shipping", 0) or 0

    # 컨텍스트 구성
    context = f"""분쟁 정보:
카테고리: {dispute.category}
결제 금액: {total:,}원 (상품 {total - shipping_fee:,}원 + 배송비 {shipping_fee:,}원)
배송 상태: {getattr(reservation, 'delivery_status', 'delivered')}

[신청자 ({dispute.initiator_role})]
요청: {dispute.requested_resolution}
금액: {dispute.requested_amount or 0:,}원 ({dispute.initiator_amount_type or 'fixed'}: {dispute.initiator_amount_value or 0})
배송비 부담: {dispute.initiator_shipping_burden or 'seller'}
반품 요구: {dispute.initiator_return_required}
사유: {dispute.description}

[상대방 반론+제안]
반론: {dispute.r1_respondent_reply or '(미제출)'}
제안: {dispute.r1_respondent_proposal_type} / {dispute.r1_respondent_proposal_amount or 0}원
금액 방식: {dispute.r1_respondent_amount_type or 'fixed'}: {dispute.r1_respondent_amount_value or 0}
배송비 부담: {dispute.r1_respondent_shipping_burden or '미지정'}
반품: {dispute.r1_respondent_return_required}
사유: {dispute.r1_respondent_proposal_text or ''}"""

    if round_num == 2:
        context += f"""

[Round 1 AI 중재 결과]
추천: {dispute.r1_ai_recommendation} / {dispute.r1_ai_recommendation_amount}원
의견: {dispute.r1_ai_opinion}

[Round 1 결과]
신청자: {dispute.r1_initiator_decision} / 상대방: {dispute.r1_respondent_decision}

[Round 2 재반론]
신청자: {dispute.r2_initiator_rebuttal or '(없음)'} / 제안: {dispute.r2_initiator_proposal_type} {dispute.r2_initiator_proposal_amount or 0}원
상대방: {dispute.r2_respondent_rebuttal or '(없음)'} / 제안: {dispute.r2_respondent_proposal_type} {dispute.r2_respondent_proposal_amount or 0}원"""

    system_prompt = f"""당신은 역핑 플랫폼의 분쟁 중재 AI입니다.
양쪽 주장과 증거를 공정하게 분석하고, 양쪽 모두 수용 가능한 합리적 해결책을 제안하세요.

━━━ 업계 표준 규칙 (반드시 준수) ━━━

1. 전자상거래법 제17조:
   - 수령 후 7일 내: 단순 변심 청약철회 가능
   - 판매자 귀책(불량/오배송/설명과다름): 수령 후 3개월 이내 가능
   - 소비자에게 불리한 규정은 무효

2. 환불 금액 절대 규칙:
   - 환불 금액 ≤ 결제 금액 ({total:,}원) — 절대 초과 불가!
   - 보상금도 결제 금액 이하

3. 배송비 부담:
   - 단순 변심: 구매자가 왕복 배송비 부담
   - 판매자 귀책: 판매자가 전부 부담
   - 양측 귀책: 각자 부담 (반반)

4. 감가:
   - 미개봉: 감가 불가
   - 개봉+미사용: 소폭 감가 가능 (5~10%)
   - 사용 흔적: 감가 가능 (10~30%)
   - 심한 훼손: 최대 50% (그 이상은 환불 거절 사유)

5. 반품:
   - 전액/부분 환불: 배송 후 상품이면 반품 필요
   - 미배송: 반품 불필요
   - 소액 보상 (결제금액의 10% 이하): 반품 없이 보상 가능

━━━ 중재 원칙 ━━━

1. 양쪽의 불편함과 입장을 모두 인정하고 공감
2. 판단 근거를 법적 기준으로 명확히 설명
3. 신청자에게: 왜 이 제안이 최선인지 + 불편함 인정
4. 상대방에게: 왜 이 금액이 합리적인지 + 수용 시 이점
5. Round 2라면 1차 결과와 거절 사유를 참고하여 더 정밀한 제안

━━━ 넛지 메시지 (빨리 끝내야 이익) ━━━

구매자 넛지: 합의 시 환불 3~5영업일 / 미합의 시 +10영업일 추가
판매자 넛지: 합의 시 정산 3일 내 재개 / 미합의 시 정산 계속 보류

━━━ 응답 형식 (JSON만! 다른 텍스트 금지) ━━━

{{{{
    "recommendation_type": "full_refund" | "partial_refund" | "exchange" | "compensation" | "no_action",
    "amount_type": "fixed" | "rate",
    "amount_value": 숫자,
    "amount_calculated": 최종금액(원),
    "shipping_burden": "buyer" | "seller" | "split",
    "return_required": true | false,
    "legal_basis": "전자상거래법 제N조 + 근거 설명",
    "opinion": "종합 분석 의견 (양쪽 모두에게 공정한 톤)",
    "explanation_to_initiator": "신청자에게 — 공감 + 왜 이 제안이 최선인지",
    "explanation_to_respondent": "상대방에게 — 공감 + 왜 합리적인지",
    "nudge_buyer": "⏰ 합의 시: 환불 3~5영업일 / ⚠️ 미합의 시: 추가 10영업일+ 소요",
    "nudge_seller": "⏰ 합의 시: 정산 3일 내 재개 / ⚠️ 미합의 시: 정산 계속 보류",
    "reasoning": "판단 근거 요약"
}}}}"""

    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=20)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        result = json.loads(response.choices[0].message.content)
    except Exception as e:
        result = {
            "recommendation_type": dispute.requested_resolution or "partial_refund",
            "amount_type": "fixed",
            "amount_value": dispute.requested_amount or 0,
            "amount_calculated": dispute.requested_amount or 0,
            "shipping_burden": "seller",
            "return_required": True,
            "legal_basis": "AI 분석 실패 — 관리자 검토 필요",
            "opinion": f"AI 분석 중 오류: {str(e)}",
            "explanation_to_initiator": "AI 분석 중 오류가 발생했습니다. 관리자가 검토 예정입니다.",
            "explanation_to_respondent": "AI 분석 중 오류가 발생했습니다.",
            "nudge_buyer": "",
            "nudge_seller": "",
            "reasoning": str(e),
        }

    # 금액 검증 (결제금액 초과 방지)
    calc_amount = result.get("amount_calculated", 0) or 0
    if calc_amount > total and total > 0:
        calc_amount = total
        result["amount_calculated"] = total

    # DB 저장
    now = datetime.utcnow()
    prefix = f"r{round_num}_"

    # 기존 필드 호환
    rec_type = result.get("recommendation_type", result.get("recommendation", ""))
    setattr(dispute, f"{prefix}ai_opinion", result.get("opinion", ""))
    setattr(dispute, f"{prefix}ai_recommendation", rec_type)
    setattr(dispute, f"{prefix}ai_recommendation_amount", calc_amount)
    setattr(dispute, f"{prefix}ai_explanation",
            json.dumps({
                "to_initiator": result.get("explanation_to_initiator", ""),
                "to_respondent": result.get("explanation_to_respondent", ""),
                "reasoning": result.get("reasoning", ""),
            }, ensure_ascii=False))

    # 구조화 필드 저장
    setattr(dispute, f"{prefix}ai_amount_type", result.get("amount_type", "fixed"))
    setattr(dispute, f"{prefix}ai_amount_value", result.get("amount_value", 0))
    setattr(dispute, f"{prefix}ai_shipping_burden", result.get("shipping_burden", "buyer"))
    setattr(dispute, f"{prefix}ai_return_required", result.get("return_required", True))
    setattr(dispute, f"{prefix}ai_legal_basis", result.get("legal_basis", ""))
    setattr(dispute, f"{prefix}ai_nudge_buyer", result.get("nudge_buyer", ""))
    setattr(dispute, f"{prefix}ai_nudge_seller", result.get("nudge_seller", ""))
    setattr(dispute, f"{prefix}ai_mediated_at", now)

    # 상태 전환 + 양쪽 검토 기한
    dispute.status = f"ROUND{round_num}_REVIEW"
    review_deadline = add_working_days(now, 1)
    setattr(dispute, f"r{round_num}_initiator_deadline", review_deadline)
    if round_num == 1:
        dispute.r1_respondent_review_deadline = review_deadline
    else:
        dispute.r2_respondent_deadline = review_deadline

    db.commit()

    # 알림 (넛지 포함)
    _safe_notify(dispute.initiator_id, "DISPUTE_AI_MEDIATION", {
        "nudge": result.get("nudge_buyer", ""),
        "dispute_id": dispute.id,
    }, db)
    _safe_notify(dispute.respondent_id, "S_DISPUTE_AI_MEDIATION", {
        "nudge": result.get("nudge_seller", ""),
        "dispute_id": dispute.id,
    }, db)

    return {"status": dispute.status, "ai_recommendation": result}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 4: 양쪽 승인/거절
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def submit_decision(dispute_id: int, user_id: int, decision: str, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        return {"error": "분쟁을 찾을 수 없습니다"}

    if dispute.status not in ("ROUND1_REVIEW", "ROUND2_REVIEW"):
        return {"error": "현재 결정 단계가 아닙니다"}

    round_num = dispute.current_round
    prefix = f"r{round_num}_"
    now = datetime.utcnow()

    if user_id == dispute.initiator_id:
        setattr(dispute, f"{prefix}initiator_decision", decision)
        setattr(dispute, f"{prefix}initiator_decision_at", now)
    elif user_id == dispute.respondent_id:
        setattr(dispute, f"{prefix}respondent_decision", decision)
        setattr(dispute, f"{prefix}respondent_decision_at", now)
    else:
        return {"error": "분쟁 당사자가 아닙니다"}

    db.commit()

    init_dec = getattr(dispute, f"{prefix}initiator_decision")
    resp_dec = getattr(dispute, f"{prefix}respondent_decision")

    if init_dec and resp_dec:
        return evaluate_round_result(dispute_id, round_num, db)

    who = "신청인" if user_id == dispute.initiator_id else "상대방"
    return {"status": dispute.status, "message": f"{who} 결정 완료. 상대방 결정 대기 중."}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 4b: 라운드 결과 판정 + 채택 결정 + 자동 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def evaluate_round_result(dispute_id: int, round_num: int, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    prefix = f"r{round_num}_"

    init_dec = getattr(dispute, f"{prefix}initiator_decision")
    resp_dec = getattr(dispute, f"{prefix}respondent_decision")
    now = datetime.utcnow()

    if init_dec == "accept" and resp_dec == "accept":
        # ★ 채택된 제안 결정 ★
        accepted = determine_accepted_proposal(dispute, round_num)

        dispute.accepted_proposal_source = accepted["source"]
        dispute.accepted_proposal_type = accepted["type"]
        dispute.accepted_amount = accepted["amount"]
        dispute.accepted_shipping_burden = accepted["shipping_burden"]
        dispute.accepted_return_required = accepted["return_required"]

        dispute.status = "ACCEPTED"
        dispute.closed_at = now
        dispute.closed_reason = f"accepted_round{round_num}"
        dispute.resolution_amount = accepted["amount"]
        dispute.resolution = getattr(dispute, f"{prefix}ai_opinion")
        db.commit()

        # ★ 구조화된 데이터로 후속 처리 ★
        try:
            from app.services.resolution_executor import execute_dispute_resolution_structured
            return execute_dispute_resolution_structured(dispute_id, accepted, db)
        except Exception:
            # fallback to old path
            try:
                from app.services.resolution_executor import execute_dispute_resolution
                execute_dispute_resolution(dispute_id, db)
            except Exception:
                pass
        return {
            "status": "ACCEPTED",
            "accepted_proposal": accepted,
            "resolution_amount": dispute.resolution_amount,
            "message": f"Round {round_num}에서 합의 완료!",
        }

    if round_num == 2:
        dispute.status = "REJECTED"
        dispute.closed_at = now
        dispute.closed_reason = "rejected_legal"
        dispute.legal_guidance_sent = True
        dispute.legal_guidance_sent_at = now
        db.commit()
        # ★ LEGAL_HOLD + 관리자 에스컬레이션
        try:
            from app.services.resolution_executor import handle_rejected_dispute
            handle_rejected_dispute(dispute_id, db)
        except Exception:
            pass
        return {"status": "REJECTED", "message": "2차 중재 미합의. 정산 보류 + 법적 안내."}

    rejecters = []
    if init_dec == "reject":
        rejecters.append("initiator")
    if resp_dec == "reject":
        rejecters.append("respondent")

    dispute.current_round = 2
    dispute.status = "ROUND2_RESPONSE"
    dispute.r2_rebuttal_by = ",".join(rejecters)
    dispute.r2_rebuttal_deadline = add_working_days(now, 2)
    db.commit()

    return {
        "status": "ROUND2_RESPONSE",
        "rejecters": rejecters,
        "deadline": str(dispute.r2_rebuttal_deadline),
    }


def determine_accepted_proposal(dispute, round_num: int) -> dict:
    """양쪽 모두 accept → 어떤 제안이 채택되었는지 결정"""
    prefix = f"r{round_num}_"

    ai_type = getattr(dispute, f"{prefix}ai_recommendation", None)
    ai_amount = getattr(dispute, f"{prefix}ai_recommendation_amount", 0)
    ai_shipping = getattr(dispute, f"{prefix}ai_shipping_burden", "buyer")
    ai_return = getattr(dispute, f"{prefix}ai_return_required", True)

    if ai_type:
        return {
            "source": "ai",
            "type": _map_to_resolution_type(ai_type),
            "amount": ai_amount or 0,
            "shipping_burden": ai_shipping or "buyer",
            "return_required": ai_return if ai_return is not None else True,
        }

    # AI 없으면 → 상대방 제안 기준
    if round_num == 1:
        resp_type = dispute.r1_respondent_proposal_type
        resp_amount = dispute.r1_respondent_proposal_amount
        resp_shipping = dispute.r1_respondent_shipping_burden
        resp_return = dispute.r1_respondent_return_required
    else:
        resp_type = dispute.r2_respondent_proposal_type
        resp_amount = dispute.r2_respondent_proposal_amount
        resp_shipping = dispute.r2_respondent_shipping_burden
        resp_return = dispute.r2_respondent_return_required

    return {
        "source": "respondent",
        "type": _map_to_resolution_type(resp_type or "partial_refund"),
        "amount": resp_amount or 0,
        "shipping_burden": resp_shipping or "buyer",
        "return_required": resp_return if resp_return is not None else True,
    }


def _map_to_resolution_type(ai_type: str) -> str:
    mapping = {
        "full_refund": "FULL_REFUND",
        "partial_refund": "PARTIAL_REFUND",
        "exchange": "EXCHANGE",
        "compensation": "COMPENSATION",
        "no_action": "NO_ACTION",
        "accept_proposal": "FULL_REFUND",
        "modified_proposal": "PARTIAL_REFUND",
    }
    return mapping.get(ai_type, "PARTIAL_REFUND")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 5: Round 2 — 재반론 + 구조화 제안
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def submit_round2_rebuttal(dispute_id: int, user_id: int, data: dict, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute or dispute.status != "ROUND2_RESPONSE":
        return {"error": "현재 Round 2 재반론 단계가 아닙니다"}
    if datetime.utcnow() > dispute.r2_rebuttal_deadline:
        return {"error": "재반론 기한이 만료되었습니다"}

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    total = getattr(reservation, "total_amount", 0) or getattr(reservation, "amount_total", 0) or 0

    amt_type = data.get("amount_type", "fixed")
    amt_value = data.get("amount_value", data.get("proposal_amount", 0))
    if amt_value is None:
        amt_value = 0
    calculated = calculate_proposal_amount(amt_type, float(amt_value), total)

    now = datetime.utcnow()

    if user_id == dispute.initiator_id:
        dispute.r2_initiator_rebuttal = data.get("rebuttal", "")
        dispute.r2_initiator_evidence_urls = json.dumps(data.get("evidence", []), ensure_ascii=False)
        dispute.r2_initiator_proposal_type = data.get("proposal_type")
        dispute.r2_initiator_proposal_amount = calculated
        dispute.r2_initiator_amount_type = amt_type
        dispute.r2_initiator_amount_value = float(amt_value)
        dispute.r2_initiator_amount_calculated = calculated
        dispute.r2_initiator_shipping_burden = data.get("shipping_burden")
        dispute.r2_initiator_return_required = data.get("return_required")
    elif user_id == dispute.respondent_id:
        dispute.r2_respondent_rebuttal = data.get("rebuttal", "")
        dispute.r2_respondent_evidence_urls = json.dumps(data.get("evidence", []), ensure_ascii=False)
        dispute.r2_respondent_proposal_type = data.get("proposal_type")
        dispute.r2_respondent_proposal_amount = calculated
        dispute.r2_respondent_amount_type = amt_type
        dispute.r2_respondent_amount_value = float(amt_value)
        dispute.r2_respondent_amount_calculated = calculated
        dispute.r2_respondent_shipping_burden = data.get("shipping_burden")
        dispute.r2_respondent_return_required = data.get("return_required")

    dispute.r2_rebuttal_at = now
    db.commit()

    rejecters = (dispute.r2_rebuttal_by or "").split(",")
    all_submitted = True
    if "initiator" in rejecters and not dispute.r2_initiator_rebuttal:
        all_submitted = False
    if "respondent" in rejecters and not dispute.r2_respondent_rebuttal:
        all_submitted = False

    if all_submitted:
        dispute.status = "ROUND2_AI"
        db.commit()
        return run_ai_mediation(dispute_id, round_num=2, db=db)

    return {"status": "ROUND2_RESPONSE", "message": "제출 완료. 상대방 제출 대기."}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 타임아웃 배치
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_dispute_timeout_batch(db: Session) -> dict:
    now = datetime.utcnow()
    auto_closed = 0
    warnings_sent = 0

    timeout_checks = [
        ("ROUND1_RESPONSE", "r1_respondent_deadline", "auto_closed_r1_response"),
        ("ROUND1_REVIEW", "r1_initiator_deadline", "auto_closed_r1_review"),
        ("ROUND2_RESPONSE", "r2_rebuttal_deadline", "auto_closed_r2_rebuttal"),
        ("ROUND2_REVIEW", "r2_initiator_deadline", "auto_closed_r2_review"),
    ]

    for status, deadline_field, close_reason in timeout_checks:
        disputes = db.query(Dispute).filter(Dispute.status == status).all()

        for d in disputes:
            deadline = getattr(d, deadline_field)
            if not deadline:
                continue

            days_left = working_days_left(deadline)

            if days_left == 1 and not d.timeout_warned:
                d.timeout_warned = True
                warnings_sent += 1
                # 기한 1일 전 경고 알림 발송
                _safe_notify(d.initiator_id, "DISPUTE_TIMEOUT_WARNING", {
                    "dispute_id": d.id, "deadline": str(deadline), "days_left": 1,
                }, db)
                _safe_notify(d.respondent_id, "DISPUTE_TIMEOUT_WARNING", {
                    "dispute_id": d.id, "deadline": str(deadline), "days_left": 1,
                }, db)

            if now > deadline:
                d.status = "AUTO_CLOSED"
                d.closed_at = now
                d.closed_reason = close_reason
                auto_closed += 1

    if auto_closed or warnings_sent:
        db.commit()

    return {"auto_closed": auto_closed, "warnings_sent": warnings_sent}
