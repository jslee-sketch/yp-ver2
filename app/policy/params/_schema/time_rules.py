# app/policy/params/_schema/time_rules.py
from pydantic import BaseModel, Field

class TimeRulesPolicy(BaseModel):
    payment_timeout_sec: int = Field(ge=60, le=3600)  # 최소 1분, 최대 1시간
    decision_deadline_hours: int = Field(ge=1, le=168)