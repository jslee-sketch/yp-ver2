"""
배송 추적 라우터 — SweetTracker API 연동
- GET  /delivery/track/{reservation_id}  — 단건 배송 조회
- POST /delivery/batch-check             — 일괄 배송 조회
- POST /delivery/auto-confirm            — 자동 구매확정
- GET  /delivery/carriers                — 택배사 목록
- GET  /delivery/status-summary          — 배송 상태 요약 (관리자)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json

from app.database import get_db
from app.models import Reservation, UserNotification
from app.services.delivery_tracker import track_delivery, get_carrier_list

router = APIRouter(prefix="/delivery", tags=["delivery-tracking"])


@router.get("/track/{reservation_id}")
async def track_reservation_delivery(reservation_id: int, db: Session = Depends(get_db)):
    """특정 예약의 배송 상태 조회"""
    resv = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not resv:
        raise HTTPException(404, "예약을 찾을 수 없습니다")

    if not getattr(resv, "shipping_carrier", None) or not getattr(resv, "tracking_number", None):
        return {"success": False, "status": "NOT_SHIPPED", "message": "운송장 정보가 없습니다"}

    result = await track_delivery(resv.shipping_carrier, resv.tracking_number)

    if result.get("success"):
        resv.delivery_status = result["status"]
        resv.delivery_last_detail = json.dumps(result.get("latest", {}), ensure_ascii=False)
        resv.delivery_last_checked_at = datetime.utcnow()

        # 배달 완료 시
        if result["status"] == "DELIVERED" and not resv.delivered_at:
            resv.delivered_at = datetime.utcnow()
            resv.auto_confirm_deadline = datetime.utcnow() + timedelta(days=3)

            try:
                notif = UserNotification(
                    user_id=resv.buyer_id,
                    type="delivery_completed",
                    title="배달이 완료되었어요!",
                    message=f"R-{resv.id} 상품이 배달 완료되었습니다. 3일 내 수취 확인해주세요.",
                    link_url="/orders",
                )
                db.add(notif)
            except Exception:
                pass

        db.commit()

    return result


@router.post("/batch-check")
async def batch_check_deliveries(db: Session = Depends(get_db)):
    """배송 중인 모든 예약의 배송 상태 일괄 조회"""
    import asyncio

    pending = db.query(Reservation).filter(
        Reservation.shipped_at != None,  # noqa: E711
        Reservation.arrival_confirmed_at == None,  # noqa: E711
        Reservation.tracking_number != None,  # noqa: E711
    ).limit(100).all()

    # delivery_status가 DELIVERED가 아닌 것만 조회
    pending = [r for r in pending if getattr(r, "delivery_status", None) != "DELIVERED"]

    results = {"total": len(pending), "checked": 0, "updated": 0, "delivered": 0, "errors": 0}

    for resv in pending:
        # 마지막 조회 후 30분 미경과면 스킵
        last_checked = getattr(resv, "delivery_last_checked_at", None)
        if last_checked:
            elapsed = (datetime.utcnow() - last_checked).total_seconds()
            if elapsed < 1800:
                continue

        result = await track_delivery(resv.shipping_carrier, resv.tracking_number)
        results["checked"] += 1

        if result.get("success"):
            old_status = getattr(resv, "delivery_status", None)
            resv.delivery_status = result["status"]
            resv.delivery_last_detail = json.dumps(result.get("latest", {}), ensure_ascii=False)
            resv.delivery_last_checked_at = datetime.utcnow()

            if old_status != result["status"]:
                results["updated"] += 1

            if result["status"] == "DELIVERED" and not resv.delivered_at:
                resv.delivered_at = datetime.utcnow()
                resv.auto_confirm_deadline = datetime.utcnow() + timedelta(days=3)
                results["delivered"] += 1

                try:
                    notif = UserNotification(
                        user_id=resv.buyer_id,
                        type="delivery_completed",
                        title="배달이 완료되었어요!",
                        message=f"R-{resv.id} 상품이 배달 완료되었습니다. 3일 내 수취 확인해주세요.",
                        link_url="/orders",
                    )
                    db.add(notif)
                except Exception:
                    pass
        else:
            results["errors"] += 1

        await asyncio.sleep(0.5)

    db.commit()
    return results


@router.post("/auto-confirm")
async def auto_confirm_expired(db: Session = Depends(get_db)):
    """자동 구매확정: 배달완료 후 3일 경과 + 수취 미확인"""
    now = datetime.utcnow()
    targets = db.query(Reservation).filter(
        Reservation.delivered_at != None,  # noqa: E711
        Reservation.arrival_confirmed_at == None,  # noqa: E711
        Reservation.auto_confirm_deadline != None,  # noqa: E711
        Reservation.auto_confirm_deadline <= now,
    ).all()

    confirmed = 0
    for resv in targets:
        resv.arrival_confirmed_at = now
        confirmed += 1

        try:
            notif = UserNotification(
                user_id=resv.buyer_id,
                type="auto_confirmed",
                title="자동 구매확정 되었어요",
                message=f"R-{resv.id} 배달 완료 후 3일이 경과하여 자동 구매확정 되었습니다.",
                link_url="/orders",
            )
            db.add(notif)
        except Exception:
            pass

    db.commit()
    return {"auto_confirmed": confirmed}


@router.get("/carriers")
async def list_carriers():
    """지원 택배사 목록"""
    return await get_carrier_list()


@router.get("/status-summary")
def delivery_status_summary(db: Session = Depends(get_db)):
    """배송 상태별 요약 (관리자용)"""
    shipped = db.query(Reservation).filter(
        Reservation.shipped_at != None,  # noqa: E711
    ).all()

    summary = {
        "total_shipped": len(shipped),
        "READY": 0,
        "COLLECTING": 0,
        "IN_TRANSIT": 0,
        "OUT_FOR_DELIVERY": 0,
        "DELIVERED": 0,
        "NOT_TRACKED": 0,
        "awaiting_confirm": 0,
        "auto_confirm_pending": 0,
    }

    now = datetime.utcnow()
    for r in shipped:
        status = getattr(r, "delivery_status", None) or "NOT_TRACKED"
        if status in summary:
            summary[status] += 1
        else:
            summary["NOT_TRACKED"] += 1

        if r.delivered_at and not r.arrival_confirmed_at:
            summary["awaiting_confirm"] += 1
            deadline = getattr(r, "auto_confirm_deadline", None)
            if deadline and deadline <= now:
                summary["auto_confirm_pending"] += 1

    return summary
