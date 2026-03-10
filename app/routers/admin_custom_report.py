# app/routers/admin_custom_report.py
"""
Custom Report Builder — 관리자 커스텀 리포트
- /admin/custom-report/fields : 사용 가능한 필드 목록
- /admin/custom-report/query  : 동적 SQL 쿼리 실행
- /admin/custom-report/templates : 템플릿 CRUD
"""
from __future__ import annotations

import csv
import io
import json
from collections import deque
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CustomReportTemplate

router = APIRouter(prefix="/admin/custom-report", tags=["admin-custom-report"])

# ───────────────────────────────────────────────────
# FIELD_REGISTRY — DB 테이블/컬럼 매핑 (실제 스키마 기준)
# ───────────────────────────────────────────────────

FIELD_REGISTRY: dict[str, dict] = {
    # ── sellers ──
    "seller.id":              {"table": "sellers", "column": "id",              "label": "판매자 ID",       "type": "int",    "category": "seller"},
    "seller.email":           {"table": "sellers", "column": "email",           "label": "판매자 이메일",   "type": "str",    "category": "seller"},
    "seller.business_name":   {"table": "sellers", "column": "business_name",   "label": "상호명",          "type": "str",    "category": "seller"},
    "seller.nickname":        {"table": "sellers", "column": "nickname",        "label": "판매자 닉네임",   "type": "str",    "category": "seller"},
    "seller.business_number": {"table": "sellers", "column": "business_number", "label": "사업자번호",      "type": "str",    "category": "seller"},
    "seller.level":           {"table": "sellers", "column": "level",           "label": "판매자 레벨",     "type": "int",    "category": "seller"},
    "seller.status":          {"table": "sellers", "column": "status",          "label": "판매자 상태",     "type": "str",    "category": "seller"},
    "seller.actuator_id":     {"table": "sellers", "column": "actuator_id",     "label": "액추에이터 ID",   "type": "int",    "category": "seller"},
    "seller.created_at":      {"table": "sellers", "column": "created_at",      "label": "가입일",          "type": "datetime","category": "seller"},

    # ── buyers ──
    "buyer.id":               {"table": "buyers",  "column": "id",              "label": "구매자 ID",       "type": "int",    "category": "buyer"},
    "buyer.email":            {"table": "buyers",  "column": "email",           "label": "구매자 이메일",   "type": "str",    "category": "buyer"},
    "buyer.nickname":         {"table": "buyers",  "column": "nickname",        "label": "구매자 닉네임",   "type": "str",    "category": "buyer"},
    "buyer.name":             {"table": "buyers",  "column": "name",            "label": "구매자 이름",     "type": "str",    "category": "buyer"},
    "buyer.points":           {"table": "buyers",  "column": "points",          "label": "보유 포인트",     "type": "int",    "category": "buyer"},
    "buyer.level":            {"table": "buyers",  "column": "level",           "label": "구매자 레벨",     "type": "int",    "category": "buyer"},
    "buyer.trust_tier":       {"table": "buyers",  "column": "trust_tier",      "label": "신뢰등급",        "type": "str",    "category": "buyer"},
    "buyer.created_at":       {"table": "buyers",  "column": "created_at",      "label": "가입일",          "type": "datetime","category": "buyer"},

    # ── actuators ──
    "actuator.id":            {"table": "actuators", "column": "id",            "label": "액추에이터 ID",   "type": "int",    "category": "actuator"},
    "actuator.name":          {"table": "actuators", "column": "name",          "label": "액추에이터 이름", "type": "str",    "category": "actuator"},
    "actuator.nickname":      {"table": "actuators", "column": "nickname",      "label": "액추에이터 닉네임","type": "str",   "category": "actuator"},
    "actuator.status":        {"table": "actuators", "column": "status",        "label": "상태",            "type": "str",    "category": "actuator"},
    "actuator.contract_agreed": {"table": "actuators", "column": "contract_agreed", "label": "계약 동의",   "type": "bool",   "category": "actuator"},

    # ── deals ──
    "deal.id":                {"table": "deals",   "column": "id",              "label": "딜 ID",           "type": "int",    "category": "deal"},
    "deal.product_name":      {"table": "deals",   "column": "product_name",    "label": "품목명",          "type": "str",    "category": "deal"},
    "deal.creator_id":        {"table": "deals",   "column": "creator_id",      "label": "딜 생성자(구매자)", "type": "int",  "category": "deal"},
    "deal.desired_qty":       {"table": "deals",   "column": "desired_qty",     "label": "목표수량",        "type": "int",    "category": "deal"},
    "deal.target_price":      {"table": "deals",   "column": "target_price",    "label": "목표가",          "type": "float",  "category": "deal"},
    "deal.market_price":      {"table": "deals",   "column": "market_price",    "label": "시장가",          "type": "float",  "category": "deal"},
    "deal.status":            {"table": "deals",   "column": "status",          "label": "딜 상태",         "type": "str",    "category": "deal"},
    "deal.created_at":        {"table": "deals",   "column": "created_at",      "label": "딜 생성일",       "type": "datetime","category": "deal"},

    # ── offers ──
    "offer.id":               {"table": "offers",  "column": "id",              "label": "오퍼 ID",         "type": "int",    "category": "offer"},
    "offer.deal_id":          {"table": "offers",  "column": "deal_id",         "label": "오퍼→딜",         "type": "int",    "category": "offer"},
    "offer.seller_id":        {"table": "offers",  "column": "seller_id",       "label": "오퍼→판매자",     "type": "int",    "category": "offer"},
    "offer.price":            {"table": "offers",  "column": "price",           "label": "오퍼 가격",       "type": "float",  "category": "offer"},
    "offer.total_available_qty": {"table": "offers", "column": "total_available_qty", "label": "오퍼 수량", "type": "int",    "category": "offer"},
    "offer.delivery_days":    {"table": "offers",  "column": "delivery_days",   "label": "리드타임(일)",    "type": "int",    "category": "offer"},
    "offer.shipping_fee_per_reservation": {"table": "offers", "column": "shipping_fee_per_reservation", "label": "배송비(건당)", "type": "float", "category": "offer"},
    "offer.created_at":       {"table": "offers",  "column": "created_at",      "label": "오퍼 생성일",     "type": "datetime","category": "offer"},

    # ── reservations ──
    "reservation.id":         {"table": "reservations", "column": "id",          "label": "예약 ID",        "type": "int",    "category": "reservation"},
    "reservation.deal_id":    {"table": "reservations", "column": "deal_id",     "label": "예약→딜",        "type": "int",    "category": "reservation"},
    "reservation.offer_id":   {"table": "reservations", "column": "offer_id",    "label": "예약→오퍼",      "type": "int",    "category": "reservation"},
    "reservation.buyer_id":   {"table": "reservations", "column": "buyer_id",    "label": "예약→구매자",    "type": "int",    "category": "reservation"},
    "reservation.qty":        {"table": "reservations", "column": "qty",         "label": "예약 수량",      "type": "int",    "category": "reservation"},
    "reservation.amount_total": {"table": "reservations", "column": "amount_total", "label": "예약 총금액", "type": "float",  "category": "reservation"},
    "reservation.status":     {"table": "reservations", "column": "status",      "label": "예약 상태",      "type": "str",    "category": "reservation"},
    "reservation.shipping_carrier": {"table": "reservations", "column": "shipping_carrier", "label": "택배사", "type": "str", "category": "reservation"},
    "reservation.tracking_number":  {"table": "reservations", "column": "tracking_number",  "label": "운송장", "type": "str", "category": "reservation"},
    "reservation.created_at": {"table": "reservations", "column": "created_at",  "label": "예약 생성일",    "type": "datetime","category": "reservation"},

    # ── reservation_settlements ──
    "settlement.id":          {"table": "reservation_settlements", "column": "id",                       "label": "정산 ID",      "type": "int",    "category": "settlement"},
    "settlement.reservation_id": {"table": "reservation_settlements", "column": "reservation_id",       "label": "정산→예약",    "type": "int",    "category": "settlement"},
    "settlement.seller_id":   {"table": "reservation_settlements", "column": "seller_id",               "label": "정산→판매자",  "type": "int",    "category": "settlement"},
    "settlement.buyer_paid_amount": {"table": "reservation_settlements", "column": "buyer_paid_amount", "label": "결제금액",     "type": "float",  "category": "settlement"},
    "settlement.pg_fee_amount": {"table": "reservation_settlements", "column": "pg_fee_amount",         "label": "PG수수료",     "type": "float",  "category": "settlement"},
    "settlement.platform_commission_amount": {"table": "reservation_settlements", "column": "platform_commission_amount", "label": "플랫폼수수료", "type": "float", "category": "settlement"},
    "settlement.seller_payout_amount": {"table": "reservation_settlements", "column": "seller_payout_amount", "label": "정산금액", "type": "float", "category": "settlement"},
    "settlement.status":      {"table": "reservation_settlements", "column": "status",                  "label": "정산 상태",    "type": "str",    "category": "settlement"},
    "settlement.created_at":  {"table": "reservation_settlements", "column": "created_at",              "label": "정산 생성일",  "type": "datetime","category": "settlement"},

    # ── tax_invoices ──
    "tax.id":                 {"table": "tax_invoices", "column": "id",             "label": "세금계산서 ID", "type": "int",   "category": "tax"},
    "tax.invoice_number":     {"table": "tax_invoices", "column": "invoice_number", "label": "계산서 번호",   "type": "str",   "category": "tax"},
    "tax.settlement_id":      {"table": "tax_invoices", "column": "settlement_id",  "label": "세금→정산",     "type": "int",   "category": "tax"},
    "tax.total_amount":       {"table": "tax_invoices", "column": "total_amount",   "label": "세금 합계액",   "type": "float", "category": "tax"},
    "tax.supply_amount":      {"table": "tax_invoices", "column": "supply_amount",  "label": "공급가액",      "type": "float", "category": "tax"},
    "tax.tax_amount":         {"table": "tax_invoices", "column": "tax_amount",     "label": "세액",          "type": "float", "category": "tax"},
    "tax.status":             {"table": "tax_invoices", "column": "status",         "label": "세금 상태",     "type": "str",   "category": "tax"},

    # ── seller_reviews ──
    "review.id":              {"table": "seller_reviews", "column": "id",              "label": "리뷰 ID",      "type": "int",   "category": "review"},
    "review.reservation_id":  {"table": "seller_reviews", "column": "reservation_id",  "label": "리뷰→예약",    "type": "int",   "category": "review"},
    "review.seller_id":       {"table": "seller_reviews", "column": "seller_id",       "label": "리뷰→판매자",  "type": "int",   "category": "review"},
    "review.buyer_id":        {"table": "seller_reviews", "column": "buyer_id",        "label": "리뷰→구매자",  "type": "int",   "category": "review"},
    "review.price_fairness":  {"table": "seller_reviews", "column": "price_fairness",  "label": "가격 만족도",  "type": "float", "category": "review"},
    "review.quality":         {"table": "seller_reviews", "column": "quality",         "label": "품질 점수",    "type": "float", "category": "review"},
    "review.shipping":        {"table": "seller_reviews", "column": "shipping",        "label": "배송 점수",    "type": "float", "category": "review"},
    "review.comment":         {"table": "seller_reviews", "column": "comment",         "label": "리뷰 내용",    "type": "str",   "category": "review"},
    "review.created_at":      {"table": "seller_reviews", "column": "created_at",      "label": "리뷰 작성일",  "type": "datetime","category": "review"},
}

# ───────────────────────────────────────────────────
# JOIN 그래프 — FK 관계를 이용한 BFS 조인 빌더
# ───────────────────────────────────────────────────

# (from_table, to_table): "FROM.col = TO.col"
JOIN_EDGES: dict[tuple[str, str], str] = {
    ("deals", "offers"):            "deals.id = offers.deal_id",
    ("offers", "sellers"):          "offers.seller_id = sellers.id",
    ("offers", "reservations"):     "offers.id = reservations.offer_id",
    ("deals", "reservations"):      "deals.id = reservations.deal_id",
    ("reservations", "buyers"):     "reservations.buyer_id = buyers.id",
    ("reservations", "reservation_settlements"): "reservations.id = reservation_settlements.reservation_id",
    ("reservation_settlements", "tax_invoices"): "reservation_settlements.id = tax_invoices.settlement_id",
    ("reservations", "seller_reviews"): "reservations.id = seller_reviews.reservation_id",
    ("sellers", "actuators"):       "sellers.actuator_id = actuators.id",
    ("deals", "buyers"):            "deals.creator_id = buyers.id",
}

# Make graph bidirectional
_GRAPH: dict[str, dict[str, str]] = {}
for (a, b), cond in JOIN_EDGES.items():
    _GRAPH.setdefault(a, {})[b] = cond
    _GRAPH.setdefault(b, {})[a] = cond


def _bfs_joins(tables: set[str], primary_table: str) -> list[str]:
    """BFS로 primary_table에서 나머지 테이블까지 JOIN 절 생성"""
    visited = {primary_table}
    queue: deque[str] = deque([primary_table])
    joins: list[str] = []

    needed = tables - visited
    while queue and needed:
        current = queue.popleft()
        for neighbor, condition in _GRAPH.get(current, {}).items():
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append(neighbor)
            if neighbor in needed:
                joins.append(f"LEFT JOIN {neighbor} ON {condition}")
                needed.discard(neighbor)
            elif needed:
                # intermediate table needed for path
                joins.append(f"LEFT JOIN {neighbor} ON {condition}")

    if needed:
        raise HTTPException(400, f"Cannot join tables: {needed}")
    return joins


# ───────────────────────────────────────────────────
# Schemas
# ───────────────────────────────────────────────────

class QueryRequest(BaseModel):
    fields: list[str]  # field keys from FIELD_REGISTRY
    limit: int = 200
    format: str = "json"  # "json" | "csv"

class TemplateCreate(BaseModel):
    name: str
    fields: list[str]

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    fields: Optional[list[str]] = None


# ───────────────────────────────────────────────────
# Endpoints
# ───────────────────────────────────────────────────

@router.get("/fields")
def list_fields():
    """사용 가능한 필드 목록 반환"""
    result: dict[str, list] = {}
    for key, meta in FIELD_REGISTRY.items():
        cat = meta["category"]
        result.setdefault(cat, []).append({
            "key": key,
            "label": meta["label"],
            "type": meta["type"],
        })
    return result


@router.post("/query")
def execute_query(body: QueryRequest, db: Session = Depends(get_db)):
    """선택된 필드로 동적 SQL 생성 및 실행"""
    if not body.fields:
        raise HTTPException(400, "최소 1개 필드를 선택하세요.")
    if len(body.fields) > 20:
        raise HTTPException(400, "최대 20개 필드까지 선택 가능합니다.")

    # Validate fields
    for f in body.fields:
        if f not in FIELD_REGISTRY:
            raise HTTPException(400, f"Unknown field: {f}")

    # Determine tables and columns
    columns: list[str] = []
    tables_needed: set[str] = set()
    for f in body.fields:
        meta = FIELD_REGISTRY[f]
        tbl = meta["table"]
        col = meta["column"]
        tables_needed.add(tbl)
        columns.append(f"{tbl}.{col}")

    # Primary table = first field's table
    primary_table = FIELD_REGISTRY[body.fields[0]]["table"]

    # Build JOIN
    joins = _bfs_joins(tables_needed, primary_table)

    limit = min(body.limit, 1000)
    sql = f"SELECT {', '.join(columns)} FROM {primary_table}"
    for j in joins:
        sql += f" {j}"
    sql += f" ORDER BY {columns[0]} DESC LIMIT {limit}"

    try:
        result = db.execute(text(sql))
        rows = result.fetchall()
        col_names = [FIELD_REGISTRY[f]["label"] for f in body.fields]
    except Exception as e:
        raise HTTPException(500, f"쿼리 실행 오류: {str(e)}")

    if body.format == "csv":
        output = io.StringIO()
        output.write('\ufeff')  # BOM for Korean Excel
        writer = csv.writer(output)
        writer.writerow(col_names)
        for row in rows:
            writer.writerow([str(v) if v is not None else "" for v in row])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"},
        )

    # JSON response
    data = []
    keys = body.fields
    for row in rows:
        data.append({keys[i]: (str(v) if v is not None else None) for i, v in enumerate(row)})

    return {"columns": col_names, "keys": keys, "rows": data, "total": len(data)}


# ── Templates CRUD ──

@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    items = db.query(CustomReportTemplate).order_by(CustomReportTemplate.id.desc()).all()
    return [{"id": t.id, "name": t.name, "fields": json.loads(t.fields), "created_at": str(t.created_at)} for t in items]


@router.post("/templates")
def create_template(body: TemplateCreate, db: Session = Depends(get_db)):
    t = CustomReportTemplate(name=body.name, fields=json.dumps(body.fields))
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, "name": t.name, "fields": json.loads(t.fields)}


@router.put("/templates/{tid}")
def update_template(tid: int, body: TemplateUpdate, db: Session = Depends(get_db)):
    t = db.query(CustomReportTemplate).filter(CustomReportTemplate.id == tid).first()
    if not t:
        raise HTTPException(404, "Template not found")
    if body.name is not None:
        t.name = body.name
    if body.fields is not None:
        t.fields = json.dumps(body.fields)
    db.commit()
    return {"id": t.id, "name": t.name, "fields": json.loads(t.fields)}


@router.delete("/templates/{tid}")
def delete_template(tid: int, db: Session = Depends(get_db)):
    t = db.query(CustomReportTemplate).filter(CustomReportTemplate.id == tid).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t)
    db.commit()
    return {"ok": True}
