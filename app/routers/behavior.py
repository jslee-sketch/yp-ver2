# app/routers/behavior.py
"""
행동 수집 + AI 프로파일링 + 마이너리티 리포트 API
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    UserBehaviorLog, UserProfile,
    Buyer, Seller, Deal, Offer, UserNotification,
)

router = APIRouter(prefix="/behavior", tags=["🔮 Behavior Tracking"])

# Optional auth — tracking should not fail for unauthenticated users
_oauth2_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _try_get_user(token: Optional[str], db: Session):
    """Decode JWT if present; return (user_type, user_id) or (None, None)."""
    if not token:
        return None, None
    try:
        from jose import jwt as jose_jwt
        from app.security import SECRET_KEY, ALGORITHM
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        role = payload.get("role", "buyer")
        if sub is None:
            return None, None
        user_type = "SELLER" if role == "seller" else "BUYER"
        return user_type, int(sub)
    except Exception:
        return None, None


# ── Schemas ──────────────────────────────────────────

class TrackRequest(BaseModel):
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    meta: Optional[dict] = None
    # frontend can override if needed
    user_type: Optional[str] = None
    user_id: Optional[int] = None


# ── POST /behavior/track ─────────────────────────────

@router.post("/track")
def track_behavior(
    body: TrackRequest,
    token: Optional[str] = Depends(_oauth2_optional),
    db: Session = Depends(get_db),
):
    """Record a single behavior event (fire-and-forget)."""
    user_type, user_id = _try_get_user(token, db)
    # allow frontend override (e.g. for seller-specific events)
    if body.user_type:
        user_type = body.user_type
    if body.user_id:
        user_id = body.user_id

    log = UserBehaviorLog(
        user_type=user_type or "ANONYMOUS",
        user_id=user_id or 0,
        action=body.action,
        target_type=body.target_type,
        target_id=body.target_id,
        target_name=body.target_name[:200] if body.target_name else None,
        meta_json=json.dumps(body.meta or {}, ensure_ascii=False),
    )
    db.add(log)
    db.commit()
    return {"ok": True}


# ── GET /behavior/logs ────────────────────────────────

@router.get("/logs")
def list_logs(
    user_type: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Admin: list behavior logs with optional filters."""
    q = db.query(UserBehaviorLog).order_by(desc(UserBehaviorLog.created_at))
    if user_type:
        q = q.filter(UserBehaviorLog.user_type == user_type)
    if action:
        q = q.filter(UserBehaviorLog.action == action)
    if user_id:
        q = q.filter(UserBehaviorLog.user_id == user_id)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "user_type": r.user_type,
            "user_id": r.user_id,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_name": r.target_name,
            "meta": json.loads(r.meta_json) if r.meta_json else {},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── GET /behavior/stats ──────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Admin: aggregate stats for minority report dashboard."""
    total_logs = db.query(func.count(UserBehaviorLog.id)).scalar() or 0
    total_profiles = db.query(func.count(UserProfile.id)).scalar() or 0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = (
        db.query(func.count(UserBehaviorLog.id))
        .filter(UserBehaviorLog.created_at >= today_start)
        .scalar() or 0
    )

    # Top keywords from SEARCH / SELLER_SEARCH actions
    search_rows = (
        db.query(UserBehaviorLog.target_name, func.count(UserBehaviorLog.id).label("cnt"))
        .filter(UserBehaviorLog.action.in_(["SEARCH", "SELLER_SEARCH"]))
        .filter(UserBehaviorLog.target_name.isnot(None))
        .group_by(UserBehaviorLog.target_name)
        .order_by(desc("cnt"))
        .limit(20)
        .all()
    )
    keywords = [{"keyword": r[0], "count": r[1]} for r in search_rows]

    # Action distribution
    action_rows = (
        db.query(UserBehaviorLog.action, func.count(UserBehaviorLog.id).label("cnt"))
        .group_by(UserBehaviorLog.action)
        .order_by(desc("cnt"))
        .all()
    )
    actions = [{"action": r[0], "count": r[1]} for r in action_rows]

    # Category distribution from meta_json
    category_counts: dict[str, int] = {}
    cat_rows = (
        db.query(UserBehaviorLog.meta_json)
        .filter(UserBehaviorLog.meta_json.isnot(None))
        .filter(UserBehaviorLog.action.in_(["VIEW_DEAL", "SEARCH", "VIEW_DEALS"]))
        .limit(2000)
        .all()
    )
    for (mj,) in cat_rows:
        try:
            m = json.loads(mj)
            cat = m.get("category")
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1
        except Exception:
            pass
    categories = sorted(
        [{"category": k, "count": v} for k, v in category_counts.items()],
        key=lambda x: x["count"], reverse=True,
    )

    return {
        "total_logs": total_logs,
        "total_profiles": total_profiles,
        "today_logs": today_logs,
        "keywords": keywords,
        "actions": actions,
        "categories": categories,
    }


# ── POST /behavior/analyze/{user_type}/{user_id} ─────

@router.post("/analyze/{user_type}/{user_id}")
def analyze_user(user_type: str, user_id: int, db: Session = Depends(get_db)):
    """AI-analyze one user's behavior logs and store profile."""
    logs = (
        db.query(UserBehaviorLog)
        .filter(UserBehaviorLog.user_type == user_type, UserBehaviorLog.user_id == user_id)
        .order_by(desc(UserBehaviorLog.created_at))
        .limit(200)
        .all()
    )
    if not logs:
        raise HTTPException(404, "No behavior logs found for this user")

    summary_lines = []
    for log in logs:
        meta = json.loads(log.meta_json) if log.meta_json else {}
        line = f"[{log.action}] target={log.target_type}:{log.target_id} name={log.target_name} meta={meta}"
        summary_lines.append(line)

    behavior_text = "\n".join(summary_lines[:100])

    if user_type == "BUYER":
        prompt = (
            "아래는 구매자의 행동 로그입니다. 분석하여 JSON으로 응답하세요:\n"
            '{"type": "유형(예: 가격민감형/트렌드추구형/신중비교형/충동구매형/브랜드충성형)",'
            ' "interests": ["관심 카테고리/브랜드 3개"],'
            ' "price_range": "선호 가격대",'
            ' "purchase_intent": "높음/중간/낮음",'
            ' "engagement": "높음/중간/낮음",'
            ' "summary": "한줄 요약"}\n\n'
            f"행동 로그:\n{behavior_text}"
        )
    else:
        prompt = (
            "아래는 판매자의 행동 로그입니다. 분석하여 JSON으로 응답하세요:\n"
            '{"pattern": "유형(예: 공격적가격/신중대응/고품질특화/다종다양/니치마켓)",'
            ' "strength_areas": ["강점 분야 3개"],'
            ' "win_rate_estimate": "높음/중간/낮음",'
            ' "shipping_speed": "빠름/보통/느림",'
            ' "review_response": "적극/보통/미흡",'
            ' "risk_level": "낮음/중간/높음",'
            ' "growth_potential": "높음/중간/낮음",'
            ' "summary": "한줄 요약"}\n\n'
            f"행동 로그:\n{behavior_text}"
        )

    try:
        from app.llm_client import get_client
        client = get_client()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        profile_text = resp.choices[0].message.content.strip()
        # Extract JSON from markdown code block if present
        if "```" in profile_text:
            parts = profile_text.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("{"):
                    profile_text = p
                    break
    except Exception as e:
        # Fallback: simple statistical profile
        actions_count: dict[str, int] = {}
        for log in logs:
            actions_count[log.action] = actions_count.get(log.action, 0) + 1
        profile_text = json.dumps({
            "type": "auto-generated",
            "actions": actions_count,
            "log_count": len(logs),
            "summary": f"AI 분석 실패 ({str(e)[:50]}), 통계 기반 프로파일",
        }, ensure_ascii=False)

    # Upsert profile
    existing = (
        db.query(UserProfile)
        .filter(UserProfile.user_type == user_type, UserProfile.user_id == user_id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.profile_json = profile_text
        existing.analyzed_at = now
        existing.behavior_count = len(logs)
        existing.updated_at = now
    else:
        existing = UserProfile(
            user_type=user_type,
            user_id=user_id,
            profile_json=profile_text,
            analyzed_at=now,
            behavior_count=len(logs),
        )
        db.add(existing)
    db.commit()

    return {"ok": True, "profile": _parse_profile_json(profile_text), "log_count": len(logs)}


def _parse_profile_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


# ── POST /behavior/analyze-all ───────────────────────

@router.post("/analyze-all")
def analyze_all(min_logs: int = Query(5), db: Session = Depends(get_db)):
    """Batch-analyze all users with sufficient logs."""
    user_groups = (
        db.query(UserBehaviorLog.user_type, UserBehaviorLog.user_id, func.count(UserBehaviorLog.id).label("cnt"))
        .group_by(UserBehaviorLog.user_type, UserBehaviorLog.user_id)
        .having(func.count(UserBehaviorLog.id) >= min_logs)
        .all()
    )
    results = []
    for ut, uid, cnt in user_groups:
        if ut in ("ANONYMOUS", None):
            continue
        try:
            r = analyze_user(ut, uid, db)
            results.append({"user_type": ut, "user_id": uid, "status": "ok", "log_count": cnt})
        except Exception as e:
            results.append({"user_type": ut, "user_id": uid, "status": "error", "error": str(e)[:100]})
    return {"analyzed": len(results), "results": results}


# ── GET /behavior/profiles ────────────────────────────

@router.get("/profiles")
def list_profiles(
    user_type: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Admin: list all AI profiles."""
    q = db.query(UserProfile).order_by(desc(UserProfile.analyzed_at))
    if user_type:
        q = q.filter(UserProfile.user_type == user_type)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "user_type": r.user_type,
            "user_id": r.user_id,
            "profile": _parse_profile_json(r.profile_json) if r.profile_json else {},
            "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
            "behavior_count": r.behavior_count,
        }
        for r in rows
    ]


# ── GET /behavior/profiles/{user_type}/{user_id} ─────

@router.get("/profiles/{user_type}/{user_id}")
def get_profile(user_type: str, user_id: int, db: Session = Depends(get_db)):
    p = (
        db.query(UserProfile)
        .filter(UserProfile.user_type == user_type, UserProfile.user_id == user_id)
        .first()
    )
    if not p:
        raise HTTPException(404, "Profile not found")
    return {
        "user_type": p.user_type,
        "user_id": p.user_id,
        "profile": _parse_profile_json(p.profile_json) if p.profile_json else {},
        "analyzed_at": p.analyzed_at.isoformat() if p.analyzed_at else None,
        "behavior_count": p.behavior_count,
    }


# ── POST /behavior/match-deals ───────────────────────

@router.post("/match-deals")
def match_deals_for_buyers(db: Session = Depends(get_db)):
    """Match open deals to interested buyers and send notifications."""
    # Get recent buyer profiles
    buyer_profiles = (
        db.query(UserProfile)
        .filter(UserProfile.user_type == "BUYER")
        .all()
    )
    # Get active deals
    active_deals = db.query(Deal).filter(Deal.status.in_(["open", "active", "round_open"])).all()

    if not buyer_profiles or not active_deals:
        return {"matched": 0, "notifications_sent": 0}

    notifications_sent = 0
    matches = []

    for profile in buyer_profiles:
        pdata = _parse_profile_json(profile.profile_json) if profile.profile_json else {}
        interests = pdata.get("interests", [])
        if not interests:
            continue

        for deal in active_deals:
            # Simple keyword matching
            deal_text = f"{deal.product_name or ''} {deal.brand or ''} {deal.category or ''}".lower()
            score = sum(1 for interest in interests if interest.lower() in deal_text)
            if score > 0:
                matches.append({
                    "buyer_id": profile.user_id,
                    "deal_id": deal.id,
                    "deal_name": deal.product_name,
                    "score": score,
                    "reason": f"관심사 매칭: {', '.join(interests[:3])}",
                })
                # Send notification
                notif = UserNotification(
                    user_type="buyer",
                    user_id=profile.user_id,
                    title=f"관심 상품 딜 오픈: {deal.product_name}",
                    body=f"'{deal.product_name}' 딜이 열렸습니다. 확인해보세요!",
                    link=f"/deal/{deal.id}",
                    category="deal_match",
                )
                db.add(notif)
                notifications_sent += 1

    db.commit()
    return {"matched": len(matches), "notifications_sent": notifications_sent, "matches": matches[:20]}


# ── POST /behavior/match-deals-for-sellers ────────────

@router.post("/match-deals-for-sellers")
def match_deals_for_sellers(db: Session = Depends(get_db)):
    """Recommend open deals to sellers based on their profiles."""
    seller_profiles = (
        db.query(UserProfile)
        .filter(UserProfile.user_type == "SELLER")
        .all()
    )
    active_deals = db.query(Deal).filter(Deal.status.in_(["open", "active", "round_open"])).all()

    if not seller_profiles or not active_deals:
        return {"matched": 0, "recommendations": []}

    recommendations = []
    notifications_sent = 0

    for profile in seller_profiles:
        pdata = _parse_profile_json(profile.profile_json) if profile.profile_json else {}
        strengths = pdata.get("strength_areas", [])
        if not strengths:
            continue

        for deal in active_deals:
            deal_text = f"{deal.product_name or ''} {deal.brand or ''} {deal.category or ''}".lower()
            score = sum(1 for s in strengths if s.lower() in deal_text)
            if score > 0:
                recommendations.append({
                    "seller_id": profile.user_id,
                    "deal_id": deal.id,
                    "deal_name": deal.product_name,
                    "score": score,
                    "reason": f"강점 분야 매칭: {', '.join(strengths[:3])}",
                })
                notif = UserNotification(
                    user_type="seller",
                    user_id=profile.user_id,
                    title=f"오퍼 기회: {deal.product_name}",
                    body=f"강점 분야에 맞는 딜이 열렸습니다. 오퍼를 제출해보세요!",
                    link=f"/deal/{deal.id}",
                    category="deal_match",
                )
                db.add(notif)
                notifications_sent += 1

    db.commit()
    return {"matched": len(recommendations), "notifications_sent": notifications_sent, "recommendations": recommendations[:20]}


# ── GET /behavior/hesitating ──────────────────────────

@router.get("/hesitating")
def get_hesitating_buyers(
    min_views: int = Query(3),
    limit: int = Query(30, le=100),
    db: Session = Depends(get_db),
):
    """Admin: find buyers who viewed deals multiple times but didn't join."""
    # Buyers who VIEW_DEAL a lot but rarely JOIN_DEAL
    view_counts = (
        db.query(
            UserBehaviorLog.user_id,
            func.count(UserBehaviorLog.id).label("view_cnt"),
        )
        .filter(
            UserBehaviorLog.user_type == "BUYER",
            UserBehaviorLog.action.in_(["VIEW_DEAL", "VIEW_PRICE_JOURNEY"]),
        )
        .group_by(UserBehaviorLog.user_id)
        .having(func.count(UserBehaviorLog.id) >= min_views)
        .subquery()
    )

    join_counts = (
        db.query(
            UserBehaviorLog.user_id,
            func.count(UserBehaviorLog.id).label("join_cnt"),
        )
        .filter(
            UserBehaviorLog.user_type == "BUYER",
            UserBehaviorLog.action == "JOIN_DEAL",
        )
        .group_by(UserBehaviorLog.user_id)
        .subquery()
    )

    results = (
        db.query(view_counts.c.user_id, view_counts.c.view_cnt)
        .outerjoin(join_counts, view_counts.c.user_id == join_counts.c.user_id)
        .filter((join_counts.c.join_cnt == None) | (join_counts.c.join_cnt < view_counts.c.view_cnt / 3))  # noqa: E711
        .order_by(desc(view_counts.c.view_cnt))
        .limit(limit)
        .all()
    )

    hesitating = []
    for uid, vcnt in results:
        # Get their most-viewed deals
        top_targets = (
            db.query(UserBehaviorLog.target_name, func.count(UserBehaviorLog.id).label("cnt"))
            .filter(
                UserBehaviorLog.user_id == uid,
                UserBehaviorLog.action.in_(["VIEW_DEAL", "SEARCH"]),
                UserBehaviorLog.target_name.isnot(None),
            )
            .group_by(UserBehaviorLog.target_name)
            .order_by(desc("cnt"))
            .limit(3)
            .all()
        )
        last_activity = (
            db.query(func.max(UserBehaviorLog.created_at))
            .filter(UserBehaviorLog.user_id == uid, UserBehaviorLog.user_type == "BUYER")
            .scalar()
        )
        hesitating.append({
            "user_id": uid,
            "view_count": vcnt,
            "interests": [{"name": t[0], "count": t[1]} for t in top_targets],
            "last_activity": last_activity.isoformat() if last_activity else None,
        })

    return hesitating


# ── GET /behavior/seller-skip-patterns ────────────────

@router.get("/seller-skip-patterns")
def get_seller_skip_patterns(db: Session = Depends(get_db)):
    """Admin: analyze why sellers skip deals."""
    skip_logs = (
        db.query(UserBehaviorLog.meta_json)
        .filter(UserBehaviorLog.action == "SELLER_SKIP_DEAL")
        .limit(500)
        .all()
    )

    reason_counts: dict[str, int] = {}
    for (mj,) in skip_logs:
        try:
            m = json.loads(mj) if mj else {}
            reason = m.get("reason", "unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        except Exception:
            pass

    patterns = sorted(
        [{"reason": k, "count": v} for k, v in reason_counts.items()],
        key=lambda x: x["count"], reverse=True,
    )

    # Add insights
    for p in patterns:
        if p["reason"] == "price_too_low":
            p["insight"] = "판매자들이 가격이 너무 낮다고 판단"
        elif p["reason"] == "wrong_category":
            p["insight"] = "전문 분야가 아닌 카테고리"
        elif p["reason"] == "no_offer_submitted":
            p["insight"] = "관심은 있었으나 오퍼 미제출 (가격 고민)"
        else:
            p["insight"] = "기타 사유"

    return {
        "total_skips": len(skip_logs),
        "patterns": patterns,
    }
