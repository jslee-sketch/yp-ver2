"""환불·교환·반품·정산조정 통합 API 라우터"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(tags=["refund"])


# ── 환불 시뮬레이터 ──
@router.get("/v3_6/refund-simulator/calculate")
def api_simulate(
    amount: int = Query(...),
    shipping_fee: int = Query(0),
    shipping_mode: str = Query("free"),
    reason: str = Query("buyer_change_mind"),
    delivery_status: str = Query("delivered"),
    days_since_delivery: int = Query(0),
    inspection_deduction_rate: float = Query(0.0),
    role: str = Query("buyer"),
):
    from app.services.refund_calculator import calculate_refund
    return calculate_refund(
        original_amount=amount, shipping_fee=shipping_fee,
        shipping_mode=shipping_mode, reason=reason,
        delivery_status=delivery_status, days_since_delivery=days_since_delivery,
        inspection_deduction_rate=inspection_deduction_rate, role=role,
    )


# ── 단순 환불 ──
@router.post("/v3_6/refund-requests")
def api_create(body: dict, db: Session = Depends(get_db)):
    try:
        from app.services.refund_request_service import create_refund_request
        r = create_refund_request(body, db)
        if "error" in r:
            raise HTTPException(400, r["error"])
        return r
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"환불 요청 처리 오류: {type(e).__name__}: {e}")


@router.put("/v3_6/refund-requests/{id}/seller-response")
def api_seller(id: int, body: dict, db: Session = Depends(get_db)):
    from app.services.refund_request_service import seller_respond_refund
    r = seller_respond_refund(id, body.get("response", ""), body.get("reject_reason", ""), db)
    if "error" in r:
        raise HTTPException(400, r["error"])
    return r


@router.get("/v3_6/refund-requests")
def api_list_requests(
    reservation_id: int = Query(None),
    buyer_id: int = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
):
    from app.models import RefundRequest
    q = db.query(RefundRequest)
    if reservation_id:
        q = q.filter(RefundRequest.reservation_id == reservation_id)
    if buyer_id:
        q = q.filter(RefundRequest.buyer_id == buyer_id)
    if status:
        q = q.filter(RefundRequest.status == status)
    return q.order_by(RefundRequest.created_at.desc()).limit(100).all()


# ── 반품 ──
@router.put("/v3_6/resolution-actions/{id}/return-tracking")
def api_return(id: int, body: dict, db: Session = Depends(get_db)):
    from app.services.resolution_executor import submit_return_tracking
    r = submit_return_tracking(id, body.get("tracking", ""), body.get("carrier", ""), db)
    if "error" in r:
        raise HTTPException(400, r["error"])
    return r


@router.put("/v3_6/resolution-actions/{id}/inspect")
def api_inspect(id: int, body: dict, db: Session = Depends(get_db)):
    from app.services.resolution_executor import confirm_return_and_inspect
    r = confirm_return_and_inspect(
        id, body.get("result", "PASS"),
        body.get("deduction_rate", 0), body.get("notes", ""), db,
    )
    if "error" in r:
        raise HTTPException(400, r["error"])
    return r


# ── 교환 ──
@router.put("/v3_6/resolution-actions/{id}/exchange-tracking")
def api_exchange(id: int, body: dict, db: Session = Depends(get_db)):
    from app.services.resolution_executor import submit_exchange_tracking
    r = submit_exchange_tracking(id, body.get("tracking", ""), body.get("carrier", ""), db)
    if "error" in r:
        raise HTTPException(400, r["error"])
    return r


@router.put("/v3_6/resolution-actions/{id}/exchange-received")
def api_exchange_done(id: int, db: Session = Depends(get_db)):
    from app.services.resolution_executor import confirm_exchange_received
    return confirm_exchange_received(id, db)


# ── 관리자 ──
@router.put("/v3_6/admin/resolution-actions/{id}/manual")
def api_admin(id: int, body: dict, db: Session = Depends(get_db)):
    from app.services.resolution_executor import admin_manual_resolution
    return admin_manual_resolution(id, body, db)


# ── 조회 ──
@router.get("/v3_6/resolution-actions/{id}")
def api_get(id: int, db: Session = Depends(get_db)):
    from app.models import ResolutionAction
    a = db.query(ResolutionAction).filter(ResolutionAction.id == id).first()
    if not a:
        raise HTTPException(404, "Not found")
    return a


@router.get("/v3_6/resolution-actions")
def api_list(
    reservation_id: int = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
):
    from app.models import ResolutionAction
    q = db.query(ResolutionAction)
    if reservation_id:
        q = q.filter(ResolutionAction.reservation_id == reservation_id)
    if status:
        q = q.filter(ResolutionAction.status == status)
    return q.order_by(ResolutionAction.created_at.desc()).limit(100).all()


@router.get("/v3_6/clawback-records")
def api_clawbacks(
    seller_id: int = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
):
    from app.models import ClawbackRecord
    q = db.query(ClawbackRecord)
    if seller_id:
        q = q.filter(ClawbackRecord.seller_id == seller_id)
    if status:
        q = q.filter(ClawbackRecord.status == status)
    return q.order_by(ClawbackRecord.created_at.desc()).limit(100).all()


# ── 배치 ──
@router.post("/v3_6/batch/refund-auto-approve")
def api_batch_approve(db: Session = Depends(get_db)):
    from app.services.refund_request_service import auto_approve_expired_refunds
    return auto_approve_expired_refunds(db)


@router.post("/v3_6/batch/clawback")
def api_batch_clawback(db: Session = Depends(get_db)):
    from app.services.resolution_executor import process_clawback_batch
    return process_clawback_batch(db)


@router.post("/v3_6/batch/resolution-timeouts")
def api_batch_timeouts(db: Session = Depends(get_db)):
    from app.services.resolution_executor import process_resolution_timeouts
    return process_resolution_timeouts(db)
