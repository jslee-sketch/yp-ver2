# app/schemas_deposit.py
from __future__ import annotations

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

class DepositHoldIn(BaseModel):
    amount: int = Field(..., ge=1, description="디파짓 홀드 금액(원)")

class DepositOut(BaseModel):
    deposit_id: int
    deal_id: int
    buyer_id: int
    amount: int
    status: Literal["HELD", "REFUNDED"]
    created_at: datetime
    refunded_at: Optional[datetime] = None