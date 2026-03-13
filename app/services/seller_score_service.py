"""판매자 AI 자동 승인 — 종합 스코어링 서비스"""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Seller, SellerExternalRating, SellerVerificationScore


def calculate_seller_score(seller_id: int, db: Session) -> dict:
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        return {"error": "판매자를 찾을 수 없습니다"}

    now = datetime.utcnow()
    reasons = []

    # 1. 업력 (20%)
    if seller.created_at:
        age_days = (now - seller.created_at).days
        score_age = min(100, age_days / 365 * 100)
    else:
        age_days = 0
        score_age = 0
    reasons.append(f"업력: {age_days}일 → {score_age:.0f}점 (20%)")

    # 2. 외부 평점 (25%)
    ratings = db.query(SellerExternalRating).filter(
        SellerExternalRating.seller_id == seller_id,
        SellerExternalRating.is_active == True,
        SellerExternalRating.is_trusted == True,
    ).all()
    if ratings:
        avg_rating = sum(r.verified_rating or 0 for r in ratings) / len(ratings)
        score_rating = min(100, avg_rating / 5.0 * 100)
    else:
        score_rating = 0
    reasons.append(f"외부 평점: {score_rating:.0f}점 (25%)")

    # 3. 리뷰 수 (15%)
    total_reviews = sum(r.verified_review_count or 0 for r in ratings)
    score_reviews = min(100, total_reviews / 100 * 100)
    reasons.append(f"리뷰 수: {total_reviews}건 → {score_reviews:.0f}점 (15%)")

    # 4. 리뷰 감성 (15%) — 평점 기반 근사
    score_sentiment = score_rating * 0.8 if score_rating > 0 else 0
    reasons.append(f"리뷰 감성: {score_sentiment:.0f}점 (15%)")

    # 5. 통신판매업 신고서 (10%)
    has_permit = bool(getattr(seller, "ecommerce_permit_image", None))
    score_trade = 100 if has_permit else 0
    reasons.append(f"통판 신고서: {'있음' if has_permit else '없음'} → {score_trade}점 (10%)")

    # 6. 계좌 인증 (10%)
    has_account = bool(getattr(seller, "bankbook_image", None))
    score_account = 100 if has_account else 0
    reasons.append(f"계좌 인증: {'있음' if has_account else '없음'} → {score_account}점 (10%)")

    # 7. 사업자등록 (5%)
    has_biz = bool(getattr(seller, "business_license_image", None))
    score_biz = 100 if has_biz else 0
    reasons.append(f"사업자등록: {'있음' if has_biz else '없음'} → {score_biz}점 (5%)")

    # 종합
    total = (
        score_age * 0.20
        + score_rating * 0.25
        + score_reviews * 0.15
        + score_sentiment * 0.15
        + score_trade * 0.10
        + score_account * 0.10
        + score_biz * 0.05
    )
    total = round(total, 1)

    auto_decision = "AUTO_APPROVED" if total >= 70 else "MANUAL_REVIEW"

    # 메시지 생성
    weak_points = []
    if score_rating == 0:
        weak_points.append("외부 평점 등록이 필요합니다 (가장 큰 비중 25%)")
    if score_trade == 0:
        weak_points.append("통신판매업 신고서를 등록해주세요 (10%)")
    if score_account == 0:
        weak_points.append("계좌 인증을 완료해주세요 (10%)")

    if auto_decision == "AUTO_APPROVED":
        seller_message = f"판매자 승인이 완료되었습니다! (종합 {total}점)\n\n승인 사유:\n" + "\n".join(f"- {r}" for r in reasons)
        admin_message = f"자동 승인 (종합 {total}점)"
    else:
        seller_message = (
            f"관리자 수동 검토 대기 중입니다. (종합 {total}점 / 자동 승인 기준: 70점)\n\n"
            f"현재 점수 구성:\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
            f"개선하면 자동 승인에 가까워지는 항목:\n" + "\n".join(f"- {w}" for w in weak_points)
        )
        admin_message = f"수동 검토 필요 (종합 {total}점). 약점: {', '.join(weak_points)}"

    # DB 저장
    score_record = db.query(SellerVerificationScore).filter(
        SellerVerificationScore.seller_id == seller_id
    ).first()
    if not score_record:
        score_record = SellerVerificationScore(seller_id=seller_id)
        db.add(score_record)

    score_record.score_age = score_age
    score_record.score_rating = score_rating
    score_record.score_reviews = score_reviews
    score_record.score_sentiment = score_sentiment
    score_record.score_trade_cert = score_trade
    score_record.score_account = score_account
    score_record.score_biz = score_biz
    score_record.total_score = total
    score_record.auto_decision = auto_decision
    score_record.reasons = json.dumps(reasons, ensure_ascii=False)
    score_record.seller_message = seller_message
    score_record.admin_message = admin_message
    score_record.updated_at = now

    db.commit()

    return {
        "total_score": total,
        "auto_decision": auto_decision,
        "scores": {
            "age": round(score_age, 1),
            "rating": round(score_rating, 1),
            "reviews": round(score_reviews, 1),
            "sentiment": round(score_sentiment, 1),
            "trade_cert": score_trade,
            "account": score_account,
            "biz": score_biz,
        },
        "reasons": reasons,
        "seller_message": seller_message,
        "admin_message": admin_message,
        "weak_points": weak_points if auto_decision == "MANUAL_REVIEW" else [],
    }
