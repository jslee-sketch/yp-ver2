# app/routers/settlements.py
from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Header
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models

router = APIRouter(
    prefix="/settlements",
    tags=["settlements"],
)

# =========================================================
# Helpers
# =========================================================

def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    SQLite에서는 naive datetime으로 들어올 수 있으므로 UTC로 간주.
    tz-aware면 UTC로 변환.
    """
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_base_time_for_reservation(resv: models.Reservation) -> Optional[datetime]:
    """
    SSOT 기준일:
      arrival_confirmed_at > delivered_at > paid_at
    """
    base = (
        getattr(resv, "arrival_confirmed_at", None)
        or getattr(resv, "delivered_at", None)
        or getattr(resv, "paid_at", None)
    )
    return _as_utc(base)


def _resolve_cooling_days_from_reservation_snapshot(resv: models.Reservation) -> int:
    """
    예약의 policy_snapshot_json에서 cancel_within_days를 쿨링으로 사용 (현재 너의 설계).
    - 없거나 파싱 실패하면 7일 fallback
    """
    raw = getattr(resv, "policy_snapshot_json", None)
    if not raw:
        return 7

    try:
        snap = json.loads(raw)
        cd = int(snap.get("cancel_within_days") or 0)
        if cd <= 0:
            return 7
        return cd
    except Exception:
        return 7


def _resolve_payout_delay_days_default() -> int:
    """
    기본 정산 지연일(쿨링 종료 후 +30일)
    ✅ 향후 운영자 정책 API로 중앙화할 자리
    """
    return 30


# =========================================================
# Refresh Ready (HOLD -> READY)
# =========================================================

@router.post(
    "/refresh-ready",
    summary="[SYSTEM] HOLD → READY 정산 갱신 (정상화/백필 포함)",
)
def refresh_settlement_ready(
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    ✅ 개선된 동작:
    1) 대상: status=HOLD 인 settlement
       - DISPUTE는 건드리지 않음
    2) ready_at이 NULL이면:
       - reservation을 읽어 base_time + cooling_days로 ready_at 계산해서 채움
       - scheduled_payout_at이 NULL이면 ready_at + 30일로 채움
    3) now >= ready_at 이면:
       - block_reason == WITHIN_COOLING 인 경우 READY 전환
       - ready_at은 절대 now로 덮어쓰지 않음(중요!)
    """
    now = datetime.now(timezone.utc)

    q = (
        db.query(models.ReservationSettlement)
        .filter(models.ReservationSettlement.status == "HOLD")
        .order_by(models.ReservationSettlement.id.asc())
        .limit(limit)
    )
    rows = q.all()

    checked = 0
    updated = 0
    backfilled = 0
    updated_ids: List[int] = []

    for s in rows:
        checked += 1

        # 분쟁 HOLD는 패스
        if (getattr(s, "block_reason", None) or "").upper() == "DISPUTE":
            continue

        # reservation 로드
        resv = (
            db.query(models.Reservation)
            .filter(models.Reservation.id == s.reservation_id)
            .first()
        )
        if not resv:
            continue

        # 1) ready_at 없으면 정책 기반으로 계산해서 채움
        if getattr(s, "ready_at", None) is None:
            base = _resolve_base_time_for_reservation(resv)
            if base is None:
                # base_time이 없으면 계산 불가 → 스킵
                continue

            cooling_days = _resolve_cooling_days_from_reservation_snapshot(resv)
            s.ready_at = base + timedelta(days=int(cooling_days))

            # scheduled도 없으면 같이 채움
            if getattr(s, "scheduled_payout_at", None) is None:
                delay_days = _resolve_payout_delay_days_default()
                s.scheduled_payout_at = s.ready_at + timedelta(days=int(delay_days))

            backfilled += 1

        ra = _as_utc(getattr(s, "ready_at", None))
        if ra is None:
            continue

        # 2) ready_at 지났으면 READY 전환 (WITHIN_COOLING만)
        if now >= ra:
            if (getattr(s, "block_reason", None) or "").upper() in {"WITHIN_COOLING", ""}:
                s.status = "READY"
                s.block_reason = None
                updated += 1
                updated_ids.append(int(s.id))

    if backfilled or updated:
        db.commit()

    return {
        "checked": checked,
        "backfilled": backfilled,
        "updated": updated,
        "updated_ids": updated_ids,
    }


@router.post(
    "/settlements/refresh-dispute",
    summary="[SYSTEM] 분쟁 상태 반영 (ANY → HOLD/DISPUTE)",
)
def refresh_settlement_dispute(
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    reservations.is_disputed = 1 인 건에 대해
    settlement를 HOLD + DISPUTE 로 강제 동기화한다.
    - 이미 READY여도 분쟁이면 HOLD로 되돌리는 게 핵심
    """
    rows = (
        db.query(models.ReservationSettlement, models.Reservation)
        .join(models.Reservation, models.Reservation.id == models.ReservationSettlement.reservation_id)
        .filter(
            models.Reservation.is_disputed == 1,
        )
        .order_by(models.ReservationSettlement.id.desc())
        .limit(limit)
        .all()
    )

    updated_ids = []

    for s, r in rows:
        s.dispute_opened_at = getattr(r, "dispute_opened_at", None)
        s.dispute_closed_at = getattr(r, "dispute_closed_at", None)

        s.status = "HOLD"
        s.block_reason = "DISPUTE"

        updated_ids.append(s.id)

    if updated_ids:
        db.commit()

    return {
        "checked": len(rows),
        "updated": len(updated_ids),
        "updated_ids": updated_ids,
    }


@router.post(
    "/settlements/refresh-dispute-closed",
    summary="[SYSTEM] 분쟁 종료 반영 (HOLD/DISPUTE → HOLD/DISPUTE_PATH)",
)
def refresh_settlement_dispute_closed(
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    reservations.dispute_closed_at 이 찍힌 건을 settlement에 반영:
    - status는 HOLD 유지
    - block_reason = DISPUTE_PATH 로 전환
    - dispute_closed_at 동기화
    - (중요) scheduled_payout_at은 여기서 '별도 정책'으로 다시 잡을 수 있게 남겨둠
    """
    rows = (
        db.query(models.ReservationSettlement, models.Reservation)
        .join(models.Reservation, models.Reservation.id == models.ReservationSettlement.reservation_id)
        .filter(
            models.Reservation.dispute_closed_at.isnot(None),
            models.ReservationSettlement.status == "HOLD",
            models.ReservationSettlement.block_reason == "DISPUTE",
        )
        .order_by(models.ReservationSettlement.id.desc())
        .limit(limit)
        .all()
    )

    updated_ids = []

    for s, r in rows:
        s.dispute_closed_at = getattr(r, "dispute_closed_at", None)
        s.block_reason = "DISPUTE_PATH"
        s.status = "HOLD"
        updated_ids.append(s.id)

    if updated_ids:
        db.commit()

    return {
        "checked": len(rows),
        "updated": len(updated_ids),
        "updated_ids": updated_ids,
    }


@router.post(
    "/settlements/refresh-dispute-path-schedule",
    summary="[SYSTEM] DISPUTE_PATH 지급 스케줄 계산/세팅 (scheduled_payout_at)",
)
def refresh_settlement_dispute_path_schedule(
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    - settlement.status = HOLD
    - settlement.block_reason = DISPUTE_PATH
    - dispute_closed_at 기준으로 scheduled_payout_at 을 계산해서 세팅
    """
    now = datetime.now(timezone.utc)

    try:
        from app.policy.api import settlement_payout_delay_days_dispute_path
        delay_days = int(settlement_payout_delay_days_dispute_path())
    except Exception:
        delay_days = 30

    rows = (
        db.query(models.ReservationSettlement)
        .filter(
            models.ReservationSettlement.status == "HOLD",
            models.ReservationSettlement.block_reason == "DISPUTE_PATH",
            models.ReservationSettlement.dispute_closed_at.isnot(None),
        )
        .order_by(models.ReservationSettlement.id.desc())
        .limit(limit)
        .all()
    )

    updated_ids = []

    for s in rows:
        base = getattr(s, "dispute_closed_at", None)
        if base is None:
            continue

        s.scheduled_payout_at = base + timedelta(days=delay_days)
        updated_ids.append(s.id)

    if updated_ids:
        db.commit()

    return {
        "checked": len(rows),
        "updated": len(updated_ids),
        "updated_ids": updated_ids,
        "delay_days": delay_days,
        "now": now.isoformat(),
    }


@router.post(
    "/settlements/refresh-dispute-path-ready",
    summary="[SYSTEM] DISPUTE_PATH (scheduled_payout_at 경과) → READY",
)
def refresh_settlement_dispute_path_ready(
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    - settlement.status = HOLD
    - settlement.block_reason = DISPUTE_PATH
    - scheduled_payout_at <= now  → READY 전환
    - 이 단계에서는 paid_at 찍지 않는다(승인/지급은 별도).
    """
    now = datetime.now(timezone.utc)

    rows = (
        db.query(models.ReservationSettlement)
        .filter(
            models.ReservationSettlement.status == "HOLD",
            models.ReservationSettlement.block_reason == "DISPUTE_PATH",
            models.ReservationSettlement.scheduled_payout_at.isnot(None),
            models.ReservationSettlement.scheduled_payout_at <= now,
        )
        .order_by(models.ReservationSettlement.scheduled_payout_at)
        .limit(limit)
        .all()
    )

    updated_ids = []
    for s in rows:
        s.status = "READY"
        updated_ids.append(s.id)

    if updated_ids:
        db.commit()

    return {
        "checked": len(rows),
        "updated": len(updated_ids),
        "updated_ids": updated_ids,
        "now": now.isoformat(),
    }


#------------------------------------
# 정산 전 사용자 수동승인
#------------------------------------
@router.post(
    "/{settlement_id}/approve",
    summary="[ADMIN] 정산 승인 (approved_at 기록 + status=APPROVED + event_logs.actor_id 기록)",
)
def approve_settlement(
    settlement_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    x_actor_id: int | None = Header(default=None, alias="X-Actor-Id"),
):
    """
    - READY만 승인 가능
    - paid_at 있으면 불가
    - approved_at 있으면 멱등 반환(이 경우 로그 중복 기록 안 함)
    - 승인 시:
        approved_at = now(datetime)
        status = 'APPROVED'
        updated_at 갱신
        event_logs에 SETTLE_APPROVE 기록 (actor_id = X-Actor-Id)
    """

    def _to_iso(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            else:
                v = v.astimezone(timezone.utc)
            return v.isoformat()
        return str(v)

    actor_id = int(x_actor_id) if x_actor_id is not None else None

    row = db.get(models.ReservationSettlement, settlement_id)
    if not row:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if getattr(row, "paid_at", None) is not None:
        raise HTTPException(status_code=409, detail="already paid")

    if getattr(row, "approved_at", None) is not None:
        return {
            "ok": True,
            "settlement_id": int(row.id),
            "status": str(row.status),
            "approved_at": _to_iso(row.approved_at),
            "block_reason": getattr(row, "block_reason", None),
            "note": "already approved (idempotent)",
        }

    if str(getattr(row, "status", "")) != "READY":
        raise HTTPException(status_code=409, detail=f"not READY (status={row.status})")

    allowed_block_reasons = {None, "", "DISPUTE_PATH"}
    br = getattr(row, "block_reason", None)
    if br not in allowed_block_reasons:
        raise HTTPException(status_code=409, detail=f"blocked by block_reason={br}")

    now = datetime.now(timezone.utc)

    row.approved_at = now
    row.status = "APPROVED"
    if hasattr(row, "updated_at"):
        row.updated_at = now

    meta = {
        "settlement_id": int(row.id),
        "prev_status": "READY",
        "settlement_status": "APPROVED",
        "block_reason": br,
        "approved_at": now.isoformat(),
        "actor_id": actor_id,
    }
    idem = f"settlement:{int(row.id)}:approve"

    db.execute(
        text(
            """
            INSERT OR IGNORE INTO event_logs (
              event_type, actor_type, actor_id,
              deal_id, offer_id, reservation_id, seller_id, buyer_id,
              reason, idempotency_key, meta, created_at
            ) VALUES (
              :event_type, :actor_type, :actor_id,
              :deal_id, :offer_id, :reservation_id, :seller_id, :buyer_id,
              :reason, :idempotency_key, :meta, :created_at
            )
            """
        ),
        {
            "event_type": "SETTLE_APPROVE",
            "actor_type": "admin",
            "actor_id": actor_id,
            "deal_id": getattr(row, "deal_id", None),
            "offer_id": getattr(row, "offer_id", None),
            "reservation_id": getattr(row, "reservation_id", None),
            "seller_id": getattr(row, "seller_id", None),
            "buyer_id": getattr(row, "buyer_id", None),
            "reason": "manual approve",
            "idempotency_key": idem,
            "meta": json.dumps(meta, ensure_ascii=False),
            "created_at": now,
        },
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "ok": True,
        "settlement_id": int(row.id),
        "status": str(row.status),
        "approved_at": _to_iso(row.approved_at),
        "block_reason": getattr(row, "block_reason", None),
        "actor_id": actor_id,
    }


#----------------------------------------
# Approved 중, Paid 안 된 것 확인 및 일괄 Paid 처리
#----------------------------------------
@router.post(
    "/bulk-mark-paid",
    summary="[SYSTEM] APPROVED → PAID (batch start/end logs + per-settlement logs + actor_id)",
)
def bulk_mark_paid(
    limit: int = 200,
    db: Session = Depends(get_db),
    x_actor_id: int | None = Header(default=None, alias="X-Actor-Id"),
):
    now = datetime.now(timezone.utc)
    batch_id = uuid.uuid4().hex

    actor_id = int(x_actor_id) if x_actor_id is not None else None
    actor_type = "system" if actor_id is None else "admin"

    # 0) 배치 시작 로그 (0건이어도 남음)
    start_meta = {"batch_id": batch_id, "limit": limit, "now": now.isoformat(), "actor_id": actor_id}
    db.execute(
        text(
            """
            INSERT OR IGNORE INTO event_logs (
              event_type, actor_type, actor_id,
              reason, idempotency_key, meta, created_at
            ) VALUES (
              :event_type, :actor_type, :actor_id,
              :reason, :idempotency_key, :meta, :created_at
            )
            """
        ),
        {
            "event_type": "SETTLE_BATCH",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "reason": f"paid_batch_start batch={batch_id}",
            "idempotency_key": f"paid_batch:{batch_id}:start",
            "meta": json.dumps(start_meta, ensure_ascii=False),
            "created_at": now,
        },
    )

    rows = (
        db.query(models.ReservationSettlement)
        .filter(
            models.ReservationSettlement.status == "APPROVED",
            models.ReservationSettlement.approved_at.isnot(None),
            models.ReservationSettlement.paid_at.is_(None),
            models.ReservationSettlement.scheduled_payout_at.isnot(None),
            models.ReservationSettlement.scheduled_payout_at <= now,
        )
        .order_by(models.ReservationSettlement.scheduled_payout_at.asc())
        .limit(limit)
        .all()
    )

    updated_ids = []

    for s in rows:
        s.status = "PAID"
        s.paid_at = now
        if hasattr(s, "updated_at"):
            s.updated_at = now

        updated_ids.append(int(s.id))

        idem = f"settlement:{int(s.id)}:paid"
        meta = {
            "batch_id": batch_id,
            "settlement_id": int(s.id),
            "prev_status": "APPROVED",
            "settlement_status": "PAID",
            "paid_at": now.isoformat(),
            "actor_id": actor_id,
            "scheduled_payout_at": getattr(s, "scheduled_payout_at", None).isoformat()
            if isinstance(getattr(s, "scheduled_payout_at", None), datetime)
            else str(getattr(s, "scheduled_payout_at", None)),
        }

        db.execute(
            text(
                """
                INSERT OR IGNORE INTO event_logs (
                  event_type, actor_type, actor_id,
                  deal_id, offer_id, reservation_id, seller_id, buyer_id,
                  reason, idempotency_key, meta, created_at
                ) VALUES (
                  :event_type, :actor_type, :actor_id,
                  :deal_id, :offer_id, :reservation_id, :seller_id, :buyer_id,
                  :reason, :idempotency_key, :meta, :created_at
                )
                """
            ),
            {
                "event_type": "SETTLE_PAID",
                "actor_type": actor_type,
                "actor_id": actor_id,
                "deal_id": getattr(s, "deal_id", None),
                "offer_id": getattr(s, "offer_id", None),
                "reservation_id": getattr(s, "reservation_id", None),
                "seller_id": getattr(s, "seller_id", None),
                "buyer_id": getattr(s, "buyer_id", None),
                "reason": f"bulk payout batch={batch_id}",
                "idempotency_key": idem,
                "meta": json.dumps(meta, ensure_ascii=False),
                "created_at": now,
            },
        )

    # 1) 배치 종료 로그 (0건이어도 남음)
    end_now = datetime.now(timezone.utc)
    end_meta = {
        "batch_id": batch_id,
        "updated": len(updated_ids),
        "updated_ids": updated_ids[:50],
        "now": end_now.isoformat(),
        "actor_id": actor_id,
    }
    db.execute(
        text(
            """
            INSERT OR IGNORE INTO event_logs (
              event_type, actor_type, actor_id,
              reason, idempotency_key, meta, created_at
            ) VALUES (
              :event_type, :actor_type, :actor_id,
              :reason, :idempotency_key, :meta, :created_at
            )
            """
        ),
        {
            "event_type": "SETTLE_BATCH",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "reason": f"paid_batch_end batch={batch_id}",
            "idempotency_key": f"paid_batch:{batch_id}:end",
            "meta": json.dumps(end_meta, ensure_ascii=False),
            "created_at": end_now,
        },
    )

    db.commit()

    return {
        "ok": True,
        "batch_id": batch_id,
        "checked": len(rows),
        "updated": len(updated_ids),
        "updated_ids": updated_ids,
        "actor_id": actor_id,
        "actor_type": actor_type,
    }


# ---------------------------------------------------------
# ✅ 레거시 호환: /settlements/refresh-ready
# ---------------------------------------------------------
@router.post(
    "/settlements/refresh-ready",
    summary="[SYSTEM][LEGACY] (임시) HOLD → READY 정산 갱신",
)
def refresh_settlement_ready_legacy(
    limit: int = 200,
    db: Session = Depends(get_db),
):
    return refresh_settlement_ready(limit=limit, db=db)


# =========================================================
# ✅ Batches (IMPORTANT: must be above /{settlement_id})
# =========================================================

VIEW_DEDUP_SECONDS = 10  # ✅ 10초 내 동일 batch+actor 조회는 로그 추가 안 함

@router.get(
    "/batches",
    summary="[ADMIN] 최근 지급 배치 목록 (end 기준 최신순)",
)
def list_paid_batches(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    최근 배치들을 end 로그 기준으로 조회해서 리스트로 반환.
    - event_logs에서 idempotency_key가 'paid_batch:{batch_id}:end' 인 것들을 긁어옴
    - end.meta.updated, updated_ids 일부 등을 요약
    - start 이벤트도 같이 붙여줌(있으면)

    ✅ 안전설계:
    - meta는 반드시 str일 때만 json.loads
    - 예상 포맷이 아닐 때 batch_id=None으로 처리
    - 어떤 row가 깨져있어도 절대 500 안 내고 skip/None 처리
    """
    # 1) limit 정규화
    try:
        limit = int(limit)
    except Exception:
        limit = 50
    limit = max(1, min(limit, 200))

    # 2) end rows 조회
    pattern = "paid_batch:%:end"  # ✅ 문자열은 파이썬에서 만들고
    end_rows = db.execute(
        text(
            """
            SELECT id, actor_type, actor_id, reason, idempotency_key,
                   CAST(meta AS TEXT) AS meta,
                   created_at
            FROM event_logs
            WHERE event_type = 'SETTLE_BATCH'
              AND idempotency_key LIKE :pattern
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {"limit": limit, "pattern": pattern},  # ✅ 여기로 넘김
    ).fetchall()

    items = []

    for r in end_rows:
        try:
            d = dict(r._mapping)

            idem = d.get("idempotency_key") or ""
            batch_id = None
            # paid_batch:{batch_id}:end 형태에서 batch_id 파싱
            if isinstance(idem, str) and idem.startswith("paid_batch:") and idem.endswith(":end"):
                mid = idem[len("paid_batch:") : -len(":end")]
                # mid가 비어있으면 None 처리
                batch_id = mid if mid else None

            # meta 파싱 (무조건 str일 때만!)
            meta_obj = None
            raw_meta = d.get("meta")
            if isinstance(raw_meta, str) and raw_meta.strip():
                try:
                    meta_obj = json.loads(raw_meta)
                except Exception:
                    meta_obj = None

            updated = meta_obj.get("updated") if isinstance(meta_obj, dict) else None
            updated_ids = meta_obj.get("updated_ids") if isinstance(meta_obj, dict) else None

            # start 이벤트 가져오기
            start_evt = None
            if batch_id:
                start_key = f"paid_batch:{batch_id}:start"
                sr = db.execute(
                    text(
                        """
                        SELECT id, actor_type, actor_id, reason, idempotency_key,
                               CAST(meta AS TEXT) AS meta,
                               created_at
                        FROM event_logs
                        WHERE event_type='SETTLE_BATCH' AND idempotency_key=:k
                        ORDER BY id DESC
                        LIMIT 1
                        """
                    ),
                    {"k": start_key},
                ).fetchone()

                if sr:
                    sd = dict(sr._mapping)

                    # start meta도 안전 파싱
                    s_meta_obj = None
                    s_raw_meta = sd.get("meta")
                    if isinstance(s_raw_meta, str) and s_raw_meta.strip():
                        try:
                            s_meta_obj = json.loads(s_raw_meta)
                        except Exception:
                            s_meta_obj = None
                    sd["meta"] = s_meta_obj
                    start_evt = sd

            items.append(
                {
                    "batch_id": batch_id,
                    "end": {
                        "id": d.get("id"),
                        "actor_type": d.get("actor_type"),
                        "actor_id": d.get("actor_id"),
                        "reason": d.get("reason"),
                        "idempotency_key": idem,
                        "meta": meta_obj,
                        "created_at": d.get("created_at"),
                    },
                    "start": start_evt,
                    "summary": {
                        "updated": updated,
                        "updated_ids": updated_ids,
                    },
                }
            )
        except Exception:
            # ✅ 어떤 row가 깨져도 전체 API는 죽지 않게
            continue

    return {
        "ok": True,
        "count": len(items),
        "items": items,
    }


@router.get(
    "/batches/{batch_id}",
    summary="[ADMIN] 지급 배치 조회 (start/end + paid 목록 + VIEW 로그 + view_event_id + rate-limit)",
)
def get_paid_batch(
    batch_id: str = Path(..., min_length=8),
    db: Session = Depends(get_db),
    x_actor_id: int | None = Header(default=None, alias="X-Actor-Id"),
):
    actor_id = int(x_actor_id) if x_actor_id is not None else None
    actor_type = "system" if actor_id is None else "admin"
    now = datetime.now(timezone.utc)

    actor_key = str(actor_id) if actor_id is not None else "anon"
    view_prefix = f"paid_batch:{batch_id}:view:{actor_key}"

    def _parse_dt(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace(" ", "T"))
        except Exception:
            return None

    last_view = db.execute(
        text(
            """
            SELECT id, created_at
            FROM event_logs
            WHERE event_type = 'SETTLE_BATCH_VIEW'
              AND idempotency_key LIKE :prefix || '%'
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"prefix": view_prefix},
    ).fetchone()

    view_deduped = False
    view_event_id = None
    view_idem = None

    if last_view:
        last_id = int(last_view[0])
        last_created = _parse_dt(str(last_view[1]))
        if last_created and (now - last_created).total_seconds() < VIEW_DEDUP_SECONDS:
            view_deduped = True
            view_event_id = last_id
            view_idem = f"{view_prefix}:dedup"
        else:
            last_view = None

    if not last_view:
        bucket = int(now.timestamp()) // VIEW_DEDUP_SECONDS
        view_idem = f"{view_prefix}:{bucket}"

        view_meta = {
            "batch_id": batch_id,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "now": now.isoformat(),
            "dedup_window_seconds": VIEW_DEDUP_SECONDS,
        }

        db.execute(
            text(
                """
                INSERT OR IGNORE INTO event_logs (
                  event_type, actor_type, actor_id,
                  reason, idempotency_key, meta, created_at
                ) VALUES (
                  :event_type, :actor_type, :actor_id,
                  :reason, :idempotency_key, :meta, :created_at
                )
                """
            ),
            {
                "event_type": "SETTLE_BATCH_VIEW",
                "actor_type": actor_type,
                "actor_id": actor_id,
                "reason": f"view paid batch {batch_id}",
                "idempotency_key": view_idem,
                "meta": json.dumps(view_meta, ensure_ascii=False),
                "created_at": now,
            },
        )
        db.commit()

        row = db.execute(
            text(
                """
                SELECT id
                FROM event_logs
                WHERE idempotency_key = :idem
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"idem": view_idem},
        ).fetchone()
        view_event_id = int(row[0]) if row else None

    start_key = f"paid_batch:{batch_id}:start"
    end_key = f"paid_batch:{batch_id}:end"

    se_rows = db.execute(
        text(
            """
            SELECT id, event_type, actor_type, actor_id, reason, idempotency_key,
                   CAST(meta AS TEXT) AS meta,
                   created_at
            FROM event_logs
            WHERE idempotency_key IN (:start_key, :end_key)
            ORDER BY id ASC
            """
        ),
        {"start_key": start_key, "end_key": end_key},
    ).fetchall()

    start_evt = None
    end_evt = None
    for r in se_rows:
        d = dict(r._mapping)
        try:
            d["meta"] = json.loads(d["meta"]) if d.get("meta") else None
        except Exception:
            pass

        if d.get("idempotency_key") == start_key:
            start_evt = d
        elif d.get("idempotency_key") == end_key:
            end_evt = d


    # ---------------------------------------------------------
    # 2) SETTLE_PAID 이벤트(해당 batch_id)
    #    ✅ SQLite JSON1 미지원 환경에서도 동작하도록 json_valid/json_extract 제거
    # ---------------------------------------------------------
    paid_rows = db.execute(
        text(
            """
            SELECT id, event_type, actor_type, actor_id,
                   deal_id, round_id, offer_id, reservation_id, seller_id, buyer_id,
                   amount, qty, reason, idempotency_key,
                   CAST(meta AS TEXT) AS meta,
                   created_at
            FROM event_logs
            WHERE event_type = 'SETTLE_PAID'
              AND CAST(meta AS TEXT) LIKE '%' || :batch_id || '%'
            ORDER BY id ASC
            """
        ),
        {"batch_id": batch_id},
    ).fetchall()

    paid_events = []
    settlement_ids: list[int] = []

    for r in paid_rows:
        d = dict(r._mapping)

        meta_raw = d.get("meta")
        meta_obj = None
        try:
            meta_obj = json.loads(meta_raw) if meta_raw else None
        except Exception:
            meta_obj = None

        # ✅ batch_id가 진짜 일치하는 것만 남김(텍스트 LIKE 오탐 방지)
        if isinstance(meta_obj, dict):
            if meta_obj.get("batch_id") != batch_id:
                continue
        else:
            # meta가 JSON이 아니면 신뢰 불가 → 제외
            continue

        d["meta"] = meta_obj

        sid = meta_obj.get("settlement_id")
        if isinstance(sid, int):
            settlement_ids.append(sid)

        paid_events.append(d)

    settlements = []
    if settlement_ids:
        uniq = list(dict.fromkeys(settlement_ids))[:500]
        placeholders = ",".join([f":id{i}" for i in range(len(uniq))])
        params = {f"id{i}": uniq[i] for i in range(len(uniq))}

        s_rows = db.execute(
            text(
                f"""
                SELECT id, status, approved_at, paid_at, scheduled_payout_at, block_reason, updated_at
                FROM reservation_settlements
                WHERE id IN ({placeholders})
                ORDER BY id ASC
                """
            ),
            params,
        ).fetchall()
        settlements = [dict(r._mapping) for r in s_rows]

    updated_cnt = None
    if isinstance(end_evt, dict) and isinstance(end_evt.get("meta"), dict):
        updated_cnt = end_evt["meta"].get("updated")

    return {
        "ok": True,
        "batch_id": batch_id,
        "view_log": {
            "event_id": view_event_id,
            "deduped": view_deduped,
            "dedup_window_seconds": VIEW_DEDUP_SECONDS,
            "idempotency_key": view_idem,
            "actor_type": actor_type,
            "actor_id": actor_id,
        },
        "start": start_evt,
        "end": end_evt,
        "paid_events_count": len(paid_events),
        "paid_events": paid_events,
        "settlements_count": len(settlements),
        "settlements": settlements,
        "summary": {
            "updated_from_end_meta": updated_cnt,
            "has_start": start_evt is not None,
            "has_end": end_evt is not None,
        },
    }


# =========================================================
# Response Schema
# =========================================================

class SettlementOut(BaseModel):
    id: int
    reservation_id: int
    deal_id: int
    offer_id: int
    seller_id: int
    buyer_id: int

    buyer_paid_amount: int
    pg_fee_amount: int
    platform_commission_amount: int
    seller_payout_amount: int

    status: str
    currency: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------
# 1) Seller 기준 정산 목록 조회
# ---------------------------------------------------------
@router.get(
    "/seller/{seller_id}",
    response_model=List[SettlementOut],
    summary="특정 Seller의 정산 목록 조회",
)
def api_list_settlements_for_seller(
    seller_id: int = Path(..., ge=1),
    status: Optional[str] = Query(None, description="필터용 정산 상태"),
    limit: int = Query(50, ge=1, le=200, description="최대 조회 개수"),
    db: Session = Depends(get_db),
):
    q = db.query(models.ReservationSettlement).filter(
        models.ReservationSettlement.seller_id == seller_id
    )
    if status:
        q = q.filter(models.ReservationSettlement.status == status)

    rows = (
        q.order_by(models.ReservationSettlement.created_at.desc())
         .limit(limit)
         .all()
    )
    return rows


# ---------------------------------------------------------
# 2) Reservation 기준 단일 정산 조회
# ---------------------------------------------------------
@router.get(
    "/reservation/{reservation_id}",
    response_model=SettlementOut,
    summary="Reservation 1건에 대한 정산 정보 조회",
)
def api_get_settlement_by_reservation(
    reservation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.ReservationSettlement)
        .filter(models.ReservationSettlement.reservation_id == reservation_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settlement not found for this reservation",
        )
    return row


# ---------------------------------------------------------
# 3) 정산 ID로 단일 조회 (⚠️ 반드시 맨 아래)
# ---------------------------------------------------------
@router.get(
    "/{settlement_id}",
    response_model=SettlementOut,
    summary="정산 ID로 단일 조회",
)
def api_get_settlement(
    settlement_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    row = db.get(models.ReservationSettlement, settlement_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settlement not found",
        )
    return row