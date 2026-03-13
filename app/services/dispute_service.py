"""분쟁 프로세스 v3 — 2라운드 AI 중재 서비스"""
import json
import os
import traceback
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Dispute, Reservation, User
from app.services.working_days import add_working_days, working_days_left


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 1: 분쟁 신청
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
        requested_amount=data.get("requested_amount"),
        status="ROUND1_RESPONSE",
        current_round=1,
        r1_respondent_deadline=add_working_days(now, 3),
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
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 2: Round 1 — 반론 + 제안
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def submit_round1_response(dispute_id: int, data: dict, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute or dispute.status != "ROUND1_RESPONSE":
        return {"error": "현재 Round 1 반론 단계가 아닙니다"}
    if datetime.utcnow() > dispute.r1_respondent_deadline:
        return {"error": "반론 기한이 만료되었습니다"}

    now = datetime.utcnow()
    dispute.r1_respondent_reply = data.get("reply", "")
    dispute.r1_respondent_evidence_urls = json.dumps(data.get("evidence", []), ensure_ascii=False)
    dispute.r1_respondent_proposal_type = data.get("proposal_type", "partial_refund")
    dispute.r1_respondent_proposal_amount = data.get("proposal_amount")
    dispute.r1_respondent_proposal_text = data.get("proposal_text", "")
    dispute.r1_respondent_at = now
    dispute.status = "ROUND1_AI"
    db.commit()

    return run_ai_mediation(dispute_id, round_num=1, db=db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 3: AI 중재
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_ai_mediation(dispute_id: int, round_num: int, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        return {"error": "분쟁을 찾을 수 없습니다"}

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    reservation_amount = getattr(reservation, "total_amount", 0) if reservation else 0

    context = f"""분쟁 카테고리: {dispute.category}
신청인({dispute.initiator_role}): {dispute.description}
희망 해결: {dispute.requested_resolution} / {dispute.requested_amount}원
예약 금액: {reservation_amount}원

[Round 1 상대방 반론]
{dispute.r1_respondent_reply or '(미제출)'}
[Round 1 상대방 제안]
유형: {dispute.r1_respondent_proposal_type} / 금액: {dispute.r1_respondent_proposal_amount}원
{dispute.r1_respondent_proposal_text or ''}"""

    if round_num == 2:
        context += f"""

[Round 1 AI 중재 결과]
{dispute.r1_ai_opinion}
추천: {dispute.r1_ai_recommendation} / {dispute.r1_ai_recommendation_amount}원

[Round 1 결과]
신청인: {dispute.r1_initiator_decision} / 상대방: {dispute.r1_respondent_decision}

[Round 2 재반론]
신청인 재반론: {dispute.r2_initiator_rebuttal or '(없음)'}
신청인 제안: {dispute.r2_initiator_proposal_type} / {dispute.r2_initiator_proposal_amount}원
상대방 재반론: {dispute.r2_respondent_rebuttal or '(없음)'}
상대방 제안: {dispute.r2_respondent_proposal_type} / {dispute.r2_respondent_proposal_amount}원"""

    system_prompt = """당신은 역핑 플랫폼의 분쟁 중재 AI입니다.
양쪽 주장과 증거를 공정하게 분석하고, 합리적 해결책을 제안하세요.

규칙:
1. 양쪽의 불편함과 입장을 모두 인정하세요.
2. 금액은 예약 금액을 초과할 수 없습니다.
3. 판단 근거를 명확히 설명하세요.
4. Round 2라면 1차 중재 결과를 참고하여 더 정밀한 제안을 하세요.

JSON으로 응답:
{
    "recommendation": "accept_proposal" | "modified_proposal",
    "recommended_amount": 숫자,
    "opinion": "종합 분석 의견",
    "explanation_to_initiator": "신청인 설명",
    "explanation_to_respondent": "상대방 설명",
    "reasoning": "판단 근거"
}"""

    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
            "recommendation": "modified_proposal",
            "recommended_amount": dispute.requested_amount or 0,
            "opinion": f"AI 분석 중 오류 발생. 관리자가 검토 예정입니다.",
            "explanation_to_initiator": "AI 분석 중 오류가 발생했습니다.",
            "explanation_to_respondent": "AI 분석 중 오류가 발생했습니다.",
            "reasoning": str(e),
        }

    now = datetime.utcnow()
    prefix = f"r{round_num}_"

    setattr(dispute, f"{prefix}ai_opinion", result.get("opinion", ""))
    setattr(dispute, f"{prefix}ai_recommendation", result.get("recommendation", ""))
    setattr(dispute, f"{prefix}ai_recommendation_amount", result.get("recommended_amount"))
    setattr(dispute, f"{prefix}ai_explanation",
            json.dumps({
                "to_initiator": result.get("explanation_to_initiator", ""),
                "to_respondent": result.get("explanation_to_respondent", ""),
                "reasoning": result.get("reasoning", ""),
            }, ensure_ascii=False))
    setattr(dispute, f"{prefix}ai_mediated_at", now)

    dispute.status = f"ROUND{round_num}_REVIEW"
    review_deadline = add_working_days(now, 1)
    setattr(dispute, f"r{round_num}_initiator_deadline", review_deadline)
    if round_num == 1:
        dispute.r1_respondent_review_deadline = review_deadline
    else:
        dispute.r2_respondent_deadline = review_deadline

    db.commit()

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


def evaluate_round_result(dispute_id: int, round_num: int, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    prefix = f"r{round_num}_"

    init_dec = getattr(dispute, f"{prefix}initiator_decision")
    resp_dec = getattr(dispute, f"{prefix}respondent_decision")
    now = datetime.utcnow()

    if init_dec == "accept" and resp_dec == "accept":
        dispute.status = "ACCEPTED"
        dispute.closed_at = now
        dispute.closed_reason = f"accepted_round{round_num}"
        dispute.resolution_amount = getattr(dispute, f"{prefix}ai_recommendation_amount")
        dispute.resolution = getattr(dispute, f"{prefix}ai_opinion")
        db.commit()
        # ★ 환불/교환/보상 자동 실행
        try:
            from app.services.resolution_executor import execute_dispute_resolution
            execute_dispute_resolution(dispute_id, db)
        except Exception:
            pass
        return {
            "status": "ACCEPTED",
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 5: Round 2 — 재반론 + 제안
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def submit_round2_rebuttal(dispute_id: int, user_id: int, data: dict, db: Session) -> dict:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute or dispute.status != "ROUND2_RESPONSE":
        return {"error": "현재 Round 2 재반론 단계가 아닙니다"}
    if datetime.utcnow() > dispute.r2_rebuttal_deadline:
        return {"error": "재반론 기한이 만료되었습니다"}

    now = datetime.utcnow()

    if user_id == dispute.initiator_id:
        dispute.r2_initiator_rebuttal = data.get("rebuttal", "")
        dispute.r2_initiator_evidence_urls = json.dumps(data.get("evidence", []), ensure_ascii=False)
        dispute.r2_initiator_proposal_type = data.get("proposal_type")
        dispute.r2_initiator_proposal_amount = data.get("proposal_amount")
    elif user_id == dispute.respondent_id:
        dispute.r2_respondent_rebuttal = data.get("rebuttal", "")
        dispute.r2_respondent_evidence_urls = json.dumps(data.get("evidence", []), ensure_ascii=False)
        dispute.r2_respondent_proposal_type = data.get("proposal_type")
        dispute.r2_respondent_proposal_amount = data.get("proposal_amount")

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

            if now > deadline:
                d.status = "AUTO_CLOSED"
                d.closed_at = now
                d.closed_reason = close_reason
                auto_closed += 1

    if auto_closed or warnings_sent:
        db.commit()

    return {"auto_closed": auto_closed, "warnings_sent": warnings_sent}
