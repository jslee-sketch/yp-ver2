# app/policy/params/_schema/refund.py
from pydantic import BaseModel, Field
from typing import Literal, Dict

class RefundRounding(BaseModel):
    mode: Literal["FLOOR", "CEIL", "HALF_UP"]
    unit: int = Field(ge=1, le=1000)

class RefundStageRule(BaseModel):
    allow_partial: bool = True
    allow_full: bool = True

class RefundPolicy(BaseModel):
    enabled: bool = True
    stages: Dict[str, RefundStageRule]
    rounding: RefundRounding
    remainder_strategy: Literal["GIVE_TO_FIRST", "GIVE_TO_LAST"] = "GIVE_TO_FIRST"