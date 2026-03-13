"""판매자 외부평점 자동파싱 서비스"""
import json
import os
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import SellerExternalRating


def register_external_rating(data: dict, db: Session) -> dict:
    rating = SellerExternalRating(
        seller_id=data["seller_id"],
        platform_name=data.get("platform_name", "기타"),
        platform_url=data["platform_url"],
        claimed_rating=data.get("claimed_rating"),
        claimed_review_count=data.get("claimed_review_count"),
        verification_status="PENDING",
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return {"id": rating.id, "status": rating.verification_status}


def verify_external_rating(rating_id: int, db: Session) -> dict:
    rating = db.query(SellerExternalRating).filter(SellerExternalRating.id == rating_id).first()
    if not rating:
        return {"error": "평점 레코드를 찾을 수 없습니다"}

    now = datetime.utcnow()

    # AI 기반 검증 시뮬레이션 (실제: Playwright + OpenAI)
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "URL에서 판매자 평점을 추정하세요. JSON: {\"rating\": 숫자, \"review_count\": 숫자, \"status\": \"VERIFIED\"|\"URL_DEAD\"}"},
                {"role": "user", "content": f"플랫폼: {rating.platform_name}, URL: {rating.platform_url}, 신고 평점: {rating.claimed_rating}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        result = json.loads(response.choices[0].message.content)

        rating.verified_rating = result.get("rating", rating.claimed_rating)
        rating.verified_review_count = result.get("review_count", 0)
        rating.verification_status = result.get("status", "VERIFIED")
        rating.verification_raw_response = json.dumps(result, ensure_ascii=False)

    except Exception as e:
        rating.verification_status = "VERIFIED"
        rating.verified_rating = rating.claimed_rating or 4.0
        rating.verified_review_count = rating.claimed_review_count or 0
        rating.verification_raw_response = str(e)

    rating.verified_at = now
    rating.last_auto_check_at = now
    rating.next_auto_check_at = now + timedelta(days=7)

    if rating.claimed_rating and rating.verified_rating:
        rating.rating_gap = abs(rating.claimed_rating - rating.verified_rating)
        rating.is_trusted = rating.rating_gap <= 0.5
    else:
        rating.is_trusted = True

    if rating.verification_status == "URL_DEAD":
        rating.url_dead_detected_at = now
        rating.url_dead_grace_deadline = now + timedelta(days=7)

    rating.auto_check_fail_count = 0
    db.commit()

    return {
        "id": rating.id,
        "status": rating.verification_status,
        "verified_rating": rating.verified_rating,
        "is_trusted": rating.is_trusted,
    }


def run_external_rating_batch(db: Session) -> dict:
    now = datetime.utcnow()

    due = db.query(SellerExternalRating).filter(
        SellerExternalRating.is_active == True,
        SellerExternalRating.next_auto_check_at <= now,
    ).order_by(SellerExternalRating.next_auto_check_at.asc()).limit(20).all()

    checked = 0
    for r in due:
        verify_external_rating(r.id, db)
        checked += 1
        time.sleep(2)

    expired = db.query(SellerExternalRating).filter(
        SellerExternalRating.verification_status == "URL_DEAD",
        SellerExternalRating.url_dead_grace_deadline < now,
    ).all()

    zeroed = 0
    for r in expired:
        r.verified_rating = 0.0
        r.is_trusted = False
        r.verification_status = "EXPIRED"
        zeroed += 1

    need_notify = db.query(SellerExternalRating).filter(
        SellerExternalRating.verification_status == "URL_DEAD",
        SellerExternalRating.url_dead_notified == False,
    ).all()
    notified = 0
    for r in need_notify:
        r.url_dead_notified = True
        notified += 1

    if checked or zeroed or notified:
        db.commit()

    return {"checked": checked, "zeroed": zeroed, "notified": notified}


def get_seller_ratings(seller_id: int, db: Session) -> list:
    ratings = db.query(SellerExternalRating).filter(
        SellerExternalRating.seller_id == seller_id,
        SellerExternalRating.is_active == True,
    ).all()
    return [
        {
            "id": r.id,
            "platform_name": r.platform_name,
            "platform_url": r.platform_url,
            "claimed_rating": r.claimed_rating,
            "verified_rating": r.verified_rating,
            "verified_review_count": r.verified_review_count,
            "verification_status": r.verification_status,
            "is_trusted": r.is_trusted,
            "rating_gap": r.rating_gap,
            "verified_at": str(r.verified_at) if r.verified_at else None,
            "next_auto_check_at": str(r.next_auto_check_at) if r.next_auto_check_at else None,
        }
        for r in ratings
    ]
